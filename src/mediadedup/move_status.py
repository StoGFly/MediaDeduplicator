"""Progress for a batch of verified exact-copy moves."""

from time import monotonic

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout

from mediadedup.scan_status import format_bytes


class MoveStatus(QDialog):
    compact_changed = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Move Status")
        self.resize(600, 245)
        self.running = False
        self.compact = ""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_elapsed)
        layout = QVBoxLayout(self)
        self.destination = QLabel()
        self.phase = QLabel("No move started.")
        self.file = QLabel()
        self.elapsed = QLabel()
        for label in (self.destination, self.phase, self.file, self.elapsed):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(label)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        hide = QPushButton("Hide")
        hide.clicked.connect(self.hide)
        layout.addWidget(hide)

    def begin(self, destination, count, size):
        self.running = True
        self.started = monotonic()
        self.count = count
        self.size = size
        self.destination.setText(str(destination))
        self.progress.setRange(0, 100)
        self.update_progress("Starting move", "", 0, 0, 0, 0)
        self.progress.show()
        self.update_elapsed()
        self.timer.start(1000)
        self.show()
        self.raise_()

    def update_elapsed(self):
        seconds = int(monotonic() - self.started)
        self.elapsed.setText(f"Elapsed {seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}")

    def update_progress(self, phase, source, processed, moved, bytes_moved, issues):
        self.compact = (
            f"{phase} · {processed:,} / {self.count:,} processed\n"
            f"{moved:,} moved · {format_bytes(bytes_moved)} / {format_bytes(self.size)} · {issues:,} issues"
        )
        self.phase.setText(self.compact)
        self.file.setText(source)
        self.progress.setValue(processed * 100 // self.count)
        self.compact_changed.emit()

    def finish(self, message):
        self.running = False
        self.timer.stop()
        self.update_elapsed()
        self.progress.hide()
        self.phase.setText(message)
        self.file.clear()
        self.compact = ""
        self.compact_changed.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self.compact_changed.emit()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.compact_changed.emit()
