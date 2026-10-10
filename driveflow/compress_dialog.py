from pathlib import Path

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QRadioButton, QButtonGroup,
                               QComboBox, QDoubleSpinBox, QCheckBox, QFileDialog, QDialogButtonBox, QMessageBox)

from . import winrar
from .widgets import label, button

CUSTOM = 'Tamanho personalizado'


class CompressDialog(QDialog):
    """Opções passadas ao WinRAR. Uma pasta por vez."""
    def __init__(self, parent, folder, destination, options, start):
        super().__init__(parent)
        self.start = start
        self.compression = None
        self.setWindowTitle('Compactar pasta • DriveFlow')
        self.setMinimumWidth(460)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        box.addWidget(label('Compactar com o WinRAR', 'section'))
        form = QFormLayout()
        form.setSpacing(10)
        source_row = QHBoxLayout()
        self.source = QLineEdit(folder or '')
        self.source.setReadOnly(True)
        self.source.setPlaceholderText('Selecione uma pasta…')
        source_row.addWidget(self.source)
        source_row.addWidget(button('Selecionar…', self.pick))
        form.addRow('Pasta', source_row)
        self.name = QLineEdit(Path(folder).name if folder else '')
        form.addRow('Nome da pasta', self.name)
        formats = QHBoxLayout()
        self.formats = QButtonGroup(self)
        for text in ('RAR', 'ZIP'):
            radio = QRadioButton(text)
            radio.setChecked(text == options.get('format', 'ZIP'))
            self.formats.addButton(radio)
            formats.addWidget(radio)
        formats.addStretch()
        form.addRow('Formato', formats)
        self.method = QComboBox()
        self.method.addItems(winrar.METHODS)
        self.method.setCurrentText(options.get('method', 'Normal'))
        form.addRow('Método de compressão', self.method)
        self.dictionary = QComboBox()
        self.dictionary.addItem(winrar.DICTIONARY)
        self.dictionary.setEnabled(False)
        form.addRow('Tamanho do dicionário', self.dictionary)
        split_row = QHBoxLayout()
        self.split = QComboBox()
        self.split.addItems([*winrar.SPLITS, CUSTOM])
        self.split.setCurrentText(options.get('split', '20 GB'))
        self.custom = QDoubleSpinBox()
        self.custom.setRange(0.01, 10000)
        self.custom.setDecimals(2)
        self.custom.setSuffix(' GB')
        self.custom.setValue(options.get('custom_gb', 4.0))
        split_row.addWidget(self.split, 1)
        split_row.addWidget(self.custom)
        self.split.currentTextChanged.connect(lambda text: self.custom.setVisible(text == CUSTOM))
        self.custom.setVisible(self.split.currentText() == CUSTOM)
        form.addRow('Dividir em volumes', split_row)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText('Sem senha')
        show = QCheckBox('Mostrar')
        show.toggled.connect(lambda on: self.password.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        password_row = QHBoxLayout()
        password_row.addWidget(self.password, 1)
        password_row.addWidget(show)
        form.addRow('Senha do arquivo', password_row)
        box.addLayout(form)
        note = label(f'Os volumes ficam ao lado da pasta e vão para {destination} assim que cada um termina.', 'muted')
        note.setWordWrap(True)
        box.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName('primary')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.confirm)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def pick(self):
        # Seletor de pasta do Windows: escolhe uma única pasta.
        path = QFileDialog.getExistingDirectory(self, 'Pasta para compactar', self.source.text())
        if path:
            path = str(Path(path))
            if not self.name.text().strip() or self.name.text() == Path(self.source.text()).name:
                self.name.setText(Path(path).name)
            self.source.setText(path)

    def options(self):
        return dict(format=self.formats.checkedButton().text(), method=self.method.currentText(),
                    split=self.split.currentText(), custom_gb=self.custom.value())

    def split_size(self):
        text = self.split.currentText()
        return winrar.split_bytes(f'{self.custom.value()} GB' if text == CUSTOM else text)

    def confirm(self):
        if not self.source.text():
            QMessageBox.information(self, 'DriveFlow', 'Selecione a pasta.')
            return
        try:
            options = self.options()
            self.compression = self.start(self.source.text(), self.name.text(), options, self.split_size(), self.password.text())
        except (OSError, ValueError) as exc:
            QMessageBox.information(self, 'DriveFlow', str(exc))
            return
        self.accept()
