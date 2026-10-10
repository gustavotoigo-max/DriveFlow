import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .drive import Drive, DriveError, DuplicateName, ExpiredSession, TemporaryError
from .auth import AuthError
from .storage import now


def retry(db, ident, stop, failure, limit, stage, exc):
    item = db.get(ident)
    diagnostic = f'stage={stage} type={type(exc).__name__} offset={item["offset"]} last_confirmed={item.get("last_confirmed") or "unknown"}'
    if stop.is_set():
        return False
    if failure > limit:
        db.update(ident, status='interrompido', error='Limite de tentativas atingido. Você pode continuar mais tarde.', speed=0)
        db.event(ident, f'RETRY_LIMIT_REACHED {diagnostic}')
        return False
    delay = min(60, 2 ** min(failure, 6)) + random.random()
    db.update(ident, status='retomando', speed=0, error=f'{exc} Tentativa {failure}/{limit} em {delay:.0f}s.')
    db.event(ident, f'NETWORK_RETRY attempt={failure} {diagnostic} reason={exc}')
    stop.wait(delay)
    return True


class Throttled:
    """Corpo do PUT entregue aos poucos para respeitar o limite de bytes/s.

    O limite é lido a cada bloco, então ligar ou desligar vale no mesmo envio."""
    BLOCK = 64 * 1024

    def __init__(self, data, limit, stop):
        self.data, self.limit, self.stop = data, limit, stop
        self.position = 0
        self.started = time.monotonic()
        self.sent = 0

    def __len__(self):
        return len(self.data)

    def read(self, size=-1):
        size = self.BLOCK if size is None or size < 0 else min(size, self.BLOCK)
        rate = self.limit()
        if rate > 0 and not self.stop.is_set():
            ahead = self.sent / rate - (time.monotonic() - self.started)
            if ahead > 0:
                self.stop.wait(ahead)
        elif rate <= 0:
            self.started, self.sent = time.monotonic(), 0
        block = self.data[self.position:self.position + size]
        self.position += len(block)
        self.sent += len(block)
        return block


class LocalFileChanged(Exception):
    pass


def validate(item):
    st = Path(item['path']).stat()
    if st.st_size != item['size'] or str(st.st_mtime_ns) != item['mtime']:
        raise LocalFileChanged('Arquivo alterado desde a seleção. Remova o item e adicione o arquivo novamente.')


class Engine:
    def __init__(self, db, drive, stop, chunk_size=8 * 1024 * 1024, retries=10, limit=lambda: 0):
        if chunk_size < 256 * 1024 or chunk_size % (256 * 1024):
            raise ValueError('O bloco deve ser múltiplo de 256 KiB.')
        self.db, self.drive, self.stop = db, drive, stop
        self.chunk_size, self.retries, self.limit = chunk_size, retries, limit

    def verify_completed(self, item):
        meta = self.drive.metadata(item['remote_id'])
        if meta is None:
            return False
        if meta.get('trashed') or int(meta.get('size', -1)) != item['size']:
            raise DriveError('Tamanho remoto divergente ou arquivo na lixeira. Verifique o arquivo no Drive.')
        self.db.update(item['id'], status='concluído', offset=item['size'], error='', speed=0, session='')
        self.db.event(item['id'], 'UPLOAD_COMPLETED_SIZE_VERIFIED')
        return True

    def run(self, ident):
        failures = 0
        expired = False
        stage = 'validate'
        while not self.stop.is_set():
            item = self.db.get(ident)
            try:
                validate(item)
                if expired:
                    stage = 'expired_session_check'
                    if self.verify_completed(item):
                        return
                    self.db.update(ident, status='sessão expirada', error='Sessão expirada. Use Reiniciar sessão para reenviar este arquivo.', speed=0)
                    self.db.event(ident, 'SESSION_EXPIRED_RESTART_REQUIRES_USER')
                    return
                stage = 'metadata'
                # A preallocated Drive ID makes final-response loss and crashes recoverable.
                if item['remote_id'] and self.verify_completed(item):
                    return
                if not item['remote_id']:
                    stage = 'prepare'
                    if self.drive.duplicates(item['folder_id'], item['name']):
                        raise DuplicateName('Já existe um arquivo com esse nome no destino. Renomeie o item antes de continuar.')
                    self.db.update(ident, remote_id=self.drive.generate_id())
                    item = self.db.get(ident)
                uri = self.db.session(item)
                if not uri:
                    stage = 'create_session'
                    self.db.update(ident, status='iniciando')
                    uri = self.drive.start(item)
                    # Persist the capability before sending any content.
                    self.db.update(ident, session=uri, offset=0)
                    self.db.event(ident, 'SESSION_CREATED')
                self.db.update(ident, status='retomando', speed=0)
                stage = 'query_session'
                offset, complete = self.drive.transfer(uri, item['size'])
                self.db.update(ident, offset=offset)
                self.db.event(ident, f'SESSION_QUERIED offset={offset}')
                with open(item['path'], 'rb') as source:
                    while not complete and not self.stop.is_set():
                        validate(item)
                        source.seek(offset)
                        chunk = source.read(min(self.chunk_size, item['size'] - offset))
                        if len(chunk) != min(self.chunk_size, item['size'] - offset):
                            raise OSError('Leitura incompleta do arquivo.')
                        self.db.update(ident, status='enviando', error='')
                        started = time.monotonic()
                        stage = 'send_chunk'
                        body = Throttled(chunk, self.limit, self.stop) if self.limit() > 0 else chunk
                        next_offset, complete = self.drive.transfer(uri, item['size'], offset, body)
                        if next_offset <= offset and not complete:
                            raise TemporaryError('O servidor ainda não confirmou novos bytes.')
                        speed = max(0, next_offset - offset) / max(.001, time.monotonic() - started)
                        offset = next_offset
                        self.db.update(ident, offset=offset, speed=speed, last_confirmed=now())
                        failures = 0
                if complete:
                    stage = 'verify_completed'
                    validate(item)
                    if not self.verify_completed(item):
                        raise TemporaryError('Aguardando confirmação dos metadados do arquivo.')
                    return
            except ExpiredSession:
                # Verify on the next protected iteration so network/auth failures
                # in this recovery operation still enter the normal retry path.
                expired = True
            except TemporaryError as exc:
                failures += 1
                if not retry(self.db, ident, self.stop, failures, self.retries, stage, exc):
                    if self.stop.is_set():
                        break
                    return
            except AuthError as exc:
                self.db.update(ident, status='erro', error=str(exc), speed=0)
                self.db.event(ident, f'AUTH_ERROR stage={stage} offset={self.db.get(ident)["offset"]} reason={exc}')
                return
            except LocalFileChanged as exc:
                self.db.update(ident, status='arquivo alterado', error=str(exc), speed=0)
                self.db.event(ident, 'LOCAL_FILE_CHANGED')
                return
            except OSError:
                self.db.update(ident, status='arquivo indisponível', error='Verifique se o disco está conectado e o arquivo pode ser lido. Depois clique em Continuar.', speed=0)
                self.db.event(ident, 'LOCAL_FILE_UNAVAILABLE')
                return
            except DuplicateName as exc:
                self.db.update(ident, status='nome duplicado', error=str(exc), speed=0)
                return
            except DriveError as exc:
                self.db.update(ident, status='erro', error=str(exc), speed=0)
                self.db.event(ident, 'DRIVE_ERROR')
                return
            except Exception as exc:
                checkpoint = self.db.get(ident)
                self.db.event(ident, f'WORKER_EXCEPTION stage={stage} type={type(exc).__name__} offset={checkpoint["offset"]} last_confirmed={checkpoint.get("last_confirmed") or "unknown"}')
                raise
        self.db.update(ident, status='pausado', speed=0)
        self.db.event(ident, 'UPLOAD_PAUSED')


class Manager:
    def __init__(self, db, auth):
        self.db, self.auth = db, auth
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='upload')
        self.running = {}
        self.clocks = {}
        self.pending_removals = set()
        self.closed = False
        # Limite de upload em bytes/s (0 = livre); a UI liga durante a compactação.
        self.rate_limit = 0

    def start(self, ident):
        item = self.db.get(ident)
        if not item or ident in self.pending_removals or not item['enabled'] or ident in self.running or item['status'] in ('concluído', 'cancelado', 'arquivo alterado', 'sessão expirada'):
            return
        if not self.auth.account_id or item['account'] != self.auth.account_id:
            raise ValueError('Conecte a conta Google usada ao adicionar este arquivo.')
        self.db.update(ident, status='aguardando', error='')

    def tick(self):
        for ident, (future, stop, desired) in list(self.running.items()):
            if ident in self.clocks:
                started, previous = self.clocks[ident]
                self.db.update(ident, elapsed=previous + time.monotonic() - started)
            if future.done():
                try:
                    future.result()
                except Exception as exc:
                    self.db.update(ident, status='erro', error=str(exc) if isinstance(exc, AuthError) else 'Falha na conexão ou no processamento. Verifique a rede e tente continuar.', speed=0)
                    item = self.db.get(ident)
                    self.db.event(ident, f'WORKER_ERROR type={type(exc).__name__} offset={item["offset"]} last_confirmed={item.get("last_confirmed") or "unknown"}')
                if desired and self.db.get(ident)['status'] != 'concluído':
                    self.db.update(ident, status=desired, speed=0)
                del self.running[ident]
                self.clocks.pop(ident, None)
                if ident in self.pending_removals:
                    self.db.remove(ident)
                    self.pending_removals.discard(ident)
        if self.closed or not self.auth.account_id or getattr(self.auth, 'reauth_required', False):
            return
        limit = self.db.setting('concurrency', 1)
        for item in self.db.all():
            if len(self.running) >= limit:
                break
            ident = item['id']
            if item['enabled'] and item['status'] == 'aguardando' and ident not in self.running and item['account'] == self.auth.account_id:
                stop = threading.Event()
                self.clocks[ident] = (time.monotonic(), item['elapsed'])
                self.running[ident] = (self.pool.submit(self._run, ident, stop), stop, None)

    def remove(self, ident):
        if ident in self.running:
            self.pending_removals.add(ident)
            self.pause(ident)
        else:
            self.db.remove(ident)

    def _run(self, ident, stop):
        failures = 0
        limit = self.db.setting('retries', 10)
        while not stop.is_set():
            try:
                session = self.auth.session()
            except TemporaryError as exc:
                failures += 1
                if not retry(self.db, ident, stop, failures, limit, 'authentication', exc):
                    if stop.is_set():
                        break
                    return
                continue
            except AuthError as exc:
                self.db.update(ident, status='erro', error=str(exc), speed=0)
                self.db.event(ident, f'AUTH_ERROR stage=authentication reason={exc}')
                return
            with session:
                Engine(self.db, Drive(session), stop, self.db.setting('chunk_mib', 8) * 1024 * 1024, limit,
                       lambda: self.rate_limit / max(1, len(self.running))).run(ident)
            return
        self.db.update(ident, status='pausado', speed=0)
        self.db.event(ident, 'UPLOAD_PAUSED')

    def pause(self, ident, cancel=False):
        # A user pause also withdraws pending work: freeing a slot must not
        # silently start the next file. Other active uploads keep running.
        if not cancel:
            for queued in self.db.all():
                if queued['status'] == 'aguardando' and queued['id'] not in self.running:
                    self.db.update(queued['id'], status='pausado', speed=0)
        desired = 'cancelado' if cancel else 'pausado'
        if ident in self.running:
            future, stop, _ = self.running[ident]
            self.running[ident] = (future, stop, desired)
            stop.set()
        else:
            item = self.db.get(ident)
            if item and item['status'] not in ('concluído', 'cancelado') and (cancel or item['status'] not in ('arquivo alterado', 'sessão expirada')):
                self.db.update(ident, status=desired, speed=0)
        self.db.event(ident, 'CANCEL_REQUESTED' if cancel else 'PAUSE_REQUESTED')

    def pause_all(self):
        for item in self.db.all():
            if item['status'] in ('aguardando', 'iniciando', 'enviando', 'retomando') or item['id'] in self.running:
                self.pause(item['id'])
