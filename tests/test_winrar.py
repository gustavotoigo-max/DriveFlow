import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from driveflow import winrar


class FakeProcess:
    def __init__(self, args, **kwargs):
        self.args, self.code, self.terminated = args, None, False

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated = True
        self.code = 255


def job(tmp_path, fmt='ZIP', split=10):
    source = tmp_path / 'origem' / 'Cliente X'
    source.mkdir(parents=True, exist_ok=True)
    (source / 'a.bin').write_bytes(b'x' * 100)
    return winrar.Compression('C:/WinRAR/WinRAR.exe', source, tmp_path, 'Cliente X', fmt, 'Normal', split, 's3nha', popen=FakeProcess)


def test_command_uses_winrar_switches():
    args = winrar.command('WinRAR.exe', 'C:/p', 'C:/p.zip', 'ZIP', 'Best', 20 * 1024 ** 3, 'abc')
    assert args[:2] == ['WinRAR.exe', 'a']
    assert {'-ibck', '-y', '-r', '-ep1', '-m5', '-afzip', '-pabc', f'-v{20 * 1024 ** 3}b'} <= set(args)
    assert '-md4m' not in args  # Dicionário só existe no RAR.
    assert args[-3:] == ['--', 'C:/p.zip', 'C:/p']
    rar = winrar.command('WinRAR.exe', 'C:/p', 'C:/p.rar', 'RAR', 'Store', 1024 ** 2, '')
    assert {'-afrar', '-md4m', '-m0'} <= set(rar) and not any(x.startswith('-p') for x in rar)


def test_split_sizes():
    assert winrar.split_bytes('20 GB') == 20 * 1024 ** 3
    assert winrar.split_bytes('1,5 GB') == int(1.5 * 1024 ** 3)
    with pytest.raises(ValueError):
        winrar.split_bytes('0 MB')


def test_zip_volumes_are_delivered_when_the_next_one_starts(tmp_path):
    compression = job(tmp_path)
    assert compression.poll() == []
    (tmp_path / 'Cliente X.z01').write_bytes(b'1' * 10)
    assert compression.poll() == []  # Ainda sendo gravado.
    (tmp_path / 'Cliente X.z02').write_bytes(b'2' * 3)
    assert [p.name for p in compression.poll()] == ['Cliente X.z01']
    path, fraction = compression.current()
    assert path.name == 'Cliente X.z02' and 0 < fraction < 1
    (tmp_path / 'Cliente X.z02').write_bytes(b'2' * 10)
    (tmp_path / 'Cliente X.zip').write_bytes(b'3')
    compression.process.code = 0
    assert [p.name for p in compression.poll()] == ['Cliente X.z02', 'Cliente X.zip']
    assert not compression.running and not compression.error
    assert compression.poll() == []


def test_rar_single_volume_and_failures(tmp_path):
    compression = job(tmp_path, 'RAR')
    (tmp_path / 'Cliente X.part1.rar').write_bytes(b'1')
    assert compression.poll() == []
    (tmp_path / 'Cliente X.part1.rar').rename(tmp_path / 'Cliente X.rar')
    compression.process.code = 0
    assert [p.name for p in compression.poll()] == ['Cliente X.rar']
    with pytest.raises(ValueError, match='Já existe'):
        job(tmp_path, 'RAR')
    other = tmp_path / 'other'
    other.mkdir()
    failed = job(other, 'ZIP')
    (other / 'Cliente X.z01').write_bytes(b'1')
    failed.process.code = 11
    assert failed.poll() == [] and 'senha' in failed.error
    cancelled = job(tmp_path / 'third', 'ZIP')
    cancelled.suspend()
    assert cancelled.suspended
    cancelled.resume()
    assert not cancelled.suspended
    cancelled.cancel()
    assert cancelled.process.terminated and cancelled.poll() == [] and cancelled.error == 'Compactação cancelada.'


def test_find_winrar_in_program_files(tmp_path, monkeypatch):
    exe = tmp_path / 'WinRAR' / 'WinRAR.exe'
    for variable in ('ProgramW6432', 'ProgramFiles', 'ProgramFiles(x86)'):
        monkeypatch.delenv(variable, raising=False)
    assert winrar.find_winrar() is None or winrar.find_winrar().name.lower() == 'winrar.exe'
    exe.parent.mkdir()
    exe.write_bytes(b'')
    monkeypatch.setenv('ProgramFiles', str(tmp_path))
    assert winrar.find_winrar() == exe


def test_output_never_inside_the_source(tmp_path):
    source = tmp_path / 'dados'
    (source / 'sub').mkdir(parents=True)
    for output in (source, source / 'sub'):
        with pytest.raises(ValueError, match='fora da pasta de origem'):
            winrar.check_output(source, output)
    winrar.check_output(source, tmp_path)
    assert winrar.same_disk(source, tmp_path)


def test_throttled_body_respects_rate(monkeypatch):
    import threading
    from driveflow.upload import Throttled
    clock = [0.0]
    monkeypatch.setattr('driveflow.upload.time.monotonic', lambda: clock[0])
    waits = []

    class Stop(threading.Event):
        def wait(self, seconds=None):
            waits.append(seconds)
            clock[0] += seconds
    body = Throttled(b'x' * (256 * 1024), lambda: 128 * 1024, Stop())
    assert len(body) == 256 * 1024 and body
    data = b''
    while block := body.read(8192 * 100):
        data += block
    assert data == b'x' * (256 * 1024)
    assert clock[0] == pytest.approx(2.0)  # 256 KiB a 128 KiB/s.
