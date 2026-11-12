"""Inline playback controls for the review panel."""

from PySide6.QtCore import QSettings, QTimer, Qt, QUrl
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
        self.settings = QSettings("MediaDeduplicator", "MediaDeduplicator")
        self.user_muted = self.settings.value("videoPreview/muted", False, type=bool)
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

        audio_controls = QHBoxLayout()
        for seconds in (-10, 10):
            button = QPushButton(f"{seconds:+d}s")
            button.clicked.connect(lambda checked=False, step=seconds: self.skip(step))
            audio_controls.addWidget(button)
        self.mute = QPushButton("Mute")
        self.mute.setCheckable(True)
        self.mute.setChecked(self.user_muted)
        self.mute.toggled.connect(self.set_muted)
        audio_controls.addWidget(self.mute)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setAccessibleName("Video volume")
        self.volume.setRange(0, 100)
        self.volume.setValue(self.settings.value("videoPreview/volume", 100, type=int))
        self.volume.valueChanged.connect(self.set_volume)
        self.audio.setVolume(self.volume.value() / 100)
        self.audio.setMuted(self.user_muted)
        audio_controls.addWidget(self.volume, 1)
        layout.addLayout(audio_controls)

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
            self.audio.setMuted(self.user_muted)
            self.player.play()

    def set_volume(self, volume):
        self.audio.setVolume(volume / 100)
        self.settings.setValue("videoPreview/volume", volume)

    def set_muted(self, muted):
        self.user_muted = muted
        self.audio.setMuted(muted or self.priming)
        self.settings.setValue("videoPreview/muted", muted)

    def skip(self, seconds):
        position = self.player.position() + seconds * 1000
        self.player.setPosition(max(0, min(position, self.player.duration())))

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
