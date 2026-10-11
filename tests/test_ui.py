import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from driveflow.auth import Auth
from driveflow.storage import Database
from driveflow.ui import MainWindow
from driveflow.upload import Manager
from driveflow.widgets import SmoothProgressBar


def test_ui_selection_persistence_settings_and_render(tmp_path, monkeypatch):
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path / 'state'))
    app = QApplication.instance() or QApplication([])
    if os.name == 'nt':
        for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisym.ttf'):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name))
    app.setStyle('Fusion')
    db, auth = Database(tmp_path / 'queue.sqlite3'), Auth()
    manager = Manager(db, auth)
    window = MainWindow(db, auth, manager)
    window.show()
    app.processEvents()
    assert window.account.text() == 'Desconectado'
    assert window.account.geometry().right() < window.connect_btn.geometry().left()
    assert not window.brand_icon.pixmap().isNull()
    assert not window.browser.units_button.icon().isNull()
    startup_calls = []
    monkeypatch.setattr('driveflow.startup.set_enabled', lambda enabled: startup_calls.append(enabled))
    window.start_windows.setChecked(False)
    window.save_settings()
    assert startup_calls == [False]
    assert db.setting('start_with_windows') is False
    source = tmp_path / 'client.zip'
    source.write_bytes(b'test')
    model = window.browser.model
    model.setData(model.index(str(source)), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    assert len(model.checked) == 1
    window.browser.navigate(str(tmp_path))
    window.browser.navigate('')
    assert len(model.checked) == 1
    # Local queue creation only, no Google calls.
    ident = db.add(source, 'folder', 'Meu Drive / Clientes', 'test-account')
    window.refresh()
    assert window.queue.rowCount() == 1
    window.queue.selectRow(0)
    assert window.selected()['id'] == ident
    window.pause_selected()
    assert db.get(ident)['status'] == 'pausado'
    window.theme.setCurrentText('Escuro')
    window.save_settings()
    assert db.setting('theme') == 'Escuro'
    window.theme.setCurrentText('Claro')
    db.remove(ident)
    model.clear()
    window.refresh()
    app.processEvents()
    screenshot = Path(__file__).resolve().parents[1] / 'docs' / 'interface.png'
    screenshot.parent.mkdir(exist_ok=True)
    assert window.grab().save(str(screenshot))
    window.close()
    app.processEvents()
    db.conn.close()


def test_progress_animation_stays_within_confirmed_bytes_and_resets():
    app = QApplication.instance() or QApplication([])
    bar = SmoothProgressBar()
    bar.set_confirmed(0, 'first')
    bar.set_confirmed(50000, 'first')
    bar.animation.setCurrentTime(200)
    assert 0 < bar.value() < 50000
    bar.set_confirmed(50000, 'first')
    assert bar.animation.currentTime() == 200
    bar.animation.setCurrentTime(450)
    assert bar.value() == 50000
    # A remote offset correction must take effect immediately.
    bar.set_confirmed(10000, 'first')
    assert bar.value() == 10000
    # Reused table rows must not animate from the previous upload's progress.
    bar.set_confirmed(70000, 'second')
    assert bar.value() == 70000
    bar.set_confirmed(80000, 'second', animate=False)
    assert bar.value() == 80000
    bar.close()


def test_continue_adds_local_files_and_only_starts_checked_queue(tmp_path, monkeypatch):
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path / 'state'))
    app = QApplication.instance() or QApplication([])
    db, auth = Database(tmp_path / 'queue.sqlite3'), Auth()
    auth.account_id = 'test-account'
    manager = Manager(db, auth)
    monkeypatch.setattr(manager, 'tick', lambda: None)  # Never access Google in UI tests.
    window = MainWindow(db, auth, manager)
    window.timer.stop()
    window.destination = ('folder', 'Meu Drive / Clientes')
    errors = []
    monkeypatch.setattr(window, 'notice', errors.append)
    first = tmp_path / 'first.zip'
    second = tmp_path / 'second.zip'
    first.write_bytes(b'one')
    second.write_bytes(b'two')
    old_id = db.add(first, 'folder', 'Meu Drive / Clientes', auth.account_id)
    window.refresh()
    assert window.queue.item(0, 0).checkState() == Qt.CheckState.Checked
    window.queue.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    assert db.get(old_id)['enabled'] == 0
    window.browser.model.setData(window.browser.model.index(str(second)), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    window.continue_button.click()
    rows = db.all()
    assert not errors
    assert len(rows) == 2
    assert db.get(old_id)['status'] == 'pausado'
    new_item = next(item for item in rows if item['id'] != old_id)
    assert new_item['status'] == 'aguardando' and new_item['enabled'] == 1
    assert not window.browser.model.checked
    window.refresh()
    assert window.queue.item(0, 0).checkState() == Qt.CheckState.Unchecked
    # Unchecking a queued item removes it from scheduling; checking alone won't start it.
    window.queue.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    assert db.get(new_item['id'])['status'] == 'pausado'
    window.queue.item(0, 0).setCheckState(Qt.CheckState.Checked)
    assert db.get(old_id)['status'] == 'pausado'
    window.continue_button.click()
    assert db.get(old_id)['status'] == 'aguardando'
    assert db.get(new_item['id'])['status'] == 'pausado'
    window.theme.setCurrentText('Escuro')
    assert '#0A1222' in app.styleSheet()
    window.show()
    app.processEvents()
    assert window.stats_panel.height() == 62
    assert window.account.parent() is window.title_bar
    screenshot = Path(__file__).resolve().parents[1] / 'docs' / 'interface-escuro.png'
    window.grab().save(str(screenshot))
    window.close()
    app.processEvents()
    db.conn.close()


def test_login_uses_bundled_client_without_asking_for_json(tmp_path, monkeypatch):
    import driveflow.ui as ui
    from driveflow.auth import FULL
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path / 'state'))
    app = QApplication.instance() or QApplication([])
    config = {'installed': {'client_id': 'id', 'client_secret': 'secret'}}
    monkeypatch.setattr(ui, 'bundled_client', lambda: config)
    db, auth = Database(tmp_path / 'queue.sqlite3'), Auth()
    manager = Manager(db, auth)
    monkeypatch.setattr(manager, 'tick', lambda: None)
    window = MainWindow(db, auth, manager)
    window.timer.stop()
    assert window.connect_btn.text() == 'Entrar com Google'
    calls = []
    monkeypatch.setattr(ui.QFileDialog, 'getOpenFileName', lambda *a: calls.append('dialog') or ('', ''))
    monkeypatch.setattr(window, 'task', lambda fn, cb, **kw: calls.append(fn))
    monkeypatch.setattr(auth, 'login', lambda client, full: calls.append((client, full)))
    window.connect_account()
    assert len(calls) == 1 and callable(calls[0])
    calls.pop()()
    assert calls == [(config, True)]  # Full Drive access is the default.
    calls.clear()
    monkeypatch.setattr(ui, 'bundled_client', lambda: None)
    window.connect_account()
    assert calls == ['dialog']
    manager.pool.shutdown()
    db.conn.close()


def test_legacy_dark_theme_maps_to_dark(tmp_path, monkeypatch):
    from driveflow.theme import palette, is_dark
    assert is_dark('Spotify') and is_dark('Escuro') and not is_dark('Claro')
    assert palette('Azul profundo')['bg'] == palette('Escuro')['bg']
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path / 'state'))
    app = QApplication.instance() or QApplication([])
    db, auth = Database(tmp_path / 'queue.sqlite3'), Auth()
    db.save_setting('theme', 'Verde escuro')
    manager = Manager(db, auth)
    monkeypatch.setattr(manager, 'tick', lambda: None)
    window = MainWindow(db, auth, manager)
    window.timer.stop()
    assert window.theme.currentText() == 'Grafite e verde'
    assert '#121212' in app.styleSheet() and palette('Grafite e verde')['accent'] == '#1DB954'
    window.theme.setCurrentText('Escuro')
    assert '#0A1222' in app.styleSheet()
    manager.pool.shutdown()
    db.conn.close()


def test_start_label_compress_button_and_compressed_volumes(tmp_path, monkeypatch):
    import driveflow.ui as ui
    from driveflow import winrar
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path / 'state'))
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui.winrar, 'find_winrar', lambda: None)
    db, auth = Database(tmp_path / 'queue.sqlite3'), Auth()
    auth.account_id = 'test-account'
    manager = Manager(db, auth)
    monkeypatch.setattr(manager, 'tick', lambda: None)
    window = MainWindow(db, auth, manager)
    window.timer.stop()
    assert not window.compress_button.isEnabled()
    window.refresh()
    assert window.continue_button.text() == 'Iniciar'
    first = tmp_path / 'first.zip'
    first.write_bytes(b'one')
    ident = db.add(first, 'folder', 'Meu Drive', auth.account_id)
    window.refresh()
    assert window.continue_button.text() == 'Iniciar'  # Nunca enviado.
    db.update(ident, offset=1, status='interrompido')
    window.refresh()
    assert window.continue_button.text() == 'Continuar'
    db.remove(ident)
    exe = tmp_path / 'WinRAR.exe'
    exe.write_bytes(b'')
    monkeypatch.setattr(ui.winrar, 'find_winrar', lambda: exe)
    window.update_compress_button()
    assert window.compress_button.isEnabled()
    source = tmp_path / 'origem' / 'Projeto'
    source.mkdir(parents=True)
    (source / 'a.txt').write_text('a')

    class Process:
        code = None
        def poll(self):
            return self.code
    process = Process()
    job = winrar.Compression(exe, source, tmp_path, 'Projeto', 'ZIP', 'Normal', 1024 ** 2, '', popen=lambda *a, **k: process)
    job.destination, job.account = ('folder', 'Meu Drive'), auth.account_id
    window.compression = job
    window.update_compress_button()
    assert not window.compress_button.isEnabled()
    (tmp_path / 'Projeto.z01').write_bytes(b'1' * 10)
    window.refresh()
    assert window.queue.rowCount() == 1 and window.queue.item(0, 2).text() == 'Compactando'
    assert manager.rate_limit == 1024 * 1024  # Upload limitado a 1 MB/s durante a compactação.
    (tmp_path / 'Projeto.z02').write_bytes(b'2')
    window.refresh()
    rows = db.all()
    assert [(r['name'], r['compressed'], r['status']) for r in rows] == [('Projeto.z01', 1, 'aguardando')]
    assert window.queue.rowCount() == 2
    cell = window.queue.cellWidget(0, 1)
    assert not cell.packing.isHidden() and cell.packing.value() == cell.packing.maximum()
    assert cell.bar.text() == 'Upload 0%'
    # Avançado: com upload na fila o WinRAR pausa; sem upload ativo ele volta.
    db.save_setting('advanced_pipeline', True)
    window.refresh()
    assert job.suspended and manager.rate_limit == 0
    assert window.queue.item(1, 2).text() == 'Aguardando upload'
    manager.pause(rows[0]['id'])
    window.refresh()
    assert not job.suspended
    process.code = 0
    (tmp_path / 'Projeto.zip').write_bytes(b'3')
    window.refresh()
    assert [r['name'] for r in db.all()] == ['Projeto.z01', 'Projeto.z02', 'Projeto.zip']
    assert window.compression is None and window.compress_button.isEnabled() and manager.rate_limit == 0
    window.folders.folderActivated.emit()
    assert window.destination == ('root', 'Meu Drive')
    window.show()
    app.processEvents()
    window.grab().save(str(tmp_path / 'compress.png'))
    window.close()
    manager.pool.shutdown()
    db.conn.close()


def test_drive_refresh_updates_every_open_folder_and_done_bar_color():
    from driveflow.drive_tree import DriveTree
    app = QApplication.instance() or QApplication([])
    requests = []
    tree = DriveTree(lambda fn, cb, **kw: requests.append(cb), None)
    tree.reset_tree()
    requests.pop()([{'id': 'a', 'name': 'A', 'mimeType': 'application/vnd.google-apps.folder'},
                    {'id': 'b', 'name': 'B', 'mimeType': 'application/vnd.google-apps.folder'}])
    for ident in ('a', 'b'):
        tree.nodes[ident].setExpanded(True)
        requests.pop()([])
    tree.refresh_all()
    assert len(requests) == 3  # Meu Drive, A e B.
    bar = SmoothProgressBar()
    bar.set_confirmed(bar.maximum(), 'x')
    bar.resize(200, 20)
    image = bar.grab().toImage()
    done = image.pixelColor(20, 10)
    assert done.green() > done.blue() * 0.6 and done.green() > done.red()  # Azul esverdeado.
    bar.close()


def test_compress_source_follows_upload_selection(tmp_path):
    from driveflow.widgets import FileBrowser
    app = QApplication.instance() or QApplication([])
    folder = tmp_path / 'Obra'
    folder.mkdir()
    file = folder / 'planta.dwg'
    file.write_bytes(b'x')
    browser = FileBrowser()
    browser.navigate(str(tmp_path))
    assert browser.selected_folder() == str(tmp_path)  # Nada escolhido: pasta aberta.
    browser.model.setData(browser.model.index(str(file)), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    assert browser.selected_folder() == str(folder)  # Pasta dos arquivos marcados.
    browser.tree.setCurrentIndex(browser.model.index(str(folder)))
    assert browser.selected_folder() == str(folder)
    browser.close()
