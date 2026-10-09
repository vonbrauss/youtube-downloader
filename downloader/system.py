from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal


def system_environment() -> dict[str, str]:
    env = os.environ.copy()
    # Finder-launched applications do not inherit an interactive shell's PATH.
    paths = ["/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin"),
             "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    env["PATH"] = os.pathsep.join(dict.fromkeys(paths + env.get("PATH", "").split(os.pathsep)))
    env["PYTHONUNBUFFERED"] = "1"
    env["HOMEBREW_NO_AUTO_UPDATE"] = "1"
    env["HOMEBREW_NO_ENV_HINTS"] = "1"
    return env


def find_tool(name: str) -> str | None:
    return shutil.which(name, path=system_environment()["PATH"])


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value.split("_")[0]))


@dataclass
class ToolStatus:
    executable: str | None = None
    version: str = ""
    latest: str = ""
    ready: bool = False
    message: str = "Checking system tools…"
    warning: str = ""
    help_text: str = ""


class SystemCheck(QThread):
    message = Signal(str)
    result = Signal(object)

    def __init__(self, update: bool = True, parent=None):
        super().__init__(parent)
        self.update = update
        self.env = system_environment()

    def command(self, arguments: list[str], timeout: int = 60) -> str:
        if self.isInterruptionRequested():
            raise RuntimeError("Tool check cancelled")
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, env=self.env, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while True:
                if self.isInterruptionRequested():
                    raise RuntimeError("Tool check cancelled")
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"{Path(arguments[0]).name} timed out. Try Check & update again.")
                try:
                    output, _ = process.communicate(timeout=0.3)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            import signal
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
            raise
        if process.returncode:
            raise RuntimeError(output.strip()[-1600:] or "System tool returned an error.")
        return output.strip()

    def latest_release(self) -> str:
        request = Request("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
                          headers={"User-Agent": "YouTubeDownloader/0.1", "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=15) as response:
            return json.load(response)["tag_name"].lstrip("v")

    def run(self):
        status = ToolStatus()
        warnings = []
        brew = find_tool("brew")
        try:
            if self.update:
                if not brew:
                    warnings.append("Homebrew is missing. Install it from brew.sh to enable automatic updates.")
                else:
                    self.message.emit("Refreshing Homebrew…")
                    self.command([brew, "update"], timeout=300)
                    self.message.emit("Checking yt-dlp, FFmpeg and Deno…")
                    info = json.loads(self.command([brew, "info", "--json=v2", "yt-dlp", "ffmpeg", "deno"], timeout=90))
                    for formula in info["formulae"]:
                        name = formula["name"]
                        if not formula.get("installed"):
                            self.message.emit(f"Installing {name} through Homebrew…")
                            self.command([brew, "install", name], timeout=1200)
                        elif name == "yt-dlp" and formula.get("outdated"):
                            self.message.emit("Updating yt-dlp through Homebrew…")
                            self.command([brew, "upgrade", "yt-dlp"], timeout=1200)
            executable = find_tool("yt-dlp")
            if executable:
                status.executable = executable
                status.version = self.command([executable, "--ignore-config", "--version"])
                status.help_text = self.command([executable, "--ignore-config", "--help"])
                try:
                    status.latest = self.latest_release()
                    if version_tuple(status.version) < version_tuple(status.latest):
                        warnings.append(f"Latest stable yt-dlp is {status.latest}. Installed: {status.version}. "
                                        "Homebrew may not have published it yet; Check & update to retry.")
                except Exception:
                    warnings.append("Latest release could not be verified. Check your connection and retry.")
            missing = [name for name in ("yt-dlp", "ffmpeg", "ffprobe", "deno") if not find_tool(name)]
            status.ready = not missing
            status.message = f"yt-dlp {status.version} · System installation" if status.ready else "Missing: " + ", ".join(missing)
            if missing:
                warnings.append("Use Check & update to install system tools through Homebrew.")
        except Exception as error:
            warnings.append(str(error))
            # An update outage should not break an otherwise usable installation.
            status.executable = find_tool("yt-dlp")
            if status.executable:
                try:
                    status.version = self.command([status.executable, "--ignore-config", "--version"])
                    status.help_text = self.command([status.executable, "--ignore-config", "--help"])
                except Exception as probe_error:
                    warnings.append(str(probe_error))
                    status.executable = None
            status.ready = bool(status.executable and all(find_tool(n) for n in ("ffmpeg", "ffprobe", "deno")))
            status.message = f"yt-dlp {status.version} · Update check failed" if status.ready else "System tools need attention"
        status.warning = "\n".join(warnings)
        self.result.emit(status)
