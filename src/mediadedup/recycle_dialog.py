"""Review and restore files from the app-managed Recycle Folder."""

from pathlib import Path
import sqlite3

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from mediadedup.move_copies import restore_copy


class RestoreCopy(QThread):
    completed = Signal(object, object, str)
    failed = Signal(str)

    def __init__(self, entry, target, history, parent):
        super().__init__(parent)
        self.entry = entry
        self.target = target
        self.history = history

    def run(self):
        try:
            restore_copy(Path(self.entry["destination"]), self.target, self.entry["digest"])
        except (OSError, ValueError) as error:
            self.failed.emit(str(error))
            return
        warning = ""
        try:
            self.history.finish_restore(self.entry, self.target)
        except (OSError, sqlite3.Error) as error:
            warning = f"Restored to {self.target}, but History could not be updated: {error}"
        self.completed.emit(self.entry, self.target, warning)


class RecycleDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.worker = None
        self.setWindowTitle("Recycle Folder")
        self.resize(900, 490)
        layout = QVBoxLayout(self)
        self.status = QLabel("Select a recycled copy to restore it.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.table = QTreeWidget()
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setHeaderLabels(["Original path", "Recycle path", "Status"])
        self.table.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 350)
        self.table.currentItemChanged.connect(self.update_buttons)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.restore = QPushButton("Restore selected…")
        self.restore.clicked.connect(self.restore_selected)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons.addWidget(self.restore)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        self.table.clear()
        try:
            entries = self.main_window.history.recycle_entries()
        except (OSError, sqlite3.Error) as error:
            self.status.setText(str(error))
            self.update_buttons()
            return
        for entry in entries:
            state = entry["status"].capitalize()
            if entry["status"] == "pending":
                state = "Needs review"
            elif entry["restored_to"]:
                state = f'Restored to {entry["restored_to"]}'
            item = QTreeWidgetItem(self.table, [entry["source"], entry["destination"], state])
            for column in range(3):
                item.setToolTip(column, item.text(column))
            item.setData(0, Qt.ItemDataRole.UserRole, dict(entry))
        if entries:
            self.table.setCurrentItem(self.table.topLevelItem(0))
        self.update_buttons()

    def selected_entry(self):
        item = self.table.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def update_buttons(self, *_):
        entry = self.selected_entry()
        self.restore.setEnabled(
            self.worker is None and entry is not None and entry["status"] in ("pending", "recycled")
        )

    def restore_selected(self):
        if not self.restore.isEnabled():
            return
        entry = self.selected_entry()
        source = Path(entry["destination"])
        target = Path(entry["source"])
        if not source.is_file():
            self.status.setText(f"Recycled file is unavailable: {source}")
            return
        if target.exists() or target.is_symlink():
            location, _ = QFileDialog.getSaveFileName(
                self, "Original path is occupied. Choose another restore path", str(target)
            )
            if not location:
                return
            target = Path(location)
        if target.exists() or target.is_symlink():
            self.status.setText(f"Choose an unused restore path: {target}")
            return
        choice = QMessageBox.question(
            self, "Restore recycled copy?",
            f"Restore the verified file to:\n{target}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        if not self.main_window.lock_operation():
            self.status.setText(self.main_window.summary.text())
            return
        self.main_window.video_preview.clear()
        self.worker = RestoreCopy(entry, target, self.main_window.history, self)
        self.main_window.worker = self.worker
        self.main_window.set_busy(True)
        self.worker.completed.connect(self.restore_completed)
        self.worker.failed.connect(self.restore_failed)
        self.worker.finished.connect(self.main_window.work_finished)
        self.worker.finished.connect(self.work_finished)
        self.status.setText("Verifying the recycled file and restoring it…")
        self.update_buttons()
        self.worker.start()

    def restore_completed(self, entry, target, warning):
        self.main_window.file_restored(entry, target)
        self.status.setText(warning or f"Restored to {target}")

    def restore_failed(self, error):
        self.status.setText(f"Restore failed: {error}")

    def work_finished(self):
        self.worker = None
        self.refresh()

    def reject(self):
        if self.worker is None:
            super().reject()
