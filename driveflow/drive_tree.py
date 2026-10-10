from PySide6.QtCore import Qt, Signal, QFileInfo
from PySide6.QtGui import QColor, QPalette, QBrush
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QFileIconProvider, QHeaderView, QStyledItemDelegate

from .widgets import size_text

FOLDER = 'application/vnd.google-apps.folder'
DESTINATION_ROLE = Qt.ItemDataRole.UserRole + 1


class DestinationDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if index.data(DESTINATION_ROLE):
            green = QColor('#1DB954')
            option.palette.setColor(QPalette.ColorRole.Text, green)
            option.palette.setColor(QPalette.ColorRole.HighlightedText, green)
            option.font.setBold(True)


class DriveTree(QTreeWidget):
    folderSelected = Signal(object)

    def __init__(self, task, with_drive):
        super().__init__()
        self.task, self.with_drive = task, with_drive
        self.icons = QFileIconProvider()
        self.generation = 0
        self.destination_id = None
        self.setItemDelegate(DestinationDelegate(self))
        self.nodes = {}
        self.loaded, self.loading = set(), set()
        self.reload_pending = set()
        self.setHeaderLabels(['NOME', 'TAMANHO'])
        self.setIndentation(20)
        self.setAlternatingRowColors(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.itemExpanded.connect(self.load)
        self.currentItemChanged.connect(lambda *_: self.folderSelected.emit(self.path()))

    def reset_tree(self):
        self.generation += 1
        self.clear()
        self.nodes.clear()
        self.loaded.clear()
        self.loading.clear()
        self.reload_pending.clear()
        root = QTreeWidgetItem(['Meu Drive', ''])
        root.setData(0, Qt.ItemDataRole.UserRole, {'id': 'root', 'name': 'Meu Drive', 'mimeType': FOLDER})
        root.setIcon(0, self.icons.icon(QFileIconProvider.IconType.Folder))
        root.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        self.addTopLevelItem(root)
        self.nodes['root'] = root
        self.mark_destination()
        self.setCurrentItem(root)
        root.setExpanded(True)

    def set_destination(self, ident):
        self.destination_id = ident
        self.mark_destination()

    def mark_destination(self):
        for ident, node in self.nodes.items():
            active = ident == self.destination_id
            node.setData(0, DESTINATION_ROLE, active)
            node.setForeground(0, QBrush(QColor('#1DB954')) if active else QBrush())
            font = node.font(0)
            font.setBold(active)
            node.setFont(0, font)

    def folder(self):
        node = self.currentItem()
        if node and node.data(0, Qt.ItemDataRole.UserRole)['mimeType'] != FOLDER:
            node = node.parent()
        return node

    def path(self):
        node, parts = self.folder(), []
        while node:
            row = node.data(0, Qt.ItemDataRole.UserRole)
            parts.append((row['id'], row['name']))
            node = node.parent()
        return list(reversed(parts)) or [('root', 'Meu Drive')]

    def refresh_folder(self, ident=None):
        node = self.nodes.get(ident) if ident else self.folder()
        if node:
            self.load(node, force=True)

    def refresh_watched(self):
        """Poll only the open folder and selected destination; never pile up requests."""
        current = self.folder()
        ids = {self.destination_id}
        if current:
            ids.add(current.data(0, Qt.ItemDataRole.UserRole)['id'])
        for ident in ids:
            node = self.nodes.get(ident)
            if node is not None and ident not in self.loading:
                self.load(node, force=True, silent=True)

    def load(self, node, force=False, silent=False):
        row = node.data(0, Qt.ItemDataRole.UserRole)
        if not row or row['mimeType'] != FOLDER:
            return
        ident, generation = row['id'], self.generation
        if ident in self.loading:
            if force:
                self.reload_pending.add(ident)
            return
        if ident in self.loaded and not force:
            return
        self.loading.add(ident)
        node.setToolTip(0, 'Carregando…')

        def failed(_):
            if generation != self.generation or self.nodes.get(ident) is not node:
                return
            self.loading.discard(ident)
            node.setToolTip(0, 'Falha ao carregar. Clique em Atualizar.')
            # Completion/manual refresh may have arrived during this failed request.
            # Consume it on errors too, rather than leaving the last upload stale.
            # Clear before retrying: another failure must not create a retry loop.
            if ident in self.reload_pending:
                self.reload_pending.discard(ident)
                self.load(node, force=True)

        def loaded(rows):
            if generation != self.generation or self.nodes.get(ident) is not node:
                return
            self.loading.discard(ident)
            self.loaded.add(ident)
            node.setToolTip(0, '')
            # Reconcile by ID to preserve expanded descendants and selection.
            existing = {node.child(i).data(0, Qt.ItemDataRole.UserRole)['id']: node.child(i) for i in range(node.childCount())}
            incoming = {item['id'] for item in rows}
            def forget(child):
                for i in range(child.childCount()):
                    forget(child.child(i))
                key = child.data(0, Qt.ItemDataRole.UserRole)['id']
                self.nodes.pop(key, None)
                self.loaded.discard(key)
            for key, child in existing.items():
                if key not in incoming:
                    forget(child)
                    node.takeChild(node.indexOfChild(child))
            for position, item in enumerate(rows):
                child = existing.get(item['id'])
                if child is None:
                    child = QTreeWidgetItem()
                    node.insertChild(position, child)
                child.setData(0, Qt.ItemDataRole.UserRole, item)
                child.setText(0, item['name'])
                is_folder = item['mimeType'] == FOLDER
                child.setText(1, '' if is_folder else size_text(item['size']) if 'size' in item else 'Google Docs')
                child.setIcon(0, self.icons.icon(QFileIconProvider.IconType.Folder) if is_folder else self.icons.icon(QFileInfo(item['name'])))
                child.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator if is_folder else QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
                self.nodes[item['id']] = child
            self.mark_destination()
            self.folderSelected.emit(self.path())
            if ident in self.reload_pending:
                self.reload_pending.discard(ident)
                self.load(node, force=True)

        self.task(lambda: self.with_drive(lambda drive: drive.children(ident)), loaded, on_error=failed, **({"silent": True} if silent else {}))
