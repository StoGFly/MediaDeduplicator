"""Media types available for exact scans and photo similarity."""

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout


LEGACY_IMAGES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
LEGACY_VIDEOS = {
    ".3gp", ".avi", ".m2ts", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg",
    ".mpg", ".mts", ".ts", ".webm", ".wmv",
}
EXTRA_IMAGES = {".avif", ".jfif", ".jpe", ".jp2", ".apng"}
SIMILARITY_IMAGES = LEGACY_IMAGES | (EXTRA_IMAGES & Image.registered_extensions().keys())
IMAGE_EXTENSIONS = LEGACY_IMAGES | EXTRA_IMAGES | {
    ".heic", ".heif", ".dng", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".rw2",
}
VIDEO_EXTENSIONS = LEGACY_VIDEOS | {
    ".3g2", ".asf", ".flv", ".m2t", ".mxf", ".ogv", ".vob", ".dv", ".mod", ".tod",
}


def extension_groups(scope, similarity, *, legacy=False):
    if similarity:
        return [("Images", LEGACY_IMAGES if legacy else SIMILARITY_IMAGES)]
    images = LEGACY_IMAGES if legacy else IMAGE_EXTENSIONS
    videos = LEGACY_VIDEOS if legacy else VIDEO_EXTENSIONS
    groups = []
    if scope != "videos":
        groups.append(("Images", images))
    if scope != "photos":
        groups.append(("Videos", videos))
    return groups


def scan_extensions(scope, similarity, *, legacy=False):
    return set().union(*(values for _, values in extension_groups(scope, similarity, legacy=legacy)))


class ExtensionDialog(QDialog):
    def __init__(self, groups, selected, parent):
        super().__init__(parent)
        self.setWindowTitle("File extensions")
        self.resize(420, 510)
        layout = QVBoxLayout(self)
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setAlternatingRowColors(True)
        self.items = {}
        for label, extensions in groups:
            group = QTreeWidgetItem(tree, [label])
            group.setFlags(group.flags() | Qt.ItemFlag.ItemIsAutoTristate)
            group.setCheckState(0, Qt.CheckState.Unchecked)
            for extension in sorted(extensions):
                item = QTreeWidgetItem(group, [extension])
                item.setCheckState(
                    0, Qt.CheckState.Checked if extension in selected else Qt.CheckState.Unchecked
                )
                self.items[extension] = item
            group.setExpanded(True)
        layout.addWidget(tree, 1)
        actions = QHBoxLayout()
        for label, checked in (("Select all", True), ("Select none", False), ("Reset defaults", True)):
            button = QPushButton(label)
            button.clicked.connect(lambda clicked=False, state=checked: self.set_all(state))
            actions.addWidget(button)
        layout.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_all(self, selected):
        for item in self.items.values():
            item.setCheckState(0, Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)

    def selected_extensions(self):
        return {extension for extension, item in self.items.items() if item.checkState(0) == Qt.CheckState.Checked}
