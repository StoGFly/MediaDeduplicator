"""Compare exact media coverage between two folder trees."""

from pathlib import Path
import sqlite3
from time import monotonic

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QProgressBar, QPushButton, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout,
)

from mediadedup.cli.app import iter_files
from mediadedup.core.hashing import file_fingerprint, sha256_file
from mediadedup.media_formats import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from mediadedup.scan_job import ScanStopped
from mediadedup.scan_status import format_bytes


SCOPES = (
    ("Photos and videos", "both"),
    ("Photos only", "photos"),
    ("Videos only", "videos"),
)


class CompareFolders(QThread):
    progress = Signal(str, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, folders, scope, history, parent):
        super().__init__(parent)
        self.folders = folders
        self.scope = scope
        self.history = history
        self.last_update = 0.0

    def check_stop(self):
        if self.isInterruptionRequested():
            raise ScanStopped

    def inventory(self, folder, extensions):
        def unreadable(error):
            raise error

        files = {}
        self.progress.emit(f"Finding media in {folder}", -1)
        for path in iter_files(folder, on_error=unreadable):
            self.check_stop()
            if path.suffix.lower() in extensions:
                files[path] = file_fingerprint(path)
        return files

    def run(self):
        try:
            self.completed.emit(self.compare())
        except ScanStopped:
            self.progress.emit("Comparison stopped.", 0)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.failed.emit(str(error))

    def compare(self):
        first, second = self.folders
        if first.samefile(second) or first.is_relative_to(second) or second.is_relative_to(first):
            raise ValueError("Choose two separate folder trees. Each file should belong to only one side.")
        extensions = {
            "both": IMAGE_EXTENSIONS | VIDEO_EXTENSIONS,
            "photos": IMAGE_EXTENSIONS,
            "videos": VIDEO_EXTENSIONS,
        }[self.scope]
        inventories = [self.inventory(folder, extensions) for folder in self.folders]
        sizes_a, sizes_b = ({signature[2] for signature in files.values()} for files in inventories)
        shared_sizes = sizes_a & sizes_b
        total = sum(
            signature[2] for files in inventories for signature in files.values()
            if signature[2] in shared_sizes
        )
        checked = 0
        self.progress.emit(f"Checking {format_bytes(total)} with SHA-256", 0)

        def on_chunk(size):
            nonlocal checked
            checked += size
            self.check_stop()
            now = monotonic()
            if now - self.last_update >= 0.15:
                self.last_update = now
                self.progress.emit(
                    f"Checked {format_bytes(checked)} / {format_bytes(total)}",
                    int(checked * 100 / total) if total else 0,
                )

        digests = []
        for files in inventories:
            hashes = {}
            for path, signature in files.items():
                self.check_stop()
                size = signature[2]
                if size in shared_sizes:
                    digest = sha256_file(path, on_chunk=on_chunk)
                    if file_fingerprint(path) != signature:
                        raise OSError(f"File changed during comparison: {path}")
                    hashes[path] = (size, digest)
            digests.append(hashes)

        results = []
        for index, (folder, files) in enumerate(zip(self.folders, inventories)):
            other = set(digests[1 - index].values())
            unmatched = []
            matched_bytes = 0
            for path, signature in sorted(files.items()):
                self.check_stop()
                if digests[index].get(path) in other:
                    matched_bytes += signature[2]
                else:
                    unmatched.append((str(path.relative_to(folder)), signature[2]))
            results.append({
                "folder": str(folder), "files": len(files),
                "matched": len(files) - len(unmatched), "matched_bytes": matched_bytes,
                "unmatched": unmatched,
            })

        self.check_stop()
        self.history.save_overlap(first, second, self.scope, results)
        return results


class FolderOverlapDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.main_window = window
        self.setWindowTitle("Folder overlap")
        self.resize(940, 620)
        self.worker = None
        self.start_folder = window.scan_folder or Path(window.folder.currentText().strip() or ".")
        self.saved = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.folders = []
        self.browse = []
        for label in ("Folder A", "Folder B"):
            field = QLineEdit()
            button = QPushButton("Browse…")
            button.clicked.connect(lambda checked=False, target=field: self.choose_folder(target))
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(button)
            form.addRow(label, row)
            self.folders.append(field)
            self.browse.append(button)
        self.scope = QComboBox()
        for label, scope in SCOPES:
            self.scope.addItem(label, scope)
        self.scope.setCurrentIndex(self.scope.findData(window.scope.currentData()))
        form.addRow("Include", self.scope)
        self.recent = QComboBox()
        self.recent.currentIndexChanged.connect(self.show_saved)
        form.addRow("Saved comparisons", self.recent)
        layout.addLayout(form)

        self.status = QLabel("Choose two folders to compare their exact matches.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        self.tabs = QTabWidget()
        self.tables = []
        for title, headers in (
            ("Summary", ["Folder", "Files", "Matched in other folder", "Matched size", "Only here", "Only here size"]),
            ("Only in A", ["Relative path", "Size"]),
            ("Only in B", ["Relative path", "Size"]),
        ):
            tree = QTreeWidget()
            tree.setRootIsDecorated(False)
            tree.setAlternatingRowColors(True)
            tree.setUniformRowHeights(True)
            tree.setHeaderLabels(headers)
            tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for index in range(1, len(headers)):
                tree.header().setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
            self.tables.append(tree)
            self.tabs.addTab(tree, title)
        layout.addWidget(self.tabs, 1)
        actions = QHBoxLayout()
        self.compare = QPushButton("Compare folders")
        self.compare.clicked.connect(self.start)
        self.stop = QPushButton("Stop")
        self.stop.clicked.connect(self.request_stop)
        self.stop.setEnabled(False)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        actions.addWidget(self.compare)
        actions.addWidget(self.stop)
        actions.addStretch()
        actions.addWidget(close)
        layout.addLayout(actions)
        self.refresh_recent()

    def choose_folder(self, field):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose comparison folder", field.text() or str(self.start_folder)
        )
        if folder:
            field.setText(folder)

    def refresh_recent(self):
        try:
            self.saved = self.main_window.history.recent_overlaps()
        except (OSError, sqlite3.Error) as error:
            self.status.setText(f"Could not load saved comparisons: {error}")
            return
        self.recent.clear()
        self.recent.addItem("Choose a saved comparison")
        for item in self.saved:
            date = item["created_at"][:16].replace("T", " ")
            self.recent.addItem(f'{date} · {item["folder_a"]} ↔ {item["folder_b"]}', item["id"])

    def show_saved(self, index):
        if index < 1:
            return
        try:
            results = self.main_window.history.load_overlap(self.recent.currentData())
        except (OSError, ValueError, sqlite3.Error) as error:
            self.status.setText(str(error))
            return
        entry = self.saved[index - 1]
        for field, key in zip(self.folders, ("folder_a", "folder_b")):
            field.setText(entry[key])
        self.scope.setCurrentIndex(self.scope.findData(entry["scope"]))
        self.show_results(results)
        self.status.setText("Saved comparison. Run Compare folders to check current files.")

    def start(self):
        if self.worker is not None or self.main_window.worker is not None:
            return
        if any(not field.text().strip() for field in self.folders):
            self.status.setText("Choose two folders first.")
            return
        try:
            folders = tuple(Path(field.text().strip()).expanduser().resolve(strict=True) for field in self.folders)
            if not all(folder.is_dir() for folder in folders):
                raise ValueError("Choose two folders.")
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
            return
        if not self.main_window.lock_operation():
            self.status.setText(self.main_window.summary.text())
            return
        for table in self.tables:
            table.clear()
        self.recent.setCurrentIndex(0)
        self.worker = CompareFolders(folders, self.scope.currentData(), self.main_window.history, self)
        self.main_window.worker = self.worker
        self.main_window.set_busy(True)
        self.worker.progress.connect(self.show_progress)
        self.worker.failed.connect(lambda message: self.status.setText(f"Comparison failed: {message}"))
        self.worker.completed.connect(self.show_results)
        self.worker.finished.connect(self.main_window.work_finished)
        self.worker.finished.connect(self.finished_work)
        self.set_running(True)
        self.show_progress("Starting comparison…", -1)
        self.worker.start()

    def set_running(self, running):
        for control in (*self.folders, *self.browse, self.scope, self.recent, self.compare):
            control.setEnabled(not running)
        self.stop.setEnabled(running)
        self.progress.setVisible(running)

    def show_progress(self, message, percent):
        self.status.setText(message)
        self.progress.setRange(0, 0 if percent < 0 else 100)
        if percent >= 0:
            self.progress.setValue(percent)

    def request_stop(self):
        if self.worker is not None:
            self.stop.setEnabled(False)
            self.status.setText("Stopping comparison…")
            self.worker.requestInterruption()

    def reject(self):
        if self.worker is not None:
            self.request_stop()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.worker is not None:
            self.request_stop()
            event.ignore()
        else:
            super().closeEvent(event)

    def finished_work(self):
        self.worker = None
        self.set_running(False)
        self.refresh_recent()

    def show_results(self, results):
        for table in self.tables:
            table.clear()
        for index, result in enumerate(results):
            files = result["files"]
            matched = result["matched"]
            only_here = result["unmatched"]
            match_text = f"{matched:,} ({matched / files:.1%})" if files else "0"
            item = QTreeWidgetItem(self.tables[0], [
                result["folder"], f"{files:,}", match_text,
                format_bytes(result["matched_bytes"]), f"{len(only_here):,}",
                format_bytes(sum(size for _, size in only_here)),
            ])
            item.setToolTip(0, result["folder"])
            for path, size in only_here:
                item = QTreeWidgetItem(self.tables[index + 1], [path, format_bytes(size)])
                item.setToolTip(0, path)
        self.tabs.setCurrentIndex(0)
        self.status.setText("Comparison complete. The Only in A and Only in B tabs list files with no exact match.")
