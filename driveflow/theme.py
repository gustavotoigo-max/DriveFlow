from pathlib import Path

THEMES = {
    'Azul profundo': ('#0c1420', '#111d2c', '#182638', '#2b3c51', '#66d7b0'),
    'Cinza grafite': ('#141619', '#1b1e23', '#242930', '#383f49', '#98baff'),
    'Verde escuro': ('#0c1916', '#11231e', '#1a3029', '#2a473c', '#84d6aa'),
    'Spotify': ('#121212', '#181818', '#282828', '#363636', '#1DB954'),
}


def stylesheet(theme):
    bg, panel, hover, border, accent = THEMES.get(theme, THEMES['Azul profundo'])
    muted = '#b3b3b3' if theme == 'Spotify' else '#91a3b7'
    check = (Path(__file__).resolve().parents[1] / 'check.svg').as_posix()
    return f'''
        QWidget {{ background: {bg}; color: #e4eaf2; font-family: 'Segoe UI'; font-size: 13px; }}
        QMainWindow, QDialog {{ background: {bg}; }}
        QLabel {{ background: transparent; }}
        QLabel#brand {{ font-size: 24px; font-weight: 700; letter-spacing: 1px; }}
        QLabel#title {{ font-size: 27px; font-weight: 600; }}
        QLabel#muted {{ color: {muted}; }}
        QLabel#section {{ font-size: 15px; font-weight: 600; }}
        QLabel#stat {{ font-size: 20px; font-weight: 600; color: {accent}; }}
        QFrame#stats {{ background: {panel}; border: 1px solid {border}; border-radius: 4px; }}
        QFrame#statDivider {{ background: {border}; border: none; }}
        QFrame#panel {{ background: {panel}; border: 1px solid {border}; border-radius: 5px; }}
        QFrame#sidebar {{ background: {panel}; border-right: 1px solid {border}; }}
        QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 4px; padding: 9px 14px; font-weight: 500; }}
        QPushButton:hover {{ background: {hover}; border-color: #64778e; }}
        QPushButton:pressed {{ background: {bg}; }}
        QPushButton:disabled {{ color: #657589; border-color: {hover}; }}
        QWidget#queueCell {{ background: transparent; }}
        QPushButton#rowControl {{ background: transparent; padding: 4px; border-radius: 3px; }}
        QPushButton#rowControl:hover {{ background: {hover}; border-color: {accent}; }}
        QPushButton#rowControl:pressed {{ background: {bg}; }}
        QPushButton#primary {{ background: {accent}; color: #0c211c; border: 1px solid {accent}; font-weight: 600; }}
        QPushButton#nav {{ text-align: left; padding: 10px 10px; border: none; border-left: 3px solid transparent; background: transparent; color: #9aabbd; }}
        QPushButton#nav:checked {{ background: {hover}; color: {accent}; border-left: 3px solid {accent}; }}
        QLineEdit, QSpinBox, QComboBox {{ background: {bg}; padding: 8px; border: 1px solid {border}; border-radius: 4px; }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {accent}; }}
        QTreeView, QTableWidget, QListWidget, QPlainTextEdit {{ background: {panel}; alternate-background-color: {bg}; border: 1px solid {border}; border-radius: 4px; selection-background-color: {hover}; gridline-color: {border}; outline: none; }}
        QTreeView::item, QListWidget::item {{ min-height: 30px; padding: 3px; }}
        QHeaderView::section {{ background: {panel}; color: #91a3b7; border: none; border-bottom: 1px solid {border}; padding: 10px 8px; font-size: 11px; font-weight: 600; }}
        QTableWidget::item {{ padding: 8px; }}
        QTableView::indicator {{ width: 16px; height: 16px; }}
        QTableView::indicator:unchecked {{ border: 1px solid #808080; background: {bg}; border-radius: 2px; }}
        QProgressBar {{ background: {bg}; border: none; border-radius: 3px; height: 7px; text-align: center; color: #e4eaf2; }}
        QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
        QCheckBox {{ spacing: 9px; background: transparent; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid #91a3b7; background: {bg}; border-radius: 2px; }}
        QCheckBox::indicator:checked, QTableView::indicator:checked {{ background: {accent}; border: 1px solid {accent}; border-radius: 2px; image: url("{check}"); }}
        QCheckBox::indicator:hover {{ border: 1px solid {accent}; }}
        QScrollBar:vertical {{ background: {bg}; width: 9px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {border}; min-height: 25px; border-radius: 3px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QToolTip {{ background: {hover}; color: #e4eaf2; border: 1px solid {border}; padding: 5px; }}
        QStatusBar {{ color: #91a3b7; border-top: 1px solid {border}; }}
        QSplitter::handle {{ background: {bg}; height: 10px; width: 10px; }}
    '''
