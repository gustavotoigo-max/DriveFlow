from pathlib import Path

from PySide6.QtWidgets import (QHBoxLayout, QFormLayout, QLineEdit, QRadioButton, QButtonGroup, QComboBox,
                               QDoubleSpinBox, QCheckBox, QFileDialog)

from . import winrar
from . import dialogs
from .widgets import button

CUSTOM = 'Tamanho personalizado'


class CompressDialog(dialogs.Dialog):
    """Opções passadas ao WinRAR. Uma pasta por vez; o dicionário é sempre 4096 KB."""
    def __init__(self, parent, folder, output, options, start):
        super().__init__(parent, 'Compactar com o WinRAR')
        self.start = start
        self.compression = None
        self.setMinimumWidth(520)
        form = QFormLayout()
        form.setSpacing(10)
        self.source = self.path_row(form, 'Pasta de origem', folder, self.pick)
        self.output = self.path_row(form, 'Salvar volumes em', output, self.pick_output)
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
        self.method.setCurrentText(options.get('method') if options.get('method') in winrar.METHODS else 'Normal')
        form.addRow('Método de compressão', self.method)
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
        self.body.addLayout(form)
        self.ok_cancel(on_ok=self.confirm)

    @staticmethod
    def path_row(form, title, value, handler):
        row = QHBoxLayout()
        field = QLineEdit(value or '')
        field.setReadOnly(True)
        field.setPlaceholderText('Selecione uma pasta…')
        row.addWidget(field, 1)
        row.addWidget(button('Selecionar…', handler))
        form.addRow(title, row)
        return field

    def pick(self):
        # Seletor de pasta do Windows: escolhe uma única pasta.
        path = QFileDialog.getExistingDirectory(self, 'Pasta para compactar', self.source.text())
        if path:
            path = str(Path(path))
            if not self.name.text().strip() or self.name.text() == Path(self.source.text()).name:
                self.name.setText(Path(path).name)
            self.source.setText(path)

    def pick_output(self):
        path = QFileDialog.getExistingDirectory(self, 'Onde salvar os volumes', self.output.text())
        if path:
            self.output.setText(str(Path(path)))

    def options(self):
        return dict(format=self.formats.checkedButton().text(), method=self.method.currentText(),
                    split=self.split.currentText(), custom_gb=self.custom.value(), output=self.output.text())

    def split_size(self):
        text = self.split.currentText()
        return winrar.split_bytes(f'{self.custom.value()} GB' if text == CUSTOM else text)

    def confirm(self):
        if not self.source.text() or not self.output.text():
            dialogs.message(self, 'Selecione a pasta de origem e onde salvar os volumes.')
            return
        try:
            winrar.check_output(self.source.text(), self.output.text())
            if winrar.same_disk(self.source.text(), self.output.text()) and not dialogs.ask(
                    self, 'Mesmo disco', 'A origem e os volumes estão no mesmo disco, o que deixa a compactação mais lenta. Continuar mesmo assim?'):
                return
            self.compression = self.start(self.source.text(), self.output.text(), self.name.text(), self.options(),
                                          self.split_size(), self.password.text())
        except (OSError, ValueError) as exc:
            dialogs.message(self, str(exc))
            return
        self.accept()
