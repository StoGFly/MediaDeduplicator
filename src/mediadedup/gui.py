"""Read-only desktop review for exact and visually similar images."""

import json
import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QLockFile, QSettings, QSignalBlocker, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QActionGroup, QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton,
    QPlainTextEdit, QProgressBar, QSpinBox, QSplitter, QStyle, QToolBar, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from mediadedup.filename_keepers import (
    CountFilenamePatterns, DATE_COMPACT, DATE_DOTS, OTHER, filename_keeper, winning_style,
)
from mediadedup.folder_overlap import FolderOverlapDialog, SCOPES
from mediadedup.media_formats import ExtensionDialog, VIDEO_EXTENSIONS, extension_groups, scan_extensions
from mediadedup.move_copies import move_copy, plan_move_targets
from mediadedup.move_status import MoveStatus
from mediadedup.recycle_dialog import RecycleDialog
from mediadedup.scan_history import ScanHistory
from mediadedup.scan_job import Scan
from mediadedup.scan_status import ScanStatus, format_bytes
from mediadedup.video_preview import VideoPreview


FILE_ROLE = Qt.ItemDataRole.UserRole
SIZE_ROLE = FILE_ROLE + 1
KEEPER_ROLE = FILE_ROLE + 2
KEEP_REASON_ROLE = FILE_ROLE + 3
REVIEW_ROLE = FILE_ROLE + 4


class MoveCopies(QThread):
    completed = Signal(object, object)
    progress = Signal(str, str, int, int, object, object, int)
    file_moved = Signal(str, str)

    def __init__(self, jobs, sizes, history, scan_id, destination, parent, *, recycle=False):
        super().__init__(parent)
        self.jobs = jobs
        self.sizes = sizes
        self.history = history
        self.scan_id = scan_id
        self.destination = destination
        self.recycle = recycle

    def run(self):
        keepers = {keeper for keeper, _, _ in self.jobs}
        if any(source in keepers for _, source, _ in self.jobs):
            self.progress.emit("Stopped", "", len(self.jobs), 0, 0, sum(self.sizes.values()), 1)
            self.completed.emit({}, ["The move queue contains a keeper. Review the queue and try again."])
            return
        moved = {}
        errors = []
        bytes_moved = 0
        failed_bytes = 0

        def report(phase, source, processed):
            self.progress.emit(
                phase, str(source), processed, len(moved), bytes_moved, failed_bytes, len(errors)
            )

        for index, (keeper, source, target) in enumerate(self.jobs):
            report("Verifying", source, index)
            recycle_id = None
            size = self.sizes[source]
            try:
                if source.stat().st_size != size:
                    raise ValueError("The source size changed since the scan. Scan it again before moving.")

                def show_moving(digest):
                    nonlocal recycle_id
                    if self.recycle:
                        recycle_id = self.history.begin_recycle(self.scan_id, source, target, digest)
                    report("Moving to Recycle Folder" if self.recycle else "Moving", source, index)

                move_copy(keeper, source, target, on_moving=show_moving)
            except (OSError, ValueError, sqlite3.Error) as error:
                failed_bytes += size
                errors.append(f"{source}\nDestination: {target}\n{error}")
            else:
                moved[str(source)] = str(target)
                bytes_moved += size
                self.file_moved.emit(str(source), str(target))
                try:
                    if self.recycle:
                        self.history.complete_recycle(recycle_id)
                    else:
                        self.history.record_move(self.scan_id, source, target)
                except (OSError, sqlite3.Error) as error:
                    errors.append(f"{source}\nMoved to {target}. History could not be updated: {error}")
            report("Recycling copies" if self.recycle else "Moving copies", source, index + 1)
        if moved and not self.recycle:
            try:
                self.history.record_destination(self.destination)
            except (OSError, sqlite3.Error) as error:
                errors.append(f"Could not save the recent destination: {error}")
        self.completed.emit(moved, errors)


class MainWindow(QMainWindow):
    def __init__(self, history=None):
        super().__init__()
        self.setWindowTitle("MediaDeduplicator")
        self.worker = None
        self.scan_folder = None
        self.scan_similarity = False
        self.history = history if history is not None else ScanHistory()
        self.scan_id = None
        self.moved_files = {}
        self.move_items = {}
        self.queued = set()
        self.preferred_keeper_folder = None
        self.keeper_report = ""
        self.extension_choices = {}
        self.settings = QSettings("MediaDeduplicator", "MediaDeduplicator")
        self.hash_workers = self.settings.value("exactHashWorkers", 4, type=int)
        if self.hash_workers not in (1, 2, 4, 8):
            self.hash_workers = 4
        self.operation_lock = QLockFile(str(self.history.path) + ".operation.lock")
        self.operation_lock.setStaleLockTime(0)
        self.scan_status = ScanStatus(self)
        self.move_status = MoveStatus(self)
        self.compact_progress = QLabel()
        self.compact_progress.setTextFormat(Qt.TextFormat.PlainText)
        self.statusBar().addWidget(self.compact_progress, 1)
        self.statusBar().hide()
        self.scan_status.compact_changed.connect(self.update_compact_status)
        self.move_status.compact_changed.connect(self.update_compact_status)
        self.scan_status.stop_requested.connect(self.stop_scan)
        self.scan_status.resume_requested.connect(self.resume_scan)
        self.scan_status.fresh_requested.connect(self.restart_scan)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self.folder = QComboBox()
        self.folder.setEditable(True)
        self.folder.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.folder.setAccessibleName("Media folder path")
        self.folder.lineEdit().setPlaceholderText("Media folder path")
        self.folder.activated.connect(self.update_related_scans)
        layout.addWidget(self.folder)
        self.related = QPushButton()
        self.related.clicked.connect(lambda: self.show_history(related_only=True))
        self.related.hide()
        layout.addWidget(self.related)
        self.folder.lineEdit().editingFinished.connect(self.update_related_scans)

        self.mode = QComboBox()
        self.mode.addItems(["Basic · Exact duplicates", "Advanced · Similar photos"])
        form = QFormLayout()
        form.addRow("&Mode", self.mode)
        self.scope = QComboBox()
        for label, scope in SCOPES:
            self.scope.addItem(label, scope)
        form.addRow("&Include", self.scope)
        self.mode.currentIndexChanged.connect(lambda index: form.setRowVisible(self.scope, index == 0))
        self.extension_summary = QLabel()
        self.extension_summary.setWordWrap(True)
        form.addRow("File extensions", self.extension_summary)
        self.mode.currentIndexChanged.connect(self.update_extension_summary)
        self.scope.currentIndexChanged.connect(self.update_extension_summary)
        layout.addLayout(form)

        self.options = QGroupBox("Experimental pHash settings")
        settings = QFormLayout(self.options)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0, 100)
        self.threshold.setDecimals(1)
        self.threshold.setSuffix("%")
        self.threshold.setValue(85)
        self.hash_size = QSpinBox()
        self.hash_size.setRange(8, 16)
        self.hash_size.setValue(8)
        settings.addRow("Minimum hash &agreement", self.threshold)
        settings.addRow("&Hash width", self.hash_size)
        hint = QLabel(
            "Lower thresholds show more candidates. Larger hashes change the scoring and use more "
            "work per comparison. Similarity searches compare every pair and may miss crops. "
            "Review the photos before drawing conclusions."
        )
        hint.setWordWrap(True)
        settings.addRow(hint)
        layout.addWidget(self.options)
        self.options.hide()
        self.mode.currentIndexChanged.connect(lambda index: self.options.setVisible(index == 1))

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setAccessibleName("Scanning")
        self.progress.hide()
        layout.addWidget(self.progress)
        self.summary = QLabel("Ready to scan.")
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter results by filename or path")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.filter_results)
        layout.addWidget(self.filter)
        queue_row = QHBoxLayout()
        self.queue_summary = QLabel()
        self.queue_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.queued_only = QCheckBox("Show queued only")
        self.queued_only.toggled.connect(lambda: self.filter_results(self.filter.text()))
        queue_row.addWidget(self.queue_summary, 1)
        queue_row.addWidget(self.queued_only)
        layout.addLayout(queue_row)
        self.queue_refresh = QTimer(self)
        self.queue_refresh.setSingleShot(True)
        self.queue_refresh.timeout.connect(self.refresh_queue_view)

        splitter = QSplitter()
        self.review_splitter = splitter
        self.results = QTreeWidget()
        self.results.setAlternatingRowColors(True)
        self.results.setUniformRowHeights(True)
        self.results.setHeaderLabels(["Match / file", "Size", "Review"])
        self.results.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results.currentItemChanged.connect(self.show_preview)
        splitter.addWidget(self.results)

        preview_panel = QGroupBox("Media preview")
        preview_layout = QVBoxLayout(preview_panel)
        self.preview = QLabel("Select a file to preview.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview, 1)
        self.video_preview = VideoPreview(preview_panel)
        self.video_preview.hide()
        preview_layout.addWidget(self.video_preview, 1)
        self.preview_path = QLabel()
        self.preview_path.setTextFormat(Qt.TextFormat.PlainText)
        self.preview_path.setWordWrap(True)
        self.preview_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        preview_layout.addWidget(self.preview_path)
        splitter.addWidget(preview_panel)
        splitter.setSizes([610, 350])
        layout.addWidget(splitter, 1)
        self.create_toolbar()
        self.results.itemSelectionChanged.connect(self.update_review_actions)
        self.results.itemChanged.connect(self.move_check_changed)
        self.results.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self.show_queue_menu)
        self.update_review_actions()
        self.refresh_scan_folders()
        self.update_related_scans()
        self.update_extension_summary()
        self.restore_layout()

    def restore_layout(self):
        geometry = self.settings.value("mainWindow/geometry", QByteArray(), type=QByteArray)
        if not geometry or not self.restoreGeometry(geometry):
            screen = self.screen().availableGeometry()
            width = round(screen.width() * 0.85)
            height = round(screen.height() * 0.85)
            x = screen.x() + (screen.width() - width) // 2
            y = screen.y() + (screen.height() - height) // 2
            self.setGeometry(x, y, width, height)
        splitter = self.settings.value("mainWindow/previewSplit", QByteArray(), type=QByteArray)
        if splitter:
            self.review_splitter.restoreState(splitter)

    def create_toolbar(self):
        toolbar = QToolBar("Photo tools", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        icon = self.style().standardIcon
        standard = QStyle.StandardPixmap
        self.start = toolbar.addAction(icon(standard.SP_MediaPlay), "Scan", self.start_scan)
        self.start.setShortcut("F5")
        toolbar.addAction("Scan Status", self.show_scan_status)
        toolbar.addAction("Move Status", self.show_move_status)

        def menu(name):
            button = QToolButton(toolbar)
            button.setText(name)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            dropdown = QMenu(button)
            button.setMenu(dropdown)
            toolbar.addWidget(button)
            return dropdown

        scan_menu = menu("Scan options")
        self.browse = scan_menu.addAction("Open folder…", self.choose_folder)
        self.browse.setShortcut("Ctrl+O")
        self.addAction(self.browse)
        self.basic_action = scan_menu.addAction("Basic · Exact duplicates", lambda: self.mode.setCurrentIndex(0))
        self.advanced_action = scan_menu.addAction("Advanced · Similar photos", lambda: self.mode.setCurrentIndex(1))

        self.file_types = scan_menu.addAction("File extensions…", self.choose_extensions)
        self.hash_menu = scan_menu.addMenu("Hash workers")
        workers = QActionGroup(self.hash_menu)
        workers.setExclusive(True)
        for count in (1, 2, 4, 8):
            label = "1 · Sequential" if count == 1 else f"{count} files in parallel"
            action = self.hash_menu.addAction(label)
            action.setCheckable(True)
            workers.addAction(action)
            action.setChecked(count == self.hash_workers)
            action.triggered.connect(lambda checked=False, count=count: self.set_hash_workers(count))

        review = menu("Review")
        self.overlap = review.addAction("Folder overlap…", self.show_folder_overlap)
        review.addAction("Expand all", self.results.expandAll)
        review.addAction("Collapse all", self.results.collapseAll)
        self.reveal = review.addAction("Open location", self.reveal_file)
        self.copy = review.addAction("Copy path", self.copy_path)

        move = menu("Move")
        self.plan = move.addAction("Keep by folder…", self.choose_keeper_folder)
        self.keep = move.addAction("Keep this file", self.keep_selected_file)
        self.filename_plan = move.addAction("Keep by filename pattern…", self.choose_filename_folder)
        self.move = move.addAction("Move exact copies…", self.choose_move_destination)
        self.recycle = move.addAction("Recycle checked copies…", self.choose_recycle_destination)
        self.recent_menu = move.addMenu("Recent destinations")
        self.recent_menu.aboutToShow.connect(self.populate_recent_destinations)

        history = menu("History")
        self.open_recycle = history.addAction("Recycle Folder…", self.show_recycle_folder)
        self.open_history = history.addAction("All scans…", self.show_history)
        self.open_history.setShortcut("Ctrl+H")
        self.addAction(self.open_history)
        self.related_history = history.addAction(
            "Related scans…", lambda: self.show_history(related_only=True)
        )

    def set_hash_workers(self, count):
        self.hash_workers = count
        self.settings.setValue("exactHashWorkers", count)

    def show_folder_overlap(self):
        if self.worker is None:
            dialog = FolderOverlapDialog(self)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.exec()

    def show_scan_status(self):
        self.scan_status.show()
        self.scan_status.raise_()
        self.scan_status.activateWindow()

    def show_move_status(self):
        self.move_status.show()
        self.move_status.raise_()
        self.move_status.activateWindow()

    def update_compact_status(self):
        message = ""
        for status in (self.scan_status, self.move_status):
            if status.running and not status.isVisible():
                message = status.compact
                break
        self.compact_progress.setText(message)
        self.statusBar().setVisible(bool(message))

    def refresh_scan_folders(self):
        try:
            folders = self.history.recent_scan_folders()
        except (OSError, sqlite3.Error):
            return
        selected = self.folder.currentText()
        with QSignalBlocker(self.folder):
            self.folder.clear()
            self.folder.addItems(folders)
            self.folder.setCurrentIndex(-1)
            self.folder.setEditText(selected)

    def extension_key(self):
        similarity = self.mode.currentIndex() == 1
        return ("photos" if similarity else self.scope.currentData(), similarity)

    def selected_extensions(self):
        key = self.extension_key()
        return self.extension_choices.get(key, scan_extensions(*key))

    def update_extension_summary(self):
        selected = self.selected_extensions()
        all_supported = scan_extensions(*self.extension_key())
        if selected == all_supported:
            label = f"All supported ({len(selected)})"
        elif not selected:
            label = "None selected"
        elif len(selected) <= 6:
            label = ", ".join(sorted(selected))
        else:
            label = f"{len(selected)} selected"
        self.extension_summary.setText(label)
        self.extension_summary.setToolTip(", ".join(sorted(selected)))

    def choose_extensions(self):
        key = self.extension_key()
        dialog = ExtensionDialog(extension_groups(*key), self.selected_extensions(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.extension_choices[key] = dialog.selected_extensions()
            self.update_extension_summary()

    def related_scans(self, scans):
        raw_path = self.folder.currentText().strip()
        if not raw_path:
            return []
        folder = Path(raw_path).expanduser().resolve()
        return [
            scan for scan in scans
            if Path(scan["folder"]).is_relative_to(folder)
            or folder.is_relative_to(Path(scan["folder"]))
        ]

    def update_related_scans(self):
        try:
            scans = self.related_scans(self.history.list_scans()) if self.folder.currentText().strip() else []
        except (OSError, ValueError, sqlite3.Error):
            scans = []
        self.related.setText(f"View {len(scans):,} related scans in History")
        self.related.setVisible(bool(scans))
        self.related_history.setEnabled(bool(scans) and self.worker is None)

    def populate_recent_destinations(self):
        self.recent_menu.clear()
        try:
            recent = self.history.recent_destinations()
        except (OSError, sqlite3.Error):
            self.recent_menu.addAction("Could not load recent destinations").setEnabled(False)
            return
        if not recent:
            self.recent_menu.addAction("No recent destinations").setEnabled(False)
        for folder in recent:
            label = folder.replace("&", "&&")
            action = self.recent_menu.addAction(
                label, lambda checked=False, path=folder: self.plan_move_to(Path(path))
            )
            action.setEnabled(self.move.isEnabled())

    def lock_operation(self):
        try:
            self.history.path.parent.mkdir(parents=True, exist_ok=True)
            if self.operation_lock.tryLock(0):
                return True
            if self.operation_lock.error() == QLockFile.LockError.LockFailedError:
                self.summary.setText("Another scan or move is already running.")
            else:
                self.summary.setText("Could not acquire the scan lock in the app data folder.")
        except OSError as error:
            self.summary.setText(str(error))
        return False

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose media folder", self.folder.currentText())
        if folder:
            self.folder.setEditText(folder)
            self.update_related_scans()

    def start_scan(self):
        self.launch_scan()

    def launch_scan(self, resume_id=None):
        if self.worker is not None:
            return
        extensions = self.selected_extensions()
        if not extensions:
            self.summary.setText("Select at least one file extension under Scan options.")
            return
        raw_path = self.folder.currentText().strip()
        folder = Path(raw_path).expanduser()
        if not raw_path or not folder.is_dir():
            self.summary.setText("Choose an existing folder.")
            return

        try:
            resolved = folder.resolve()
        except OSError as error:
            self.summary.setText(str(error))
            return
        if not self.lock_operation():
            return
        self.scan_folder = resolved
        self.scan_similarity = self.mode.currentIndex() == 1
        self.scan_id = None
        self.keeper_report = ""
        self.preferred_keeper_folder = None
        self.moved_files.clear()
        self.move_items.clear()
        self.queued.clear()
        self.results.clear()
        self.filter.clear()
        self.queued_only.setChecked(False)
        self.show_preview(None)
        self.summary.setText("Scanning files…")

        self.worker = Scan(
            self.scan_folder, self.scan_similarity, self.threshold.value(),
            self.hash_size.value(), self.history, self, resume_id=resume_id,
            scope=self.scope.currentData(), extensions=extensions, hash_workers=self.hash_workers,
        )
        self.worker.completed.connect(self.scan_completed)
        self.worker.failed.connect(self.show_error)
        self.worker.stopped.connect(self.scan_stopped)
        self.worker.progress.connect(self.scan_status.update_progress)
        self.worker.finished.connect(self.work_finished)
        self.set_busy(True)
        self.scan_status.begin(self.scan_folder)
        self.worker.start()

    def stop_scan(self):
        if isinstance(self.worker, Scan):
            self.worker.requestInterruption()

    def scan_stopped(self, scan_id):
        self.summary.setText("Scan stopped. Resume or start fresh from Scan Status.")
        self.scan_status.finish("Scan stopped. Progress saved.", stopped_id=scan_id)

    def scan_completed(self, groups, count, scan_id):
        self.show_results(groups, count, scan_id)
        if self.scan_similarity:
            message = f"Finished · {count:,} images · {len(groups):,} similarity candidates"
        else:
            extra = sum(len(files) - 1 for _, files in groups)
            size = sum(size for _, files in groups for _, size in files[1:])
            message = (
                f"Finished · {count:,} files · {len(groups):,} exact groups\n"
                f"{extra:,} extra copies · {format_bytes(size)}"
            )
        self.scan_status.finish(message)

    def apply_settings(self, scan):
        self.folder.setEditText(scan["folder"])
        similarity = bool(scan["similarity"])
        self.mode.setCurrentIndex(int(similarity))
        self.scope.setCurrentIndex(self.scope.findData(scan["scope"]))
        key = self.extension_key()
        supported = scan_extensions(*key)
        if scan["extensions"] is None:
            selected = scan_extensions(*key, legacy=True)
        else:
            selected = set(json.loads(scan["extensions"])) & supported
        self.extension_choices[key] = selected
        self.update_extension_summary()
        if similarity:
            self.threshold.setValue(scan["threshold"])
            self.hash_size.setValue(scan["hash_size"])

    def resume_scan(self, scan_id):
        self.continue_scan(scan_id, resume=True)

    def restart_scan(self, scan_id):
        self.continue_scan(scan_id, resume=False)

    def continue_scan(self, scan_id, *, resume):
        if self.worker is not None:
            return
        try:
            scan = self.history.scan_settings(scan_id)
        except (OSError, ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Scan history", str(error))
            return
        self.apply_settings(scan)
        self.launch_scan(resume_id=scan_id if resume else None)

    def show_results(self, groups, count, scan_id):
        self.scan_id = scan_id
        self.keeper_report = ""
        self.preferred_keeper_folder = None
        self.scan_status.set_keeper_summary("")
        self.move_items.clear()
        self.queued.clear()
        self.results.clear()
        self.filter.clear()
        self.queued_only.setChecked(False)
        kind = "similarity candidates" if self.scan_similarity else "exact duplicate groups"
        unit = "photos" if self.scan_similarity else "files"
        self.summary.setText(f"Scanned {count:,} {unit} · {len(groups):,} {kind}")
        for label, files in groups:
            group = QTreeWidgetItem(self.results, [label])
            keeper = None
            for path, size in files:
                name = str(path.relative_to(self.scan_folder))
                destination = self.moved_files.get(str(path))
                item = QTreeWidgetItem(group, [name, f"{size:,} B", "Moved" if destination else ""])
                item.setData(0, FILE_ROLE, str(path))
                item.setData(0, SIZE_ROLE, size)
                if not self.scan_similarity:
                    self.move_items[str(path)] = item
                item.setToolTip(0, destination or str(path))
                if keeper is None and not destination:
                    keeper = item
            if keeper is not None and not self.scan_similarity:
                self.set_keeper(group, keeper)
        if groups:
            group = self.results.topLevelItem(0)
            group.setExpanded(True)
            self.results.setCurrentItem(group.child(0))

    def result_path(self, item):
        source = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        return self.moved_files.get(source, source)

    def show_preview(self, item, _previous=None):
        self.update_review_actions()
        path = self.result_path(item)
        self.preview_path.setText(path or "")
        self.video_preview.clear()
        self.video_preview.hide()
        self.preview.show()
        self.preview.setText("Select a file to preview.")
        if not path:
            return

        if Path(path).suffix.lower() in VIDEO_EXTENSIONS:
            if isinstance(self.worker, MoveCopies):
                self.preview.setText("Video preview paused during move.")
            else:
                self.preview.hide()
                self.video_preview.show()
                self.video_preview.set_file(path)
            return

        reader = QImageReader(path)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(QSize(300, 300), Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        if image.isNull():
            self.preview.setText("Preview unavailable.")
        else:
            self.preview.setPixmap(QPixmap.fromImage(image))

    def show_error(self, message):
        self.summary.setText(f"Scan failed: {message}")
        self.scan_status.finish(f"Scan failed: {message}")

    def set_busy(self, busy):
        self.progress.setVisible(busy)
        for control in (
            self.folder, self.browse, self.start, self.mode, self.scope, self.options, self.open_history,
            self.basic_action, self.advanced_action, self.related, self.related_history, self.overlap,
            self.file_types, self.hash_menu, self.results, self.open_recycle, self.queued_only,
        ):
            control.setEnabled(not busy)
        self.update_review_actions()

    def work_finished(self):
        moved = isinstance(self.worker, MoveCopies)
        self.queue_refresh.stop()
        self.worker.deleteLater()
        self.worker = None
        self.operation_lock.unlock()
        self.set_busy(False)
        self.refresh_scan_folders()
        self.update_related_scans()
        if moved:
            self.refresh_queue_view()
            self.show_preview(self.results.currentItem())
        self.update_compact_status()

    def filter_results(self, text):
        query = text.strip()
        query_path = Path(query)
        absolute = bool(query) and query_path.is_absolute()
        search = query.replace("/", os.sep).casefold()
        current = self.results.currentItem()
        with QSignalBlocker(self.results):
            for index in range(self.results.topLevelItemCount()):
                group = self.results.topLevelItem(index)
                group_visible = False
                for position in range(group.childCount()):
                    child = group.child(position)
                    path = self.result_path(child)
                    matches = (
                        Path(path).is_relative_to(query_path) if absolute
                        else search in path.casefold()
                    )
                    if self.queued_only.isChecked():
                        matches = matches and child.data(0, FILE_ROLE) in self.queued
                    child.setHidden(not matches)
                    group_visible |= matches
                group.setHidden(not group_visible)
                if not self.scan_similarity:
                    self.refresh_group_checks(group)
        if current is not None and current.isHidden():
            self.results.setCurrentItem(None)
        self.update_review_actions()

    def show_history(self, *, related_only=False):
        if self.worker is not None:
            return
        try:
            scans = self.history.list_scans()
            if related_only:
                scans = self.related_scans(scans)
        except (OSError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Scan history", str(error))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Related scans" if related_only else "Scan history")
        dialog.resize(860, 430)
        layout = QVBoxLayout(dialog)
        if not scans:
            layout.addWidget(QLabel("Completed and attempted scans will appear here."))
        tree = QTreeWidget()
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setHeaderLabels(["Started", "Folder", "Mode", "State", "Files", "Matches"])
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(tree)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        open_button = buttons.button(QDialogButtonBox.StandardButton.Open)
        open_button.setEnabled(False)
        for scan in scans:
            def display_count(key):
                return "" if scan[key] is None else f"{scan[key]:,}"

            item = QTreeWidgetItem(tree, [
                scan["started_at"].replace("T", " "), scan["folder"],
                "Similar" if scan["similarity"] else {
                    "both": "Exact · Photos and videos",
                    "photos": "Exact · Photos",
                    "videos": "Exact · Videos",
                }.get(scan["scope"], "Exact"),
                scan["status"].capitalize(), display_count("image_count"),
                display_count("match_count"),
            ])
            if scan["status"] in ("completed", "incomplete"):
                item.setData(0, FILE_ROLE, scan["id"])
                item.setData(0, SIZE_ROLE, scan["status"])
            if scan["error"]:
                item.setToolTip(3, scan["error"])

        def select_history(item, _previous):
            open_button.setEnabled(bool(item and item.data(0, FILE_ROLE)))
            open_button.setText("Resume" if item and item.data(0, SIZE_ROLE) == "incomplete" else "Open")

        tree.currentItemChanged.connect(select_history)
        tree.itemDoubleClicked.connect(lambda item, _: dialog.accept() if open_button.isEnabled() else None)
        if tree.topLevelItemCount():
            tree.setCurrentItem(tree.topLevelItem(0))
        if dialog.exec() != QDialog.DialogCode.Accepted or not tree.currentItem():
            return
        item = tree.currentItem()
        scan_id = item.data(0, FILE_ROLE)
        if item.data(0, SIZE_ROLE) == "incomplete":
            self.resume_scan(scan_id)
            return
        if scan_id is None:
            return
        try:
            scan, groups = self.history.load(scan_id)
            self.moved_files = self.history.moved_files(scan_id)
        except (OSError, ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Scan history", str(error))
            return

        self.scan_folder = Path(scan["folder"])
        self.scan_similarity = bool(scan["similarity"])
        self.apply_settings(scan)
        self.show_results(groups, scan["image_count"], scan_id)
        self.update_related_scans()

    def reveal_file(self):
        path = self.result_path(self.results.currentItem())
        if path and not QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent))):
            QMessageBox.warning(self, "Open location", "The containing folder could not be opened.")

    def copy_path(self):
        path = self.result_path(self.results.currentItem())
        if path:
            QApplication.clipboard().setText(path)

    def set_keeper(self, group, item, reason="Default order"):
        keeper = item.data(0, FILE_ROLE)
        with QSignalBlocker(self.results):
            group.setData(0, KEEPER_ROLE, keeper)
            group.setData(0, KEEP_REASON_ROLE, reason)
            group.setData(0, REVIEW_ROLE, None)
            group.setText(2, "")
            for index in range(group.childCount()):
                child = group.child(index)
                source = child.data(0, FILE_ROLE)
                if source not in self.moved_files:
                    child.setText(2, f"Keep · {reason}" if source == keeper else "")
            self.refresh_group_checks(group)

    def eligible_copies(self, group, *, visible_only=False):
        keeper = group.data(0, KEEPER_ROLE)
        if keeper and not group.data(0, REVIEW_ROLE):
            for index in range(group.childCount()):
                child = group.child(index)
                source = child.data(0, FILE_ROLE)
                if source == keeper or source in self.moved_files:
                    continue
                if not visible_only or not child.isHidden():
                    yield child

    def refresh_group_checks(self, group):
        role = Qt.ItemDataRole.CheckStateRole
        flag = Qt.ItemFlag.ItemIsUserCheckable
        eligible = {child.data(0, FILE_ROLE) for child in self.eligible_copies(group)}
        for index in range(group.childCount()):
            child = group.child(index)
            source = child.data(0, FILE_ROLE)
            if source in eligible:
                child.setFlags(child.flags() | flag)
                child.setCheckState(0, Qt.CheckState.Checked if source in self.queued else Qt.CheckState.Unchecked)
            else:
                self.queued.discard(source)
                child.setFlags(child.flags() & ~flag)
                child.setData(0, role, None)

        visible = {child.data(0, FILE_ROLE) for child in self.eligible_copies(group, visible_only=True)}
        count = len(visible & self.queued)
        if not visible:
            group.setFlags(group.flags() & ~flag)
            group.setData(0, role, None)
        else:
            group.setFlags(group.flags() | flag)
            state = Qt.CheckState.Unchecked
            if count:
                state = Qt.CheckState.Checked if count == len(visible) else Qt.CheckState.PartiallyChecked
            group.setCheckState(0, state)

    def move_check_changed(self, item, column):
        if column != 0 or self.worker is not None or self.scan_similarity:
            return
        if item.data(0, Qt.ItemDataRole.CheckStateRole) is None:
            return
        parent = item.parent()
        group = item if parent is None else parent
        checked = item.checkState(0) == Qt.CheckState.Checked
        with QSignalBlocker(self.results):
            children = self.eligible_copies(group, visible_only=True) if parent is None else [item]
            for child in children:
                source = child.data(0, FILE_ROLE)
                if checked:
                    self.queued.add(source)
                else:
                    self.queued.discard(source)
            self.refresh_group_checks(group)
        self.refresh_queue_view()

    def can_keep(self, item):
        return (
            self.worker is None and self.scan_id is not None and not self.scan_similarity
            and item is not None and item.parent() is not None
            and not item.isHidden() and not item.parent().isHidden()
            and item.data(0, FILE_ROLE) not in self.moved_files
        )

    def keep_file(self, item):
        if self.can_keep(item):
            self.set_keeper(item.parent(), item, "Manual choice")
            self.refresh_queue_view()

    def keep_selected_file(self):
        self.keep_file(self.results.currentItem())

    def choose_keeper_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose the folder to keep copies from", str(self.scan_folder)
        )
        if folder:
            self.plan_by_folder(Path(folder).resolve())

    def plan_by_folder(self, folder):
        self.preferred_keeper_folder = folder
        self.keeper_report = ""
        planned = 0
        skipped = 0
        with QSignalBlocker(self.results):
            self.queued.clear()
            for index in range(self.results.topLevelItemCount()):
                group = self.results.topLevelItem(index)
                self.refresh_group_checks(group)
                if group.isHidden():
                    continue
                available = [
                    group.child(i) for i in range(group.childCount())
                    if group.child(i).data(0, FILE_ROLE) not in self.moved_files
                ]
                if len(available) < 2:
                    continue
                preferred = [
                    item for item in available
                    if Path(item.data(0, FILE_ROLE)).is_relative_to(folder)
                ]
                if len(preferred) != 1:
                    skipped += 1
                    continue
                self.set_keeper(group, preferred[0], "Preferred folder")
                self.queued.update(
                    child.data(0, FILE_ROLE) for child in self.eligible_copies(group, visible_only=True)
                )
                self.refresh_group_checks(group)
                planned += 1
        self.refresh_queue_view()
        self.summary.setText(
            f"Queued {planned:,} visible groups · {skipped:,} need manual review"
        )

    def show_queue_menu(self, position):
        item = self.results.itemAt(position)
        path = self.result_path(item)
        allow_queue = self.plan.isEnabled()
        if not path and not allow_queue:
            return
        menu = QMenu(self.results)
        if path:
            folder = str(Path(path).parent)
            menu.addAction("Copy file path", lambda: QApplication.clipboard().setText(path))
            menu.addAction("Copy folder path", lambda: QApplication.clipboard().setText(folder))
            folder_filter = folder.rstrip("/\\") + os.sep
            menu.addAction("Filter by this folder", lambda: self.filter.setText(folder_filter))
            if self.can_keep(item):
                menu.addAction("Keep this file", lambda: self.keep_file(item))
        if allow_queue:
            if path:
                menu.addSeparator()
            menu.addAction("Check all visible copies", lambda: self.change_bulk_checks("check"))
            menu.addAction("Uncheck all visible copies", lambda: self.change_bulk_checks("uncheck"))
            menu.addAction("Clear move queue", lambda: self.change_bulk_checks("clear"))
        menu.exec(self.results.viewport().mapToGlobal(position))
        menu.deleteLater()

    def change_bulk_checks(self, operation):
        if not self.plan.isEnabled():
            return
        with QSignalBlocker(self.results):
            if operation == "clear":
                self.queued.clear()
            for index in range(self.results.topLevelItemCount()):
                group = self.results.topLevelItem(index)
                if group.isHidden() and operation != "clear":
                    continue
                paths = {
                    child.data(0, FILE_ROLE) for child in self.eligible_copies(group, visible_only=True)
                }
                if operation == "check":
                    self.queued.update(paths)
                elif operation == "uncheck":
                    self.queued.difference_update(paths)
                self.refresh_group_checks(group)
        self.refresh_queue_view()

    def choose_filename_folder(self):
        if not self.filename_plan.isEnabled():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Count filename patterns in folder", str(self.scan_folder)
        )
        if not folder:
            return
        try:
            scope_folder = Path(folder).resolve(strict=True)
            if not scope_folder.is_relative_to(self.scan_folder):
                raise ValueError("Choose the scanned folder or one of its subfolders.")
            scan = self.history.scan_settings(self.scan_id)
            extensions = (
                set(json.loads(scan["extensions"])) if scan["extensions"] is not None
                else scan_extensions(scan["scope"], False, legacy=True)
            )
        except (OSError, ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Filename patterns", str(error))
            return
        if not self.lock_operation():
            return
        self.worker = CountFilenamePatterns(scope_folder, extensions, self)
        self.worker.counted.connect(self.filename_counts_ready)
        self.worker.failed.connect(self.filename_count_failed)
        self.worker.finished.connect(self.work_finished)
        self.summary.setText(f"Counting filename patterns in {scope_folder}…")
        self.set_busy(True)
        self.worker.start()

    def filename_counts_ready(self, counts):
        self.apply_filename_plan(self.worker.folder, counts)

    def filename_count_failed(self, message):
        self.summary.setText(f"Could not count filenames: {message}")

    def flag_for_review(self, group, reason):
        group.setData(0, KEEPER_ROLE, None)
        group.setData(0, KEEP_REASON_ROLE, None)
        group.setData(0, REVIEW_ROLE, reason)
        group.setText(2, f"Review · {reason}")
        for index in range(group.childCount()):
            child = group.child(index)
            if child.data(0, FILE_ROLE) not in self.moved_files:
                child.setText(2, "")
        self.refresh_group_checks(group)

    def apply_filename_plan(self, folder, counts):
        style = winning_style(counts)
        flagged = 0
        with QSignalBlocker(self.results):
            for index in range(self.results.topLevelItemCount()):
                group = self.results.topLevelItem(index)
                if group.isHidden():
                    continue
                available = {
                    Path(child.data(0, FILE_ROLE)): child
                    for child in (group.child(i) for i in range(group.childCount()))
                    if child.data(0, FILE_ROLE) not in self.moved_files
                }
                if len(available) < 2 or not any(path.is_relative_to(folder) for path in available):
                    continue
                self.queued.difference_update(str(path) for path in available)
                if group.data(0, KEEP_REASON_ROLE) != "Manual choice":
                    if style is None:
                        keeper, reason = None, "No winning filename pattern"
                    else:
                        keeper, reason = filename_keeper(
                            available, folder, style, self.preferred_keeper_folder
                        )
                    if keeper is None:
                        self.flag_for_review(group, reason)
                        flagged += 1
                        continue
                    self.set_keeper(group, available[keeper], reason)
                self.queued.update(
                    child.data(0, FILE_ROLE) for child in self.eligible_copies(group, visible_only=True)
                )
                self.refresh_group_checks(group)
        winner = style or "No clear winner"
        counts_text = " · ".join(
            f"{pattern}: {counts.get(pattern, 0):,}" for pattern in (DATE_DOTS, DATE_COMPACT, OTHER)
        )
        self.keeper_report = (
            f"Keeper rule · {winner}\n{folder}\n{counts_text}\n"
            f"{flagged:,} groups flagged for manual review when the rule ran."
        )
        self.summary.setText(f"Filename rule · {len(self.queued):,} copies queued · {flagged:,} flagged")
        self.refresh_queue_view()

    def keeper_summary(self):
        if self.keeper_report:
            return f"{self.keeper_report}\n{len(self.queued):,} copies currently queued."
        return ""

    def checked_copies(self):
        copies = {}
        for source in sorted(self.queued):
            child = self.move_items[source]
            group = child.parent()
            keeper = group.data(0, KEEPER_ROLE)
            if keeper and source != keeper and source not in self.moved_files and not group.data(0, REVIEW_ROLE):
                copies[Path(source)] = (Path(keeper), child.data(0, SIZE_ROLE))
        return copies

    def update_review_actions(self):
        item = self.results.currentItem()
        path = self.result_path(item)
        self.reveal.setEnabled(bool(path))
        self.copy.setEnabled(bool(path))
        exact_ready = self.worker is None and self.scan_id is not None and not self.scan_similarity
        self.plan.setEnabled(exact_ready and self.results.topLevelItemCount() > 0)
        self.filename_plan.setEnabled(self.plan.isEnabled())
        self.scan_status.set_keeper_summary(self.keeper_summary())
        self.keep.setEnabled(self.can_keep(item))
        ready_to_move = exact_ready and bool(self.queued)
        self.move.setEnabled(ready_to_move)
        self.recycle.setEnabled(ready_to_move)
        count = len(self.queued)
        self.move.setText(f"Move {count:,} checked copies…" if count else "Move exact copies…")
        self.update_queue_summary()

    def update_queue_summary(self):
        hidden = 0
        size = 0
        for source in self.queued:
            item = self.move_items.get(source)
            if item is not None:
                size += item.data(0, SIZE_ROLE)
                hidden += item.isHidden() or item.parent().isHidden()
        self.queue_summary.setText(
            f"{len(self.queued):,} queued · {hidden:,} hidden by filter · {format_bytes(size)}"
        )

    def refresh_queue_view(self):
        if self.queued_only.isChecked():
            self.filter_results(self.filter.text())
        else:
            self.update_review_actions()

    def confirm_move_plan(self, jobs, destination, sizes, *, recycle=False):
        dialog = QDialog(self)
        dialog.setWindowTitle("Review Recycle Folder batch" if recycle else "Review exact-copy moves")
        dialog.resize(940, 520)
        layout = QVBoxLayout(dialog)
        remaining = dict(enumerate(jobs))
        summary = QLabel()
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setWordWrap(True)
        layout.addWidget(summary)
        if self.keeper_report:
            rule = QLabel(self.keeper_report)
            rule.setTextFormat(Qt.TextFormat.PlainText)
            rule.setWordWrap(True)
            layout.addWidget(rule)

        table = QTreeWidget()
        table.setRootIsDecorated(False)
        table.setAlternatingRowColors(True)
        table.setUniformRowHeights(True)
        table.setHeaderLabels(["Keeper path", "Source path", "Destination path"])
        table.setColumnWidth(0, 240)
        table.setColumnWidth(1, 240)
        for index, (keeper, source, target) in remaining.items():
            item = QTreeWidgetItem(table, [str(keeper.relative_to(self.scan_folder)), str(source), str(target)])
            item.setData(0, FILE_ROLE, index)
            for column, full_path in enumerate((keeper, source, target)):
                item.setToolTip(column, str(full_path))
        table.setSortingEnabled(True)
        table.sortItems(1, Qt.SortOrder.AscendingOrder)
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        confirm = buttons.addButton("Recycle copies" if recycle else "Move copies", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
        confirm.setAutoDefault(False)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        def refresh_summary():
            size = sum(sizes[source] for _, source, _ in remaining.values())
            renamed = sum(source.name != target.name for _, source, target in remaining.values())
            message = (
                f"{len(remaining):,} copies · {format_bytes(size)}\n"
                f"Scanned folder: {self.scan_folder}\nDestination folder: {destination}\n"
                "The app verifies each copy against its keeper before moving."
            )
            if renamed:
                message += f"\n{renamed:,} copies have new names to avoid conflicts."
            summary.setText(message)
            confirm.setEnabled(bool(remaining))

        def remove_row(item):
            remaining.pop(item.data(0, FILE_ROLE))
            table.takeTopLevelItem(table.indexOfTopLevelItem(item))
            refresh_summary()

        def open_folder(path):
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))):
                QMessageBox.warning(dialog, "Open folder", f"Could not open {path.parent}")

        def row_menu(position):
            item = table.itemAt(position)
            if item is None:
                return
            keeper, source, target = remaining[item.data(0, FILE_ROLE)]
            menu = QMenu(table)
            for name, path in zip(("keeper", "source", "destination"), (keeper, source, target)):
                menu.addAction(
                    f"Copy {name} path",
                    lambda checked=False, value=str(path): QApplication.clipboard().setText(value),
                )
            menu.addAction(
                "Copy all three paths",
                lambda: QApplication.clipboard().setText(
                    f"Keeper: {keeper}\nSource: {source}\nDestination: {target}"
                ),
            )
            menu.addSeparator()
            menu.addAction("Open keeper folder", lambda: open_folder(keeper))
            menu.addAction("Open source folder", lambda: open_folder(source))
            menu.addSeparator()
            menu.addAction("Remove from this move", lambda: remove_row(item))
            menu.exec(table.viewport().mapToGlobal(position))
            menu.deleteLater()

        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(row_menu)
        refresh_summary()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return list(remaining.values())
        return None

    def choose_move_destination(self):
        if not self.move.isEnabled():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Choose where to move selected exact copies", str(self.scan_folder.parent)
        )
        if folder:
            self.plan_move_to(Path(folder))

    def choose_recycle_destination(self):
        if not self.recycle.isEnabled():
            return
        recent = self.settings.value("recycleFolder", str(self.scan_folder.parent), type=str)
        folder = QFileDialog.getExistingDirectory(self, "Choose the Recycle Folder", recent)
        if folder:
            self.plan_move_to(Path(folder), recycle=True)

    def show_recycle_folder(self):
        if self.worker is None:
            RecycleDialog(self).exec()

    def file_restored(self, entry, target):
        if entry["scan_id"] != self.scan_id:
            return
        source = entry["source"]
        same_location = Path(source) == target
        if same_location:
            self.moved_files.pop(source, None)
        else:
            self.moved_files[source] = str(target)
        item = self.move_items.get(source)
        if item is not None:
            with QSignalBlocker(self.results):
                item.setText(2, "" if same_location else "Restored")
                item.setToolTip(0, str(target))
                self.refresh_group_checks(item.parent())
            self.filter_results(self.filter.text())
            self.show_preview(self.results.currentItem())

    def plan_move_to(self, destination, *, recycle=False):
        copies = self.checked_copies()
        if self.worker is not None or self.scan_similarity or not copies:
            return
        try:
            destination = destination.resolve(strict=True)
            jobs = plan_move_targets(self.scan_folder, destination, copies)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Move destination", str(error))
            return
        sizes = {source: size for source, (_, size) in copies.items()}
        jobs = self.confirm_move_plan(jobs, destination, sizes, recycle=recycle)
        if not jobs or not self.lock_operation():
            return

        included = {source for _, source, _ in jobs}
        with QSignalBlocker(self.results):
            for source in copies.keys() - included:
                self.queued.discard(str(source))
                self.refresh_group_checks(self.move_items[str(source)].parent())
        total_size = sum(sizes[source] for source in included)
        self.video_preview.clear()
        if recycle:
            self.settings.setValue("recycleFolder", str(destination))
        self.worker = MoveCopies(
            jobs, {source: sizes[source] for source in included}, self.history, self.scan_id,
            destination, self, recycle=recycle,
        )
        self.worker.progress.connect(self.move_status.update_progress)
        self.worker.file_moved.connect(self.show_file_moved)
        self.worker.completed.connect(self.show_move_results)
        self.worker.finished.connect(self.work_finished)
        self.summary.setText("Verifying copies for Recycle Folder…" if recycle else "Verifying and moving checked copies…")
        self.set_busy(True)
        self.show_preview(self.results.currentItem())
        self.move_status.begin(destination, len(jobs), total_size)
        self.worker.start()

    def show_file_moved(self, source, destination):
        self.moved_files[source] = destination
        self.queued.discard(source)
        item = self.move_items.get(source)
        if item is not None:
            with QSignalBlocker(self.results):
                item.setText(2, "Moved")
                item.setToolTip(0, destination)
                self.refresh_group_checks(item.parent())
                if self.results.currentItem() is item:
                    item.setSelected(False)
        if not self.queue_refresh.isActive():
            self.queue_refresh.start(150)

    def show_move_results(self, moved, errors):
        self.filter_results(self.filter.text())
        self.summary.setText(f"Moved {len(moved):,} copies · {len(errors):,} issues")
        self.move_status.finish(self.summary.text())
        if errors:
            self.show_move_errors(errors)

    def show_move_errors(self, errors):
        dialog = QDialog(self)
        dialog.setWindowTitle("Move results")
        dialog.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setSizeGripEnabled(True)
        dialog.resize(860, 440)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.summary.text()))
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        details.setPlainText("\n\n".join(errors))
        layout.addWidget(details, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy = buttons.addButton("Copy details", QDialogButtonBox.ButtonRole.ActionRole)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(details.toPlainText()))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.open()

    def closeEvent(self, event):
        if self.worker is not None:
            self.summary.setText("An operation is still running. Close the window after it finishes.")
            event.ignore()
        else:
            super().closeEvent(event)
            if event.isAccepted():
                self.settings.setValue("mainWindow/geometry", self.saveGeometry())
                self.settings.setValue("mainWindow/previewSplit", self.review_splitter.saveState())
                self.settings.sync()


def main():
    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
