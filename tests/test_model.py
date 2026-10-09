from dataclasses import asdict
from pathlib import Path
import subprocess

import pytest

from downloader.model import Job, Settings, Storage, browser_spec, build_arguments, parse_help, parse_links
from downloader.system import find_tool, version_tuple


def test_highest_quality_and_advanced_overrides():
    arguments = build_arguments(Settings(), "https://example.com/video")
    assert arguments[arguments.index("--format") + 1] == "bestvideo+bestaudio/best"
    assert arguments[arguments.index("--format-sort") + 1] == "res,fps"
    assert "--format-sort-force" in arguments
    assert "--no-playlist" in arguments
    assert "--extract-audio" not in arguments
    assert arguments[-2:] == ["--", "https://example.com/video"]
    custom = Settings(extra='--format "18" --proxy "http://localhost:8080"')
    command = build_arguments(custom, "https://example.com")
    assert command[-6:] == ["--format", "18", "--proxy", "http://localhost:8080", "--", "https://example.com"]


def test_resolution_audio_and_raw_mode():
    command = build_arguments(Settings(resolution="1080p"), "https://example.com")
    assert command[command.index("--format") + 1] == "bestvideo[height<=?1080]+bestaudio/best[height<=?1080]"
    audio = build_arguments(Settings(mode="Audio only", audio_format="MP3"), "https://example.com")
    assert audio[audio.index("--audio-format") + 1] == "mp3"
    raw = build_arguments(Settings(only_extra=True, extra="--list-formats --simulate"), "https://example.com")
    assert "--format" not in raw
    assert "--paths" not in raw
    assert "--no-simulate" not in raw
    assert "--simulate" in raw


def test_cookies_and_no_shell_interpolation(tmp_path):
    settings = Settings(cookie_source="Browser", browser="firefox", profile="Profile 1", cookie_container="Work")
    assert browser_spec(settings) == "firefox:Profile 1::Work"
    args = build_arguments(settings, "https://example.com")
    assert args[args.index("--cookies-from-browser") + 1] == "firefox:Profile 1::Work"
    settings.extra = '--output "$(touch /tmp/should-not-exist).%(ext)s"'
    assert "$(touch /tmp/should-not-exist).%(ext)s" in build_arguments(settings, "https://example.com")
    settings.extra = '"unterminated'
    with pytest.raises(ValueError):
        build_arguments(settings, "https://example.com")
    with pytest.raises(ValueError):
        build_arguments(Settings(cookie_source="Cookie file", cookie_file=str(tmp_path / "missing")), "https://example.com")


def test_links_and_recovery(tmp_path):
    links, bad = parse_links("https://youtu.be/a\nhttps://youtu.be/a\n--exec http:// https://example.com/watch?v=x&list=y")
    assert links == ["https://youtu.be/a", "https://example.com/watch?v=x&list=y"]
    assert bad == ["--exec", "http://"]
    storage = Storage(tmp_path)
    job = Job("https://example.com", status="Downloading", progress=42)
    storage.write("queue.json", [job.to_dict()])
    restored = Job.from_dict(storage.read("queue.json", [])[0])
    assert restored.status == "Interrupted"
    storage.write("queue.json", [])
    assert (tmp_path / "queue.json.backup").exists()
    assert (tmp_path / "queue.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        Settings.from_dict({"parallel": "not a number"})
    for malformed in ([], "wrong structure", None):
        with pytest.raises(ValueError):
            Settings.from_dict(malformed)
        with pytest.raises(ValueError):
            Job.from_dict(malformed)
    with pytest.raises(ValueError):
        Job.from_dict({"url": "https://example.com", "progress": float("nan")})


def test_complete_live_help_catalog():
    executable = find_tool("yt-dlp")
    if not executable:
        pytest.skip("System yt-dlp is unavailable")
    help_text = subprocess.check_output([executable, "--ignore-config", "--help"], text=True)
    options = parse_help(help_text)
    signatures = [line.strip().split("  ")[0] for line in help_text.splitlines() if line.startswith("    -")]
    assert len(options) == len(signatures)
    assert len(options) > 250
    assert any(o.flag == "--cookies-from-browser" for o in options)
    assert any(o.flag == "--exec" for o in options)
    assert len({o.category for o in options}) > 10
    assert version_tuple("2026.8.19_2") == version_tuple("2026.08.19")
