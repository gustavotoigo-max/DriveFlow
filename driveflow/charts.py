from collections import deque
import math
import time

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QScrollArea

from .theme import palette
from .widgets import label, size_text


def duration(seconds):
    seconds = max(0, int(seconds))
    return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'


class UploadPlot(QWidget):
    def __init__(self):
        super().__init__()
        self.samples = deque(maxlen=241)
        self.item = {}
        self.theme = 'Automático'
        self.setMinimumSize(290, 260)

    def sample(self, stamp, item, theme):
        self.item, self.theme = item, theme
        self.samples.append((stamp, item['speed'] / 1048576))
        self.update()

    def paintEvent(self, event):
        if not self.item:
            return
        c = palette(self.theme)
        border, accent, muted = c['border'], c['accent'], c['subtle']
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(border))
        p.setBrush(QColor(c['surface']))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QColor(c['text']))
        font = p.font()
        font.setBold(True)
        p.setFont(font)
        p.drawText(16, 26, p.fontMetrics().elidedText(self.item['name'], Qt.TextElideMode.ElideMiddle, self.width() - 32))
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor(accent))
        p.drawText(16, 49, f'{size_text(self.item["speed"])}/s   ·   {self.item["status"].capitalize()}')
        p.setPen(QColor(muted))
        eta = duration((self.item['size'] - self.item['offset']) / self.item['speed']) if self.item['speed'] > 0 else '—'
        p.drawText(16, 71, f'Decorrido {duration(self.item["elapsed"])}   ·   Restante {eta}')
        plot = QRectF(62, 103, self.width() - 82, self.height() - 147)
        now = self.samples[-1][0]
        visible = [(t, speed) for t, speed in self.samples if t >= now - 120]
        peak = max([v for _, v in visible] + [0.1])
        magnitude = 10 ** math.floor(math.log10(peak))
        ceiling = math.ceil(peak / magnitude) * magnitude
        p.drawText(16, 94, 'MiB/s')
        for i in range(5):
            y = plot.bottom() - i * plot.height() / 4
            p.setPen(QPen(QColor(border), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(muted))
            p.drawText(QRectF(2, y - 8, 53, 18), Qt.AlignmentFlag.AlignRight, f'{ceiling * i / 4:.2g}')
        for i, seconds in enumerate((120, 90, 60, 30, 0)):
            x = plot.left() + i * plot.width() / 4
            p.drawText(QRectF(x - 23, plot.bottom() + 9, 46, 20), Qt.AlignmentFlag.AlignCenter, f'-{seconds}s' if seconds else 'agora')
        path = QPainterPath()
        for i, (stamp, value) in enumerate(visible):
            point = QPointF(plot.right() - (now - stamp) * plot.width() / 120, plot.bottom() - value / ceiling * plot.height())
            path.moveTo(point) if i == 0 else path.lineTo(point)
        if visible:
            area = QPainterPath(path)
            area.lineTo(plot.right(), plot.bottom())
            area.lineTo(plot.right() - (now - visible[0][0]) * plot.width() / 120, plot.bottom())
            area.closeSubpath()
            gradient = QLinearGradient(plot.topLeft(), plot.bottomLeft())
            color = QColor(accent)
            color.setAlpha(65)
            gradient.setColorAt(0, color)
            color.setAlpha(4)
            gradient.setColorAt(1, color)
            p.fillPath(area, gradient)
            p.setPen(QPen(QColor(accent), 2))
            p.drawPath(path)
        p.end()


class ChartsPage(QWidget):
    def __init__(self):
        super().__init__()
        box = QVBoxLayout(self)
        box.addWidget(label('Gráficos de upload', 'title'))
        box.addWidget(label('Últimos 2 minutos', 'muted'))
        self.empty = label('Nenhum upload ativo.', 'muted')
        box.addWidget(self.empty)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self.grid = QGridLayout(body)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(body)
        box.addWidget(scroll)
        self.plots = {}
        self.last_active = set()

    def sample(self, rows, running, theme):
        by_id = {item['id']: item for item in rows}
        active = set(running)
        # Keep the last finished plots until a new batch starts; bound memory.
        keep = active if active else self.last_active
        if active:
            self.last_active = active.copy()
        for ident in list(self.plots):
            if ident not in keep or ident not in by_id:
                self.plots.pop(ident).deleteLater()
        for ident in sorted(keep):
            if ident in by_id:
                if ident not in self.plots:
                    self.plots[ident] = UploadPlot()
                self.plots[ident].sample(time.monotonic(), by_id[ident], theme)
        for index, plot in enumerate(self.plots.values()):
            self.grid.addWidget(plot, index // 2, index % 2)
        self.empty.setVisible(not self.plots)
