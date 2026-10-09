from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
import time

import pytest
from PySide6.QtCore import QProcess

from downloader.engine import DownloadProcess, QueueController
from downloader.model import Job, Settings
from downloader.system import find_tool


def wait_until(app, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("Timed out waiting for download state")
        time.sleep(0.01)
    app.processEvents()


@pytest.fixture
def fake(tmp_path):
    script = tmp_path / "fake-yt-dlp"
    script.write_text('''#!/usr/bin/env python3
import json, pathlib, sys, time
url = sys.argv[-1]
print('__YTDL_TITLE__' + json.dumps('A test video'), flush=True)
if url.endswith('/slow'):
    time.sleep(60)
elif url.endswith('/fail'):
    print('ERROR: Intentional download failure', flush=True)
    sys.exit(2)
elif url.endswith('/empty'):
    sys.exit(0)
print('__YTDL_PROGRESS__' + json.dumps({'status':'downloading','downloaded':5,'total':10,'speed':5,'eta':1}), flush=True)
time.sleep(0.15)
path = pathlib.Path.cwd() / (url.rsplit('/',1)[-1] + '.mp4')
path.write_bytes(b'test')
print('__YTDL_FILE__' + json.dumps(str(path)), flush=True)
''')
    script.chmod(0o755)
    return str(script)


def test_parallel_queue_and_failures(app, fake, tmp_path):
    jobs = [Job(f"https://example.com/{i}") for i in range(5)] + [Job("https://example.com/fail"), Job("https://example.com/empty")]
    controller = QueueController(jobs, Settings(destination=str(tmp_path), parallel=2))
    controller.executable = fake
    observed = []
    controller.state_changed.connect(lambda: observed.append(len(controller.workers)))
    controller.start()
    assert len(controller.workers) == 2
    wait_until(app, lambda: not controller.running and not controller.workers)
    assert max(observed) == 2
    assert all(j.status == "Completed" and len(j.files) == 1 for j in jobs[:5])
    assert jobs[5].status == "Failed"
    assert jobs[5].detail == "Intentional download failure"
    assert jobs[6].status == "Finished" and jobs[6].files == []


def test_pause_cancel_and_failed_start(app, fake, tmp_path):
    jobs = [Job("https://example.com/slow"), Job("https://example.com/next")]
    controller = QueueController(jobs, Settings(destination=str(tmp_path), parallel=1))
    controller.executable = fake
    controller.start()
    wait_until(app, lambda: controller.workers[jobs[0].id].pid > 0)
    controller.pause()
    assert jobs[1].status == "Queued"
    controller.stop()
    wait_until(app, lambda: not controller.workers)
    assert jobs[0].status == "Cancelled"
    assert jobs[1].status == "Queued"
    job = Job("https://example.com")
    worker = DownloadProcess(job, "/no/such/executable", Settings(destination=str(tmp_path)))
    worker.start()
    wait_until(app, lambda: worker.done)
    assert job.status == "Failed"


def test_real_system_downloader_with_local_media(app, tmp_path):
    executable, ffmpeg = find_tool("yt-dlp"), find_tool("ffmpeg")
    if not executable or not ffmpeg:
        pytest.skip("System tools unavailable")
    fixture = tmp_path / "source"
    fixture.mkdir()
    video = fixture / "sample.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=128x72:rate=10", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "0.6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], check=True)
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(fixture)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        job = Job(f"http://127.0.0.1:{server.server_port}/sample.mp4")
        settings = Settings(destination=str(tmp_path / "downloads"), metadata=True)
        worker = DownloadProcess(job, executable, settings)
        worker.start()
        wait_until(app, lambda: worker.done, timeout=30)
        assert job.status == "Completed", list(job.log)
        assert job.title == "sample"
        assert len(job.files) == 1 and Path(job.files[0]).stat().st_size > 1000
        assert job.progress == 100
        metadata = subprocess.check_output([find_tool("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", job.files[0]], text=True)
        assert '"video"' in metadata and '"audio"' in metadata
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
