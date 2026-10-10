"""Compactação pelo WinRAR instalado: volumes entram na fila assim que ficam prontos."""
import ctypes
import os
import re
import subprocess
import threading
import time
from pathlib import Path

# Mesmos níveis da janela "Nome e parâmetros do arquivo" do WinRAR (-m0 a -m5).
METHODS = ('Armazenar', 'Mais rápido', 'Rápido', 'Normal', 'Bom', 'Melhor')
DICTIONARY = '4096 KB'
SPLITS = ('20 GB', '25 GB', '30 GB')
# Códigos de saída do WinRAR; 0 e 1 (aviso) mantêm o arquivo válido.
EXIT_CODES = {2: 'erro fatal', 3: 'falha de verificação (CRC)', 4: 'arquivo bloqueado', 5: 'erro de gravação',
              6: 'erro ao abrir um arquivo', 7: 'parâmetro inválido', 8: 'memória insuficiente',
              9: 'erro ao criar o arquivo', 10: 'nenhum arquivo para compactar', 11: 'senha incorreta', 255: 'cancelado'}


def find_winrar():
    """WinRAR.exe pelo registro ou pelas pastas padrão; None quando não instalado."""
    candidates = []
    try:
        import winreg
        for hive, key, value in ((winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WinRAR', 'exe64'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WinRAR', 'exe32'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\WinRAR', 'exe32'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WinRAR.exe', ''),
                                 (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WinRAR.exe', '')):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    candidates.append(winreg.QueryValueEx(handle, value)[0])
            except OSError:
                pass
    except ImportError:
        pass
    for variable in ('ProgramW6432', 'ProgramFiles', 'ProgramFiles(x86)'):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / 'WinRAR' / 'WinRAR.exe')
    for candidate in candidates:
        path = Path(str(candidate).strip('"'))
        if path.name.lower() == 'winrar.exe' and path.is_file():
            return path
    return None


def split_bytes(text):
    """'20 GB' ou '1.5 GB' em bytes (múltiplos de 1024, como no WinRAR)."""
    match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(MB|GB)\s*', text, re.IGNORECASE)
    if not match:
        raise ValueError('Tamanho de divisão inválido.')
    value = float(match.group(1).replace(',', '.')) * 1024 ** (3 if match.group(2).upper() == 'GB' else 2)
    if value < 1024 ** 2:
        raise ValueError('O tamanho de divisão mínimo é 1 MB.')
    return int(value)


def clean_name(name):
    name = name.strip().rstrip('. ')
    if not name or re.search(r'[<>:"/\\|?*]', name):
        raise ValueError('Nome inválido. Não use < > : " / \\ | ? *')
    return name


def command(exe, source, archive, fmt, method, split, password):
    """Linha de comando do WinRAR em segundo plano, sem janela."""
    args = [str(exe), 'a', '-ibck', '-y', '-r', '-ep1', f'-m{METHODS.index(method)}', f'-v{split}b']
    if fmt == 'ZIP':
        args.append('-afzip')
    else:
        args += ['-afrar', '-ma5', '-md4m']
    if password:
        args.append(f'-p{password}')
    args += ['--', str(archive), str(source)]
    return args


def volume_order(name, fmt):
    """Posição do volume pelo nome; None quando o arquivo não é volume deste pacote."""
    if fmt == 'ZIP':
        match = re.search(r'\.z(\d{2,})$', name, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 10 ** 6 if name.lower().endswith('.zip') else None
    match = re.search(r'\.part(\d+)\.rar$', name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0 if name.lower().endswith('.rar') else None


def volumes(folder, base, fmt):
    found = []
    for path in Path(folder).glob(base + '.*'):
        suffix = path.name[len(base):]
        if fmt == 'ZIP' and re.fullmatch(r'\.(z\d{2,}|zip)', suffix, re.IGNORECASE) or \
           fmt == 'RAR' and re.fullmatch(r'(\.part\d+)?\.rar', suffix, re.IGNORECASE):
            found.append(path)
    return sorted(found, key=lambda path: volume_order(path.name, fmt))


def existing_output(folder, base):
    return [path.name for fmt in ('ZIP', 'RAR') for path in volumes(folder, base, fmt)]


def folder_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.stat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def bytes_read(process):
    """Bytes que o WinRAR já leu do disco (Windows); serve de progresso geral."""
    handle = getattr(process, '_handle', None)
    if os.name != 'nt' or handle is None:
        return None

    class Counters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in ('ro', 'wo', 'oo', 'read', 'written', 'other')]
    counters = Counters()
    if not ctypes.windll.kernel32.GetProcessIoCounters(int(handle), ctypes.byref(counters)):
        return None
    return counters.read


class Compression:
    """Acompanha um WinRAR em execução. poll() devolve os volumes que ficaram prontos.

    Um volume está pronto quando o WinRAR já começou o seguinte, ou quando terminou."""
    def __init__(self, exe, source, name, fmt, method, split, password, popen=subprocess.Popen):
        self.source, self.fmt, self.split = Path(source), fmt, split
        self.name = clean_name(name)
        self.folder = self.source.parent
        if not self.source.is_dir():
            raise ValueError('Selecione uma pasta.')
        clash = existing_output(self.folder, self.name)
        if clash:
            raise ValueError(f'Já existe {clash[0]} em {self.folder}. Escolha outro nome.')
        self.archive = self.folder / (self.name + ('.zip' if fmt == 'ZIP' else '.rar'))
        self.started = time.monotonic()
        self.delivered = []
        self.total = None
        self.result = None
        self.cancelled = False
        threading.Thread(target=self._measure, daemon=True).start()
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        self.process = popen(command(exe, self.source, self.archive, fmt, method, split, password), creationflags=flags)

    def _measure(self):
        self.total = folder_size(self.source)

    @property
    def running(self):
        return self.result is None

    def poll(self):
        code = self.process.poll()
        found = volumes(self.folder, self.name, self.fmt)
        ready = found if code is not None else found[:-1]
        fresh = [path for path in ready if path not in self.delivered]
        if code is not None and self.result is None:
            self.result = code
        if self.cancelled or (code is not None and code > 1):
            return []
        self.delivered += fresh
        return fresh

    @property
    def error(self):
        if self.cancelled:
            return 'Compactação cancelada.'
        if self.result is None or self.result <= 1:
            return ''
        return f'O WinRAR parou: {EXIT_CODES.get(self.result, f"código {self.result}")}.'

    def current(self):
        """Volume em gravação e sua fração estimada (0 a 1)."""
        found = [path for path in volumes(self.folder, self.name, self.fmt) if path not in self.delivered]
        if not found or not self.running:
            return None, 1.0 if not self.running else 0.0
        path = found[-1]
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        expected = self.split
        read = bytes_read(self.process)
        if read and self.total:
            # Tamanho final estimado pela proporção já lida da pasta.
            fraction = min(1.0, read / self.total)
            written = sum(self._size(p) for p in self.delivered) + size
            if fraction > .02:
                expected = min(self.split, max(size, written / fraction - sum(self._size(p) for p in self.delivered)))
        return path, min(.99, size / expected) if expected else 0.0

    @staticmethod
    def _size(path):
        try:
            return path.stat().st_size
        except OSError:
            return 0

    def cancel(self):
        if self.running:
            self.cancelled = True
            self.process.terminate()
