import ctypes
import sys
import uuid
from enum import Enum
from os.path import join

import yt_dlp

from PyQt5.QtGui import QIcon, QPixmap, QStandardItemModel, QStandardItem, QFont
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget, \
    QMessageBox, QTableWidget, QProgressBar, QLabel, QLineEdit, QSizePolicy, QGroupBox, QVBoxLayout, QHBoxLayout, \
    QComboBox, QListView
from PyQt5.QtCore import QRunnable, QObject, pyqtSlot, pyqtSignal, QThreadPool, Qt, QSettings, QByteArray

pool = QThreadPool.globalInstance()
STANDARD_OPTIONS = {
    "allow_unplayable_formats": True,
    'noprogress': True,
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True
}


def icon():
    return QIcon(QPixmap("icon.png"))


def clean_name(s):
    return ''.join(filter(lambda c: 31 < ord(c) < 127, s))


def format_seconds(s):
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f'{int(h)}h {int(m)}m {int(s)}s'


class MediaType(Enum):
    VIDEO = 'video'
    AUDIO = 'audio'


class Stream(QWidget):
    def __init__(
            self,
            download_function
    ):
        super().__init__()

        self.resize(600, 300)
        self.setWindowIcon(icon())
        self.setWindowTitle("General Download/Stream")

        self.settings = QSettings("DevLARLEY", "GeneralDownloadStream")
        self.restoreGeometry(self.settings.value("geometry", QByteArray()))

        self.verticalLayout = QVBoxLayout(self)

        self.widget_2 = QWidget(self)
        self.widget_2.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum))

        self.horizontalLayout = QHBoxLayout(self.widget_2)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)

        self.url_label = QLabel("URL:", self.widget_2)
        self.horizontalLayout.addWidget(self.url_label)

        self.url = QLineEdit(self.widget_2)
        self.url.setEnabled(False)
        self.horizontalLayout.addWidget(self.url)

        self.verticalLayout.addWidget(self.widget_2)

        self.metadata_box = QGroupBox("Metadata:", self)
        self.horizontalLayout_4 = QHBoxLayout(self.metadata_box)

        self.resolution_label = QLabel("Resolution:", self.metadata_box)
        self.horizontalLayout_4.addWidget(self.resolution_label)

        self.resolution = QLineEdit(self.metadata_box)
        self.resolution.setEnabled(False)
        self.horizontalLayout_4.addWidget(self.resolution)

        self.duration_label = QLabel("Duration:", self.metadata_box)
        self.horizontalLayout_4.addWidget(self.duration_label)

        self.duration = QLineEdit(self.metadata_box)
        self.duration.setEnabled(False)
        self.horizontalLayout_4.addWidget(self.duration)

        self.drm_label = QLabel("DRM:", self.metadata_box)
        self.horizontalLayout_4.addWidget(self.drm_label)

        self.drm = QLineEdit(self.metadata_box)
        self.drm.setEnabled(False)
        self.horizontalLayout_4.addWidget(self.drm)
        self.is_drm = False

        self.verticalLayout.addWidget(self.metadata_box)

        self.stream_box = QGroupBox("Streams", self)
        self.verticalLayout_2 = QVBoxLayout(self.stream_box)

        mono = QFont()
        mono.setFamily("Courier New")

        self.widget = QWidget(self.stream_box)
        self.widget.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum))

        self.horizontalLayout_2 = QHBoxLayout(self.widget)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)

        self.video_label = QLabel("Video:", self.widget)
        self.horizontalLayout_2.addWidget(self.video_label)

        self.video = QComboBox(self.widget)
        self.video.setFont(mono)
        self.video.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.horizontalLayout_2.addWidget(self.video)
        self.video_ids = []

        self.verticalLayout_2.addWidget(self.widget)

        self.audio_box = QGroupBox("Audio", self.stream_box)
        self.horizontalLayout_3 = QHBoxLayout(self.audio_box)

        self.audio = QListView(self.audio_box)
        self.audio.setFont(mono)
        self.horizontalLayout_3.addWidget(self.audio)
        self.audio_model = QStandardItemModel()
        self.audio_ids = []

        self.verticalLayout_2.addWidget(self.audio_box)
        self.verticalLayout.addWidget(self.stream_box)

        self.download = QPushButton("Download", self)
        self.download.setEnabled(False)
        self.download.clicked.connect(
            lambda: download_function(
                self.url.text(),
                self.video_ids[self.video.currentIndex()],
                list(
                    map(
                        lambda i: self.audio_ids[i],
                        [
                            row
                            for row in range(self.audio_model.rowCount())
                            if self.audio_model.item(row).checkState() == Qt.CheckState.Checked
                        ]
                    )
                ),
                self.is_drm
            )
        )
        self.verticalLayout.addWidget(self.download)

    def setup(
            self,
            metadata: dict
    ):
        self.url.clear()
        self.resolution.clear()
        self.duration.clear()
        self.drm.clear()
        self.drm.setStyleSheet("")
        self.is_drm = False
        self.video_ids.clear()
        self.video.clear()
        self.audio_ids.clear()
        self.audio_model.clear()
        self.audio.setModel(self.audio_model)
        self.download.setEnabled(False)

        if url := metadata.get('webpage_url'):
            self.url.setText(url)

        if resolution := metadata.get('resolution'):
            if resolution:
                self.resolution.setText(resolution)

        if duration := metadata.get('duration'):
            if duration:
                self.duration.setText(format_seconds(duration))

        if drm := metadata.get('_has_drm'):
            self.drm.setText("DRM" if drm else "No DRM")
            self.drm.setStyleSheet("QLineEdit { color: red }")
            self.is_drm = bool(drm)
        else:
            self.drm.setText("No DRM")

        # video
        for f in metadata.get("formats"):
            if f.get("vcodec") == "none":
                continue

            stream = []

            if ext := f.get("ext"):
                if ext:
                    stream.append(ext.ljust(5))
            if resolution := f.get("resolution"):
                if resolution:
                    stream.append(resolution.ljust(10))
            if tbr := f.get("tbr"):
                if tbr:
                    stream.append(f"{int(tbr)}k".ljust(7))
            if vcodec := f.get("vcodec"):
                if vcodec:
                    stream.append(vcodec.ljust(14))
            if has_drm := f.get('has_drm'):
                if has_drm:
                    stream.append("DRM")

            self.video_ids.append(f.get("format_id"))

            self.video.addItem(' | '.join(stream))

        # audio
        for f in metadata.get("formats"):
            if f.get("vcodec") != "none":
                continue
            if f.get("format_note") == "storyboard":
                continue

            stream = []

            if lang := f.get("language"):
                if lang:
                    stream.append(lang.ljust(4))
            if ext := f.get("ext"):
                if ext:
                    stream.append(ext.ljust(5))
            if tbr := f.get("tbr"):
                if tbr:
                    stream.append(f"{int(tbr)}k".ljust(7))
            if acodec := f.get("acodec"):
                if acodec != 'none':
                    stream.append(acodec.ljust(14))
            if has_drm := f.get('has_drm'):
                if has_drm:
                    stream.append("DRM")

            self.audio_ids.append(f.get("format_id"))

            item = QStandardItem(' | '.join(stream))
            item.setEditable(False)
            item.setCheckable(True)
            self.audio_model.appendRow(item)

        self.audio.setModel(self.audio_model)

        self.download.setEnabled(True)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)
        event.accept()


class ExtractorSignals(QObject):
    done = pyqtSignal(dict)
    error = pyqtSignal(str)


class Extractor(QRunnable):
    def __init__(
            self,
            url: str
    ):
        super().__init__()
        self.url = url
        self.signals = ExtractorSignals()

    @pyqtSlot()
    def run(self):
        try:
            metadata = yt_dlp.YoutubeDL(STANDARD_OPTIONS).extract_info(
                self.url,
                download=False
            )
            self.signals.done.emit(metadata)
        except Exception as e:
            self.signals.error.emit(str(e).replace("\033[31m", ""))


class DownloaderSignals(QObject):
    started = pyqtSignal(tuple)
    completed = pyqtSignal(str)
    progress = pyqtSignal(tuple)
    error = pyqtSignal(str)


class Downloader(QRunnable):
    def __init__(
            self,
            url: str,
            video_id: str,
            audio_ids: list,
            is_drm: bool,
            output_path: str
    ):
        super().__init__()
        self.url = url
        self.video_id = video_id
        self.audio_ids = audio_ids
        self.is_drm = is_drm
        self.output_path = output_path

        self.task_id = str(uuid.uuid4())
        self.signals = DownloaderSignals()

        self.current_media_type = MediaType.VIDEO

    @pyqtSlot()
    def run(self):
        title = yt_dlp.YoutubeDL(STANDARD_OPTIONS).extract_info(self.url, download=False).get("title", None)

        def log(data: dict):
            status = data.get('status')
            if status == 'error':
                return

            size, progress = 0, 0
            if (
                    (size_estimate := data.get('total_bytes_estimate')) and
                    (size_downloaded := data.get('downloaded_bytes'))
            ):
                if size_estimate:
                    size = int(size_estimate / 1000000)
                    if size_downloaded:
                        progress = int(size_downloaded / size_estimate * 100)

            if eta := data.get('eta'):
                if eta:
                    eta = format_seconds(eta)
                else:
                    eta = 'N/A'
            else:
                eta = 'N/A'

            frags = f"{data.get('fragment_index', '?')}/{data.get('fragment_count', '?')}"

            if speed := data.get('speed', 0):
                if speed:
                    speed = int(speed / 1000)

            if status == 'finished' and progress == 0:
                self.current_media_type = MediaType.AUDIO

            self.signals.progress.emit(
                (
                    self.task_id,
                    f"{status.capitalize()} {self.current_media_type.value}",
                    title,
                    size,
                    progress,
                    frags,
                    speed,
                    eta
                )
            )

        try:
            self.signals.started.emit(
                (
                    self.task_id,
                    self.url
                )
            )

            ydl_opts = {
                'allow_unplayable_formats': self.is_drm,
                'noprogress': True,
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'allow_multiple_audio_streams': True,
                'add_metadata': True,
                'format': '+'.join([self.video_id, *self.audio_ids]),
                'outtmpl': {
                    'default': join(self.output_path if self.output_path else '.', '%(title)s-%(id)s.%(ext)s')
                },
                'progress_hooks': [log]
            }
            yt_dlp.YoutubeDL(ydl_opts).download(self.url)

        except Exception as e:
            self.signals.error.emit(str(e).replace("\033[31m", ""))

        self.signals.completed.emit(self.task_id)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()

        self.resize(1000, 500)
        self.setWindowTitle('General Download')
        self.setWindowIcon(icon())

        self.settings = QSettings("DevLARLEY", "GeneralDownload")

        self.statusbar = self.statusBar()
        self.statusbar.setStyleSheet("QStatusBar{background-color: #E5E5E5}")

        self.status_widget = QWidget()
        self.status_widget.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum))
        self.horizontalLayout = QHBoxLayout(self.status_widget)
        self.horizontalLayout.setContentsMargins(4, 0, 8, 4)

        self.output_path = QLineEdit(self.settings.value("output_path"))
        self.output_path.setPlaceholderText("Output path")
        self.output_path.textChanged.connect(
            lambda: self.settings.setValue("output_path", self.output_path.text())
        )
        self.horizontalLayout.addWidget(self.output_path)

        self.select_output_path = QPushButton("Select")
        self.horizontalLayout.addWidget(self.select_output_path)

        self.statusbar.addWidget(self.status_widget, 100)

        self.stream = Stream(self.launch_downloader)

        self.widget = QWidget()
        self.verticalLayout = QVBoxLayout(self.widget)
        self.setCentralWidget(self.widget)

        self.tableWidget = QTableWidget(self.widget)
        self.tableWidget.setColumnCount(8)
        self.horizontalHeader = self.tableWidget.horizontalHeader()
        if sections := self.settings.value("header_sections"):
            for i in range(8):
                self.horizontalHeader.resizeSection(i, int(sections[i]))
        self.horizontalHeader.sectionResized.connect(
            lambda: self.settings.setValue(
                "header_sections",
                list(
                    map(
                        lambda i: int(self.horizontalHeader.sectionSize(i)),
                        [0, 1, 2, 3, 4, 5, 6, 7]
                    )
                )
            )
        )
        self.verticalLayout.addWidget(self.tableWidget)

        self.widget2 = QWidget(self.widget)
        self.horizontalLayout2 = QHBoxLayout(self.widget2)
        self.horizontalLayout2.setContentsMargins(0, 0, 0, 0)

        self.url = QLineEdit(self.widget2)
        self.url.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred))
        self.url.setPlaceholderText("URL")
        self.horizontalLayout2.addWidget(self.url)

        self.launch = QPushButton('Launch', self.widget2)
        self.launch.clicked.connect(self.launch_extractor)
        self.horizontalLayout2.addWidget(self.launch)

        self.verticalLayout.addWidget(self.widget2)

        self.tableWidget.setHorizontalHeaderLabels(
            {
                "ID": "0",
                "Status": "1",
                "Name": "2",
                "Size": "3",
                "Progress": "4",
                "Fragments": "5",
                "Speed": "6",
                "ETA": "7"
            }.keys()
        )

        self.restoreGeometry(self.settings.value("geometry", QByteArray()))
        self.show()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)
        event.accept()

    def launch_downloader(
            self,
            url: str,
            video_id: str,
            audio_ids: list,
            is_drm: bool
    ):
        self.statusbar.showMessage("Launching downloader...")
        downloader = Downloader(url, video_id, audio_ids, is_drm, self.settings.value("output_path"))
        downloader.signals.completed.connect(self.handle_complete)
        downloader.signals.started.connect(self.handle_started)
        downloader.signals.progress.connect(self.handle_progress)
        downloader.signals.error.connect(self.handle_error)
        pool.start(downloader)
        self.statusbar.showMessage("Download has started.", 1000)
        self.stream.hide()

    def launch_extractor(self):
        if not self.url.text():
            return
        self.statusbar.showMessage("Launching extractor...")
        extractor = Extractor(self.url.text())
        extractor.signals.done.connect(self.handle_extract)
        extractor.signals.error.connect(self.handle_fail)
        pool.start(extractor)
        self.statusbar.showMessage("Extracting...")
        self.url.clear()

    def handle_fail(self, error):
        self.statusbar.showMessage("Failed", 3000)
        self.handle_error(error)

    def handle_extract(self, metadata):
        self.statusbar.showMessage("Parsing metadata...")
        self.stream.setup(metadata)
        self.stream.show()
        self.stream.move(
            int(self.pos().x() + (self.width() / 2 - self.stream.width() / 2)),
            int(self.pos().y() - (self.stream.height() / 2 - self.height() / 2))
        )
        self.statusbar.showMessage("Done", 3000)

    def handle_error(self, error):
        QMessageBox.critical(
            self,
            "Error",
            error,
            buttons=QMessageBox.Ok,
            defaultButton=QMessageBox.Ok,
        )

    def handle_started(self, data):
        task_id, url = data
        self.tableWidget.insertRow(0)
        self.tableWidget.setCellWidget(0, 0, QLabel(task_id))
        self.tableWidget.setCellWidget(0, 1, QLabel("Starting..."))
        self.tableWidget.setCellWidget(0, 2, QLabel(url))
        self.tableWidget.setCellWidget(0, 3, QLabel())
        self.tableWidget.setCellWidget(0, 4, QProgressBar())
        self.tableWidget.setCellWidget(0, 5, QLabel())
        self.tableWidget.setCellWidget(0, 6, QLabel())
        self.tableWidget.setCellWidget(0, 7, QLabel())
        self.tableWidget.scrollToBottom()

    def handle_progress(self, data):
        task_id, status, name, size, progress, frags, speed, eta = data
        for i in range(self.tableWidget.rowCount()):
            if task_id == self.tableWidget.cellWidget(i, 0).text():
                self.tableWidget.cellWidget(i, 1).setText(status)
                self.tableWidget.cellWidget(i, 2).setText(name)
                self.tableWidget.cellWidget(i, 3).setText(f"{size} MB")
                self.tableWidget.cellWidget(i, 4).setValue(progress)
                self.tableWidget.cellWidget(i, 5).setText(frags)
                self.tableWidget.cellWidget(i, 6).setText(f"{speed} KB/s")
                self.tableWidget.cellWidget(i, 7).setText(eta)

    def handle_complete(self, task_id):
        for i in range(self.tableWidget.rowCount()):
            if task_id == self.tableWidget.cellWidget(i, 0).text():
                self.tableWidget.removeRow(i)


if __name__ == '__main__':
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ModularDL")
    app = QApplication(sys.argv)
    window = Main()
    sys.exit(app.exec())
