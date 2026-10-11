"""Public GitHub release updates; no OAuth/Firebase credentials leave the app."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import requests
from .storage import data_dir

REPO = 'gustavotoigo-max/DriveFlow'
API = f'https://api.github.com/repos/{REPO}/releases'
MAX_SIZE = 300 * 1024 * 1024


def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value)
    return tuple(map(int, match.groups())) if match else None


def select_update(releases, current):
    candidates = []
    for release in releases:
        version = version_tuple(release.get('tag_name', ''))
        if release.get('draft') or release.get('prerelease') or not version or version <= version_tuple(current):
            continue
        number = '.'.join(map(str, version))
        name = f'DriveFlow-v{number}-portatil.exe'
        for asset in release.get('assets', []):
            # Exact names exclude installers (including private ones) and Android releases.
            digest = asset.get('digest') or ''
            expected_url = f'https://github.com/{REPO}/releases/download/{release["tag_name"]}/{name}'
            if (asset.get('name') == name and asset.get('browser_download_url') == expected_url
                    and re.fullmatch(r'sha256:[a-fA-F0-9]{64}', digest)
                    and 0 < asset.get('size', 0) <= MAX_SIZE and asset.get('state') == 'uploaded'):
                candidates.append(dict(version=number, url=expected_url, sha256=digest[7:].lower(), size=asset['size']))
    return max(candidates, key=lambda item: version_tuple(item['version']), default=None)


def find_update(current):
    releases = []
    # Multiple pages avoid confusing a newer Android release with the desktop version.
    for page in range(1, 6):
        with requests.get(API, params={'per_page': 100, 'page': page},
                          headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'DriveFlow-Updater'}, timeout=(10, 30)) as response:
            response.raise_for_status()
            batch = response.json()
        if not isinstance(batch, list):
            raise ValueError('Resposta de versões inválida.')
        releases.extend(batch)
        if len(batch) < 100:
            break
    return select_update(releases, current)


def verify_file(path, release):
    if path.stat().st_size != release['size']:
        raise ValueError('Tamanho da atualização inválido.')
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if digest != release['sha256']:
        raise ValueError('A atualização não passou na verificação SHA-256.')
    with path.open('rb') as source:
        if source.read(2) != b'MZ':
            raise ValueError('A atualização não é um executável Windows.')


def download_update(release, progress=lambda value: None):
    updates = data_dir() / 'updates'
    updates.mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='download-', dir=updates))
    target = folder / 'DriveFlow.exe'
    try:
        with requests.get(release['url'], stream=True, timeout=(10, 60), headers={'User-Agent': 'DriveFlow-Updater'}) as response:
            response.raise_for_status()
            received, last = 0, -1
            with target.open('wb') as output:
                for chunk in response.iter_content(256 * 1024):
                    received += len(chunk)
                    if received > release['size']:
                        raise ValueError('Download excedeu o tamanho esperado.')
                    output.write(chunk)
                    percent = int(received * 100 / release['size'])
                    if percent != last:
                        progress(percent)
                        last = percent
        verify_file(target, release)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        folder.rmdir()
        raise


def prepare_install(path, release, target):
    """Prepare everything while the old app is still usable; never overwrite here."""
    verify_file(path, release)
    # Prove write access before requesting shutdown (no administrator elevation).
    with tempfile.TemporaryFile(dir=target.parent):
        pass
    job = path.parent / 'install.json'
    helper = path.parent / 'install.ps1'
    shutil.copyfile(Path(__file__).with_name('update_helper.ps1'), helper)
    job.write_text(json.dumps(dict(target=str(target.resolve()), source=str(path.resolve()),
                                  sha256=release['sha256'], version=release['version'], pid=os.getpid())), encoding='utf-8')
    return job


def clean_environment(environ=None):
    """Environment for processes that start another DriveFlow executable.

    The one-file bootloader passes its temporary folder (_MEI…) through these
    variables; a new executable that inherits them looks for python3xx.dll in a
    folder that is deleted when this app closes."""
    env = {k: v for k, v in (os.environ if environ is None else environ).items()
           if not k.upper().startswith('_PYI_') and k.upper() not in ('_MEIPASS', '_MEIPASS2')}
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return env


def launch_install(job):
    powershell = Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    subprocess.Popen([str(powershell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                      '-File', str(job.with_name('install.ps1')), '-JobFile', str(job)],
                     creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True, env=clean_environment())


def last_result():
    try:
        reports = list((data_dir() / 'updates').glob('download-*/result.txt'))
        if reports:
            return max(reports, key=lambda p: p.stat().st_mtime).read_text(encoding='utf-8-sig').strip()
    except (OSError, UnicodeError):
        pass
    return ''
