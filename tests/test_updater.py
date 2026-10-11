import hashlib
from pathlib import Path

import pytest
from driveflow import updater


def asset(version, name, payload):
    return dict(name=name, state='uploaded', size=len(payload), digest='sha256:'+hashlib.sha256(payload).hexdigest(),
                browser_download_url=f'https://github.com/{updater.REPO}/releases/download/v{version}/{name}')


def release(version='1.3.0', zip_payload=None, **flags):
    assets = [asset(version, f'DriveFlow-v{version}-portatil.exe', b'MZtest executable')]
    if zip_payload:
        assets.append(asset(version, f'DriveFlow-v{version}-pasta.zip', zip_payload))
    return dict(tag_name='v'+version, **flags, assets=assets)


def test_selects_newest_stable_desktop_not_latest_android():
    assert updater.select_update([release('1.10.0'), release('1.9.0'), release('2.0.0', prerelease=True),
                                  dict(tag_name='android-v9.0.0'), release('3.0.0', draft=True)], '1.2.0')['version'] == '1.10.0'
    assert updater.select_update([release('1.1.0'), release('1.2.0')], '1.2.0') is None


@pytest.mark.parametrize('field,value', [('digest', None), ('size', updater.MAX_SIZE+1),
    ('browser_download_url', 'https://example.com/malware.exe'), ('name', 'DriveFlow-Setup-PRIVADO.exe')])
def test_rejects_untrusted_or_unverifiable_asset(field, value):
    item=release(); item['assets'][0][field]=value
    assert updater.select_update([item], '1.2.0') is None


class Response:
    def __init__(self, payload): self.payload=payload
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_content(self, size): yield self.payload


def test_download_checks_hash_and_reports_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, 'data_dir', lambda: tmp_path)
    monkeypatch.setattr(updater.requests, 'get', lambda *a, **kw: Response(b'MZtest executable'))
    info=updater.select_update([release()], '1.2.0'); progress=[]
    path=updater.download_update(info, progress.append)
    assert path.read_bytes()==b'MZtest executable' and progress[-1]==100


@pytest.mark.parametrize('data', [b'MZbad!executable', b'MZtest executable with excess bytes', b'MZshort'])
def test_corrupt_or_incomplete_download_is_removed(tmp_path, monkeypatch, data):
    monkeypatch.setattr(updater, 'data_dir', lambda: tmp_path)
    monkeypatch.setattr(updater.requests, 'get', lambda *a, **kw: Response(data))
    with pytest.raises(ValueError): updater.download_update(updater.select_update([release()], '1.2.0'))
    assert not list((tmp_path/'updates').glob('**/*.exe'))


def test_prepare_does_not_replace_installed_executable(tmp_path):
    info=updater.select_update([release()], '1.2.0')
    stage=tmp_path/'new.exe'; stage.write_bytes(b'MZtest executable')
    target=tmp_path/'old.exe'; target.write_bytes(b'MZold')
    job=updater.prepare_install(stage, info, target)
    assert job.exists() and job.with_name('install.ps1').exists()
    assert target.read_bytes()==b'MZold'
    stage.write_bytes(b'MZtampered')
    with pytest.raises(ValueError): updater.prepare_install(stage, info, target)


def test_install_helper_does_not_inherit_one_file_temp_folder():
    env = updater.clean_environment({'PATH': 'C:/Windows', '_PYI_APPLICATION_HOME_DIR': 'C:/Temp/_MEI123',
                                     '_PYI_ARCHIVE_FILE': 'C:/DriveFlow.exe', '_PYI_PARENT_PROCESS_LEVEL': '1', '_MEIPASS2': 'x'})
    assert env == {'PATH': 'C:/Windows', 'PYINSTALLER_RESET_ENVIRONMENT': '1'}
    helper = Path(updater.__file__).with_name('update_helper.ps1').read_text(encoding='utf-8-sig')
    assert helper.index("PYINSTALLER_RESET_ENVIRONMENT") < helper.index('Start-Process')


def folder_package(tmp_path):
    import zipfile
    path = tmp_path / 'pkg.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('DriveFlow.exe', b'MZnew')
        archive.writestr('_internal/python314.dll', b'dll')
    return path.read_bytes()


def test_folder_install_updates_from_folder_package(tmp_path, monkeypatch):
    install = tmp_path / 'Programs' / 'DriveFlow'
    (install / '_internal').mkdir(parents=True)
    (install / 'DriveFlow.exe').write_bytes(b'MZold')
    assert updater.installed_kind(install / 'DriveFlow.exe') == 'pasta'
    assert updater.installed_kind(tmp_path / 'DriveFlow-v1.4.1-portatil.exe') == 'portatil'
    payload = folder_package(tmp_path)
    # Versões sem o pacote em pasta não servem para a instalação em pasta.
    assert updater.select_update([release('1.4.1')], '1.4.0', 'pasta') is None
    info = updater.select_update([release('1.4.2', payload)], '1.4.1', 'pasta')
    assert info['kind'] == 'pasta' and info['url'].endswith('DriveFlow-v1.4.2-pasta.zip')
    assert updater.select_update([release('1.4.2', payload)], '1.4.1')['url'].endswith('portatil.exe')
    monkeypatch.setattr(updater, 'data_dir', lambda: tmp_path)
    monkeypatch.setattr(updater.requests, 'get', lambda *a, **kw: Response(payload))
    path = updater.download_update(info)
    job = updater.prepare_install(path, info, install / 'DriveFlow.exe')
    details = __import__('json').loads(job.read_text(encoding='utf-8'))
    assert details['kind'] == 'pasta' and (Path(details['folder']) / '_internal' / 'python314.dll').exists()
    assert (install / 'DriveFlow.exe').read_bytes() == b'MZold'


def test_folder_package_rejects_paths_outside_folder(tmp_path):
    import zipfile
    path = tmp_path / 'evil' / 'DriveFlow.zip'
    path.parent.mkdir()
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('../fora.txt', b'x')
    info = dict(kind='pasta', version='1.4.2', size=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError):
        updater.prepare_install(path, info, tmp_path / 'DriveFlow.exe')
    assert not (tmp_path / 'evil' / 'fora.txt').exists() and not (tmp_path / 'fora.txt').exists()
