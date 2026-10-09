from pathlib import Path
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from downloader.model import Settings, Storage
from downloader.settings_dialog import SettingsDialog
from downloader.system import ToolStatus, find_tool
from downloader.theme import STYLE
from downloader.window import MainWindow


def test_window_queue_and_settings(app, tmp_path):
    app.setStyleSheet(STYLE)
    window = MainWindow(Storage(tmp_path), check_system=False)
    window.tool_status = ToolStatus(executable="/fake", ready=True)
    window.controller.executable = "/fake"
    window.show()
    app.processEvents()
    window.link_input.setPlainText("https://example.com/a\nhttps://example.com/b\nhttps://example.com/a")
    window.add_links()
    app.processEvents()
    assert len(window.jobs) == 2
    assert window.queue.count() == 2
    assert window.start.isEnabled()
    window.controller.cancel(window.jobs[0])
    window.retry_failed()
    assert window.jobs[0].status == "Queued"
    window.save_state()
    assert len(Storage(tmp_path).read("queue.json", [])) == 2
    window.close()


def test_settings_option_search_and_round_trip(app, tmp_path):
    executable = find_tool("yt-dlp")
    help_text = subprocess.check_output([executable, "--ignore-config", "--help"], text=True) if executable else "  Network Options:\n    --proxy URL                    Use this proxy\n"
    dialog = SettingsDialog(Settings(destination=str(tmp_path)), help_text, executable or "yt-dlp")
    dialog.search.setText("--proxy")
    assert dialog.option_list.count() >= 1
    index = next(i for i in range(dialog.option_list.count()) if dialog.option_list.item(i).data(Qt.ItemDataRole.UserRole).flag == "--proxy")
    dialog.option_list.setCurrentRow(index)
    dialog.option_value.setText('"http://127.0.0.1:8080"')
    dialog.insert_option()
    assert '--proxy "http://127.0.0.1:8080"' in dialog.controls["extra"].toPlainText()
    dialog.save()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.result_settings.destination == str(tmp_path)
