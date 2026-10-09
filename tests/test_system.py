import json

from downloader.system import SystemCheck


class FakeCheck(SystemCheck):
    def __init__(self, installed=True, outdated=False, latest="2026.08.19"):
        super().__init__(update=True)
        self.installed = installed
        self.outdated = outdated
        self.latest = latest
        self.commands = []

    def command(self, arguments, timeout=60):
        self.commands.append(arguments)
        if "info" in arguments:
            return json.dumps({"formulae": [{"name": n, "installed": [{}] if self.installed else [], "outdated": self.outdated} for n in ("yt-dlp", "ffmpeg", "deno")]})
        if "--version" in arguments:
            return "2026.08.19"
        return ""

    def latest_release(self):
        return self.latest


def test_upgrade_only_outdated_ytdlp(app, monkeypatch):
    monkeypatch.setattr("downloader.system.find_tool", lambda name: "/brew/bin/" + name)
    check = FakeCheck(outdated=True)
    results = []
    check.result.connect(results.append)
    check.run()
    assert ["/brew/bin/brew", "upgrade", "yt-dlp"] in check.commands
    assert not any("upgrade" in c and "ffmpeg" in c for c in check.commands)
    assert results[0].ready
    assert not results[0].warning


def test_install_missing_and_upstream_lag(app, monkeypatch):
    monkeypatch.setattr("downloader.system.find_tool", lambda name: "/brew/bin/" + name)
    check = FakeCheck(installed=False, latest="2026.10.01")
    results = []
    check.result.connect(results.append)
    check.run()
    assert ["/brew/bin/brew", "install", "yt-dlp"] in check.commands
    assert ["/brew/bin/brew", "install", "ffmpeg"] in check.commands
    assert ["/brew/bin/brew", "install", "deno"] in check.commands
    assert "may not have published" in results[0].warning


def test_homebrew_outage_retains_usable_tools(app, monkeypatch):
    monkeypatch.setattr("downloader.system.find_tool", lambda name: "/brew/bin/" + name)
    check = FakeCheck()
    original = check.command
    def failing(arguments, timeout=60):
        if "update" in arguments:
            raise RuntimeError("Connection failed")
        return original(arguments, timeout)
    check.command = failing
    results = []
    check.result.connect(results.append)
    check.run()
    assert results[0].ready
    assert "Connection failed" in results[0].warning
