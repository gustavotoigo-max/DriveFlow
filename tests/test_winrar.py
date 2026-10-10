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
    source = tmp_path / 'Cliente X'
    source.mkdir(exist_ok=True)
    (source / 'a.bin').write_bytes(b'x' * 100)
    return winrar.Compression('C:/WinRAR/WinRAR.exe', source, 'Cliente X', fmt, 'Normal', split, 's3nha', popen=FakeProcess)


def test_command_uses_winrar_switches():
    args = winrar.command('WinRAR.exe', 'C:/p', 'C:/p.zip', 'ZIP', 'Melhor', 20 * 1024 ** 3, 'abc')
    assert args[:2] == ['WinRAR.exe', 'a']
    assert {'-ibck', '-y', '-r', '-ep1', '-m5', '-afzip', '-pabc', f'-v{20 * 1024 ** 3}b'} <= set(args)
    assert '-md4m' not in args  # Dicionário só existe no RAR.
    assert args[-3:] == ['--', 'C:/p.zip', 'C:/p']
    rar = winrar.command('WinRAR.exe', 'C:/p', 'C:/p.rar', 'RAR', 'Armazenar', 1024 ** 2, '')
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
    cancelled = job(tmp_path / 'other' / 'Cliente X', 'ZIP')
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
