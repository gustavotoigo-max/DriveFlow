from pathlib import Path

# Identidade Nexotool: azul #2563EB, ciano nos detalhes, cabeçalho e rodapé azul-marinho.
LIGHT = dict(bg='#F4F6FA', surface='#FFFFFF', alt='#F8FAFC', border='#E2E8F0', strong='#CBD5E1', hover_border='#94A3B8',
             text='#0F172A', muted='#475569', subtle='#64748B', disabled='#94A3B8', disabled_fill='#E2E8F0',
             accent='#2563EB', accent_hover='#1D4ED8', accent_pressed='#1E40AF', soft='#EFF6FF', selection='#DBEAFE',
             success='#16A34A', danger='#DC2626', warning='#D97706', scroll='#94A3B8')
DARK = dict(LIGHT, bg='#0A1222', surface='#111B2E', alt='#16223A', border='#24324E', strong='#33456A', hover_border='#4E6390',
            text='#E6ECF5', muted='#A9B5C9', subtle='#8090A8', disabled='#5D6B84', disabled_fill='#1C2840',
            accent='#3B82F6', soft='#14294F', selection='#1D3B72', success='#22C55E', danger='#F87171', warning='#FBBF24',
            scroll='#4E6390')
NAVY = dict(navy='#0B1733', navy2='#132447', navy3='#1E3260', on_navy='#F8FAFC', on_navy_muted='#94A3B8', cyan='#22D3EE')

THEMES = ('Automático', 'Claro', 'Escuro')
# Temas escuros das versões anteriores continuam escuros.
LEGACY_DARK = {'Azul profundo', 'Cinza grafite', 'Verde escuro', 'Spotify'}


def windows_prefers_dark():
    """Modo escuro dos aplicativos em Configurações > Personalização > Cores."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] == 0
    except (ImportError, OSError):
        return False


def is_dark(theme):
    if theme == 'Escuro' or theme in LEGACY_DARK:
        return True
    if theme == 'Claro':
        return False
    return windows_prefers_dark()


def palette(theme):
    return dict(DARK if is_dark(theme) else LIGHT, **NAVY)


def stylesheet(theme):
    c = palette(theme)
    check = (Path(__file__).resolve().parents[1] / 'check.svg').as_posix()
    chevron = (Path(__file__).resolve().parents[1] / 'chevron.svg').as_posix()
    return f'''
        QWidget {{ background: {c['bg']}; color: {c['text']}; font-family: 'Segoe UI Variable Text', 'Segoe UI'; font-size: 13px; }}
        QMainWindow, QDialog {{ background: {c['bg']}; }}
        QLabel {{ background: transparent; }}
        QLabel#title {{ font-size: 22px; font-weight: 600; }}
        QLabel#muted {{ color: {c['muted']}; }}
        QLabel#section {{ font-size: 14px; font-weight: 600; }}
        QLabel#stat {{ font-size: 20px; font-weight: 600; color: {c['accent']}; }}
        QLabel#statLabel {{ color: {c['subtle']}; font-size: 11px; font-weight: 600; }}
        QFrame#titleBar {{ background: {c['navy']}; }}
        QFrame#titleBar QLabel {{ color: {c['on_navy']}; }}
        QLabel#appName {{ font-size: 13px; font-weight: 600; }}
        QFrame#titleBar QLabel#tagline, QFrame#titleBar QLabel#account {{ color: {c['on_navy_muted']}; font-size: 12px; }}
        QFrame#accentLine {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['accent']}, stop:1 {c['cyan']}); border: none; }}
        QPushButton#navyButton {{ background: {c['navy2']}; color: {c['on_navy']}; border: 1px solid {c['navy3']}; border-radius: 3px; padding: 5px 12px; font-weight: 600; font-size: 12px; }}
        QPushButton#navyButton:hover {{ background: {c['navy3']}; }}
        QPushButton#caption, QPushButton#captionClose {{ background: transparent; color: {c['on_navy']}; border: none; border-radius: 0; padding: 0; min-width: 46px; max-width: 46px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets'; font-size: 10px; }}
        QPushButton#caption:hover {{ background: {c['navy3']}; }}
        QPushButton#captionClose:hover {{ background: #C42B1C; color: #FFFFFF; }}
        QFrame#stats {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 4px; }}
        QFrame#statDivider {{ background: {c['border']}; border: none; }}
        QFrame#panel {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 4px; }}
        QFrame#panel QWidget#panelBody, QFrame#panel QLabel {{ background: transparent; }}
        QFrame#sidebar {{ background: {c['surface']}; border-right: 1px solid {c['border']}; }}
        QPushButton {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['strong']}; border-radius: 3px; padding: 8px 14px; font-weight: 600; }}
        QPushButton:hover {{ background: {c['alt']}; border-color: {c['hover_border']}; }}
        QPushButton:pressed {{ background: {c['border']}; }}
        QPushButton:disabled {{ color: {c['disabled']}; background: {c['disabled_fill']}; border-color: {c['border']}; }}
        QWidget#queueCell {{ background: transparent; }}
        QPushButton#rowControl {{ background: transparent; border: 1px solid transparent; padding: 4px; border-radius: 3px; }}
        QPushButton#rowControl:hover {{ background: {c['soft']}; border-color: {c['selection']}; }}
        QPushButton#primary {{ background: {c['accent']}; color: #FFFFFF; border: 1px solid {c['accent']}; }}
        QPushButton#primary:hover {{ background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
        QPushButton#primary:pressed {{ background: {c['accent_pressed']}; }}
        QPushButton#nav {{ text-align: left; padding: 9px 10px; border: none; border-radius: 3px; background: transparent; color: {c['muted']}; }}
        QPushButton#nav:hover {{ background: {c['alt']}; }}
        QPushButton#nav:checked {{ background: {c['soft']}; color: {c['accent']}; }}
        QLineEdit, QSpinBox, QComboBox {{ background: {c['surface']}; padding: 7px 9px; border: 1px solid {c['strong']}; border-radius: 3px; }}
        QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{ border-color: {c['hover_border']}; }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {c['accent']}; }}
        QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
        QComboBox::drop-down {{ border: none; width: 30px; }}
        QComboBox::down-arrow {{ image: url("{chevron}"); width: 12px; height: 12px; }}
        QComboBox QAbstractItemView {{ background: {c['surface']}; border: 1px solid {c['border']}; selection-background-color: {c['soft']}; selection-color: {c['text']}; }}
        QTreeView, QTableWidget, QListWidget, QPlainTextEdit {{ background: {c['surface']}; alternate-background-color: {c['alt']}; border: 1px solid {c['border']}; border-radius: 3px; selection-background-color: {c['selection']}; selection-color: {c['text']}; gridline-color: {c['border']}; outline: none; }}
        QTreeView::item, QListWidget::item {{ min-height: 30px; padding: 3px; }}
        QHeaderView::section {{ background: {c['alt']}; color: {c['subtle']}; border: none; border-bottom: 1px solid {c['border']}; padding: 9px 8px; font-size: 11px; font-weight: 600; }}
        QTableWidget::item {{ padding: 8px; }}
        QTableView::indicator {{ width: 16px; height: 16px; }}
        QTableView::indicator:unchecked {{ border: 1px solid {c['strong']}; background: {c['surface']}; border-radius: 2px; }}
        QProgressBar {{ background: {c['border']}; border: none; border-radius: 4px; height: 8px; text-align: center; color: {c['text']}; }}
        QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['accent']}, stop:1 {c['cyan']}); border-radius: 4px; }}
        QCheckBox {{ spacing: 9px; background: transparent; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {c['strong']}; background: {c['surface']}; border-radius: 2px; }}
        QCheckBox::indicator:checked, QTableView::indicator:checked {{ background: {c['accent']}; border: 1px solid {c['accent']}; border-radius: 2px; image: url("{check}"); }}
        QCheckBox::indicator:hover {{ border: 1px solid {c['accent']}; }}
        QScrollArea {{ border: none; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {c['scroll']}; min-height: 28px; border-radius: 3px; }}
        QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ background: {c['scroll']}; min-width: 28px; border-radius: 3px; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        QToolTip {{ background: {c['navy']}; color: {c['on_navy']}; border: 1px solid {c['navy3']}; padding: 5px; }}
        QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; padding: 4px; }}
        QMenu::item {{ padding: 6px 18px; border-radius: 3px; }}
        QMenu::item:selected {{ background: {c['soft']}; color: {c['text']}; }}
        QStatusBar {{ background: {c['navy']}; color: {c['on_navy_muted']}; font-size: 12px; min-height: 30px; padding-left: 14px; }}
        QStatusBar QLabel {{ color: {c['on_navy_muted']}; padding-right: 14px; }}
        QStatusBar::item {{ border: none; }}
        QSplitter::handle {{ background: {c['bg']}; height: 12px; width: 12px; }}
    '''
