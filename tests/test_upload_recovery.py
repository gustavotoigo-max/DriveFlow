import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.auth.exceptions import RefreshError, TransportError
from google.oauth2.credentials import Credentials

from driveflow.auth import Auth, AuthError
from driveflow.drive import Drive, TemporaryError, ExpiredSession
from driveflow.storage import Database
from driveflow.upload import Engine, Manager


class Vault:
    def seal(self, value): return value
    def open(self, value): return value


class NoDelay(threading.Event):
    def wait(self, timeout=None): return self.is_set()


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path / 'state'))
    auth = Auth()
    auth.vault = Vault()
    auth.account_id, auth.email = 'account', 'test@example.com'
    auth.credentials = Credentials(token='old', refresh_token='synthetic',
        token_uri='https://oauth2.googleapis.com/token', client_id='fake', client_secret='fake',
        expiry=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1))
    db = Database(':memory:', Vault())
    source = tmp_path / 'data.bin'
    source.write_bytes(b'a' * 524288)
    ident = db.add(source, 'folder', 'Folder', 'account')
    yield auth, db, ident
    db.conn.close()


def expire(auth):
    auth.credentials.expiry = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)


def renewed(auth):
    auth.credentials.token = 'renewed'
    auth.credentials.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)


def events(db): return [row[2] for row in db.events()]


@pytest.mark.parametrize('failure', [TransportError('secret-url'), RefreshError('secret-token', retryable=True)])
def test_initial_auth_failure_recovers_without_worker_error(context, monkeypatch, failure):
    auth, db, ident = context
    expire(auth)
    calls = []
    def refresh(request):
        calls.append(1)
        if len(calls) == 1: raise failure
        renewed(auth)
    monkeypatch.setattr(auth.credentials, 'refresh', refresh)
    monkeypatch.setattr(Engine, 'run', lambda self, key: db.update(key, status='concluído'))
    manager = Manager(db, auth)
    try:
        manager._run(ident, NoDelay())
        assert len(calls) == 2 and db.get(ident)['status'] == 'concluído'
        assert any('stage=authentication' in e for e in events(db))
        assert not any('secret' in e or 'WORKER_ERROR' in e for e in events(db))
    finally:
        manager.pool.shutdown()


def test_mid_upload_refresh_failure_queries_offset_and_finishes(context, monkeypatch):
    auth, db, ident = context
    db.update(ident, remote_id='remote', session='https://www.googleapis.com/upload/test')
    received, queries = [], []
    def raw_request(session, method, url, **kwargs):
        if method == 'GET':
            return SimpleNamespace(status_code=404)
        data = kwargs.get('data', b'')
        if not data:
            queries.append(sum(received))
            return SimpleNamespace(status_code=308, headers={'Range': f'bytes=0-{sum(received)-1}'} if received else {})
        received.append(len(data))
        if len(received) == 1:
            expire(auth)
            return SimpleNamespace(status_code=308, headers={'Range': 'bytes=0-262143'})
        return SimpleNamespace(status_code=200, json=lambda: {})
    monkeypatch.setattr('requests.Session.request', raw_request)
    refresh_calls = []
    def refresh(request):
        refresh_calls.append(1)
        if len(refresh_calls) == 1: raise TransportError('secret')
        renewed(auth)
    monkeypatch.setattr(auth.credentials, 'refresh', refresh)
    with auth.session() as session:
        drive = Drive(session)
        monkeypatch.setattr(drive, 'metadata', lambda _: {'size': '524288'} if sum(received) == 524288 else None)
        Engine(db, drive, NoDelay(), chunk_size=262144).run(ident)
    assert db.get(ident)['status'] == 'concluído'
    assert received == [262144, 262144] and queries == [0, 262144]
    assert db.get(ident)['last_confirmed']
    assert any('stage=send_chunk' in e for e in events(db))


def test_expired_session_check_retries_network_failure(context):
    _, db, ident = context
    db.update(ident, remote_id='remote', session='synthetic')
    remote = SimpleNamespace(metadata=Mock(side_effect=[None, TemporaryError('Offline'), {'size': '524288'}]),
                             transfer=Mock(side_effect=ExpiredSession()))
    Engine(db, remote, NoDelay()).run(ident)
    assert db.get(ident)['status'] == 'concluído'
    assert remote.transfer.call_count == 1
    assert any('stage=expired_session_check' in e for e in events(db))


def test_concurrent_sessions_refresh_once_and_save(context, monkeypatch):
    auth, _, _ = context
    sessions = [auth.session(), auth.session()]
    expire(auth)
    calls = []
    def refresh(request):
        calls.append(1)
        renewed(auth)
    monkeypatch.setattr(auth.credentials, 'refresh', refresh)
    monkeypatch.setattr('requests.Session.request', lambda *a, **k: SimpleNamespace(status_code=200))
    gate = threading.Barrier(2)
    def send(session):
        gate.wait(timeout=3)
        return session.get('https://www.googleapis.com/test').status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(send, sessions)) == [200, 200]
    assert calls == [1] and 'renewed' in auth.path.read_text()
    for session in sessions: session.close()


def test_401_refreshes_once_and_retries_request(context, monkeypatch):
    auth, _, _ = context
    seen = []
    def raw_request(session, method, url, **kw):
        seen.append(kw['headers']['authorization'])
        return SimpleNamespace(status_code=401 if len(seen) == 1 else 200, close=lambda: None)
    monkeypatch.setattr('requests.Session.request', raw_request)
    monkeypatch.setattr(auth.credentials, 'refresh', lambda request: renewed(auth))
    with auth.session() as session:
        assert session.get('https://www.googleapis.com/test').status_code == 200
    assert seen == ['Bearer old', 'Bearer renewed']


def test_revocation_preserves_credential_and_stops_queue_cascade(context, monkeypatch):
    auth, db, ident = context
    auth.save()
    before = auth.path.read_bytes()
    expire(auth)
    monkeypatch.setattr(auth.credentials, 'refresh', Mock(side_effect=RefreshError('private', {'error': 'invalid_grant'})))
    manager = Manager(db, auth)
    try:
        manager._run(ident, NoDelay())
        assert auth.reauth_required and db.get(ident)['status'] == 'erro'
        assert auth.path.read_bytes() == before
        db.update(ident, status='aguardando')
        manager.tick()
        assert not manager.running
        assert not any('NETWORK_RETRY' in e or 'private' in e for e in events(db))
    finally:
        manager.pool.shutdown()


def test_pause_during_auth_backoff_prevents_next_item(context, monkeypatch):
    auth, db, ident = context
    next_id = db.add(db.get(ident)['path'], 'other-folder', 'Other', 'account')
    expire(auth)
    monkeypatch.setattr(auth.credentials, 'refresh', Mock(side_effect=TransportError('offline')))
    waiting = threading.Event()
    real_wait = threading.Event.wait
    def observed_wait(self, timeout=None):
        if threading.current_thread().name.startswith('upload'):
            waiting.set()
        return real_wait(self, timeout)
    monkeypatch.setattr(threading.Event, 'wait', observed_wait)
    manager = Manager(db, auth)
    try:
        manager.start(ident)
        manager.start(next_id)
        manager.tick()
        assert waiting.wait(3)
        manager.pause(ident)
        manager.running[ident][0].result(timeout=3)
        manager.tick()
        assert not manager.running
        assert db.get(ident)['status'] == db.get(next_id)['status'] == 'pausado'
    finally:
        manager.pool.shutdown()


def test_old_session_cannot_use_replacement_account(context):
    auth, _, _ = context
    session = auth.session()
    auth.credentials = None
    with pytest.raises(AuthError, match='AUTH_ACCOUNT_CHANGED'):
        session.get('https://www.googleapis.com/test')
    session.close()


def test_unexpected_worker_diagnostic_redacts_secrets(context):
    _, db, ident = context
    remote = SimpleNamespace(duplicates=Mock(side_effect=ValueError('secret-token')))
    with pytest.raises(ValueError): Engine(db, remote, NoDelay()).run(ident)
    assert any('stage=prepare type=ValueError' in e for e in events(db))
    assert not any('secret-token' in e for e in events(db))


def test_refresh_uses_real_google_exchange_with_bounded_timeout(context, monkeypatch):
    import json
    auth, _, _ = context
    expire(auth)
    timeouts = []
    def raw_request(session, method, url, **kwargs):
        timeouts.append(kwargs['timeout'])
        return SimpleNamespace(status_code=200, headers={}, content=json.dumps({
            'access_token': 'new-access', 'expires_in': 3600, 'token_type': 'Bearer',
            'refresh_token': 'new-refresh'}).encode())
    monkeypatch.setattr('requests.Session.request', raw_request)
    with auth.session(): pass
    assert timeouts == [(15, 30)]
    assert auth.credentials.token == 'new-access'
    assert 'new-refresh' in auth.path.read_text()


def test_refresh_save_failure_retries_save_without_second_refresh(context, monkeypatch):
    auth, _, _ = context
    expire(auth)
    refresh = Mock(side_effect=lambda request: renewed(auth))
    monkeypatch.setattr(auth.credentials, 'refresh', refresh)
    original = auth.save
    calls = []
    def save():
        calls.append(1)
        if len(calls) == 1: raise PermissionError('private-path')
        original()
    monkeypatch.setattr(auth, 'save', save)
    with pytest.raises(TemporaryError, match='AUTH_SAVE_RETRY'):
        auth.session()
    with auth.session(): pass
    assert refresh.call_count == 1 and len(calls) == 2


def test_repeated_401_stops_and_preserves_saved_account(context, monkeypatch):
    auth, _, _ = context
    auth.save()
    monkeypatch.setattr('requests.Session.request', lambda *a, **k: SimpleNamespace(status_code=401, close=lambda: None))
    refresh = Mock(side_effect=lambda request: renewed(auth))
    monkeypatch.setattr(auth.credentials, 'refresh', refresh)
    with auth.session() as session:
        with pytest.raises(AuthError, match='AUTH_HTTP_401'):
            session.get('https://www.googleapis.com/test')
    assert auth.reauth_required and auth.path.exists() and refresh.call_count == 1


def test_initial_auth_retry_limit_keeps_progress(context, monkeypatch):
    auth, db, ident = context
    db.update(ident, offset=123, session='saved-session')
    db.save_setting('retries', 2)
    expire(auth)
    refresh = Mock(side_effect=TransportError('private-secret'))
    monkeypatch.setattr(auth.credentials, 'refresh', refresh)
    manager = Manager(db, auth)
    try:
        manager._run(ident, NoDelay())
        assert refresh.call_count == 3
        assert db.get(ident)['status'] == 'interrompido'
        assert db.get(ident)['offset'] == 123 and db.session(db.get(ident)) == 'saved-session'
        assert any('RETRY_LIMIT_REACHED stage=authentication' in e for e in events(db))
    finally:
        manager.pool.shutdown()
