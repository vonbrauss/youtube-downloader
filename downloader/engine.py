from __future__ import annotations

import codecs
import json
import os
from pathlib import Path
import signal

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from .model import ACTIVE, Job, Settings, build_arguments, format_bytes
from .system import system_environment


class DownloadProcess(QObject):
    changed = Signal(object)
    logged = Signal(object, str)
    finished = Signal(object)

    def __init__(self, job: Job, executable: str, settings: Settings, parent=None):
        super().__init__(parent)
        self.job = job
        self.executable = executable
        self.settings = settings
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment()
        for key, value in system_environment().items():
            environment.insert(key, value)
        self.process.setProcessEnvironment(environment)
        parameters = QProcess.UnixProcessParameters()
        parameters.flags = QProcess.UnixProcessFlag.CreateNewSession
        self.process.setUnixProcessParameters(parameters)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.started.connect(self.started)
        self.process.finished.connect(self.complete)
        self.process.errorOccurred.connect(self.process_error)
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.buffer = ""
        self.cancelled = False
        self.done = False
        self.error_seen = False
        self.pid = 0
        self.kill_timer = QTimer(self)
        self.kill_timer.setSingleShot(True)
        self.kill_timer.setInterval(3500)
        self.kill_timer.timeout.connect(self.force_kill)

    def start(self):
        try:
            arguments = build_arguments(self.settings, self.job.url)
            Path(self.settings.destination).expanduser().mkdir(parents=True, exist_ok=True)
            self.process.setWorkingDirectory(str(Path(self.settings.destination).expanduser()))
        except (OSError, ValueError) as error:
            self.job.detail = str(error)
            self.complete(1, QProcess.ExitStatus.NormalExit)
            return
        self.job.status, self.job.detail = "Starting", "Reading video information…"
        self.changed.emit(self.job)
        self.process.start(self.executable, arguments)

    def started(self):
        self.pid = self.process.processId()

    def append_log(self, line: str):
        self.job.log.append(line)
        self.logged.emit(self.job, line)

    def read_output(self):
        self.buffer += self.decoder.decode(bytes(self.process.readAllStandardOutput()))
        self.buffer = self.buffer.replace("\r", "\n")
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.parse_line(line)
        # Prevent an external command with an unbounded line from exhausting memory.
        if len(self.buffer) > 65536:
            self.append_log(self.buffer[:65536])
            self.buffer = ""

    def parse_line(self, line: str):
        if not line.strip():
            return
        try:
            if line.startswith("__YTDL_PROGRESS__"):
                data = json.loads(line.removeprefix("__YTDL_PROGRESS__"))
                total = data.get("total") or data.get("estimate") or 0
                downloaded = data.get("downloaded") or 0
                self.job.progress = min(100.0, downloaded / total * 100) if total else 0
                self.job.status = "Processing" if data.get("status") == "finished" else "Downloading"
                eta = data.get("eta")
                remaining = f"{int(eta)//60}:{int(eta)%60:02d} left" if isinstance(eta, (int, float)) else "Calculating time…"
                self.job.detail = f"{format_bytes(downloaded)} / {format_bytes(total)}   ·   {format_bytes(data.get('speed'))}/s   ·   {remaining}"
            elif line.startswith("__YTDL_TITLE__"):
                self.job.title = str(json.loads(line.removeprefix("__YTDL_TITLE__")))
                self.job.progress = 0
                self.job.detail = "Preparing next file…"
            elif line.startswith("__YTDL_PROCESS__"):
                self.job.status, self.job.detail = "Processing", "Merging audio and video / finalizing file…"
            elif line.startswith("__YTDL_FILE__"):
                path = json.loads(line.removeprefix("__YTDL_FILE__"))
                if isinstance(path, str) and Path(path).is_file() and path not in self.job.files:
                    self.job.files.append(path)
                self.append_log("Saved: " + str(path))
            else:
                self.append_log(line)
                if line.startswith("ERROR:"):
                    self.error_seen = True
                    self.job.detail = line.removeprefix("ERROR:").strip()
                elif line.startswith("WARNING:"):
                    self.job.detail = line
            if self.cancelled:
                self.job.status, self.job.detail = "Stopping", "Stopping this download…"
            self.changed.emit(self.job)
        except (ValueError, TypeError, ZeroDivisionError, OverflowError):
            self.append_log(line)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.job.detail = self.process.errorString()
            self.append_log(self.job.detail)
            self.complete(1, QProcess.ExitStatus.NormalExit)

    def complete(self, code: int, exit_status):
        if self.done:
            return
        self.done = True
        self.kill_timer.stop()
        self.read_output()
        self.buffer += self.decoder.decode(b"", final=True)
        if self.buffer:
            self.parse_line(self.buffer)
        if self.cancelled:
            self.job.status, self.job.detail = "Cancelled", "Partial files retained · Retry to resume"
        elif code != 0 or exit_status == QProcess.ExitStatus.CrashExit or self.error_seen:
            self.job.status = "Failed"
            if not self.job.detail or self.job.detail.startswith(("Reading", "Preparing", "Merging")):
                self.job.detail = f"yt-dlp exited with code {code} · View details"
        else:
            self.job.status = "Completed" if self.job.files else "Finished"
            self.job.progress = 100
            self.job.detail = (f"{len(self.job.files)} file(s) available · Ready to open" if self.job.files
                               else "Command finished · No media files reported (see details)")
        self.changed.emit(self.job)
        self.finished.emit(self.job)

    def signal_group(self, sig: int):
        if self.pid and not self.done:
            try:
                os.killpg(self.pid, sig)
            except ProcessLookupError:
                pass
            except OSError:
                self.process.kill() if sig == signal.SIGKILL else self.process.terminate()

    def cancel(self):
        if self.done:
            return
        self.cancelled = True
        self.job.status, self.job.detail = "Stopping", "Stopping this download…"
        self.changed.emit(self.job)
        if self.pid:
            self.signal_group(signal.SIGTERM)
        else:
            self.process.kill()
        self.kill_timer.start()

    def force_kill(self):
        self.signal_group(signal.SIGKILL)


class QueueController(QObject):
    changed = Signal(object)
    logged = Signal(object, str)
    state_changed = Signal()

    def __init__(self, jobs: list[Job], settings: Settings, parent=None):
        super().__init__(parent)
        self.jobs = jobs
        self.settings = settings
        self.executable = ""
        self.running = False
        self.workers: dict[str, DownloadProcess] = {}

    def start(self):
        if not self.executable:
            return
        self.running = True
        self.pump()

    def pump(self):
        if self.running:
            while len(self.workers) < self.settings.parallel:
                job = next((j for j in self.jobs if j.status == "Queued"), None)
                if not job:
                    break
                snapshot = Settings.from_dict(vars(self.settings))
                worker = DownloadProcess(job, self.executable, snapshot, self)
                self.workers[job.id] = worker
                worker.changed.connect(self.changed)
                worker.logged.connect(self.logged)
                worker.finished.connect(self.worker_finished)
                worker.start()
            if not self.workers and not any(j.status == "Queued" for j in self.jobs):
                self.running = False
        self.state_changed.emit()

    def worker_finished(self, job: Job):
        worker = self.workers.pop(job.id, None)
        if worker:
            worker.deleteLater()
        QTimer.singleShot(0, self.pump)

    def pause(self):
        self.running = False
        self.state_changed.emit()

    def stop(self):
        self.pause()
        for worker in list(self.workers.values()):
            worker.cancel()

    def cancel(self, job: Job):
        worker = self.workers.get(job.id)
        if worker:
            worker.cancel()
        elif job.status == "Queued":
            job.status, job.detail = "Cancelled", "Removed from the pending queue · Retry to resume"
            self.changed.emit(job)
            self.state_changed.emit()
