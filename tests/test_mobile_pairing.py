import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from driveflow.mobile_pairing import PairingService, PairingError
from driveflow.firebase_monitor import FirebaseMonitor, default_config


def test_code_stores_only_hash_expires_and_has_no_credentials():
    records = {}
    class Ref:
        def document(self, key):
            self.key = key
            return self
        def set(self, value, **kwargs):
            records[self.key] = value
    client = SimpleNamespace(project='demo', collection=lambda _: Ref())
    writer = SimpleNamespace(client=client, close=lambda: None)
    service = PairingService(dict(default_config(), enabled=True), lambda *args: None, lambda _: writer)
    payload, expires, digest = service.create_code()
    code = json.loads(payload)
    assert code['version'] == 2
    assert records[digest]['protocol'] == 'spark-v2'
    assert len(code['token']) == 43
    assert hashlib.sha256(code['token'].encode()).hexdigest() == digest
    assert 290 < (expires-datetime.now(timezone.utc)).total_seconds() <= 300
    assert code['token'] not in str(records)
    assert set(code) == {'type', 'version', 'project', 'computer_id', 'name', 'token'}


def test_pairing_error_does_not_disclose_credentials():
    logs = []
    def broken(_):
        raise RuntimeError('private-key-secret')
    service = PairingService(dict(default_config(), enabled=True), lambda *args: logs.append(args), broken)
    with pytest.raises(PairingError) as error:
        service.create_code()
    assert 'private-key-secret' not in str(error.value) + str(logs)


def test_parallel_upload_events_and_progress_no_spam():
    monitor = FirebaseMonitor(default_config(), lambda *args: None)
    def item(ident, status, offset=0):
        return dict(id=ident, name=ident+'.zip', status=status, offset=offset)
    a, b = item('a', 'pausado'), item('b', 'pausado')
    monitor._collect_events([a,b],[a,b])
    a = item('a','enviando')
    b = item('b','enviando')
    monitor._collect_events([a,b],[a,b])
    a = item('a','concluído',100)
    monitor._collect_events([a,b],[b])
    b['offset'] = 50
    monitor._collect_events([a,b],[b])
    b = item('b','cancelado',50)
    monitor._collect_events([a,b],[])
    events = list(monitor.notification_events)
    assert [e['kind'] for e in events] == ['started','started','completed','cancelled']
    assert len({e['id'] for e in events}) == 4


def test_queue_complete_resume_and_pause():
    monitor = FirebaseMonitor(default_config(), lambda *args: None)
    row = dict(id='a', name='a.zip', status='pausado', offset=10)
    monitor._collect_events([row],[row])
    for status in ['aguardando','enviando','pausado','aguardando','erro','aguardando','concluído']:
        row = dict(row,status=status)
        monitor._collect_events([row], [] if status == 'concluído' else [row])
    assert [e['kind'] for e in monitor.notification_events] == [
        'resumed','paused','resumed','error','resumed','completed','queue_completed']
