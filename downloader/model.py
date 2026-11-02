from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field, fields
import json
import math
import os
from pathlib import Path
import re
import shlex
import uuid
from urllib.parse import urlparse

ACTIVE = {"Starting", "Downloading", "Processing", "Stopping"}
RETRYABLE = {"Failed", "Cancelled", "Interrupted"}


@dataclass
class Settings:
    destination: str = str(Path.home() / "Downloads" / "YouTube Downloader")
    mode: str = "Video + audio"
    resolution: str = "Highest available"
    container: str = "Automatic"
    audio_format: str = "Original"
    parallel: int = 2
    playlist: bool = False
    auto_update: bool = True
    cookie_source: str = "None"
    browser: str = "chrome"
    profile: str = ""
    keyring: str = ""
    cookie_container: str = ""
    cookie_file: str = ""
    template: str = "%(title).180B [%(id)s].%(ext)s"
    subtitles: bool = False
    auto_subtitles: bool = False
    subtitle_languages: str = "en.*"
    embed_subtitles: bool = False
    metadata: bool = True
    thumbnail: bool = False
    rate_limit: str = ""
    retries: int = 10
    fragments: int = 4
    archive: str = ""
    sponsorblock: str = ""
    extra: str = ""
    only_extra: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        if not isinstance(data, dict):
            raise ValueError("Settings must be a JSON object")
        known = {f.name for f in fields(cls)}
        result = cls(**{k: v for k, v in data.items() if k in known})
        # Local files may be edited outside the app; reject bad types early.
        for f in fields(cls):
            if type(getattr(result, f.name)) is not type(getattr(cls(), f.name)):
                raise ValueError(f"Invalid setting: {f.name}")
        result.parallel = max(1, min(8, result.parallel))
        result.fragments = max(1, min(32, result.fragments))
        result.retries = max(0, min(100, result.retries))
        return result


def browser_spec(settings: Settings) -> str:
    result = settings.browser
    if settings.keyring.strip():
        result += "+" + settings.keyring.strip()
    if settings.profile.strip():
        result += ":" + settings.profile.strip()
    if settings.cookie_container.strip():
        result += "::" + settings.cookie_container.strip()
    return result


def build_arguments(settings: Settings, url: str) -> list[str]:
    """Argument array only; never execute a shell or import yt_dlp."""
    extra = shlex.split(settings.extra, posix=True)
    args = ["--ignore-config"]
    if not settings.only_extra:
        args += ["--no-update", "--no-simulate", "--continue", "--no-overwrites",
                 "--yes-playlist" if settings.playlist else "--no-playlist",
                 "--paths", str(Path(settings.destination).expanduser()),
                 "--output", settings.template]
        if settings.mode == "Audio only":
            args += ["--format", "bestaudio/best"]
            if settings.audio_format != "Original":
                args += ["--extract-audio", "--audio-format", settings.audio_format.lower(),
                         "--audio-quality", "0"]
        else:
            limit = "" if settings.resolution == "Highest available" else f"[height<=?{int(settings.resolution.rstrip('p'))}]"
            args += ["--format", f"bestvideo{limit}+bestaudio/best{limit}",
                     "--format-sort", "res,fps", "--format-sort-force"]
            if settings.container != "Automatic":
                args += ["--merge-output-format", settings.container.lower(),
                         "--remux-video", settings.container.lower()]
        if settings.cookie_source == "Browser":
            args += ["--cookies-from-browser", browser_spec(settings)]
        elif settings.cookie_source == "Cookie file":
            if not Path(settings.cookie_file).expanduser().is_file():
                raise ValueError("Choose an existing Netscape cookies file in Settings → Cookies.")
            args += ["--cookies", str(Path(settings.cookie_file).expanduser())]
        if settings.cookie_source != "None":
            # Authenticated default clients can expose only a 360p combined stream
            # under YouTube's SABR experiment. Keep the defaults (including private
            # and restricted content support) and add the cookie-compatible HLS
            # client. This argument affects only YouTube, never other extractors.
            # Native advanced extractor arguments come last and can override it.
            args += ["--extractor-args", "youtube:player_client=default,web_safari"]
        if settings.subtitles:
            args += ["--write-subs", "--sub-langs", settings.subtitle_languages]
        if settings.auto_subtitles:
            args += ["--write-auto-subs", "--sub-langs", settings.subtitle_languages]
        if settings.embed_subtitles:
            args += ["--embed-subs"]
        if settings.metadata:
            args += ["--embed-metadata"]
        if settings.thumbnail:
            args += ["--embed-thumbnail"]
        if settings.rate_limit.strip():
            args += ["--limit-rate", settings.rate_limit.strip()]
        args += ["--retries", str(settings.retries), "--fragment-retries", str(settings.retries),
                 "--concurrent-fragments", str(settings.fragments)]
        if settings.archive.strip():
            args += ["--download-archive", str(Path(settings.archive).expanduser())]
        if settings.sponsorblock.strip():
            args += ["--sponsorblock-remove", settings.sponsorblock.strip()]
    # Machine-readable callbacks. A playlist remains one queue item, with per-file progress.
    args += ["--newline", "--progress", "--progress-delta", "0.3", "--no-colors",
             "--progress-template", 'download:__YTDL_PROGRESS__{"status":%(progress.status)j,"downloaded":%(progress.downloaded_bytes)j,"total":%(progress.total_bytes)j,"estimate":%(progress.total_bytes_estimate)j,"speed":%(progress.speed)j,"eta":%(progress.eta)j}',
             "--progress-template", "postprocess:__YTDL_PROCESS__%(progress.status)j",
             "--print", "before_dl:__YTDL_TITLE__%(title)j",
             "--print", "before_dl:__YTDL_QUALITY__%(resolution)j",
             "--print", "after_move:__YTDL_FILE__%(filepath)j"]
    # Advanced options deliberately come last, so every native option is available.
    args += extra + ["--", url]
    return args


def parse_links(text: str) -> tuple[list[str], list[str]]:
    valid, invalid = [], []
    for value in text.split():
        url = urlparse(value)
        if url.scheme.lower() in {"http", "https"} and url.hostname and not any(c in value for c in '\x00\r\n'):
            if value not in valid:
                valid.append(value)
        else:
            invalid.append(value)
    return valid, invalid


@dataclass
class Job:
    url: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    status: str = "Queued"
    progress: float = 0.0
    detail: str = "Ready when you are"
    files: list[str] = field(default_factory=list)
    resolution: str = ""
    log: deque[str] = field(default_factory=lambda: deque(maxlen=600), repr=False)

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "log"}

    @classmethod
    def from_dict(cls, data: dict) -> Job:
        if not isinstance(data, dict):
            raise ValueError("Queue entries must be JSON objects")
        known = {f.name for f in fields(cls)} - {"log"}
        result = cls(**{k: v for k, v in data.items() if k in known})
        if not isinstance(result.url, str) or not isinstance(result.id, str) or not result.id:
            raise ValueError("Invalid queue entry")
        if any(not isinstance(getattr(result, key), str) for key in ("title", "status", "detail", "resolution")):
            raise ValueError("Invalid queue text")
        if not isinstance(result.files, list) or any(not isinstance(path, str) for path in result.files):
            raise ValueError("Invalid saved file list")
        if not isinstance(result.progress, (int, float)) or not math.isfinite(result.progress):
            raise ValueError("Invalid queue progress")
        result.progress = max(0, min(100, result.progress))
        if result.status not in ACTIVE | RETRYABLE | {"Queued", "Completed", "Finished"}:
            raise ValueError("Unknown queue status")
        if result.status in ACTIVE:
            result.status, result.detail = "Interrupted", "Interrupted last session · Retry to resume"
        return result


class Storage:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or Path.home() / "Library" / "Application Support" / "YouTube Downloader"
        self.warning = ""

    def read(self, filename: str, default):
        path = self.directory / filename
        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            return default
        except (OSError, ValueError):
            self.warning = f"Could not read {filename}; its original contents have been preserved."
            return default

    def write(self, filename: str, value):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / filename
        # Keep a recovery copy before replacing an existing file.
        if path.exists():
            backup = self.directory / (filename + ".backup")
            backup.write_bytes(path.read_bytes())
            backup.chmod(0o600)
        temporary = self.directory / (filename + ".tmp")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temporary.chmod(0o600)
        os.replace(temporary, path)


@dataclass
class Option:
    signature: str
    description: str
    category: str

    @property
    def flag(self) -> str:
        names = re.findall(r"(?<!\w)--[\w-]+", self.signature)
        return names[0] if names else self.signature.split()[0].rstrip(",")


def parse_help(text: str) -> list[Option]:
    options: list[Option] = []
    category = "General"
    current = None
    for line in text.splitlines():
        if re.match(r"^  \S.*:$", line):
            category = line.strip().rstrip(":")
            current = None
        elif re.match(r"^    -", line):
            chunks = re.split(r"\s{2,}", line.strip(), maxsplit=1)
            current = Option(chunks[0], chunks[1] if len(chunks) > 1 else "", category)
            options.append(current)
        elif current and line.startswith("        "):
            current.description += " " + line.strip()
        else:
            current = None
    return options


def format_bytes(value: float | None) -> str:
    if not value:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"
