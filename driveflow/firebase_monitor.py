"""Optional current-state telemetry. No Drive credentials or network work on callers."""
import math
import re
import socket
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from .storage import data_dir
from .version import __version__


def default_config():
    return dict(enabled=False, computer_id=uuid.uuid4().hex,
                computer_name=socket.gethostname(), update_interval_seconds=5,
                firebase_credentials='config/firebase-service-account.json')


class FirestoreWriter:
    def __init__(self, config):
        # Explicit service account only; never reuse Drive OAuth or ambient credentials.
        from google.cloud import firestore
        from google.oauth2 import service_account
        path = Path(config['firebase_credentials'])
        if not path.is_absolute():
            path = data_dir() / path
        credentials = service_account.Credentials.from_service_account_file(str(path))
        self.client = firestore.Client(project=credentials.project_id, credentials=credentials)
        self.document = self.client.collection('computers').document(config['computer_id'])
        self.timestamp = firestore.SERVER_TIMESTAMP

    def write(self, state):
        self.document.set(dict(state, last_update=self.timestamp), merge=False,
                          retry=None, timeout=3)

    def close(self):
        self.client.close()


class FirebaseMonitor:
    """Coalesces progress in memory; state transitions wake a dedicated daemon.

    A single latest snapshot bounds memory during outages. Intermediate transitions
    may be superseded while a write is in flight; only current state is retained.
    """
    def __init__(self, config, log, writer_factory=FirestoreWriter):
        self.log = log
        self.config = config
        self.enabled = False
        self.condition = threading.Condition()
        self.state = {}
        self.revision = 0
        self.urgent = False
        self.stopping = False
        self.thread = None
        self.writer_factory = writer_factory
        self.notification_events = deque(maxlen=64)
        self.previous_rows = None
        try:
            if config.get('enabled') is not True:
                return
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', config['computer_id']):
                raise ValueError('computer_id')
            self.interval = float(config.get('update_interval_seconds', 5))
            if not math.isfinite(self.interval) or self.interval < 1:
                raise ValueError('interval')
            if not config.get('firebase_credentials') or not config.get('computer_name'):
                raise ValueError('configuration')
            self.enabled = True
            self.thread = threading.Thread(target=self._run, name='firebase-monitor', daemon=True)
            self.thread.start()
        except Exception as exc:
            self.enabled = False
            self._log(exc)

    def _log(self, exc):
        try:
            # Exception messages may include keys, tokens or credential file contents.
            self.log('', f'FIREBASE_MONITOR_ERROR type={type(exc).__name__}')
        except Exception:
            pass

    def observe_queue(self, rows):
        if not self.enabled:
            return
        try:
            active = [r for r in rows if r['status'] in ('enviando', 'iniciando', 'retomando', 'aguardando')]
            remaining = [r for r in rows if r['enabled'] and r['status'] not in ('concluído', 'cancelado')]
            # With concurrent uploads, current_* describes the oldest active file.
            item = next((r for r in active if r['status'] == 'enviando'), None)
            item = item or (active[0] if active else (remaining[0] if remaining else (rows[-1] if rows else None)))
            status_map = {'enviando': 'uploading', 'iniciando': 'preparing',
                          'retomando': 'preparing', 'aguardando': 'preparing',
                          'pausado': 'paused', 'concluído': 'completed', 'cancelado': 'idle'}
            status = status_map.get(item['status'], 'error') if item else 'idle'
            size = max(0, item['size']) if item else 0
            uploaded = min(size, max(0, item['offset'])) if item else 0
            speed = max(0, item['speed']) if item and status == 'uploading' else 0
            state = dict(computer_id=self.config['computer_id'], computer_name=self.config['computer_name'],
                         status=status, current_file=item['name'] if item else '',
                         current_file_size=size, bytes_uploaded=uploaded,
                         progress_percent=round(uploaded / size * 100, 2) if size else (100 if status == 'completed' else 0),
                         upload_speed=speed, estimated_time_remaining=(size-uploaded)/speed if speed else None,
                         queue_total=len(rows), queue_remaining=len(remaining),
                         current_destination=item['folder_name'] if item else '', software_version=__version__)
            # Any file's state transition matters, including concurrent completion.
            signature = tuple((r['id'], r['status'], r['enabled']) for r in rows)
            with self.condition:
                if self.stopping:
                    return
                # Spark edition: publish current state only, with no notification events.
                state['update_interval_seconds'] = self.interval
                urgent = signature != getattr(self, 'signature', None)
                self.signature = signature
                if state != self.state or urgent:
                    self.state = state
                    self.revision += 1
                    self.urgent |= urgent
                    self.condition.notify()
        except Exception as exc:
            self._log(exc)

    def _collect_events(self, rows, remaining):
        previous = self.previous_rows
        current = {r['id']: dict(r) for r in rows}
        self.previous_rows = current
        if previous is None:
            return
        active = {'aguardando', 'iniciando', 'retomando', 'enviando'}
        errors = {'erro', 'interrompido', 'sessão expirada', 'arquivo alterado', 'arquivo indisponível', 'nome duplicado'}
        completed = False
        for ident, item in current.items():
            old = previous.get(ident)
            if old is None or old['status'] == item['status']:
                continue
            status = item['status']
            kind = None
            if status in active and old['status'] not in active:
                kind = 'resumed' if item.get('offset', 0) else 'started'
            elif status == 'concluído':
                kind = 'completed'
                completed = True
            elif status == 'cancelado':
                kind = 'cancelled'
            elif status == 'pausado' and old['status'] in active:
                kind = 'paused'
            elif status in errors and old['status'] not in errors:
                kind = 'error'
            if kind:
                self.notification_events.append(dict(id=uuid.uuid4().hex, kind=kind, file=item['name']))
        if completed and not remaining:
            self.notification_events.append(dict(id=uuid.uuid4().hex, kind='queue_completed', file=''))

    def close(self):
        if not self.enabled:
            return
        with self.condition:
            self.stopping = True
            if self.state:
                self.state = dict(self.state, status='offline', upload_speed=0, estimated_time_remaining=None)
                self.revision += 1
                self.urgent = True
            self.condition.notify()
        # Do not block UI/upload shutdown on network. Offline delivery is best effort.

    def _run(self):
        writer = None
        sent = -1
        next_write = 0
        retry_at = 0
        try:
            while True:
                with self.condition:
                    while True:
                        now = time.monotonic()
                        active = self.state.get('status') in ('uploading', 'preparing')
                        pending = bool(self.state) and (sent != self.revision or active)
                        due = max(retry_at, 0 if self.urgent else next_write)
                        if pending and (now >= due or self.stopping):
                            state, revision = dict(self.state), self.revision
                            self.urgent = False
                            break
                        if self.stopping:
                            return
                        self.condition.wait(max(.01, due-now) if pending else None)
                try:
                    if writer is None:
                        writer = self.writer_factory(self.config)
                    writer.write(state)
                    sent = revision
                    retry_at = 0
                except Exception as exc:
                    self._log(exc)
                    retry_at = time.monotonic() + self.interval
                next_write = time.monotonic() + self.interval
                if self.stopping and state['status'] == 'offline':
                    return
        except Exception as exc:
            self._log(exc)
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception as exc:
                    self._log(exc)


def attach_monitor(db):
    """Startup boundary: missing configuration/dependencies never prevent launch."""
    try:
        config = db.setting('remote_monitoring')
        if config is None:
            config = default_config()
            db.save_setting('remote_monitoring', config)
        monitor = FirebaseMonitor(config, db.event)
        if monitor.enabled:
            db.on_change = monitor.observe_queue
            monitor.observe_queue(db.all())
        return monitor
    except Exception:
        try:
            db.event('', 'FIREBASE_MONITOR_CONFIGURATION_ERROR')
        except Exception:
            pass
        return None
