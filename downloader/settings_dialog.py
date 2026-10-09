from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import shlex

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                             QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
                             QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from .model import Settings, build_arguments, parse_help


def button(text, callback, name=""):
    result = QPushButton(text)
    result.setObjectName(name)
    result.clicked.connect(callback)
    return result


def note(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName("muted")
    return label


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, help_text: str, executable: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings · YouTube Downloader")
        self.resize(820, 730)
        self.setMinimumSize(730, 640)
        self.original = settings
        self.result_settings = None
        self.executable = executable or "yt-dlp"
        self.controls = {}
        self.options = parse_help(help_text)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("Make it yours")
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(note("Simple defaults. Precise control when you need it."))
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.output_tab(settings)
        self.cookie_tab(settings)
        self.processing_tab(settings)
        self.advanced_tab(settings)
        footer = QHBoxLayout()
        footer.addWidget(button("Restore defaults", self.restore))
        footer.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        footer.addWidget(buttons)
        layout.addLayout(footer)

    def form_tab(self, title):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.tabs.addTab(scroll, title)
        return form, layout

    def text(self, form, label, key, settings, browse=None):
        field = QLineEdit(str(getattr(settings, key)))
        self.controls[key] = field
        if browse:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(field)
            layout.addWidget(button("Choose…", lambda: self.browse(field, browse)))
            form.addRow(label, row)
        else:
            form.addRow(label, field)
        return field

    def combo(self, form, label, key, items, settings):
        combo = QComboBox()
        combo.addItems(items)
        combo.setCurrentText(getattr(settings, key))
        self.controls[key] = combo
        form.addRow(label, combo)
        return combo

    def check(self, form, label, key, settings):
        checkbox = QCheckBox(label)
        checkbox.setChecked(getattr(settings, key))
        self.controls[key] = checkbox
        form.addRow(checkbox)
        return checkbox

    def spin(self, form, label, key, minimum, maximum, settings):
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(getattr(settings, key))
        self.controls[key] = spin
        form.addRow(label, spin)

    def browse(self, field, kind):
        if kind == "directory":
            path = QFileDialog.getExistingDirectory(self, "Download folder", field.text())
        elif kind == "save":
            path, _ = QFileDialog.getSaveFileName(self, "Download archive", field.text(), "Text files (*.txt);;All files (*)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Choose file", field.text(), "All files (*)")
        if path:
            field.setText(path)

    def output_tab(self, settings):
        form, layout = self.form_tab("Downloads")
        self.text(form, "Save to", "destination", settings, "directory")
        self.combo(form, "Download", "mode", ["Video + audio", "Audio only"], settings)
        self.combo(form, "Resolution", "resolution", ["Highest available", "2160p", "1440p", "1080p", "720p", "480p"], settings)
        self.combo(form, "Video container", "container", ["Automatic", "MKV", "MP4", "WebM"], settings)
        self.combo(form, "Audio format", "audio_format", ["Original", "MP3", "M4A", "Opus", "FLAC", "WAV", "AAC"], settings)
        layout.addWidget(note("Automatic preserves source quality. Container changes remux without re-encoding; incompatible codecs can fail. Audio conversion applies only to Audio only mode."))
        self.spin(form, "Downloads at once", "parallel", 1, 8, settings)
        self.check(form, "Download entire playlists", "playlist", settings)
        self.text(form, "File name template", "template", settings)
        self.text(form, "Speed limit per download", "rate_limit", settings).setPlaceholderText("Optional, e.g. 5M or 500K")
        self.spin(form, "Retries", "retries", 0, 100, settings)
        self.spin(form, "Fragments at once per download", "fragments", 1, 32, settings)
        self.text(form, "Download archive", "archive", settings, "save").setPlaceholderText("Optional: skip previously downloaded video IDs")
        self.check(form, "Check and update system yt-dlp at launch", "auto_update", settings)
        layout.addWidget(note("Updates use Homebrew. Missing yt-dlp, FFmpeg and Deno are installed as system tools. Latest stable release is checked separately; Homebrew can lag behind."))
        layout.addStretch()

    def cookie_tab(self, settings):
        form, layout = self.form_tab("Cookies")
        source = self.combo(form, "Cookie source", "cookie_source", ["None", "Browser", "Cookie file"], settings)
        self.combo(form, "Browser", "browser", ["chrome", "safari", "firefox", "brave", "edge", "chromium", "opera", "vivaldi", "whale"], settings)
        self.text(form, "Browser profile", "profile", settings).setPlaceholderText("Optional: profile name or full profile path")
        self.text(form, "Keyring", "keyring", settings).setPlaceholderText("Optional: used by Chromium browsers on Linux")
        self.text(form, "Firefox container", "cookie_container", settings).setPlaceholderText("Optional: Firefox container name")
        self.text(form, "Netscape cookie file", "cookie_file", settings, "file")
        layout.addWidget(note("yt-dlp reads cookies directly from the browser you select when a download starts. The app stores your selection and file paths, never the cookie contents. macOS may ask for Keychain or Full Disk Access. Close the browser if its cookie database is locked."))
        layout.addWidget(button("Browser-cookie documentation ↗", lambda: QDesktopServices.openUrl(QUrl("https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp")), "quiet"))
        def update_fields():
            for key in ("browser", "profile", "keyring", "cookie_container"):
                self.controls[key].setEnabled(source.currentText() == "Browser")
            self.controls["cookie_file"].setEnabled(source.currentText() == "Cookie file")
        source.currentTextChanged.connect(update_fields)
        update_fields()
        layout.addStretch()

    def processing_tab(self, settings):
        form, layout = self.form_tab("Processing")
        self.check(form, "Embed video metadata", "metadata", settings)
        self.check(form, "Embed thumbnail", "thumbnail", settings)
        self.check(form, "Download subtitles", "subtitles", settings)
        self.check(form, "Include automatically generated subtitles", "auto_subtitles", settings)
        self.text(form, "Subtitle languages", "subtitle_languages", settings)
        self.check(form, "Embed subtitles in the media file", "embed_subtitles", settings)
        self.text(form, "Remove SponsorBlock categories", "sponsorblock", settings).setPlaceholderText("Optional, e.g. sponsor,intro,outro")
        layout.addWidget(note("Subtitle languages accept yt-dlp patterns, e.g. en.*,es or all,-live_chat. Enable subtitle downloading to embed them. SponsorBlock cuts the selected segments from the video."))
        layout.addStretch()

    def advanced_tab(self, settings):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addWidget(note("All installed yt-dlp options are available below. Advanced arguments override app defaults and are passed directly without a shell. Options such as --exec still run programs through yt-dlp."))
        extra = QPlainTextEdit(settings.extra)
        extra.setPlaceholderText('--format "bestvideo+bestaudio/best"\n--playlist-items 1:10 --write-description')
        extra.setMaximumHeight(90)
        self.controls["extra"] = extra
        layout.addWidget(extra)
        only = QCheckBox("Use only advanced arguments (skip app download and cookie defaults)")
        only.setChecked(settings.only_extra)
        self.controls["only_extra"] = only
        layout.addWidget(only)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search every option: subtitles, proxy, formats…")
        self.search.textChanged.connect(self.filter_options)
        search_row.addWidget(self.search)
        self.categories = QComboBox()
        self.categories.addItems(["All categories"] + list(dict.fromkeys(o.category for o in self.options)))
        self.categories.currentTextChanged.connect(self.filter_options)
        search_row.addWidget(self.categories)
        layout.addLayout(search_row)
        self.option_list = QListWidget()
        self.option_list.currentItemChanged.connect(self.option_selected)
        layout.addWidget(self.option_list, 1)
        self.description = note("Select an option to see its description and add it to your arguments.")
        self.description.setMinimumHeight(60)
        layout.addWidget(self.description)
        value_row = QHBoxLayout()
        self.option_value = QLineEdit()
        self.option_value.setPlaceholderText('Value(s), if needed. Quote paths with spaces: "/my folder/file"')
        value_row.addWidget(self.option_value)
        value_row.addWidget(button("Add option", self.insert_option))
        layout.addLayout(value_row)
        layout.addWidget(note("Arguments are saved locally with your settings. Avoid putting passwords or tokens here. Simulation/listing options may finish without saving media; output options can change progress reporting."))
        links = QHBoxLayout()
        links.addWidget(button("Preview command", self.preview))
        links.addWidget(button("yt-dlp documentation ↗", lambda: QDesktopServices.openUrl(QUrl("https://github.com/yt-dlp/yt-dlp#usage-and-options")), "quiet"))
        links.addStretch()
        layout.addLayout(links)
        self.tabs.addTab(content, "All yt-dlp options")
        self.filter_options()

    def filter_options(self, *_):
        self.option_list.clear()
        query = self.search.text().lower()
        category = self.categories.currentText()
        for option in self.options:
            if query in (option.signature + " " + option.description).lower() and (category == "All categories" or category == option.category):
                item = QListWidgetItem(option.signature)
                item.setData(Qt.ItemDataRole.UserRole, option)
                self.option_list.addItem(item)
        if not self.options:
            self.description.setText("Option reference will load after the system tool check. You can already enter any yt-dlp argument above.")

    def option_selected(self, item, _):
        if item:
            option = item.data(Qt.ItemDataRole.UserRole)
            self.description.setText(option.description)
            self.option_value.clear()

    def insert_option(self):
        item = self.option_list.currentItem()
        if not item:
            return
        option = item.data(Qt.ItemDataRole.UserRole)
        addition = option.flag + (" " + self.option_value.text().strip() if self.option_value.text().strip() else "")
        field = self.controls["extra"]
        existing = field.toPlainText().rstrip()
        field.setPlainText(existing + ("\n" if existing else "") + addition)

    def collect(self):
        values = asdict(self.original)
        for key, control in self.controls.items():
            if isinstance(control, QCheckBox):
                values[key] = control.isChecked()
            elif isinstance(control, QComboBox):
                values[key] = control.currentText()
            elif isinstance(control, QSpinBox):
                values[key] = control.value()
            elif isinstance(control, QPlainTextEdit):
                values[key] = control.toPlainText()
            else:
                values[key] = control.text().strip()
        return Settings.from_dict(values)

    def preview(self):
        try:
            settings = self.collect()
            command = shlex.join([self.executable] + build_arguments(settings, "https://www.youtube.com/watch?v=VIDEO_ID"))
        except ValueError as error:
            QMessageBox.warning(self, "Check your settings", str(error))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Command preview")
        dialog.resize(800, 420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(note("This is a preview; the example link will be replaced by each queue item."))
        text = QPlainTextEdit(command)
        text.setReadOnly(True)
        layout.addWidget(text)
        layout.addWidget(button("Close", dialog.accept))
        dialog.exec()

    def restore(self):
        defaults = Settings()
        for key, control in self.controls.items():
            value = getattr(defaults, key)
            if isinstance(control, QCheckBox):
                control.setChecked(value)
            elif isinstance(control, QComboBox):
                control.setCurrentText(value)
            elif isinstance(control, QSpinBox):
                control.setValue(value)
            elif isinstance(control, QPlainTextEdit):
                control.setPlainText(value)
            else:
                control.setText(value)

    def save(self):
        try:
            settings = self.collect()
            if not settings.destination or not settings.template:
                raise ValueError("Choose a download folder and a file name template.")
            build_arguments(settings, "https://example.com/video")
            if settings.embed_subtitles and not (settings.subtitles or settings.auto_subtitles) and not settings.only_extra:
                raise ValueError("Enable subtitle downloading before embedding subtitles.")
        except ValueError as error:
            QMessageBox.warning(self, "Check your settings", str(error))
            return
        self.result_settings = settings
        self.accept()
