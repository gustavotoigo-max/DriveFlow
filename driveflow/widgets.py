from pathlib import Path
import os

from PySide6.QtCore import Qt, Signal, QFileInfo, QSize, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QLinearGradient, QPainterPath, QFont
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
    """Animate toward acknowledged bytes only, never predict network progress.

    Desenho do padrão Nexotool: trilho arredondado, preenchimento azul→ciano e o %
    centralizado, legível tanto sobre o preenchimento quanto sobre o trilho."""
    colors = dict(track='#E2E8F0', start='#2563EB', end='#22D3EE', text='#0F172A', done_start='#0D9488', done_end='#2DD4BF')
    HEIGHT = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100000)
        self.setValue(0)
        self.setFixedHeight(self.HEIGHT)
        self.caption = ''
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


    def set_caption(self, caption):
        if caption != self.caption:
            self.caption = caption
            self.update()

    def text(self):
        fraction = self.value() / self.maximum() if self.maximum() else 0
        percent = f'{fraction * 100:.0f}%' if fraction < .995 or self.value() == self.maximum() else '99%'
        return f'{self.caption} {percent}'.strip()

    def paintEvent(self, event):
        c = self.colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        track = QPainterPath()
        track.addRoundedRect(rect, radius, radius)
        painter.fillPath(track, QColor(c['track']))
        fraction = (self.value() - self.minimum()) / max(1, self.maximum() - self.minimum())
        fill = QRectF(rect.left(), rect.top(), rect.width() * fraction, rect.height())
        if fill.width() > 0:
            gradient = QLinearGradient(fill.topLeft(), fill.topRight())
            done = self.value() >= self.maximum()
            gradient.setColorAt(0, QColor(c['done_start' if done else 'start']))
            gradient.setColorAt(1, QColor(c['done_end' if done else 'end']))
            painter.save()
            painter.setClipPath(track)
            painter.fillRect(fill, gradient)
            painter.restore()
        font = QFont(self.font())
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        text = self.text()
        painter.setPen(QColor(c['text']))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        # Parte do texto sobre o preenchimento em branco.
        painter.setClipRect(fill)
        painter.setPen(QColor('#FFFFFF'))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.end()


def keep_horizontal(view, scroll_to, *args):
    """Abrir uma pasta não desloca a árvore para o lado: só a rolagem vertical acompanha."""
    bar = view.horizontalScrollBar()
    value = bar.value()
    scroll_to(*args)
    bar.setValue(value)


class SteadyTree(QTreeView):
    def scrollTo(self, index, hint=QTreeView.ScrollHint.EnsureVisible):
        keep_horizontal(self, super().scrollTo, index, hint)


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
        self.tree = SteadyTree()
        self.tree.setModel(self.model)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(1, 95)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.header().setStretchLastSection(False)
        self.tree.setIndentation(16)
        layout.addWidget(self.tree)
        bottom = QHBoxLayout()
        self.summary = label('Nenhum arquivo selecionado', 'muted')
        bottom.addWidget(self.summary)
        bottom.addStretch()
        bottom.addWidget(button('Limpar seleção', self.model.clear))
        layout.addLayout(bottom)
        self.model.selection_changed.connect(self.update_summary)

    def selected_folder(self):
        """Pasta dos arquivos escolhidos para upload: a pasta marcada na árvore, a pasta
        comum dos arquivos marcados ou, por fim, a pasta aberta."""
        index = self.tree.currentIndex()
        if index.isValid() and self.tree.selectionModel().isSelected(index):
            path = Path(self.model.filePath(index))
            return str(path if self.model.isDir(index) else path.parent)
        if self.model.checked:
            return os.path.commonpath([str(Path(p).parent) for p in self.model.checked])
        return self.path.text() if self.path.text() and Path(self.path.text()).is_dir() else ''

    def update_summary(self):
        self.summary.setText(f'{len(self.model.checked)} arquivo(s) selecionado(s)')

    def navigate(self, path):
        if path and not Path(path).is_dir():
            self.path.setToolTip('Pasta não encontrada.')
            return
        self.tree.setRootIndex(self.model.index(path))
        self.path.setText(path)

    def up(self):
        path = Path(self.path.text())
        self.navigate('' if str(path.parent) == str(path) else str(path.parent))

    def pick(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Selecionar arquivos', '', 'Todos os arquivos (*)')
        for path in paths:
            self.model.setData(self.model.index(path), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
