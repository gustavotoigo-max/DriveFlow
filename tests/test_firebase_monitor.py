import threading
import time

from driveflow.firebase_monitor import FirebaseMonitor, FirestoreWriter, attach_monitor, default_config
from driveflow.storage import Database


def row(status='enviando', offset=25, **kwargs):
    return dict(id='one', status=status, enabled=1, name='backup.zip', size=100,
                offset=offset, speed=5, folder_name='Cliente', **kwargs)


class Writer:
    def __init__(self):
        self.writes = []
        self.event = threading.Event()
        self.fail = False

    def write(self, state):
        if self.fail:
            raise RuntimeError('secret must not appear in log')
        self.writes.append(state)
        self.event.set()

    def close(self):
        pass


def monitor_for(writer, logs):
    return FirebaseMonitor(dict(default_config(), enabled=True), lambda *args: logs.append(args), lambda _: writer)


def finish(monitor):
    monitor.close()
    if monitor.thread:
        monitor.thread.join(2)
        assert not monitor.thread.is_alive()


def test_disabled_never_connects():
    calls = []
    monitor = FirebaseMonitor(default_config(), lambda *args: None, lambda _: calls.append(1))
    monitor.observe_queue([row()])
    monitor.close()
    assert not calls
    assert monitor.thread is None


def test_progress_coalesced_and_transitions_immediate():
    writer, logs = Writer(), []
    monitor = monitor_for(writer, logs)
    try:
        monitor.observe_queue([row(session='secret', account='private', path='private')])
        assert writer.event.wait(1)
        writer.event.clear()
        for offset in range(26, 90):
            monitor.observe_queue([row(offset=offset)])
        assert not writer.event.wait(.1)
        assert len(writer.writes) == 1
        assert writer.writes[0]['progress_percent'] == 25
        assert 'notification_events' not in writer.writes[0]
        assert writer.writes[0]['estimated_time_remaining'] == 15
        assert not {'session', 'account', 'path', 'error'} & writer.writes[0].keys()
        monitor.observe_queue([row('pausado', 89)])
        assert writer.event.wait(1)
        assert writer.writes[-1]['status'] == 'paused'
        assert writer.writes[-1]['upload_speed'] == 0
    finally:
        finish(monitor)
    assert writer.writes[-1]['status'] == 'offline'
    assert not logs


def test_failure_retries_latest_without_blocking_or_leaking():
    writer, logs = Writer(), []
    writer.fail = True
    config = dict(default_config(), enabled=True, update_interval_seconds=1)
    monitor = FirebaseMonitor(config, lambda *args: logs.append(args), lambda _: writer)
    try:
        start = time.monotonic()
        monitor.observe_queue([row()])
        assert time.monotonic() - start < .2
        deadline = time.monotonic() + 1
        while not logs and time.monotonic() < deadline:
            time.sleep(.01)
        assert logs and 'secret' not in str(logs)
        writer.fail = False
        monitor.observe_queue([row('concluído', 100)])
        assert writer.event.wait(2)
        assert writer.writes[-1]['status'] == 'completed'
        writer.event.clear()
        assert not writer.event.wait(1.1)
    finally:
        finish(monitor)


def test_active_heartbeat_and_idle_silence():
    writer = Writer()
    monitor = FirebaseMonitor(dict(default_config(), enabled=True, update_interval_seconds=1),
                              lambda *args: None, lambda _: writer)
    try:
        monitor.observe_queue([row()])
        assert writer.event.wait(1)
        writer.event.clear()
        assert writer.event.wait(1.5)
        writer.event.clear()
        monitor.observe_queue([])
        assert writer.event.wait(1)
        assert writer.writes[-1]['status'] == 'idle'
        writer.event.clear()
        assert not writer.event.wait(1.1)
    finally:
        finish(monitor)


def test_configuration_and_observer_failures_are_isolated(tmp_path):
    db = Database(tmp_path / 'queue.db')
    monitor = attach_monitor(db)
    assert not monitor.enabled
    assert db.on_change is None
    computer_id = db.setting('remote_monitoring')['computer_id']
    assert attach_monitor(db).config['computer_id'] == computer_id
    source = tmp_path / 'sample'
    source.write_bytes(b'abc')
    def broken(rows):
        raise RuntimeError('broken observer')
    db.on_change = broken
    ident = db.add(source, 'dest', 'Destino', 'account')
    db.update(ident, offset=3, status='concluído')
    assert db.get(ident)['offset'] == 3
    db.remove(ident)
    db.save_setting('remote_monitoring', {'enabled': True, 'computer_id': 'bad/id'})
    assert not attach_monitor(db).enabled
    db.conn.close()


def test_writer_overwrites_with_server_timestamp():
    calls = []
    class Document:
        def set(self, state, **kwargs):
            calls.append((state, kwargs))
    writer = object.__new__(FirestoreWriter)
    writer.document = Document()
    writer.timestamp = object()
    writer.write({'computer_id': 'pc'})
    assert calls == [({'computer_id': 'pc', 'last_update': writer.timestamp},
                      {'merge': False, 'retry': None, 'timeout': 3})]
