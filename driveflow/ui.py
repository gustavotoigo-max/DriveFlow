import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QMessageBox, QFileDialog, QCheckBox, QComboBox, QSpinBox, QFormLayout,
    QListWidget, QListWidgetItem, QInputDialog, QPlainTextEdit, QDialog, QDialogButtonBox, QSizePolicy, QMenu, QLineEdit, QScrollArea)

from .drive import Drive
from .auth import AuthError
from .storage import data_dir
from .theme import THEMES, stylesheet
from .widgets import FileBrowser, label, button, size_text, themed_icon, SmoothProgressBar
from . import startup
from .version import __version__
from .drive_tree import DriveTree
from .charts import ChartsPage, duration


class Bridge(QObject):
    result = Signal(object, object, object)
    update_progress = Signal(int)


class MainWindow(QMainWindow):
    def __init__(self, db, auth, manager):
        super().__init__()
        self.db, self.auth, self.manager = db, auth, manager
        self.folder_stack = [('root', 'Meu Drive')]
        self.destination = None
        self.busy = 0
        self.auth_busy = False
        self.completed_ids = {x['id'] for x in db.all() if x['status'] == 'concluído'}
        self.closing = False
        self.update_job = None
        self.available_update = None
        self.downloaded_update = None
        self.bridge = Bridge()
        self.bridge.result.connect(self.task_done)
        self.setWindowTitle(f'DriveFlow v{__version__} • Gerenciador de uploads')
        app_icon = QIcon(str(Path(__file__).resolve().parents[1] / 'upload.ico'))
        self.setWindowIcon(app_icon)
        self.resize(1390, 920)
        self.setMinimumSize(1080, 750)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(198)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 27, 16, 22)
        branding = QHBoxLayout()
        branding.setSpacing(8)
        self.brand_icon = label('')
        self.brand_icon.setFixedSize(28, 28)
        self.brand_icon.setPixmap(app_icon.pixmap(28, 28))
        branding.addWidget(self.brand_icon)
        branding.addWidget(label('DriveFlow', 'brand'))
        side.addLayout(branding)
        side.addWidget(label('UPLOADS CONFIÁVEIS', 'muted'))
        side.addSpacing(36)
        self.nav = []
        self.nav_assets = ['transferencias_24px.png', 'graficos.svg', 'historico_24px.png', 'config_24px.png', 'lista_24px.png']
        for i, title in enumerate(['Transferências', 'Gráficos', 'Histórico', 'Configurações', 'Atividade']):
            btn = button(title, lambda checked=False, n=i: self.page(n))
            btn.setObjectName('nav')
            btn.setCheckable(True)
            btn.setIconSize(QSize(24, 24))
            side.addWidget(btn)
            self.nav.append(btn)
        side.addStretch()
        side.addWidget(label('LOCAL → GOOGLE DRIVE', 'muted'))
        note = label('Seus arquivos, diretamente\npara o destino escolhido.\nSem sincronização.', 'muted')
        note.setWordWrap(True)
        side.addWidget(note)
        side.addSpacing(14)
        side.addWidget(label(f'DESKTOP  /  v{__version__}', 'muted'))
        outer.addWidget(sidebar)
        main = QVBoxLayout()
        main.setContentsMargins(22, 16, 22, 12)
        header = QHBoxLayout()
        header.setSpacing(16)
        self.stats_panel = QFrame()
        self.stats_panel.setObjectName('stats')
        self.stats_panel.setFixedHeight(62)
        stats_layout = QHBoxLayout(self.stats_panel)
        stats_layout.setContentsMargins(14, 7, 14, 7)
        stats_layout.setSpacing(14)
        self.stats = []
        for i, title in enumerate(['NA FILA', 'CONFIRMADOS', 'VELOCIDADE', 'CONCLUÍDOS']):
            if i:
                divider = QFrame()
                divider.setObjectName('statDivider')
                divider.setFixedSize(1, 32)
                stats_layout.addWidget(divider)
            metric = QVBoxLayout()
            metric.setSpacing(0)
            metric.addWidget(label(title, 'muted'))
            value = label('—', 'stat')
            self.stats.append(value)
            metric.addWidget(value)
            stats_layout.addLayout(metric, 1)
        header.addWidget(self.stats_panel, 1)
        self.account = label('Desconectado', 'muted')
        self.account.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.account.setWordWrap(False)
        self.account.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSpacing(14)
        header.addWidget(self.account, 0, Qt.AlignmentFlag.AlignVCenter)
        self.connection_dot = label('')
        self.connection_dot.setFixedSize(7, 7)
        # Segoe UI's visible glyphs sit slightly below the line box center.
        # Keep the dot on their optical center, not above the text.
        dot_holder = QWidget()
        dot_holder.setFixedSize(7, 10)
        dot_layout = QVBoxLayout(dot_holder)
        dot_layout.setContentsMargins(0, 3, 0, 0)
        dot_layout.addWidget(self.connection_dot)
        header.addWidget(dot_holder, 0, Qt.AlignmentFlag.AlignVCenter)
        self.update_connection_dot()
        self.connect_btn = button('Conectar conta', self.connect_account)
        header.addWidget(self.connect_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        main.addLayout(header)
        main.addSpacing(6)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.transfer_page())
        self.charts = ChartsPage()
        self.pages.addWidget(self.charts)
        self.pages.addWidget(self.history_page())
        self.pages.addWidget(self.settings_page())
        self.pages.addWidget(self.activity_page())
        main.addWidget(self.pages)
        outer.addLayout(main)
        self.statusBar().showMessage('Fila salva automaticamente neste computador • Nenhum arquivo é compartilhado automaticamente')
        self.page(0)
        self.apply_theme()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)
        self.refresh()
        self.folder_timer = QTimer(self)
        self.folder_timer.timeout.connect(self.refresh_watched_folders)
        self.folder_timer.start(30000)
        if getattr(sys, 'frozen', False) and '--smoke-test' not in sys.argv:
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self.auto_check_update)
            self.update_timer.start(6 * 60 * 60 * 1000)
            QTimer.singleShot(20000, self.auto_check_update)
        self.bridge.update_progress.connect(lambda value: self.update_status.setText(f'Baixando atualização: {value}%'))
        if auth.path.exists():
            self.task(auth.restore, lambda _: self.connected(), auth_task=True)

    def panel(self):
        frame = QFrame()
        frame.setObjectName('panel')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(17, 15, 17, 15)
        return frame, layout

    def transfer_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Vertical)
        source_dest = QSplitter(Qt.Orientation.Horizontal)
        self.browser = FileBrowser()
        source_dest.addWidget(self.browser)
        drive_panel, drive_box = self.panel()
        drive_box.addWidget(label('02   Destino no Google Drive', 'section'))
        self.drive_path = label('Meu Drive', 'muted')
        self.drive_path.setWordWrap(True)
        drive_box.addWidget(self.drive_path)
        drive_actions = QHBoxLayout()
        drive_actions.addWidget(button('↑ Voltar', self.drive_back))
        drive_actions.addWidget(button('Atualizar', self.load_folders))
        drive_actions.addWidget(button('+ Pasta', self.new_folder))
        drive_box.addLayout(drive_actions)
        self.folders = DriveTree(self.task, self.with_drive)
        self.folders.folderSelected.connect(self.folder_selected)
        drive_box.addWidget(self.folders)
        self.choose = button('Usar esta pasta', self.choose_folder)
        drive_box.addWidget(self.choose)
        self.destination_label = label('Escolha explicitamente uma pasta de destino.', 'muted')
        self.destination_label.setWordWrap(True)
        drive_box.addWidget(self.destination_label)
        hint = label('Marque os arquivos e clique em Continuar na fila para iniciar o envio.', 'muted')
        hint.setWordWrap(True)
        drive_box.addWidget(hint)
        source_dest.addWidget(drive_panel)
        source_dest.setSizes([690, 380])
        splitter.addWidget(source_dest)
        queue_panel, queue_box = self.panel()
        heading = QHBoxLayout()
        heading.addWidget(label('03   Fila de uploads', 'section'))
        heading.addStretch()
        heading.addWidget(button('Pausar todos', self.manager.pause_all))
        self.continue_button = button('Continuar', self.resume_checked, True)
        self.continue_button.setToolTip('Adiciona os arquivos locais selecionados e inicia os uploads marcados na fila.')
        heading.addWidget(self.continue_button)
        queue_box.addLayout(heading)
        self.queue = self.make_table(['ARQUIVO / DESTINO', 'PROGRESSO', 'STATUS', 'TEMPO / VELOCIDADE', 'CONTROLES'])
        for col, width in ((2, 115), (3, 175), (4, 196)):
            self.queue.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.queue.setColumnWidth(col, width)
        self.queue.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue.customContextMenuRequested.connect(self.queue_menu)
        queue_box.addWidget(self.queue)
        self.queue.itemSelectionChanged.connect(self.show_details)
        self.queue.itemChanged.connect(self.queue_check_changed)
        splitter.addWidget(queue_panel)
        splitter.setSizes([360, 290])
        layout.addWidget(splitter)
        return page

    def make_table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label('Histórico de envios', 'title'))
        layout.addWidget(label('Arquivos concluídos e verificados. Copiar um link não altera as permissões de acesso.', 'muted'))
        self.history = self.make_table(['ARQUIVO', 'TAMANHO', 'DESTINO', 'CONCLUÍDO EM'])
        layout.addWidget(self.history)
        actions = QHBoxLayout()
        actions.addWidget(button('Copiar link', self.copy_link, True))
        actions.addWidget(button('Abrir no Google Drive', self.open_link))
        actions.addWidget(button('Copiar ID', self.copy_id))
        actions.addStretch()
        actions.addWidget(button('Limpar histórico', self.clear_history))
        layout.addLayout(actions)
        return page

    def settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label('Configurações', 'title'))
        frame, box = self.panel()
        form = QFormLayout()
        form.setSpacing(18)
        self.theme = QComboBox()
        self.theme.addItems(THEMES)
        self.theme.setCurrentText(self.db.setting('theme', 'Azul profundo'))
        self.theme.currentTextChanged.connect(self.save_settings)
        form.addRow('Tema', self.theme)
        self.start_windows = QCheckBox('Abrir o DriveFlow ao entrar no Windows')
        self.start_windows.setChecked(self.db.setting('start_with_windows', True))
        form.addRow('Inicialização', self.start_windows)
        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 3)
        self.concurrency.setValue(self.db.setting('concurrency', 1))
        form.addRow('Uploads simultâneos', self.concurrency)
        self.chunks = QComboBox()
        self.chunks.addItems(['1', '4', '8', '16', '32', '64'])
        self.chunks.setCurrentText(str(self.db.setting('chunk_mib', 8)))
        form.addRow('Tamanho do bloco (MiB)', self.chunks)
        self.retries = QSpinBox()
        self.retries.setRange(0, 50)
        self.retries.setValue(self.db.setting('retries', 10))
        form.addRow('Máximo de tentativas por interrupção', self.retries)
        self.full_scope = QCheckBox('Acessar pastas existentes de todo o Drive no próximo login')
        self.full_scope.setChecked(self.db.setting('full_scope', False))
        form.addRow('Permissão de acesso', self.full_scope)
        from .firebase_monitor import default_config
        remote = self.db.setting('remote_monitoring')
        if not isinstance(remote, dict):
            remote = default_config()
        self.remote_enabled = QCheckBox('Publicar estado dos uploads no Firebase')
        self.remote_enabled.setChecked(remote.get('enabled') is True)
        form.addRow('Monitoramento remoto', self.remote_enabled)
        self.remote_id = QLineEdit(str(remote.get('computer_id', '')))
        self.remote_name = QLineEdit(str(remote.get('computer_name', '')))
        self.remote_credentials = QLineEdit(str(remote.get('firebase_credentials', '')))
        self.remote_interval = QSpinBox()
        self.remote_interval.setRange(1, 3600)
        try:
            self.remote_interval.setValue(int(remote.get('update_interval_seconds', 5)))
        except (ValueError, TypeError):
            self.remote_interval.setValue(5)
        form.addRow('ID exclusivo do computador', self.remote_id)
        form.addRow('Nome do computador', self.remote_name)
        form.addRow('Intervalo de publicação (segundos)', self.remote_interval)
        credentials_row = QHBoxLayout()
        credentials_row.addWidget(self.remote_credentials)
        credentials_row.addWidget(button('Selecionar JSON…', self.select_firebase_credentials))
        form.addRow('Credencial Firebase', credentials_row)
        form.addRow(label('Monitoramento: alterações entram em vigor ao reabrir o aplicativo.', 'muted'))
        mobile_row = QHBoxLayout()
        mobile_row.addWidget(button('Conectar celular • QR code', self.pair_mobile))
        mobile_row.addWidget(button('Celulares vinculados', self.mobile_readers))
        form.addRow('Aplicativo Android', mobile_row)
        box.addLayout(form)
        info = label('Por padrão, o Google permite acessar apenas arquivos e pastas criados ou autorizados para este aplicativo. '
                     'Para navegar pelas pastas já existentes, ative a opção acima e reconecte a conta: o Google solicitará acesso amplo ao Drive. '
                     'O aplicativo não torna arquivos públicos e não exclui arquivos do Drive.', 'muted')
        info.setWordWrap(True)
        box.addWidget(info)
        box.addWidget(button('Salvar configurações', self.save_settings, True))
        box.addWidget(label('Pastas do Drive: atualização automática a cada 30 segundos. Arquivos locais acompanham as alterações do Windows.', 'muted'))
        from .updater import last_result
        self.update_status = label(f'Versão instalada: {__version__}\n{last_result()}', 'muted')
        self.update_status.setWordWrap(True)
        box.addWidget(self.update_status)
        self.update_button = button('Verificar atualizações', self.check_update)
        self.install_button = button('Baixar atualização', self.download_update)
        self.install_button.setEnabled(False)
        box.addWidget(self.update_button)
        box.addWidget(self.install_button)
        layout.addWidget(frame)
        frame, box = self.panel()
        box.addWidget(label('Conexão e armazenamento local', 'section'))
        note = label('Para conectar: crie um projeto no Google Cloud, habilite a Google Drive API e baixe um cliente OAuth do tipo Aplicativo para computador. '
                     'No modo de teste, adicione sua conta como usuário de teste. Depois clique em Conectar conta e selecione o JSON.', 'muted')
        note.setWordWrap(True)
        box.addWidget(note)
        location = label(f'Fila, eventos e tokens protegidos pelo Windows:\n{data_dir()}', 'muted')
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(location)
        box.addWidget(button('Abrir pasta de dados', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))))
        layout.addWidget(frame)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def refresh_watched_folders(self):
        if self.auth.account_id and not self.closing and not self.auth_busy:
            self.folders.refresh_watched()

    def update_failed(self, error):
        self.update_status.setText('Falha na atualização. Tente novamente; a versão atual foi preservada.')
        self.update_button.setEnabled(True)
        self.install_button.setEnabled(self.available_update is not None)

    def auto_check_update(self):
        if not self.closing and self.update_button.isEnabled() and not self.downloaded_update:
            self.check_update(silent=True)

    def check_update(self, silent=False):
        from .updater import find_update
        self.update_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.update_status.setText('Consultando versões do desktop no GitHub…')
        def checked(release):
            self.available_update = release
            self.downloaded_update = None
            self.update_button.setEnabled(True)
            self.install_button.setText('Baixar atualização')
            self.install_button.setEnabled(release is not None and getattr(sys, 'frozen', False))
            self.update_status.setText(f'Versão {release["version"]} disponível.' if release else 'Você já está na versão mais recente disponível.')
            if release and not getattr(sys, 'frozen', False):
                self.update_status.setText('Atualização disponível. A instalação automática funciona no executável Windows; esta execução usa código-fonte.')
        self.task(lambda: find_update(__version__), checked, on_error=self.update_failed, silent=silent)

    def download_update(self):
        from .updater import download_update, prepare_install
        if self.downloaded_update:
            if self.manager.running or self.busy:
                self.notice('Pause os uploads e aguarde as operações em andamento antes de reiniciar para atualizar.')
                return
            if QMessageBox.question(self, 'Atualizar DriveFlow', 'Instalar a atualização e reiniciar? A fila e as credenciais serão preservadas; os uploads ficarão pausados.') != QMessageBox.StandardButton.Yes:
                return
            if self.manager.running or self.busy:
                self.notice('Aguarde as operações em andamento e tente novamente.')
                return
            try:
                self.update_job = prepare_install(self.downloaded_update, self.available_update, Path(sys.executable))
            except Exception as exc:
                self.db.event('', f'UPDATE_PREPARE_ERROR type={type(exc).__name__}')
                self.notice('Não foi possível preparar a atualização. Confira a permissão de gravação na pasta do programa.')
                return
            self.close()
            return
        if not self.available_update:
            return
        self.update_button.setEnabled(False)
        self.install_button.setEnabled(False)
        def downloaded(path):
            self.downloaded_update = path
            self.update_status.setText('Download validado. Pause os uploads para instalar e reiniciar.')
            self.install_button.setText('Instalar e reiniciar')
            self.install_button.setEnabled(True)
            self.update_button.setEnabled(True)
        release = self.available_update
        self.task(lambda: download_update(release, self.bridge.update_progress.emit), downloaded, on_error=self.update_failed)

    def select_firebase_credentials(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Credencial de serviço Firebase', '', 'JSON (*.json)')
        if path:
            self.remote_credentials.setText(path)

    def activity_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label('Atividade', 'title'))
        layout.addWidget(label('Últimos 500 eventos locais. Tokens, endereços de sessão e conteúdo de arquivos não são registrados.', 'muted'))
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        layout.addWidget(self.logs)
        layout.addWidget(button('Exportar eventos…', self.export_events))
        return page

    def pairing_service(self):
        from .mobile_pairing import PairingService
        config = self.db.setting('remote_monitoring', {})
        if not config.get('enabled'):
            self.notice('Ative e salve o monitoramento remoto antes de conectar um celular.')
            return None
        return PairingService(config, self.db.event)

    def pair_mobile(self):
        try:
            import qrcode
        except ImportError:
            self.notice('Instale as dependências de requirements-monitoring.txt para gerar o QR code.')
            return
        service = self.pairing_service()
        if service is None:
            return
        def show_code(result):
            payload, expires, digest = result
            qr = qrcode.QRCode(box_size=1, border=4)
            qr.add_data(payload)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            size = len(matrix)
            image = QImage(size, size, QImage.Format.Format_RGB32)
            for y, row in enumerate(matrix):
                for x, black in enumerate(row):
                    image.setPixelColor(x, y, QColor('black' if black else 'white'))
            dialog = QDialog(self)
            dialog.setWindowTitle('Conectar celular • DriveFlow')
            box = QVBoxLayout(dialog)
            box.addWidget(label('Escaneie com o DriveFlow Monitor', 'title'))
            picture = label('')
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scale = max(3, 360 // size)
            picture.setPixmap(QPixmap.fromImage(image).scaled(size * scale, size * scale,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
            box.addWidget(picture)
            note = label('Código de uso único. Compartilhe somente com o celular que deseja autorizar.', 'muted')
            note.setWordWrap(True)
            box.addWidget(note)
            countdown = label('')
            box.addWidget(countdown)
            def tick():
                from datetime import datetime, timezone
                remaining = max(0, int((expires - datetime.now(timezone.utc)).total_seconds()))
                countdown.setText(f'Expira em {remaining // 60:02d}:{remaining % 60:02d}')
                if not remaining:
                    picture.clear()
                    countdown.setText('Código expirado. Feche e gere outro.')
                    timer.stop()
            timer = QTimer(dialog)
            timer.timeout.connect(tick)
            timer.start(1000)
            tick()
            box.addWidget(button('Fechar', dialog.accept))
            dialog.exec()
            self.task(lambda: service.cancel_code(digest), lambda _: None)
        self.task(service.create_code, show_code)

    def mobile_readers(self):
        service = self.pairing_service()
        if service is None:
            return
        def show_readers(rows):
            dialog = QDialog(self)
            dialog.setWindowTitle('Celulares vinculados')
            dialog.resize(460, 300)
            box = QVBoxLayout(dialog)
            box.addWidget(label('Acesso de leitura a esta máquina', 'section'))
            listing = QListWidget()
            for uid, name in rows:
                item = QListWidgetItem(f'{name} • {uid[:8]}')
                item.setData(Qt.ItemDataRole.UserRole, uid)
                listing.addItem(item)
            box.addWidget(listing)
            if not rows:
                box.addWidget(label('Nenhum celular vinculado.', 'muted'))
            def revoke():
                item = listing.currentItem()
                if item is None:
                    return
                uid = item.data(Qt.ItemDataRole.UserRole)
                dialog.accept()
                self.task(lambda: service.revoke(uid), lambda _: self.notice('Acesso do celular revogado.'))
            box.addWidget(button('Revogar acesso selecionado', revoke))
            box.addWidget(button('Fechar', dialog.accept))
            dialog.exec()
        self.task(service.readers, show_readers)

    def page(self, index):
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate(self.nav):
            btn.setChecked(i == index)

    def apply_theme(self):
        theme = self.db.setting('theme', 'Azul profundo')
        QApplication.instance().setStyleSheet(stylesheet(theme))
        accent = THEMES.get(theme, THEMES['Azul profundo'])[4]
        for btn, filename in zip(self.nav, self.nav_assets):
            btn.setIcon(themed_icon(filename, accent))
        self.action_icons = {name: themed_icon(name, accent) for name in ('play_24px.png', 'pausa_24px.png', 'stop.png', 'remover.png')}

    def update_connection_dot(self):
        connected = bool(self.auth.account_id)
        self.connection_dot.setStyleSheet('background: ' + ('#36df80' if connected else '#df6666') + '; border-radius: 3px;')
        self.connection_dot.setToolTip('Conta autenticada' if connected else 'Conta desconectada')

    def save_settings(self, *_):
        # Signals during construction cannot access fields that don't exist yet.
        if not hasattr(self, 'retries'):
            return
        requested_startup = self.start_windows.isChecked()
        if hasattr(self, 'remote_enabled'):
            import re
            remote_id = self.remote_id.text().strip()
            if self.remote_enabled.isChecked() and (not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', remote_id)
                    or not self.remote_name.text().strip() or not self.remote_credentials.text().strip()):
                self.notice('Informe ID (letras, números, _ ou -), nome e caminho da credencial Firebase.')
                return
            self.db.save_setting('remote_monitoring', dict(enabled=self.remote_enabled.isChecked(),
                computer_id=remote_id, computer_name=self.remote_name.text().strip(),
                update_interval_seconds=self.remote_interval.value(),
                firebase_credentials=self.remote_credentials.text().strip()))
        if requested_startup != self.db.setting('start_with_windows', True):
            try:
                startup.set_enabled(requested_startup)
            except OSError:
                self.notice('O Windows não permitiu alterar a inicialização automática. A configuração anterior foi preservada.')
                self.start_windows.setChecked(self.db.setting('start_with_windows', True))
                return
            self.db.save_setting('start_with_windows', requested_startup)
        for key, value in [('theme', self.theme.currentText()),
                           ('concurrency', self.concurrency.value()), ('chunk_mib', int(self.chunks.currentText())),
                           ('retries', self.retries.value()), ('full_scope', self.full_scope.isChecked())]:
            self.db.save_setting(key, value)
        self.apply_theme()
        self.statusBar().showMessage('Configurações salvas. Blocos e tentativas serão aplicados aos próximos workers.', 6000)

    def task(self, fn, callback, auth_task=False, on_error=None, silent=False):
        self.busy += 1
        if auth_task:
            self.auth_busy = True
            self.connect_btn.setEnabled(False)
        def run():
            result, safe = None, None
            try:
                result = fn()
            except Exception as exc:
                safe = str(exc) if isinstance(exc, AuthError) or (isinstance(exc, ValueError) and 'http' not in str(exc).lower()) else 'Não foi possível completar a operação. Verifique conexão, credencial OAuth e permissões no Google Cloud.'
                try:
                    self.db.event('', str(exc) if isinstance(exc, AuthError) else f'BACKGROUND_ERROR type={type(exc).__name__}')
                except Exception:
                    pass
            finally:
                self.bridge.result.emit((callback, auth_task, on_error, silent), result, safe)
        threading.Thread(target=run, daemon=True).start()

    def task_done(self, context, result, error):
        callback, auth_task, on_error = context[:3]
        silent = context[3] if len(context) > 3 else False
        self.busy -= 1
        if auth_task:
            self.auth_busy = False
        self.connect_btn.setEnabled(not self.auth_busy)
        self.update_connection_dot()
        if error:
            if on_error:
                on_error(error)
            if not silent:
                self.notice(error)
        else:
            callback(result)

    def notice(self, text):
        QMessageBox.information(self, 'DriveFlow', text)

    def connect_account(self):
        if self.auth_busy:
            return
        if self.manager.running:
            self.notice('Pause os uploads e aguarde o bloco atual terminar antes de trocar a conta.')
            return
        if self.auth.account_id:
            self.manager.pause_all()
            self.auth.logout()
            self.destination = None
            self.folders.set_destination(None)
            self.destination_label.setStyleSheet('')
            self.folder_stack = [('root', 'Meu Drive')]
            self.folders.generation += 1
            self.folders.clear()
            self.folders.nodes.clear()
            self.drive_path.setText('Meu Drive')
            self.destination_label.setText('Escolha uma pasta após conectar a conta.')
            self.account.setText('Desconectado')
            self.update_connection_dot()
            self.account.setToolTip('')
            self.connect_btn.setText('Conectar conta')
            self.db.event('', 'ACCOUNT_DISCONNECTED_LOCALLY')
            return
        if self.auth.path.exists() and not self.auth.reauth_required:
            self.task(self.auth.restore, lambda _: self.connected(), auth_task=True)
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Importar cliente OAuth Desktop', '', 'Credenciais Google (*.json)')
        if path:
            self.task(lambda: self.auth.login(path, self.db.setting('full_scope', False)), lambda _: self.connected(), auth_task=True)

    def connected(self):
        self.destination = None
        self.folders.set_destination(None)
        self.folders.generation += 1
        self.folders.clear()
        self.folders.nodes.clear()
        self.destination_label.setText('Escolha uma pasta de destino.')
        self.destination_label.setStyleSheet('')
        self.account.setText('Conectado')
        self.update_connection_dot()
        self.account.setToolTip(self.auth.email)
        self.connect_btn.setText('Desconectar')
        with self.db.lock, self.db.conn:
            self.db.conn.execute('INSERT OR REPLACE INTO accounts VALUES (?,?)', (self.auth.account_id, self.auth.email))
        self.db.event('', 'ACCOUNT_CONNECTED')
        self.load_folders()

    def with_drive(self, fn):
        with self.auth.session() as session:
            return fn(Drive(session))

    def folder_selected(self, parts):
        self.folder_stack = parts
        self.drive_path.setText('/'.join(x[1] for x in parts))

    def load_folders(self):
        if not self.auth.account_id:
            return
        if not self.folders.nodes:
            self.folders.reset_tree()
        else:
            self.folders.refresh_folder()

    def drive_back(self):
        node = self.folders.folder()
        if node and node.parent():
            self.folders.setCurrentItem(node.parent())

    def choose_folder(self):
        if not self.auth.account_id:
            self.notice('Conecte sua conta Google primeiro.')
            return
        self.destination = (self.folder_stack[-1][0], '/'.join(x[1] for x in self.folder_stack))
        self.destination_label.setText('✓  Destino: ' + self.destination[1])
        self.destination_label.setStyleSheet('color: #1DB954; font-weight: 600;')
        self.folders.set_destination(self.destination[0])

    def new_folder(self):
        if not self.auth.account_id:
            self.notice('Conecte sua conta Google primeiro.')
            return
        name, ok = QInputDialog.getText(self, 'Nova pasta no Drive', 'Nome da pasta:')
        if ok and name.strip():
            parent = self.folder_stack[-1][0]
            self.task(lambda: self.with_drive(lambda drive: drive.create_folder(parent, name.strip())), lambda _: self.load_folders())

    def enqueue(self):
        if not self.destination or not self.auth.account_id:
            self.notice('Conecte sua conta e use o botão Usar esta pasta para definir o destino.')
            return
        if not self.browser.model.checked:
            self.notice('Marque pelo menos um arquivo no explorador.')
            return
        errors = []
        added = []
        for path in sorted(self.browser.model.checked):
            try:
                ident = self.db.add(path, *self.destination, self.auth.account_id)
                added.append(path)
                self.db.event(ident, 'ADDED_TO_QUEUE')
            except (OSError, ValueError) as exc:
                errors.append(f'{Path(path).name}: {exc}')
        for path in added:
            self.browser.model.setData(self.browser.model.index(path), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        if errors:
            self.notice('\n'.join(errors))
        return True

    def selected(self, table=None):
        table = table if table is not None else self.queue
        row = table.currentRow()
        cell = table.item(row, 0) if row >= 0 else None
        return self.db.get(cell.data(Qt.ItemDataRole.UserRole)) if cell else None

    def resume_selected(self):
        item = self.selected()
        if item:
            try:
                self.manager.start(item['id'])
            except ValueError as exc:
                self.notice(str(exc))

    def resume_checked(self):
        if not self.auth.account_id:
            self.notice('Conecte sua conta Google primeiro.')
            return
        if self.browser.model.checked and not self.enqueue():
            return
        for item in self.db.all():
            if item['enabled'] and item['account'] == self.auth.account_id:
                self.manager.start(item['id'])
        self.refresh()

    def queue_check_changed(self, cell):
        if cell.column() != 0:
            return
        ident = cell.data(Qt.ItemDataRole.UserRole)
        item = self.db.get(ident)
        if not item:
            return
        enabled = cell.checkState() == Qt.CheckState.Checked
        if bool(item['enabled']) == enabled:
            return
        self.db.update(ident, enabled=int(enabled))
        if not enabled:
            self.manager.pause(ident)

    def pause_selected(self):
        item = self.selected()
        if item:
            self.manager.pause(item['id'])

    def cancel_selected(self):
        item = self.selected()
        if item and QMessageBox.question(self, 'Cancelar upload', 'Cancelar este envio? Nenhum arquivo no Drive será excluído.') == QMessageBox.StandardButton.Yes:
            self.manager.pause(item['id'], cancel=True)

    def rename_selected(self):
        item = self.selected()
        if not item:
            return
        if item['remote_id'] or item['id'] in self.manager.running:
            self.notice('Renomear está disponível antes de iniciar uma sessão de upload.')
            return
        name, ok = QInputDialog.getText(self, 'Nome no Google Drive', 'Novo nome (o arquivo local permanece igual):', text=item['name'])
        if ok and name.strip():
            self.db.update(item['id'], name=name.strip(), status='pausado', error='')

    def restart_selected(self):
        item = self.selected()
        if not item or item['status'] != 'sessão expirada':
            self.notice('Este controle é destinado a sessões que o Google informou como expiradas.')
            return
        if QMessageBox.question(self, 'Reiniciar sessão expirada', 'O Google não permite mais retomar esta sessão. Reenviar este arquivo desde o início?') == QMessageBox.StandardButton.Yes:
            self.db.event(item['id'], f'USER_RESTART_EXPIRED previous_offset={item["offset"]}')
            self.db.update(item['id'], session='', offset=0, status='pausado', error='')
            self.resume_selected()

    def remove_selected(self):
        item = self.selected()
        if item:
            self.remove_item(item['id'])

    def remove_item(self, ident):
        if QMessageBox.question(self, 'Remover da fila', 'Remover este upload da lista? O envio será pausado automaticamente. Os arquivos local e do Google Drive serão preservados.') == QMessageBox.StandardButton.Yes:
            self.manager.remove(ident)
            self.refresh()

    def play_item(self, ident):
        item = self.db.get(ident)
        if not item or ident in self.manager.pending_removals:
            return
        if item['status'] == 'cancelado' and ident not in self.manager.running:
            self.db.update(ident, status='pausado')
        self.db.update(ident, enabled=1)
        try:
            self.manager.start(ident)
        except ValueError as exc:
            self.notice(str(exc))
        self.refresh()

    def queue_menu(self, point):
        cell = self.queue.itemAt(point)
        if not cell:
            return
        self.queue.selectRow(cell.row())
        menu = QMenu(self)
        menu.addAction('Renomear antes do envio', self.rename_selected)
        menu.addAction('Reiniciar sessão expirada', self.restart_selected)
        menu.exec(self.queue.viewport().mapToGlobal(point))

    def show_details(self):
        item = self.selected()
        if item and item['error']:
            self.statusBar().showMessage(item['error'], 6000)

    def copy_link(self):
        item = self.selected(self.history)
        if item:
            QApplication.clipboard().setText(f'https://drive.google.com/file/d/{item["remote_id"]}/view')
            self.statusBar().showMessage('Link copiado. As permissões de acesso continuam iguais.', 5000)

    def open_link(self):
        item = self.selected(self.history)
        if item:
            QDesktopServices.openUrl(QUrl(f'https://drive.google.com/file/d/{item["remote_id"]}/view'))

    def copy_id(self):
        item = self.selected(self.history)
        if item:
            QApplication.clipboard().setText(item['remote_id'])

    def clear_history(self):
        if QMessageBox.question(self, 'Limpar histórico', 'Remover apenas os registros locais concluídos? Os arquivos no Google Drive serão preservados.') == QMessageBox.StandardButton.Yes:
            for item in self.db.all():
                if item['status'] == 'concluído':
                    self.db.remove(item['id'])

    def export_events(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar eventos', 'driveflow-eventos.log', 'Log (*.log)')
        if path:
            try:
                Path(path).write_text(self.logs.toPlainText(), encoding='utf-8')
            except OSError:
                self.notice('Não foi possível gravar o arquivo no local escolhido.')

    def fill_rows(self, table, rows, history=False):
        selected = self.selected(table)
        selected_id = selected['id'] if selected else None
        table.blockSignals(True)
        table.setRowCount(len(rows))
        selected_row = -1
        for row, item in enumerate(rows):
            ident = item['id']
            if ident == selected_id:
                selected_row = row
            table.setRowHeight(row, 82 if not history else 62)
            values = ([item['name'], size_text(item['size']), item['folder_name'].replace(' / ', '/'), item['updated'][:19].replace('T', ' ') + ' UTC'] if history else
                      [item['name'] + '\n' + item['folder_name'].replace(' / ', '/'), '', item['status'].capitalize(), '—'])
            if not history:
                remaining = duration(max(0, item['size'] - item['offset']) / item['speed']) if item['speed'] > 0 else '—'
                values[3] = f'{size_text(item["speed"])}/s\nDecorrido {duration(item["elapsed"])}\nRestante {remaining}'
                if ident in self.manager.pending_removals:
                    values[2] = 'Removendo…'
            for col, value in enumerate(values):
                cell = table.item(row, col)
                if cell is None:
                    cell = QTableWidgetItem()
                    table.setItem(row, col, cell)
                cell.setText(value)
                cell.setData(Qt.ItemDataRole.UserRole, ident)
                cell.setToolTip(item['error'] or item['path'])
                if col == 0 and not history:
                    cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    cell.setCheckState(Qt.CheckState.Checked if item['enabled'] else Qt.CheckState.Unchecked)
                if col == 2 and not history:
                    accent = THEMES.get(self.db.setting('theme', 'Azul profundo'), THEMES['Azul profundo'])[4]
                    cell.setForeground(QColor(accent if item['status'] in ('enviando', 'retomando') else '#a9b8c9'))
            if not history:
                for column, definitions in ((4, [('play_24px.png', 'Iniciar / continuar', self.play_item),
                                                ('pausa_24px.png', 'Pausar', self.manager.pause),
                                                ('stop.png', 'Parar', lambda key: self.manager.pause(key, cancel=True)),
                                                ('remover.png', 'Remover da lista', self.remove_item)]),):
                    controls = table.cellWidget(row, column)
                    if controls is None or controls.property('uploadId') != ident:
                        controls = QWidget()
                        controls.setObjectName('queueCell')
                        controls.setProperty('uploadId', ident)
                        layout = QHBoxLayout(controls)
                        layout.setContentsMargins(8, 0, 12, 0)
                        layout.setSpacing(6)
                        layout.addStretch()
                        controls.buttons = []
                        for asset, tip, fn in definitions:
                            if asset == 'remover.png':
                                layout.addSpacing(12)
                            btn = button('', lambda checked=False, key=ident, action=fn: action(key))
                            btn.setObjectName('rowControl')
                            btn.setFixedSize(32, 32)
                            btn.setIconSize(QSize(20, 20))
                            btn.setToolTip(tip)
                            layout.addWidget(btn)
                            controls.buttons.append((btn, asset))
                        table.setCellWidget(row, column, controls)
                    for btn, asset in controls.buttons:
                        btn.setIcon(self.action_icons[asset])
                        btn.setEnabled(ident not in self.manager.pending_removals)
                widget = table.cellWidget(row, 1)
                if widget is None:
                    widget = QWidget()
                    widget.setObjectName('queueCell')
                    box = QVBoxLayout(widget)
                    box.setContentsMargins(8, 7, 8, 7)
                    widget.text = label('')
                    widget.bar = SmoothProgressBar()
                    widget.bar.setTextVisible(False)
                    widget.bar.setFixedHeight(6)
                    box.addWidget(widget.text)
                    box.addWidget(widget.bar)
                    table.setCellWidget(row, 1, widget)
                pct = item['offset'] / item['size'] if item['size'] else 0
                widget.text.setText(f'{pct:.1%}   •   {size_text(item["offset"])} / {size_text(item["size"])}')
                widget.bar.set_confirmed(int(pct * 100000), ident, animate=item['status'] in ('enviando', 'retomando'))
        if selected_row >= 0:
            table.selectRow(selected_row)
        else:
            table.clearSelection()
            table.setCurrentCell(-1, -1)
        table.blockSignals(False)

    def refresh(self):
        self.manager.tick()
        rows = self.db.all()
        pending = [x for x in rows if x['status'] != 'concluído']
        done = [x for x in rows if x['status'] == 'concluído']
        self.stats[0].setText(str(len([x for x in pending if x['status'] != 'cancelado'])))
        self.stats[1].setText(size_text(sum(x['offset'] for x in rows)))
        self.stats[2].setText(size_text(sum(x['speed'] for x in rows)) + '/s')
        self.stats[3].setText(str(len(done)))
        self.fill_rows(self.queue, pending)
        self.fill_rows(self.history, list(reversed(done)), True)
        self.charts.sample(rows, self.manager.running, self.db.setting('theme', 'Azul profundo'))
        newly_done = [x for x in done if x['id'] not in self.completed_ids]
        self.completed_ids = {x['id'] for x in done}
        if self.auth.account_id:
            for folder_id in {x['folder_id'] for x in newly_done if x['account'] == self.auth.account_id}:
                self.folders.refresh_folder(folder_id)
        if self.pages.currentIndex() == 4:
            text = '\n'.join(f'{row[0]}   {row[1][:8] or "APP"}   {row[2]}' for row in self.db.events())
            if self.logs.toPlainText() != text:
                self.logs.setPlainText(text)
        if self.closing and not self.manager.running:
            self.close()

    def closeEvent(self, event):
        if self.manager.running:
            if not self.closing and QMessageBox.question(self, 'Fechar DriveFlow', 'Há uploads ativos. Pausar e fechar após salvar o bloco atual? Você poderá continuar ao abrir novamente.') != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.closing = True
            self.manager.closed = True
            self.manager.pause_all()
            self.statusBar().showMessage('Salvando o bloco atual antes de fechar… Aguarde o término ou timeout da requisição.')
            event.ignore()
            return
        self.manager.closed = True
        self.manager.pause_all()
        self.db.event('', 'APPLICATION_CLOSED')
        self.manager.pool.shutdown(wait=False)
        event.accept()
