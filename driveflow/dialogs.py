"""Janelas internas no mesmo padrão da principal: sem a barra do Windows, cabeçalho
azul-marinho com fechar, faixa azul-ciano e botões centralizados."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from . import window_chrome
from .widgets import button, label


class Dialog(QDialog):
    def __init__(self, parent, title):
        super().__init__(parent)
        if not QApplication.instance().styleSheet():
            from .theme import stylesheet
            QApplication.instance().setStyleSheet(stylesheet('Automático'))
        self.setWindowTitle(title)
        window_chrome.make_frameless(self)
        self.native_styled = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.title_bar = window_chrome.TitleBar(self, dialog=True)
        self.title_bar.layout_.addWidget(label(title, 'appName'))
        self.title_bar.layout_.addStretch()
        self.title_bar.finish()
        outer.addWidget(self.title_bar)
        accent = QFrame()
        accent.setObjectName('accentLine')
        accent.setFixedHeight(2)
        outer.addWidget(accent)
        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(22, 18, 22, 18)
        self.body.setSpacing(12)
        outer.addWidget(content, 1)

    def add_buttons(self, *buttons):
        """Botões centralizados na base da janela."""
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        for item in buttons:
            item.setMinimumWidth(110)
            row.addWidget(item)
        row.addStretch()
        self.body.addSpacing(4)
        self.body.addLayout(row)
        return buttons

    def ok_cancel(self, ok='OK', cancel='Cancelar', on_ok=None):
        ok_button = button(ok, on_ok or self.accept, True)
        ok_button.setDefault(True)
        return self.add_buttons(ok_button, button(cancel, self.reject))

    def showEvent(self, event):
        super().showEvent(event)
        if not self.native_styled:
            self.native_styled = True
            window_chrome.apply_native_style(self)

    def nativeEvent(self, event_type, message):
        handled = window_chrome.native_event(self, event_type, message, resizable=False)
        return handled if handled is not None else super().nativeEvent(event_type, message)


def _text(dialog, text):
    item = label(text)
    item.setWordWrap(True)
    item.setMinimumWidth(320)
    item.setMaximumWidth(520)
    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    dialog.body.addWidget(item)


def message(parent, text, title='DriveFlow'):
    dialog = Dialog(parent, title)
    _text(dialog, text)
    ok = button('OK', dialog.accept, True)
    ok.setDefault(True)
    dialog.add_buttons(ok)
    dialog.exec()


def ask(parent, title, text, yes='Sim', no='Não'):
    dialog = Dialog(parent, title)
    _text(dialog, text)
    dialog.ok_cancel(yes, no)
    return dialog.exec() == QDialog.DialogCode.Accepted


def get_text(parent, title, prompt, text=''):
    dialog = Dialog(parent, title)
    dialog.body.addWidget(label(prompt))
    field = QLineEdit(text)
    field.setMinimumWidth(340)
    dialog.body.addWidget(field)
    dialog.ok_cancel()
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    return field.text(), accepted
