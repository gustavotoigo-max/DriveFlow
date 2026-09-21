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
    window.theme.setCurrentText('Verde escuro')
    window.save_settings()
    assert db.setting('theme') == 'Verde escuro'
    window.theme.setCurrentText('Azul profundo')
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
    window.theme.setCurrentText('Spotify')
    assert '#1DB954' in app.styleSheet()
    window.show()
    app.processEvents()
    assert window.stats_panel.height() == 62
    assert window.stats_panel.geometry().right() < window.account.geometry().left()
    screenshot = Path(__file__).resolve().parents[1] / 'docs' / 'interface-spotify.png'
    window.grab().save(str(screenshot))
    window.close()
    app.processEvents()
    db.conn.close()
