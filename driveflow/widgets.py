from pathlib import Path
import os

from PySide6.QtCore import Qt, Signal, QFileInfo, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (QFileSystemModel, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QTreeView, QLabel, QFileDialog, QHeaderView, QFileIconProvider, QProgressBar)


def size_text(value):
    value = float(value)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if value < 1024 or unit == 'TiB':
            return f'{value:.1f} {unit}' if unit != 'B' else f'{value:.0f} B'
        value /= 1024


def label(text, kind=None):
    item = QLabel(text)
    if kind:
        item.setObjectName(kind)
    return item


def button(text, handler=None, primary=False):
    item = QPushButton(text)
    if primary:
        item.setObjectName('primary')
    if handler:
        item.clicked.connect(handler)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    return item


def themed_icon(filename, color):
    """Tint the existing transparent asset at render time; keep the PNG intact."""
    pixmap = QPixmap(str(Path(__file__).resolve().parents[1] / filename))
    if pixmap.isNull():
        return QIcon()
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    return QIcon(pixmap)


class SmoothProgressBar(QProgressBar):
    """Animate toward acknowledged bytes only, never predict network progress."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100000)
        self.setValue(0)
        self._identity = None
        self._confirmed = 0
        self.animation = QPropertyAnimation(self, b'value', self)
        self.animation.setDuration(450)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_confirmed(self, value, identity, animate=True):
        value = max(self.minimum(), min(self.maximum(), value))
        if identity != self._identity or value < self._confirmed or not animate:
            self.animation.stop()
            self._identity, self._confirmed = identity, value
            self.setValue(value)
        elif value != self._confirmed:
            self.animation.stop()
            self._confirmed = value
            self.animation.setStartValue(self.value())
            self.animation.setEndValue(value)
            self.animation.start()


class CheckedFiles(QFileSystemModel):
    selection_changed = Signal()

    def __init__(self):
        super().__init__()
        self.checked = set()
        self.setReadOnly(True)
        self.setRootPath('')

    def flags(self, index):
        flags = super().flags(index)
        if index.column() == 0 and not self.isDir(index):
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ['Nome', 'Tamanho', 'Tipo', 'Modificado em'][section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0 and not self.isDir(index):
            return Qt.CheckState.Checked if self.filePath(index) in self.checked else Qt.CheckState.Unchecked
        return super().data(index, role)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.CheckStateRole and not self.isDir(index):
            path = self.filePath(index)
            if value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value):
                self.checked.add(path)
            else:
                self.checked.discard(path)
            self.dataChanged.emit(index, index, [role])
            self.selection_changed.emit()
            return True
        return super().setData(index, value, role)

    def clear(self):
        old = list(self.checked)
        self.checked.clear()
        for path in old:
            index = self.index(path)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        self.selection_changed.emit()


class FileBrowser(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addWidget(label('Arquivos locais', 'section'))
        top.addStretch()
        top.addWidget(button('Selecionar arquivos', self.pick))
        layout.addLayout(top)
        address = QHBoxLayout()
        self.units_button = button('Unidades', lambda: self.navigate(''))
        self.units_button.setIcon(QFileIconProvider().icon(QFileInfo(os.environ.get('SystemDrive', 'C:') + '/')))
        self.units_button.setIconSize(QSize(20, 20))
        address.addWidget(self.units_button)
        address.addWidget(button('↑', self.up))
        self.path = QLineEdit()
        self.path.setPlaceholderText('Caminho da pasta…')
        self.path.returnPressed.connect(lambda: self.navigate(self.path.text()))
        address.addWidget(self.path)
        layout.addLayout(address)
        self.model = CheckedFiles()
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(1, 95)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.doubleClicked.connect(self.enter)
        layout.addWidget(self.tree)
        bottom = QHBoxLayout()
        self.summary = label('Nenhum arquivo selecionado', 'muted')
        bottom.addWidget(self.summary)
        bottom.addStretch()
        bottom.addWidget(button('Limpar seleção', self.model.clear))
        layout.addLayout(bottom)
        self.model.selection_changed.connect(self.update_summary)

    def update_summary(self):
        self.summary.setText(f'{len(self.model.checked)} arquivo(s) selecionado(s)')

    def navigate(self, path):
        if path and not Path(path).is_dir():
            self.path.setToolTip('Pasta não encontrada.')
            return
        self.tree.setRootIndex(self.model.index(path))
        self.path.setText(path)

    def enter(self, index):
        if self.model.isDir(index):
            self.navigate(self.model.filePath(index))

    def up(self):
        path = Path(self.path.text())
        self.navigate('' if str(path.parent) == str(path) else str(path.parent))

    def pick(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Selecionar arquivos', '', 'Todos os arquivos (*)')
        for path in paths:
            self.model.setData(self.model.index(path), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
