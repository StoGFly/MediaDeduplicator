"""Inline playback controls for the review panel."""

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget


def duration_text(milliseconds):
    seconds = max(0, milliseconds) // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


class VideoPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = None
        self.priming = False
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.prime_timer = QTimer(self)
        self.prime_timer.setSingleShot(True)
        self.prime_timer.timeout.connect(self.pause_preview)
        layout = QVBoxLayout(self)
        self.video = QVideoWidget(self)
        self.player.setVideoOutput(self.video)
        self.video.videoSink().videoFrameChanged.connect(self.frame_ready)
        layout.addWidget(self.video, 1)

        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        self.message.hide()
        layout.addWidget(self.message)

        controls = QHBoxLayout()
        self.play = QPushButton("Play")
        self.play.clicked.connect(self.toggle_play)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.setAccessibleName("Video position")
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.time = QLabel("0:00 / 0:00")
        controls.addWidget(self.play)
        controls.addWidget(self.seek, 1)
        controls.addWidget(self.time)
        layout.addLayout(controls)
        self.open_default = QPushButton("Open in default player")
        self.open_default.clicked.connect(self.open_external)
        layout.addWidget(self.open_default, 0, Qt.AlignmentFlag.AlignLeft)

        self.player.durationChanged.connect(self.duration_changed)
        self.player.positionChanged.connect(self.position_changed)
        self.player.playbackStateChanged.connect(self.state_changed)
        self.player.mediaStatusChanged.connect(self.media_status)
        self.player.errorOccurred.connect(self.show_error)

    def set_file(self, path):
        self.clear()
        self.path = path
        self.priming = True
        self.play.setEnabled(True)
        self.audio.setMuted(True)
        self.message.hide()
        self.player.setSource(QUrl.fromLocalFile(path))
        self.prime_timer.start(4000)

    def clear(self):
        self.path = None
        self.priming = False
        self.prime_timer.stop()
        self.player.stop()
        self.player.setSource(QUrl())
        self.seek.setRange(0, 0)
        self.time.setText("0:00 / 0:00")

    def media_status(self, state):
        if self.priming and state == QMediaPlayer.MediaStatus.LoadedMedia:
            self.player.play()

    def frame_ready(self, frame):
        if self.priming and frame.isValid():
            self.pause_preview()

    def pause_preview(self):
        if self.priming:
            self.priming = False
            self.prime_timer.stop()
            self.player.pause()

    def toggle_play(self):
        was_priming = self.priming
        self.priming = False
        self.prime_timer.stop()
        if not was_priming and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.audio.setMuted(False)
            self.player.play()

    def state_changed(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState and not self.priming
        self.play.setText("Pause" if playing else "Play")

    def duration_changed(self, duration):
        self.seek.setRange(0, min(duration, 2**31 - 1))
        self.position_changed(self.player.position())

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(min(position, self.seek.maximum()))
        self.time.setText(f"{duration_text(position)} / {duration_text(self.player.duration())}")

    def show_error(self, error, message):
        if self.path:
            self.priming = False
            self.prime_timer.stop()
            self.play.setEnabled(False)
            self.message.setText(f"Video preview unavailable. {message}")
            self.message.show()

    def open_external(self):
        if self.path and not QDesktopServices.openUrl(QUrl.fromLocalFile(self.path)):
            self.message.setText("Could not open the default player.")
            self.message.show()
