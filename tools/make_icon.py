"""Build a multi-resolution Windows icon from the supplied PNG."""
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

root = Path(__file__).resolve().parents[1]
source = QImage(str(root / 'upload.png'))
if source.isNull():
    raise RuntimeError('upload.png não pôde ser carregado.')
images = []
sizes = (16, 24, 32, 48, 64, 128, 256)
for size in sizes:
    image = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise RuntimeError('Não foi possível converter o ícone.')
    images.append(bytes(buffer.data()))
offset = 6 + 16 * len(images)
directory = bytearray(struct.pack('<HHH', 0, 1, len(images)))
for size, image in zip(sizes, images):
    directory.extend(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(image), offset))
    offset += len(image)
(root / 'upload.ico').write_bytes(directory + b''.join(images))
