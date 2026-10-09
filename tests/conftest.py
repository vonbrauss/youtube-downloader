import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def app():
    result = QApplication.instance() or QApplication([])
    yield result

@pytest.fixture(autouse=True)
def cleanup_widgets(app):
    yield
    from PySide6.QtCore import QCoreApplication, QEvent
    import gc
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()
