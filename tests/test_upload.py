import os
import threading

import pytest

from driveflow.storage import Database, Vault
from driveflow.upload import Engine, Manager
from driveflow.drive import Drive, DriveError, ExpiredSession, TemporaryError


class TestVault:
    def seal(self, value):
        return 'test:' + value if value else ''

    def open(self, value):
        return value.removeprefix('test:')


@pytest.fixture
def queued(tmp_path):
    source = tmp_path / 'customer.zip'
    source.write_bytes(b'01234567' * 100000)
    db = Database(tmp_path / 'queue.sqlite3', TestVault())
    ident = db.add(source, 'folder', 'Clientes', 'account')
    yield db, ident, source
    db.conn.close()


class Remote:
    def __init__(self):
        self.content = bytearray()
        self.complete = False
        self.offsets = []
        self.queries = 0
        self.starts = 0
        self.fail_once = False
        self.stop_after_chunk = None

    def metadata(self, ident):
        return {'id': ident, 'size': str(len(self.content))} if self.complete else None

    def duplicates(self, folder, name):
        return []

    def generate_id(self):
        return 'allocated-id'

    def start(self, item):
        self.starts += 1
        return 'https://www.googleapis.com/upload/test'

    def transfer(self, uri, size, offset=None, chunk=b''):
        if offset is None:
            self.queries += 1
            return len(self.content), self.complete
        assert offset == len(self.content)
        self.offsets.append(offset)
        self.content.extend(chunk)
        self.complete = len(self.content) == size
        if self.stop_after_chunk:
            self.stop_after_chunk.set()
        if self.fail_once:
            self.fail_once = False
            raise TemporaryError('Lost response after server accepted chunk')
        return len(self.content), self.complete


class FastStop:
    def is_set(self):
        return False

    def wait(self, seconds):
        return False


def engine(db, remote, stop=None, **kwargs):
    return Engine(db, remote, stop or threading.Event(), chunk_size=256 * 1024, **kwargs)


def test_lost_chunk_response_queries_actual_remote_offset(queued):
    db, ident, source = queued
    remote = Remote()
    remote.fail_once = True
    engine(db, remote, FastStop()).run(ident)
    assert db.get(ident)['status'] == 'concluído'
    assert remote.content == source.read_bytes()
    assert remote.offsets == [0, 262144, 524288, 786432]
    assert remote.queries == 2
    assert remote.starts == 1


def test_pause_and_process_restart_preserve_session(queued):
    db, ident, source = queued
    remote, stop = Remote(), threading.Event()
    remote.stop_after_chunk = stop
    engine(db, remote, stop).run(ident)
    assert db.get(ident)['offset'] == 262144
    assert db.get(ident)['status'] == 'pausado'
    db.update(ident, status='enviando', offset=1)  # simulate stale disk checkpoint
    reopened = Database(source.parent / 'queue.sqlite3', TestVault())
    assert reopened.get(ident)['status'] == 'interrompido'
    remote.stop_after_chunk = None
    engine(reopened, remote).run(ident)
    assert remote.offsets[1] == 262144
    assert remote.content == source.read_bytes()
    assert remote.starts == 1
    reopened.conn.close()


def test_lost_final_response_recovers_by_preallocated_id(queued):
    db, ident, source = queued
    remote = Remote()
    remote.content.extend(source.read_bytes())
    remote.complete = True
    db.update(ident, remote_id='allocated-id', offset=0)
    engine(db, remote).run(ident)
    assert db.get(ident)['status'] == 'concluído'
    assert remote.starts == 0 and remote.queries == 0


def test_modified_file_never_resumes(queued):
    db, ident, source = queued
    source.write_bytes(b'changed')
    remote = Remote()
    engine(db, remote).run(ident)
    assert db.get(ident)['status'] == 'arquivo alterado'
    assert remote.starts == 0


def test_disconnected_disk_keeps_session_for_retry(queued):
    db, ident, source = queued
    db.update(ident, session='session', offset=100, remote_id='allocated-id')
    moved = source.with_suffix('.off')
    source.rename(moved)
    engine(db, Remote()).run(ident)
    assert db.get(ident)['status'] == 'arquivo indisponível'
    assert db.session(db.get(ident)) == 'session'
    moved.rename(source)
    remote = Remote()
    remote.content.extend(source.read_bytes()[:100])
    engine(db, remote).run(ident)
    assert db.get(ident)['status'] == 'concluído'


def test_session_expiry_does_not_discard_progress(queued):
    db, ident, source = queued
    db.update(ident, session='session', offset=123, remote_id='allocated-id')
    remote = Remote()
    def expired(*args):
        raise ExpiredSession()
    remote.transfer = expired
    engine(db, remote).run(ident)
    assert db.get(ident)['status'] == 'sessão expirada'
    assert db.get(ident)['offset'] == 123
    assert remote.starts == 0


def test_size_mismatch_is_not_success(queued):
    db, ident, source = queued
    db.update(ident, remote_id='allocated-id')
    remote = Remote()
    remote.complete = True
    engine(db, remote).run(ident)
    assert db.get(ident)['status'] == 'erro'


def test_duplicate_name_requires_rename(queued):
    db, ident, source = queued
    remote = Remote()
    remote.duplicates = lambda *args: [{'id': 'existing'}]
    engine(db, remote).run(ident)
    assert db.get(ident)['status'] == 'nome duplicado'
    assert remote.starts == 0


def test_retry_limit_preserves_session(queued):
    db, ident, source = queued
    db.update(ident, session='session', offset=123, remote_id='allocated-id')
    remote = Remote()
    def offline(*args):
        raise TemporaryError('Offline')
    remote.transfer = offline
    engine(db, remote, FastStop(), retries=2).run(ident)
    assert db.get(ident)['status'] == 'interrompido'
    assert db.get(ident)['offset'] == 123
    assert db.session(db.get(ident)) == 'session'


def test_wrong_account_cannot_send(queued):
    db, ident, source = queued
    auth = type('Auth', (), {'account_id': 'another-account'})()
    manager = Manager(db, auth)
    with pytest.raises(ValueError):
        manager.start(ident)
    manager.pool.shutdown()


def test_same_name_from_another_disk_cannot_race_in_queue(queued):
    db, ident, source = queued
    other = source.parent / 'another-drive'
    other.mkdir()
    other_file = other / source.name
    other_file.write_bytes(b'other-data')
    with pytest.raises(ValueError):
        db.add(other_file, 'folder', 'Clientes', 'account')


def test_cancel_expired_item_is_terminal(queued):
    db, ident, source = queued
    db.update(ident, status='sessão expirada')
    auth = type('Auth', (), {'account_id': 'account'})()
    manager = Manager(db, auth)
    manager.pause(ident, cancel=True)
    manager.start(ident)
    assert db.get(ident)['status'] == 'cancelado'
    manager.pool.shutdown()


def test_unchecked_queue_item_is_never_scheduled(queued):
    db, ident, source = queued
    auth = type('Auth', (), {'account_id': 'account'})()
    manager = Manager(db, auth)
    db.update(ident, enabled=0)
    manager.start(ident)
    assert db.get(ident)['status'] == 'pausado'
    db.update(ident, status='aguardando')
    manager.tick()
    assert manager.running == {}
    manager.pool.shutdown()


def test_upgrade_preserves_old_queue_and_checkbox_choices(queued):
    db, ident, source = queued
    db.update(ident, offset=123, session='saved-session')
    # Recreate the previous schema without the new checkbox column.
    with db.conn:
        db.conn.execute('ALTER TABLE uploads DROP COLUMN enabled')
    upgraded = Database(source.parent / 'queue.sqlite3', TestVault())
    item = upgraded.get(ident)
    assert item['enabled'] == 1
    assert item['offset'] == 123 and upgraded.session(item) == 'saved-session'
    upgraded.update(ident, enabled=0)
    upgraded.conn.close()
    reopened = Database(source.parent / 'queue.sqlite3', TestVault())
    assert reopened.get(ident)['enabled'] == 0
    reopened.conn.close()


class Response:
    def __init__(self, status, headers=None, data=None):
        self.status_code, self.headers, self.payload = status, headers or {}, data or {}

    def json(self):
        return self.payload


class Http:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return next(self.responses)


def test_http_range_and_probe_headers():
    http = Http([Response(308, {'Range': 'bytes=0-42'}), Response(308)])
    drive = Drive(http)
    assert drive.transfer('https://www.googleapis.com/upload/test', 100) == (43, False)
    assert http.calls[0][1]['headers']['Content-Range'] == 'bytes */100'
    assert http.calls[0][1]['allow_redirects'] is False
    assert drive.transfer('https://www.googleapis.com/upload/test', 100, 43, b'123') == (0, False)
    assert http.calls[1][1]['headers']['Content-Range'] == 'bytes 43-45/100'


@pytest.mark.parametrize('uri', ['http://www.googleapis.com/x', 'https://evil.example/x', 'https://www.googleapis.com.evil.example/x'])
def test_untrusted_session_url_rejected(uri):
    with pytest.raises(DriveError):
        Drive.validate_uri(uri)


@pytest.mark.skipif(os.name != 'nt', reason='DPAPI Windows')
def test_tokens_and_sessions_encrypted_with_windows():
    vault = Vault()
    encrypted = vault.seal('sensitive-test-value')
    assert 'sensitive-test-value' not in encrypted
    assert vault.open(encrypted) == 'sensitive-test-value'


def test_large_file_bounded_reads(tmp_path):
    path = tmp_path / 'large.zip'
    # A sparse 100 GiB fixture: seek near the end, never allocate/read the whole file.
    total = 100 * 1024 ** 3
    with path.open('wb') as stream:
        if os.name == 'nt':
            import ctypes
            import msvcrt
            returned = ctypes.c_ulong()
            handle = ctypes.c_void_p(msvcrt.get_osfhandle(stream.fileno()))
            assert ctypes.windll.kernel32.DeviceIoControl(handle, 0x900C4, None, 0, None, 0, ctypes.byref(returned), None)
            assert ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(total), None, 0)
            assert ctypes.windll.kernel32.SetEndOfFile(handle)
        else:
            stream.truncate(total)
    db = Database(tmp_path / 'large.sqlite3', TestVault())
    ident = db.add(path, 'folder', 'Folder', 'account')
    db.update(ident, remote_id='allocated-id', session='session', offset=total - 262144)
    class LargeRemote(Remote):
        def metadata(self, ident):
            return {'id': ident, 'size': str(total)} if self.complete else None

        def transfer(self, uri, size, offset=None, chunk=b''):
            if offset is None:
                return total - 262144, False
            assert offset == total - 262144
            assert len(chunk) == 262144
            self.complete = True
            return total, True
    engine(db, LargeRemote()).run(ident)
    assert db.get(ident)['status'] == 'concluído'
    db.conn.close()
