"""Janela sem a barra de título do Windows, como nos aplicativos Nexotool.

O cabeçalho do próprio app faz o papel da barra: arrastar, duplo clique para
maximizar e botões de minimizar, maximizar e fechar. No Windows a janela mantém
redimensionamento pelas bordas, encaixe (Aero Snap), sombra e cantos arredondados.
DRIVEFLOW_NATIVE_FRAME=1 volta para a barra padrão do Windows.
"""
import ctypes
import os
import sys

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QAbstractButton

GWL_STYLE = -16
WS_CAPTION, WS_THICKFRAME, WS_MINIMIZEBOX, WS_MAXIMIZEBOX, WS_SYSMENU = 0x00C00000, 0x00040000, 0x00020000, 0x00010000, 0x00080000
WM_NCCALCSIZE, WM_NCHITTEST = 0x0083, 0x0084
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 10, 11, 12, 13, 14, 15, 16, 17
SM_CXFRAME, SM_CYFRAME, SM_CXPADDEDBORDER = 32, 33, 92
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2
RESIZE_BORDER = 6


def enabled():
    return os.environ.get('DRIVEFLOW_NATIVE_FRAME') != '1'


def windows():
    return sys.platform == 'win32' and enabled()


# Ícones de Segoe Fluent Icons / MDL2; fora do Windows, caracteres comuns.
GLYPHS = {'min': '', 'max': '', 'restore': '', 'close': ''} if sys.platform == 'win32' else \
         {'min': '–', 'max': '□', 'restore': '❐', 'close': '✕'}


class _Margins(ctypes.Structure):
    _fields_ = [('left', ctypes.c_int), ('right', ctypes.c_int), ('top', ctypes.c_int), ('bottom', ctypes.c_int)]


def make_frameless(window):
    if not enabled():
        return
    window.setWindowFlags(window.windowFlags() | Qt.WindowType.FramelessWindowHint)


def apply_native_style(window):
    """Devolve ao Windows bordas de redimensionamento, animações e sombra."""
    if not windows():
        return
    try:
        hwnd = int(window.winId())
        user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        get_style = getattr(user32, 'GetWindowLongPtrW', user32.GetWindowLongW)
        set_style = getattr(user32, 'SetWindowLongPtrW', user32.SetWindowLongW)
        get_style.restype = set_style.restype = ctypes.c_ssize_t
        get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
        set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        style = get_style(hwnd, GWL_STYLE)
        set_style(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        # 1 px de vidro na base mantém a sombra do Windows.
        dwm.DwmExtendFrameIntoClientArea(ctypes.c_void_p(hwnd), ctypes.byref(_Margins(0, 0, 0, 1)))
        corner = ctypes.c_int(DWMWCP_ROUND)
        dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(corner), ctypes.sizeof(corner))
    except (AttributeError, OSError):
        pass  # Windows 10 sem cantos arredondados, ou API indisponível.


def native_event(window, event_type, message):
    """Trata WM_NCCALCSIZE (sem moldura) e WM_NCHITTEST (bordas). None = deixar o Qt tratar."""
    if not windows() or event_type != b'windows_generic_MSG':
        return None
    from ctypes import wintypes
    msg = wintypes.MSG.from_address(int(message))
    user32 = ctypes.windll.user32
    if msg.message == WM_NCCALCSIZE and msg.wParam:
        if user32.IsZoomed(msg.hWnd):
            # Maximizada, a janela passa da tela pela borda invisível; compensa aqui.
            dpi = user32.GetDpiForWindow(msg.hWnd) if hasattr(user32, 'GetDpiForWindow') else 96
            metric = getattr(user32, 'GetSystemMetricsForDpi', None)
            pad = metric(SM_CXPADDEDBORDER, dpi) if metric else user32.GetSystemMetrics(SM_CXPADDEDBORDER)
            fx = (metric(SM_CXFRAME, dpi) if metric else user32.GetSystemMetrics(SM_CXFRAME)) + pad
            fy = (metric(SM_CYFRAME, dpi) if metric else user32.GetSystemMetrics(SM_CYFRAME)) + pad
            rect = wintypes.RECT.from_address(msg.lParam)
            rect.left += fx
            rect.top += fy
            rect.right -= fx
            rect.bottom -= fy
        return True, 0
    if msg.message == WM_NCHITTEST and not user32.IsZoomed(msg.hWnd):
        rect = wintypes.RECT()
        user32.GetWindowRect(msg.hWnd, ctypes.byref(rect))
        x, y = ctypes.c_short(msg.lParam & 0xFFFF).value, ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        border = round(RESIZE_BORDER * window.devicePixelRatioF())
        left, right = x < rect.left + border, x >= rect.right - border
        top, bottom = y < rect.top + border, y >= rect.bottom - border
        code = {(True, False, True, False): HTTOPLEFT, (False, True, True, False): HTTOPRIGHT,
                (True, False, False, True): HTBOTTOMLEFT, (False, True, False, True): HTBOTTOMRIGHT}.get((left, right, top, bottom))
        code = code or (HTLEFT if left else HTRIGHT if right else HTTOP if top else HTBOTTOM if bottom else None)
        if code:
            return True, code
    return None


class TitleBar(QFrame):
    """Cabeçalho azul-marinho que também é a barra da janela."""
    HEIGHT = 40

    def __init__(self, window):
        super().__init__()
        self.window_ref = window
        self.setObjectName('titleBar')
        self.setFixedHeight(self.HEIGHT)
        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(14, 0, 0, 0)
        self.layout_.setSpacing(10)
        self.captions = QHBoxLayout()
        self.captions.setSpacing(0)
        self.minimize = self._caption(GLYPHS['min'], 'Minimizar', window.showMinimized)
        self.maximize = self._caption(GLYPHS['max'], 'Maximizar', self.toggle_maximize)
        self.close_button = self._caption(GLYPHS['close'], 'Fechar', window.close, 'captionClose')
        window.installEventFilter(self)

    def _caption(self, glyph, tip, handler, name='caption'):
        btn = QPushButton(glyph)
        btn.setObjectName(name)
        btn.setToolTip(tip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedHeight(self.HEIGHT)
        btn.clicked.connect(handler)
        self.captions.addWidget(btn)
        return btn

    def finish(self):
        """Chamar depois de adicionar o conteúdo do cabeçalho."""
        if enabled():
            self.layout_.addSpacing(6)
            self.layout_.addLayout(self.captions)
        else:
            for btn in (self.minimize, self.maximize, self.close_button):
                btn.hide()

    def toggle_maximize(self):
        window = self.window_ref
        window.showNormal() if window.isMaximized() else window.showMaximized()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.WindowStateChange:
            maximized = self.window_ref.isMaximized()
            self.maximize.setText(GLYPHS['restore' if maximized else 'max'])
            self.maximize.setToolTip('Restaurar' if maximized else 'Maximizar')
        return False

    def _on_button(self, pos):
        return isinstance(self.childAt(pos), QAbstractButton)

    def mousePressEvent(self, event):
        if enabled() and event.button() == Qt.MouseButton.LeftButton and not self._on_button(event.position().toPoint()):
            handle = self.window_ref.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if enabled() and event.button() == Qt.MouseButton.LeftButton and not self._on_button(event.position().toPoint()):
            self.toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
