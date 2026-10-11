import base64
import ctypes
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def data_dir():
    path = Path(os.environ.get('DRIVEFLOW_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'DriveFlow')
    path.mkdir(parents=True, exist_ok=True)
    return path


class Vault:
    """DPAPI: tokens and session capabilities encrypted for this Windows user."""
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    def transform(self, raw, decrypt=False):
        if os.name != 'nt':
            raise RuntimeError('O cofre seguro requer Windows.')
        buf = ctypes.create_string_buffer(raw)
        source = self.Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
        target = self.Blob()
        fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
        if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(target.data, target.size)
        finally:
            ctypes.windll.kernel32.LocalFree(target.data)

    def seal(self, value):
        return base64.b64encode(self.transform(value.encode())).decode() if value else ''

    def open(self, value):
        return self.transform(base64.b64decode(value), True).decode() if value else ''


class Database:
    def __init__(self, path=None, vault=None):
        self.on_change = None
        self.vault = vault or Vault()
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path or data_dir() / 'queue.sqlite3', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY, path TEXT, name TEXT, size INTEGER, mtime TEXT,
                folder_id TEXT, folder_name TEXT, account TEXT, status TEXT,
                offset INTEGER DEFAULT 0, session TEXT DEFAULT '', remote_id TEXT DEFAULT '',
                error TEXT DEFAULT '', created TEXT, updated TEXT, speed REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, email TEXT);
            CREATE TABLE IF NOT EXISTS events (time TEXT, upload_id TEXT, event TEXT);
        ''')
        with self.conn:
            columns = {row[1] for row in self.conn.execute('PRAGMA table_info(uploads)')}
            if 'enabled' not in columns:
                self.conn.execute('ALTER TABLE uploads ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1')
            if 'elapsed' not in columns:
                self.conn.execute('ALTER TABLE uploads ADD COLUMN elapsed REAL NOT NULL DEFAULT 0')
            if 'last_confirmed' not in columns:
                self.conn.execute("ALTER TABLE uploads ADD COLUMN last_confirmed TEXT NOT NULL DEFAULT ''")
            if 'compressed' not in columns:
                # Volume gerado pelo Compactar: a fila mostra a barra de compactação concluída.
                self.conn.execute('ALTER TABLE uploads ADD COLUMN compressed INTEGER NOT NULL DEFAULT 0')
            if 'notify_name' not in columns:
                # Pasta anunciada no WhatsApp quando o lote termina.
                self.conn.execute("ALTER TABLE uploads ADD COLUMN notify_name TEXT NOT NULL DEFAULT ''")
            self.conn.execute("UPDATE uploads SET folder_name=replace(folder_name, ' / ', '/')")
            self.conn.execute("UPDATE uploads SET status='interrompido', speed=0 WHERE status IN ('enviando','iniciando','retomando','aguardando')")

    def all(self):
        with self.lock:
            return [dict(x) for x in self.conn.execute('SELECT * FROM uploads ORDER BY created')]

    def _notify(self):
        if self.on_change is not None:
            try:
                self.on_change(self.all())
            except Exception:
                try:
                    self.event('', 'MONITOR_OBSERVER_ERROR')
                except Exception:
                    pass

    def get(self, ident):
        with self.lock:
            row = self.conn.execute('SELECT * FROM uploads WHERE id=?', (ident,)).fetchone()
            return dict(row) if row else None

    def add(self, path, folder_id, folder_name, account, name=None, compressed=False, notify_name=''):
        path = Path(path).resolve()
        st = path.stat()
        if not path.is_file():
            raise ValueError('Selecione um arquivo.')
        with self.lock, self.conn:
            duplicate = self.conn.execute("SELECT id FROM uploads WHERE (path=? OR name=?) AND folder_id=? AND account=? AND status NOT IN ('concluído','cancelado')", (str(path), name or path.name, folder_id, account)).fetchone()
            if duplicate:
                raise ValueError('Este arquivo ou outro com o mesmo nome já está na fila para esse destino. Renomeie o item existente antes de adicionar outro com esse nome.')
            ident = uuid.uuid4().hex
            self.conn.execute('INSERT INTO uploads (id,path,name,size,mtime,folder_id,folder_name,account,status,created,updated,compressed,notify_name) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                              (ident, str(path), name or path.name, st.st_size, str(st.st_mtime_ns), folder_id, folder_name, account, 'pausado', now(), now(), int(compressed), notify_name))
            self._notify()
            return ident

    def update(self, ident, **values):
        allowed = {'status', 'offset', 'session', 'remote_id', 'error', 'speed', 'name', 'enabled', 'elapsed', 'last_confirmed'}
        if not values.keys() <= allowed:
            raise ValueError('Campo inválido')
        if 'session' in values:
            values['session'] = self.vault.seal(values['session'])
        values['updated'] = now()
        with self.lock, self.conn:
            self.conn.execute('UPDATE uploads SET ' + ','.join(f'{k}=?' for k in values) + ' WHERE id=?', (*values.values(), ident))
            if values.keys() & {'status', 'offset', 'speed', 'name', 'enabled'}:
                self._notify()

    def session(self, item):
        return self.vault.open(item['session'])

    def setting(self, key, default=None):
        with self.lock:
            row = self.conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def save_setting(self, key, value):
        with self.lock, self.conn:
            self.conn.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))

    def event(self, ident, event):
        with self.lock, self.conn:
            self.conn.execute('INSERT INTO events VALUES (?,?,?)', (now(), ident, event))

    def events(self):
        with self.lock:
            return list(self.conn.execute('SELECT * FROM events ORDER BY rowid DESC LIMIT 500'))

    def remove(self, ident):
        with self.lock, self.conn:
            self.conn.execute('DELETE FROM uploads WHERE id=?', (ident,))
            self._notify()
