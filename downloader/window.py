from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                             QLabel, QListWidget, QListWidgetItem, QMainWindow,
                             QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                             QStackedWidget, QVBoxLayout, QWidget)

from .engine import QueueController
from .model import ACTIVE, RETRYABLE, Job, Settings, Storage, build_arguments, parse_links
from .settings_dialog import SettingsDialog, button, note
from .system import SystemCheck, ToolStatus


def heading(text, name="section"):
    label = QLabel(text)
    label.setObjectName(name)
    return label


class JobRow(QFrame):
    details_requested = Signal(object)
    action_requested = Signal(object)

    def __init__(self, job: Job, parent=None):
        super().__init__(parent)
        self.job = job
        self.setObjectName("row")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        top = QHBoxLayout()
        self.title = QLabel()
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setStyleSheet("font-weight: 600; font-size: 14px;")
        top.addWidget(self.title, 1)
        self.quality = QLabel()
        self.quality.setObjectName("badge")
        self.quality.setToolTip("The resolution selected by yt-dlp for the current video")
        top.addWidget(self.quality)
        self.badge = QLabel()
        self.badge.setObjectName("badge")
        top.addWidget(self.badge)
        self.details = button("Details", lambda: self.details_requested.emit(self.job), "quiet")
        top.addWidget(self.details)
        self.action = button("Cancel", lambda: self.action_requested.emit(self.job), "quiet")
        top.addWidget(self.action)
        layout.addLayout(top)
        self.source = note("")
        self.source.setWordWrap(False)
        self.source.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.source)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        self.detail = note("")
        self.detail.setWordWrap(False)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setStyleSheet("font-size: 11px; color: #95a2b5;")
        layout.addWidget(self.detail)
        self.refresh()

    def refresh(self):
        self.quality.setText("Selected " + self.job.resolution.replace("x", "×"))
        self.quality.setVisible(bool(self.job.resolution))
        width = max(200, self.width() - (475 if self.job.resolution else 320))
        self.title.setText(self.title.fontMetrics().elidedText(self.job.title or self.job.url, Qt.TextElideMode.ElideRight, width))
        self.title.setToolTip(self.job.title or self.job.url)
        self.source.setText(self.source.fontMetrics().elidedText(self.job.url, Qt.TextElideMode.ElideRight, max(400, self.width() - 40)))
        self.source.setToolTip(self.job.url)
        self.badge.setText(self.job.status)
        color, background = ("#79ddc2", "#1d3633")
        if self.job.status in {"Failed", "Cancelled", "Interrupted"}:
            color, background = "#edb18d", "#3b2c28"
        elif self.job.status in {"Queued", "Finished"}:
            color, background = "#aab8ca", "#283241"
        self.badge.setStyleSheet(f"color: {color}; background: {background};")
        if self.job.status in {"Starting", "Processing", "Stopping"}:
            self.bar.setRange(0, 0)
        else:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(self.job.progress * 10))
        self.detail.setText(self.detail.fontMetrics().elidedText(self.job.detail, Qt.TextElideMode.ElideRight, max(400, self.width() - 40)))
        self.detail.setToolTip(self.job.detail)
        self.action.setText("Cancel" if self.job.status in ACTIVE | {"Queued"} else "Retry" if self.job.status in RETRYABLE else "Open" if self.job.files else "Remove")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()


class DetailsDialog(QDialog):
    def __init__(self, job: Job, controller: QueueController, parent=None):
        super().__init__(parent)
        self.job = job
        self.controller = controller
        self.setWindowTitle("Download details")
        self.resize(860, 550)
        layout = QVBoxLayout(self)
        title = heading(job.title or "Download details")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        layout.addWidget(title)
        source = note(job.url)
        source.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(source)
        self.status = note(job.status + " · " + job.detail)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(600)
        self.log.setStyleSheet("font-family: 'SF Mono', Menlo, monospace; font-size: 11px;")
        self.log.setPlainText("\n".join(job.log) or "Download messages will appear here.")
        layout.addWidget(self.log, 1)
        layout.addWidget(note("Logs stay in memory and are cleared when the app closes. Advanced verbose options may include account or authentication information."))
        row = QHBoxLayout()
        row.addWidget(button("Copy log", lambda: self.log.selectAll() or self.log.copy()))
        row.addStretch()
        row.addWidget(button("Close", self.accept))
        layout.addLayout(row)
        controller.logged.connect(self.on_log)
        controller.changed.connect(self.on_change)
        self.finished.connect(self.disconnect_signals)

    def on_log(self, job, line):
        if job.id == self.job.id:
            self.log.appendPlainText(line)

    def on_change(self, job):
        if job.id == self.job.id:
            self.status.setText(job.status + " · " + job.detail)

    def disconnect_signals(self, *_):
        self.controller.logged.disconnect(self.on_log)
        self.controller.changed.disconnect(self.on_change)


class MainWindow(QMainWindow):
    def __init__(self, storage: Storage | None = None, check_system=True):
        super().__init__()
        self.storage = storage or Storage()
        self.setWindowTitle("YouTube Downloader")
        self.resize(1120, 910)
        self.setMinimumSize(900, 800)
        self.settings = Settings()
        self.jobs: list[Job] = []
        self.rows = {}
        self.tool_status = ToolStatus()
        self.checker = None
        self.closing = False
        self.storage_failed = False
        try:
            self.settings = Settings.from_dict(self.storage.read("settings.json", {}))
            ids = set()
            for data in self.storage.read("queue.json", []):
                job = Job.from_dict(data)
                if job.id not in ids:
                    self.jobs.append(job)
                    ids.add(job.id)
        except (ValueError, TypeError, KeyError):
            self.storage.warning = "Some saved settings or queue entries could not be read. Original files will be backed up on save."
        self.controller = QueueController(self.jobs, self.settings, self)
        self.controller.changed.connect(self.job_changed)
        self.controller.state_changed.connect(self.state_changed)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(600)
        self.save_timer.timeout.connect(self.save_state)
        self.build_ui()
        for job in self.jobs:
            self.add_row(job)
        self.state_changed()
        if self.storage.warning:
            self.show_notice(self.storage.warning)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.add_links)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)
        if check_system:
            QTimer.singleShot(150, self.check_tools)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 26, 30, 22)
        layout.setSpacing(18)
        header = QHBoxLayout()
        mark = QLabel("↓")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(52, 52)
        mark.setStyleSheet("background: #79ddc2; color: #10221e; font-size: 33px; font-weight: 600; border-radius: 15px;")
        header.addWidget(mark)
        brand = QVBoxLayout()
        brand.setSpacing(3)
        brand.addWidget(heading("YouTube Downloader", "title"))
        brand.addWidget(note("A little less waiting. A lot more watching."))
        header.addLayout(brand)
        header.addStretch()
        self.settings_button = button("⚙  Settings", self.open_settings)
        header.addWidget(self.settings_button)
        layout.addLayout(header)

        self.notice = QLabel()
        self.notice.setObjectName("warning")
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.hide()
        layout.addWidget(self.notice)

        add_card = QFrame()
        add_card.setObjectName("card")
        add_layout = QVBoxLayout(add_card)
        add_layout.setContentsMargins(20, 17, 20, 17)
        add_layout.setSpacing(10)
        add_heading = QHBoxLayout()
        add_heading.addWidget(heading("What would you like to download?"))
        add_heading.addStretch()
        add_heading.addWidget(button("Import links…", self.import_links, "quiet"))
        add_layout.addLayout(add_heading)
        self.link_input = QPlainTextEdit()
        self.link_input.setPlaceholderText("Paste video or playlist links here, one per line…")
        self.link_input.setFixedHeight(78)
        add_layout.addWidget(self.link_input)
        add_footer = QHBoxLayout()
        shortcut_note = note("Add as many as you like.  ⌘ + Return to add.")
        shortcut_note.setWordWrap(False)
        add_footer.addWidget(shortcut_note)
        add_footer.addStretch()
        add_footer.addWidget(button("+  Add to queue", self.add_links, "primary"))
        add_layout.addLayout(add_footer)
        layout.addWidget(add_card)

        preset = QHBoxLayout()
        preset.addWidget(heading("Download as"))
        self.mode = QComboBox()
        self.mode.addItems(["Video + audio", "Audio only"])
        self.mode.setCurrentText(self.settings.mode)
        self.mode.currentTextChanged.connect(self.mode_changed)
        self.mode.setMinimumWidth(160)
        preset.addWidget(self.mode)
        self.quality = QLabel()
        self.quality.setObjectName("badge")
        preset.addWidget(self.quality)
        preset.addStretch()
        self.cookie_summary = note("")
        self.cookie_summary.setWordWrap(False)
        preset.addWidget(self.cookie_summary)
        layout.addLayout(preset)

        queue_header = QHBoxLayout()
        queue_header.addWidget(heading("Download queue"))
        self.summary = note("")
        self.summary.setWordWrap(False)
        queue_header.addWidget(self.summary)
        queue_header.addStretch()
        self.retry = button("Retry failed", self.retry_failed, "quiet")
        queue_header.addWidget(self.retry)
        self.clear = button("Clear finished", self.clear_finished, "quiet")
        queue_header.addWidget(self.clear)
        layout.addLayout(queue_header)

        self.queue_stack = QStackedWidget()
        empty = QFrame()
        empty.setObjectName("card")
        empty_layout = QVBoxLayout(empty)
        empty_layout.addStretch()
        arrow = heading("↓", "title")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet("font-size: 42px; color: #506276;")
        empty_layout.addWidget(arrow)
        empty_title = heading("Your queue starts here")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_note = note("Paste your links above. We’ll take care of the best available quality.")
        empty_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_note)
        empty_layout.addStretch()
        self.queue_stack.addWidget(empty)
        self.queue = QListWidget()
        self.queue.setObjectName("queue")
        self.queue.setSpacing(6)
        self.queue.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.queue.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.queue_stack.addWidget(self.queue)
        layout.addWidget(self.queue_stack, 1)

        destination_card = QFrame()
        destination_card.setObjectName("card")
        destination_layout = QHBoxLayout(destination_card)
        destination_layout.setContentsMargins(17, 12, 17, 12)
        destination_text = QVBoxLayout()
        destination_text.setSpacing(3)
        destination_text.addWidget(heading("SAVE TO", "eyebrow"))
        self.destination_label = QLabel()
        self.destination_label.setTextFormat(Qt.TextFormat.PlainText)
        destination_text.addWidget(self.destination_label)
        destination_layout.addLayout(destination_text, 1)
        destination_layout.addWidget(button("Change…", self.change_destination, "quiet"))
        destination_layout.addWidget(button("Open folder ↗", self.open_folder, "quiet"))
        layout.addWidget(destination_card)

        actions = QHBoxLayout()
        self.system_label = note("Checking system tools…")
        self.system_label.setTextFormat(Qt.TextFormat.PlainText)
        actions.addWidget(self.system_label, 1)
        self.update_button = button("Check & update", lambda: self.check_tools(True), "quiet")
        actions.addWidget(self.update_button)
        self.pause = button("Pause queue", self.pause_queue)
        self.pause.setToolTip("Let active downloads finish; hold the remaining queue.")
        actions.addWidget(self.pause)
        self.stop = button("Stop", self.controller.stop)
        self.stop.setToolTip("Cancel active downloads and hold the queue. Partial files can resume on retry.")
        actions.addWidget(self.stop)
        self.start = button("↓  Download queue", self.start_queue, "primary")
        self.start.setMinimumWidth(170)
        self.start.setMinimumHeight(43)
        actions.addWidget(self.start)
        layout.addLayout(actions)
        self.refresh_preferences()

    def show_notice(self, message):
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

    def refresh_preferences(self):
        self.quality.setText("Best audio" if self.settings.mode == "Audio only" else self.settings.resolution)
        if self.settings.only_extra:
            self.quality.setText("Advanced arguments")
        source = self.settings.cookie_source
        self.cookie_summary.setText("Cookies: " + (self.settings.browser.title() if source == "Browser" else "File" if source == "Cookie file" else "Off"))
        self.destination_label.setText(self.destination_label.fontMetrics().elidedText(self.settings.destination, Qt.TextElideMode.ElideMiddle, max(400, self.width() - 380)))
        self.destination_label.setToolTip(self.settings.destination)
        self.controller.settings = self.settings

    def mode_changed(self, value):
        self.settings.mode = value
        self.refresh_preferences()
        self.save_timer.start()

    def add_links(self):
        valid, invalid = parse_links(self.link_input.toPlainText())
        existing = {j.url for j in self.jobs if j.status in ACTIVE | {"Queued"}}
        count = 0
        for url in valid:
            if url not in existing:
                job = Job(url)
                self.jobs.append(job)
                self.add_row(job)
                count += 1
        self.link_input.setPlainText("\n".join(invalid))
        if invalid:
            self.show_notice(f"Added {count} link(s). {len(invalid)} invalid entry/entries remain above. Use complete http:// or https:// links.")
        elif count:
            self.show_notice(self.tool_status.warning)
        elif valid:
            self.show_notice("Those links are already pending or downloading.")
        self.state_changed()
        self.save_timer.start()
        self.controller.pump()

    def import_links(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import a list of links", "", "Text files (*.txt);;All files (*)")
        if path:
            try:
                # Avoid loading arbitrary large files into a text widget.
                if Path(path).stat().st_size > 5_000_000:
                    raise ValueError("Choose a text file smaller than 5 MB.")
                text = Path(path).read_text(encoding="utf-8-sig")
                links = "\n".join(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
                self.link_input.appendPlainText(links)
                self.add_links()
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Could not import links", str(error))

    def add_row(self, job):
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 120))
        row = JobRow(job)
        row.details_requested.connect(self.open_details)
        row.action_requested.connect(self.row_action)
        self.queue.addItem(item)
        self.queue.setItemWidget(item, row)
        self.rows[job.id] = (item, row)

    def job_changed(self, job):
        if job.id in self.rows:
            self.rows[job.id][1].refresh()
        self.save_timer.start()
        self.state_changed()

    def state_changed(self):
        active = len(self.controller.workers)
        pending = sum(j.status == "Queued" for j in self.jobs)
        completed = sum(j.status == "Completed" for j in self.jobs)
        self.summary.setText(f"{pending} queued  ·  {active} active  ·  {completed} saved")
        self.queue_stack.setCurrentIndex(1 if self.jobs else 0)
        self.start.setEnabled(self.tool_status.ready and pending > 0 and not self.controller.running and not self.checker_running())
        self.start.setText("↓  Resume queue" if active and not self.controller.running else "↓  Download queue")
        self.pause.setEnabled(self.controller.running)
        self.stop.setEnabled(bool(active))
        self.retry.setEnabled(any(j.status in RETRYABLE for j in self.jobs))
        self.clear.setEnabled(any(j.status not in ACTIVE | {"Queued"} for j in self.jobs))
        self.update_button.setEnabled(not self.checker_running() and not active)
        self.settings_button.setEnabled(not active)
        self.mode.setEnabled(not active)
        # A tool check never starts or resumes media downloads on its own.

    def checker_running(self):
        return self.checker is not None and self.checker.isRunning()

    def check_tools(self, force=None):
        if self.checker_running() or self.controller.workers:
            return
        self.show_notice("")
        self.checker = SystemCheck(self.settings.auto_update if force is None else force, self)
        self.checker.message.connect(self.system_label.setText)
        self.checker.result.connect(self.tools_ready)
        self.checker.finished.connect(self.check_finished)
        self.checker.start()
        self.state_changed()

    def tools_ready(self, status):
        self.tool_status = status
        self.controller.executable = status.executable or ""
        self.system_label.setText(status.message)
        self.system_label.setToolTip(f"Executable: {status.executable or 'Missing'}\nLatest stable: {status.latest or 'Unverified'}")
        self.show_notice(status.warning)
        self.state_changed()

    def check_finished(self):
        self.state_changed()
        if self.closing and not self.controller.workers:
            QTimer.singleShot(0, self.close)

    def start_queue(self):
        try:
            build_arguments(self.settings, "https://example.com/video")
        except ValueError as error:
            QMessageBox.warning(self, "Check your settings", str(error))
            return
        self.controller.start()

    def pause_queue(self):
        self.controller.pause()
        self.show_notice("Queue paused. Active downloads will finish; remaining links will wait for Download queue.")

    def row_action(self, job):
        if job.status in ACTIVE | {"Queued"}:
            self.controller.cancel(job)
        elif job.status in RETRYABLE:
            job.status, job.detail, job.progress = "Queued", "Ready to retry · Partial files will resume", 0
            job.log.clear()
            self.job_changed(job)
            self.controller.pump()
        elif job.files:
            existing = next((path for path in job.files if Path(path).exists()), None)
            if existing:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(existing).parent)))
            else:
                self.show_notice("The saved files have moved or been removed. The download folder can be opened below.")
        else:
            self.remove_job(job)

    def retry_failed(self):
        for job in self.jobs:
            if job.status in RETRYABLE:
                job.status, job.detail, job.progress = "Queued", "Ready to retry · Partial files will resume", 0
                job.log.clear()
                self.rows[job.id][1].refresh()
        self.save_timer.start()
        self.controller.pump()
        self.state_changed()

    def remove_job(self, job):
        if job.status in ACTIVE:
            return
        item, row = self.rows.pop(job.id)
        self.queue.takeItem(self.queue.row(item))
        row.deleteLater()
        self.jobs.remove(job)
        self.state_changed()
        self.save_timer.start()

    def clear_finished(self):
        for job in list(self.jobs):
            if job.status not in ACTIVE | {"Queued"}:
                self.remove_job(job)

    def open_details(self, job):
        DetailsDialog(job, self.controller, self).exec()

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self.tool_status.help_text, self.controller.executable, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.result_settings
            self.mode.blockSignals(True)
            self.mode.setCurrentText(self.settings.mode)
            self.mode.blockSignals(False)
            self.refresh_preferences()
            self.save_state()

    def change_destination(self):
        path = QFileDialog.getExistingDirectory(self, "Download folder", self.settings.destination)
        if path:
            self.settings.destination = path
            self.refresh_preferences()
            self.save_state()

    def open_folder(self):
        path = Path(self.settings.destination).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except OSError as error:
            QMessageBox.warning(self, "Could not open folder", str(error))

    def save_state(self):
        try:
            self.storage.write("settings.json", asdict(self.settings))
            self.storage.write("queue.json", [job.to_dict() for job in self.jobs])
        except OSError as error:
            if not self.storage_failed:
                self.storage_failed = True
                self.show_notice("Settings and queue could not be saved: " + str(error))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "destination_label"):
            self.refresh_preferences()

    def closeEvent(self, event):
        if self.controller.workers:
            if not self.closing:
                answer = QMessageBox.question(self, "Downloads are active", "Stop downloads and close? Partial files will be retained so you can retry later.",
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                              QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
                self.closing = True
                self.controller.stop()
                self.controller.state_changed.connect(self.finish_close)
            event.ignore()
            return
        if self.checker_running():
            self.closing = True
            self.checker.requestInterruption()
            self.system_label.setText("Stopping tool check before closing…")
            event.ignore()
            return
        self.save_timer.stop()
        self.save_state()
        event.accept()

    def finish_close(self):
        if self.closing and not self.controller.workers:
            QTimer.singleShot(0, self.close)
