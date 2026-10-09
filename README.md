# YouTube Downloader

A native Python / Qt desktop application for macOS. yt-dlp is **not embedded, imported, or bundled**. The app runs the system executable as a separate process and manages it through Homebrew.

## Run from PyCharm

For an existing local setup, select `.venv/bin/python` as your PyCharm interpreter and run `main.py`. A fresh clone does not include the virtual environment; create it using the commands below.

To set up a fresh checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python main.py
```

## Standalone macOS app

Build the app using the commands below. The resulting app is at `dist/YouTube Downloader.app`; double-click it, or drag it into Applications. Generated apps and build files are excluded from Git. Python and Qt are included in the app; yt-dlp, FFmpeg and Deno stay on your system. The original local build targets Apple Silicon and macOS 26 or newer because it used a Homebrew Python runtime built for macOS 26. The build script records the Python runtime’s minimum system version. For older macOS releases, rebuild with a compatible Python runtime and Qt version. For Intel Macs, build again using Intel Python on an Intel Mac.

The development build is locally signed, not notarized. For public distribution, use an Apple Developer signing identity and notarize the app.

Build it again with:

```sh
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python build_app.py
```

## Downloading

1. Paste complete links or import a UTF-8 `.txt` file. One link per line; comments beginning with `#` are skipped on import.
2. Choose **Video + audio** or **Audio only** and your download folder.
3. Click **Download queue**. Two links run simultaneously by default. The limit is configurable from 1–8.

Video defaults to separate best video + best audio, with a combined-format fallback. Resolution and frame rate get priority. No resolution cap, forced codec or re-encoding is applied by default. Audio-only defaults to the original best available audio stream. Container and conversion choices live in Settings.

A link with a playlist parameter downloads the single video by default. Enable **Download entire playlists** to download a whole playlist. One playlist is one queue item; its current video, current-file progress and saved file count are displayed. Progress may reset between audio/video streams and playlist entries.

**Pause queue** lets active downloads finish and holds remaining links. **Stop** cancels active downloads, including merger subprocesses, and holds remaining links. **Retry** resumes retained partial files where yt-dlp supports it. Closing with active downloads offers to stop them. Interrupted jobs remain visible on relaunch and require an explicit retry. No media download starts automatically.

**Clear finished** removes terminal queue entries, never media files. Completed entries open the folder containing the first saved file. A successful command that reports no saved media (such as simulation, listing formats or skipping an archived video) is labeled **Finished**, rather than claiming a download was saved. Details shows live diagnostic output.

## System tools and updates

On launch, the app refreshes Homebrew metadata, installs missing yt-dlp / FFmpeg / Deno tools, and upgrades an outdated Homebrew yt-dlp. It does not install Homebrew itself. If Homebrew is missing, install it from <https://brew.sh>.

The app prefers `/opt/homebrew/bin`, then `/usr/local/bin`, before other paths. This avoids an old pip-installed copy taking precedence over the Homebrew version. Finder launch does not depend on your shell configuration.

Latest stable yt-dlp is checked against the official GitHub release API. A Homebrew release can lag upstream; the app reports that explicitly. If the update check fails, existing usable tools remain available with a warning. **Check & update** retries the process. Disable launch updates in Settings if desired; manual checks still work. Homebrew cannot be updated while a download is active.

FFmpeg/ffprobe enable merging and post-processing. Deno and the Homebrew yt-dlp installation provide the current YouTube JavaScript support. Tools are system dependencies and remain separate from the standalone app.

## Browser cookies

Open **Settings → Cookies** and choose Browser or Cookie file. Supported browser names come from yt-dlp: Chrome, Safari, Firefox, Brave, Edge, Chromium, Opera, Vivaldi and Whale. Optional profile, keyring and Firefox container fields use yt-dlp's native `BROWSER[+KEYRING][:PROFILE][::CONTAINER]` syntax.

The app stores only browser selections and cookie-file paths. yt-dlp reads the cookies when a download starts. Browser permissions, Keychain access, protected cookie databases and site authentication may affect availability. A cookies file must be in Netscape format. No cookies are read during the startup tool check.

## Every yt-dlp option

**Settings → All yt-dlp options** loads searchable, categorized help directly from the installed external `yt-dlp --help`, including newly introduced options. Select an option, enter its argument(s), and click **Add option**, or type/paste native CLI arguments directly. Quote values containing spaces. Multi-argument options accept multiple quoted values.

Advanced arguments are passed as an argument array without invoking a shell, and are appended after the defaults so native overrides work. App progress callbacks are injected; native options can override those too. **Use only advanced arguments** removes app download, quality, path and cookie defaults; it retains `--ignore-config`, reporting callbacks, and the queue URL. To use yt-dlp configuration files, pass `--config-locations` in advanced arguments.

Some native options intentionally exit, simulate downloads, change output reporting or run external programs (`--exec`). The app permits them. Use **Preview command** to inspect the resulting invocation; the actual queue URL replaces the example. yt-dlp's own `--update` option is available, but app-managed updates use Homebrew.

## Local data

Settings and queue history live in:

```
~/Library/Application Support/YouTube Downloader/
```

Writes are atomic, use owner-only file permissions and retain a `.backup` copy. Logs are memory-only. Raw advanced arguments are saved in settings, so avoid placing tokens/passwords there. Two copies of the app cannot manage the same queue concurrently.

## Validation

```sh
.venv/bin/python -m pytest -q
```

Tests cover argument construction, browser syntax, the complete live option catalog, recovery, parallel scheduling, failures, pause/cancel, missing executables, update/install routing and Homebrew outages. An integration test creates a tiny local video with audio, serves it locally, downloads it through the real system yt-dlp and verifies the saved audio/video with ffprobe. A live YouTube metadata/format extraction check also succeeded for “Me at the zoo” without accessing browser cookies. Browser authentication depends on your accounts and permissions and has not been exercised. Packaging smoke checks open the actual bundled app without updating system tools or changing real user data (`--smoke-test`).

## References

- yt-dlp options and format selection: <https://github.com/yt-dlp/yt-dlp#usage-and-options>
- Cookie support: <https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp>
- Homebrew formula: <https://formulae.brew.sh/formula/yt-dlp>
- Qt for Python packaging: <https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html>
