"""Status window for a desktop scan."""

from time import monotonic

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout


def format_bytes(value):
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1000 or unit == "TB":
            return f"{amount:,.0f} {unit}" if unit == "B" else f"{amount:,.2f} {unit}"
        amount /= 1000


class ScanStatus(QDialog):
    compact_changed = Signal()
    stop_requested = Signal()
    resume_requested = Signal(int)
    fresh_requested = Signal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Scan Status")
        self.resize(560, 250)
        self.running = False
        self.compact = ""
        self.settings = QSettings("MediaDeduplicator", "MediaDeduplicator")
        self.started = 0.0
        self.stopped_id = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_elapsed)

        layout = QVBoxLayout(self)
        self.folder = QLabel()
        self.phase = QLabel("No scan started.")
        self.totals = QLabel()
        self.elapsed = QLabel()
        for label in (self.folder, self.phase, self.totals, self.elapsed):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            layout.addWidget(label)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)

        actions = QHBoxLayout()
        self.stop_button = QPushButton("Stop scan")
        self.stop_button.clicked.connect(self.request_stop)
        self.stop_button.setEnabled(False)
        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(lambda: self.resume_requested.emit(self.stopped_id))
        self.resume_button.hide()
        self.fresh_button = QPushButton("Start fresh")
        self.fresh_button.clicked.connect(lambda: self.fresh_requested.emit(self.stopped_id))
        self.fresh_button.hide()
        hide = QPushButton("Hide")
        hide.clicked.connect(self.close)
        for button in (self.stop_button, self.resume_button, self.fresh_button, hide):
            actions.addWidget(button)
        layout.addLayout(actions)

    def begin(self, folder):
        self.running = True
        self.stopped_id = None
        self.started = monotonic()
        self.folder.setText(str(folder))
        self.stop_button.setEnabled(True)
        self.update_progress(("Starting scan", 0, 0, 0, 0, 0, None))
        self.update_elapsed()
        self.timer.start(1000)
        self.resume_button.hide()
        self.fresh_button.hide()
        self.progress.show()
        self.show()
        self.raise_()

    def update_elapsed(self):
        seconds = int(monotonic() - self.started)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        self.elapsed.setText(f"Elapsed {hours:02d}:{minutes:02d}:{seconds:02d}")

    def update_progress(self, status):
        phase, done, total, photos, videos, size, byte_progress = status
        if self.stop_button.isEnabled() or not self.running:
            progress = f"{phase} · {done:,} / {total:,}" if total else phase
            if byte_progress is not None and byte_progress[1]:
                covered, to_check = byte_progress
                progress += f"\n{format_bytes(covered)} / {format_bytes(to_check)} checked"
                done, total = covered, to_check
            self.phase.setText(progress)
            self.compact = progress
            self.compact_changed.emit()
        self.totals.setText(
            f"{photos:,} photos · {videos:,} videos · {format_bytes(size)} found"
        )
        self.progress.setRange(0, 100 if total else 0)
        if total:
            self.progress.setValue(int(done * 100 / total))

    def request_stop(self):
        self.stop_button.setEnabled(False)
        self.phase.setText("Stopping and saving progress…")
        self.compact = self.phase.text()
        self.compact_changed.emit()
        self.stop_requested.emit()

    def finish(self, message, *, stopped_id=None):
        self.running = False
        self.timer.stop()
        self.update_elapsed()
        self.progress.hide()
        self.phase.setText(message)
        self.stop_button.setEnabled(False)
        self.stopped_id = stopped_id
        self.resume_button.setVisible(stopped_id is not None)
        self.fresh_button.setVisible(stopped_id is not None)
        self.compact = ""
        self.compact_changed.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self.compact_changed.emit()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.compact_changed.emit()

    def closeEvent(self, event):
        if self.running and not self.settings.value("skipHideScanStatusPrompt", False, type=bool):
            box = QMessageBox(
                QMessageBox.Icon.Question, "Hide Scan Status?",
                "The scan will continue while MediaDeduplicator stays open. "
                "Use Scan Status to bring this window back.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self,
            )
            remember = QCheckBox("Don't show this message again")
            box.setCheckBox(remember)
            box.setDefaultButton(QMessageBox.StandardButton.No)
            if box.exec() != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if remember.isChecked():
                self.settings.setValue("skipHideScanStatusPrompt", True)
        event.accept()
