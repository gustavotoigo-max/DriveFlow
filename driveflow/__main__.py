import sys
import os
import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .auth import Auth
from .storage import Database, data_dir
from .ui import MainWindow
from .upload import Manager
from . import startup
from .version import __version__
from .firebase_monitor import attach_monitor


def main():
    smoke_dir = None
    smoke_output = None
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        smoke_output = Path(sys.argv[2]).resolve()
        smoke_dir = tempfile.TemporaryDirectory(prefix='driveflow-smoke-')
        os.environ['DRIVEFLOW_DATA_DIR'] = smoke_dir.name
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('DriveFlow.Desktop.1')
    app = QApplication(sys.argv)
    app.setApplicationName('DriveFlow')
    app.setApplicationVersion(__version__)
    app.setOrganizationName('DriveFlow')
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1] / 'upload.ico')))
    app.setStyle('Fusion')
    lock = QLockFile(str(data_dir() / 'application.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, 'DriveFlow', 'O DriveFlow já está aberto neste usuário do Windows.')
        return 1
    db, auth = Database(), Auth()
    monitor = attach_monitor(db)
    if not smoke_output:
        try:
            startup.set_enabled(db.setting('start_with_windows', True))
        except OSError:
            db.event('', 'WINDOWS_STARTUP_REGISTRATION_FAILED')
    db.event('', 'APPLICATION_STARTED')
    window = MainWindow(db, auth, Manager(db, auth))
    window.show()
    if smoke_output:
        def finish_smoke():
            # Check optional packaged dependencies without accessing credentials or the network.
            from google.cloud import firestore
            from google.auth.credentials import AnonymousCredentials
            import qrcode
            client = firestore.Client(project='driveflow-smoke', credentials=AnonymousCredentials())
            reference = client.collection('computers').document('smoke')
            transport = client._firestore_api
            qr = qrcode.QRCode()
            qr.add_data('driveflow-smoke')
            qr.make(fit=True)
            monitoring_dependencies = bool(reference.path and transport and qr.get_matrix())
            client.close()
            smoke_output.write_text(json.dumps({'ok': True, 'monitoring_dependencies': monitoring_dependencies, 'version': __version__, 'title': window.windowTitle(), 'pages': window.pages.count(), 'icon': not window.windowIcon().isNull(), 'assets': all(not icon.isNull() for icon in window.action_icons.values())}), encoding='utf-8')
            window.close()
        QTimer.singleShot(500, finish_smoke)
    code = app.exec()
    db.on_change = None
    if monitor:
        monitor.close()
    lock.unlock()
    db.conn.close()
    if smoke_dir:
        smoke_dir.cleanup()
    if window.update_job:
        from .updater import launch_install
        try:
            launch_install(window.update_job)
        except OSError:
            QMessageBox.warning(None, 'Atualização', 'Não foi possível iniciar o atualizador. O executável anterior foi preservado. Abra o DriveFlow novamente.')
    return code


if __name__ == '__main__':
    sys.exit(main())
