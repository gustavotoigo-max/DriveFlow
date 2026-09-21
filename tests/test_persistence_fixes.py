import threading
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem
from PySide6.QtGui import QPalette

from driveflow.auth import Auth, AuthError
from driveflow.storage import Database
from driveflow.upload import Manager
from driveflow.drive_tree import DriveTree, FOLDER


def credentials():
    return Credentials(token=None, refresh_token='test-refresh', token_uri='https://oauth2.googleapis.com/token',
                       client_id='test-client', client_secret='test-secret')


def test_saved_account_restores_offline_across_versions(tmp_path, monkeypatch):
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path))
    auth = Auth()
    auth.credentials = credentials()
    auth.email, auth.account_id = 'test@example.com', 'account'
    auth.save()
    assert 'test-refresh' not in auth.path.read_text()
    restored = Auth()
    with patch.object(restored, 'identify', side_effect=AssertionError('Must restore offline')):
        assert restored.restore()
    assert restored.account_id == 'account'
    assert restored.credentials.refresh_token == 'test-refresh'
    restored.logout()
    assert not Auth().restore()


def test_legacy_token_survives_offline_and_migrates_without_oauth(tmp_path, monkeypatch):
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path))
    auth = Auth()
    auth.path.write_text(auth.vault.seal(credentials().to_json()))
    before = auth.path.read_bytes()
    with patch.object(auth, 'identify', side_effect=requests.ConnectionError('offline')):
        with pytest.raises(AuthError):
            auth.restore()
    assert auth.path.read_bytes() == before
    assert auth.credentials.refresh_token == 'test-refresh'
    assert not auth.reauth_required
    def identify():
        auth.email, auth.account_id = 'test@example.com', 'account'
        auth.save()
    with patch.object(auth, 'identify', side_effect=identify):
        assert auth.restore()
    assert Auth().restore()


def test_refresh_failure_preserves_file_and_distinguishes_revocation(tmp_path, monkeypatch):
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path))
    auth = Auth()
    auth.credentials = credentials()
    auth.email, auth.account_id = 'test@example.com', 'account'
    auth.save()
    before = auth.path.read_bytes()
    with patch.object(auth.credentials, 'refresh', side_effect=RefreshError('redacted', {'error': 'invalid_grant'})):
        with pytest.raises(AuthError, match='AUTH_REAUTH_REQUIRED'):
            auth.session()
    assert auth.reauth_required
    assert auth.path.read_bytes() == before
    assert auth.account_id == 'account'


def test_pause_prevents_next_upload_even_when_last_chunk_completes(tmp_path):
    db = Database(tmp_path / 'queue.db')
    ids = []
    for i in range(3):
        source = tmp_path / f'file{i}.bin'
        source.write_bytes(b'123')
        ids.append(db.add(source, 'root', 'Meu Drive', 'account'))
    manager = Manager(db, SimpleNamespace(account_id='account'))
    try:
        for ident in ids:
            manager.start(ident)
        future, stop = Future(), threading.Event()
        manager.running[ids[0]] = (future, stop, None)
        manager.pause(ids[0])
        assert stop.is_set()
        db.update(ids[0], status='concluído')
        future.set_result(None)
        with patch.object(manager.pool, 'submit') as submit:
            manager.tick()
            submit.assert_not_called()
        assert all(db.get(ident)['status'] == 'pausado' for ident in ids[1:])
        manager.start(ids[1])
        assert db.get(ids[1])['status'] == 'aguardando'
        assert db.get(ids[2])['status'] == 'pausado'
    finally:
        manager.pool.shutdown()
        db.conn.close()


def test_destination_stays_green_after_selection_refresh_and_change(tmp_path):
    app = QApplication.instance() or QApplication([])
    callbacks = []
    tree = DriveTree(lambda fn, cb, **kw: callbacks.append(cb), None)
    tree.reset_tree()
    rows = [{'id': 'folder', 'name': 'Clientes', 'mimeType': FOLDER}]
    callbacks.pop(0)(rows)
    tree.set_destination('folder')
    tree.setCurrentItem(tree.nodes['root'])
    tree.refresh_folder('root')
    callbacks.pop(0)(rows)
    folder = tree.nodes['folder']
    assert folder.foreground(0).color().name() == '#1db954'
    option = QStyleOptionViewItem()
    tree.itemDelegate().initStyleOption(option, tree.indexFromItem(folder))
    assert option.palette.color(QPalette.ColorRole.HighlightedText).name() == '#1db954'
    from driveflow.theme import stylesheet
    app.setStyleSheet(stylesheet('Cinza grafite'))
    tree.setCurrentItem(folder)
    tree.resize(550, 230)
    tree.show()
    app.processEvents()
    assert tree.grab().save(str(tmp_path / 'destination.png'))
    tree.set_destination('root')
    assert not folder.font(0).bold()
    tree.set_destination(None)
    assert not tree.nodes['root'].font(0).bold()
    tree.close()
