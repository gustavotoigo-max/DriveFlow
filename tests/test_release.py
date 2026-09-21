import os
import threading
from concurrent.futures import Future
from types import SimpleNamespace
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from driveflow.storage import Database
from driveflow.upload import Manager
from driveflow.drive_tree import DriveTree, FOLDER
from driveflow.charts import ChartsPage
from driveflow.ui import MainWindow
from driveflow.auth import Auth, AuthError


def test_active_removal_waits_for_worker_and_persists_elapsed(tmp_path, monkeypatch):
    source = tmp_path / 'test.bin'
    source.write_bytes(b'123')
    db = Database(tmp_path / 'queue.db')
    ident = db.add(source, 'root', 'Meu Drive', 'account')
    manager = Manager(db, SimpleNamespace(account_id='account'))
    future, stop = Future(), threading.Event()
    manager.running[ident] = (future, stop, None)
    manager.clocks[ident] = (100, 12)
    monkeypatch.setattr('driveflow.upload.time.monotonic', lambda: 110)
    manager.tick()
    assert db.get(ident)['elapsed'] == 22
    manager.remove(ident)
    assert stop.is_set() and db.get(ident) is not None
    manager.start(ident)
    assert db.get(ident)['status'] != 'aguardando'
    future.set_result(None)
    manager.tick()
    assert db.get(ident) is None
    assert not manager.running and not manager.pending_removals
    manager.pool.shutdown()
    db.conn.close()


def test_tree_retains_hierarchy_and_lists_uploaded_files():
    app = QApplication.instance() or QApplication([])
    callbacks = []
    def task(fn, cb, **kwargs):
        callbacks.append(cb)
    tree = DriveTree(task, None)
    tree.reset_tree()
    callbacks.pop(0)([{'id': 'folder', 'name': 'Clientes', 'mimeType': FOLDER}])
    folder = tree.nodes['folder']
    tree.setCurrentItem(folder)
    folder.setExpanded(True)
    callbacks.pop(0)([{'id': 'file', 'name': 'contrato.pdf', 'mimeType': 'application/pdf', 'size': '123'}])
    assert tree.nodes['file'].parent() is folder
    assert tree.path() == [('root', 'Meu Drive'), ('folder', 'Clientes')]
    tree.refresh_folder('folder')
    callbacks.pop(0)([{'id': 'file', 'name': 'contrato.pdf', 'mimeType': 'application/pdf', 'size': '123'},
                      {'id': 'new', 'name': 'novo.zip', 'mimeType': 'application/zip', 'size': '5'}])
    assert tree.nodes['new'].parent() is folder
    assert folder.isExpanded()
    tree.setCurrentItem(tree.nodes['new'])
    assert tree.path()[-1] == ('folder', 'Clientes')
    # A late response from a previous account cannot overwrite a new tree.
    tree.refresh_folder('folder')
    stale = callbacks.pop(0)
    tree.reset_tree()
    stale([])
    assert 'folder' not in tree.nodes
    tree.close()


def test_auth_failure_reenables_connect_while_folder_task_pending(tmp_path, monkeypatch):
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path / 'state'))
    app = QApplication.instance() or QApplication([])
    db, auth = Database(tmp_path / 'queue.db'), Auth()
    window = MainWindow(db, auth, Manager(db, auth))
    window.timer.stop()
    notices = []
    monkeypatch.setattr(window, 'notice', notices.append)
    window.busy, window.auth_busy = 2, True
    window.connect_btn.setEnabled(False)
    window.task_done((lambda _: None, True, None), None, 'Autenticação recusada')
    assert window.busy == 1 and window.connect_btn.isEnabled()
    assert not window.auth_busy and notices == ['Autenticação recusada']
    assert 'df6666' in window.connection_dot.styleSheet()
    window.close()
    db.conn.close()


def test_simultaneous_charts_render_in_each_theme(tmp_path, monkeypatch):
    from driveflow.theme import THEMES, stylesheet
    app = QApplication.instance() or QApplication([])
    if os.name == 'nt':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name))
    page = ChartsPage()
    page.resize(1120, 700)
    rows = [dict(id=str(i), name=f'Backup {i+1}.zip', speed=0, elapsed=30, size=1000000000, offset=0, status='enviando') for i in range(2)]
    for theme_index, theme in enumerate(THEMES):
        app.setStyleSheet(stylesheet(theme))
        for i in range(50):
            monkeypatch.setattr('driveflow.charts.time.monotonic', lambda i=i, t=theme_index: 100 + t * 100 + i * 2)
            for n, row in enumerate(rows):
                row['speed'] = (i % 12 + 3 + n * 2) * 1048576
                row['elapsed'] = i
            page.sample(rows, {'0', '1'}, theme)
        assert len(page.plots) == 2
        page.show()
        app.processEvents()
        assert page.grab().save(str(tmp_path / f'{theme}.png'))
    screenshot = Path(__file__).resolve().parents[1] / 'docs' / 'graficos.png'
    assert page.grab().save(str(screenshot))
    page.sample(rows, set(), 'Spotify')
    assert len(page.plots) == 2
    page.sample([], set(), 'Spotify')
    assert not page.plots
    page.close()
