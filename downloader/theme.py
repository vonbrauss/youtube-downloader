STYLE = """
* { font-family: '.AppleSystemUIFont', 'SF Pro Display', 'Helvetica Neue', sans-serif; font-size: 13px; }
QMainWindow, QDialog { background: #11151c; }
QWidget { color: #edf2f8; }
QLabel { background: transparent; }
QLabel#title { font-size: 27px; font-weight: 700; }
QLabel#section { font-size: 16px; font-weight: 600; }
QLabel#muted { color: #95a2b5; }
QLabel#eyebrow { color: #79ddc2; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#badge { color: #79ddc2; background: #1d3633; border-radius: 7px; padding: 6px 11px; font-size: 11px; }
QLabel#warning { background: #332b1c; color: #ebcc8d; padding: 10px; border: 1px solid #5a4930; border-radius: 8px; }
QFrame#card { background: #1a202a; border: 1px solid #2c3543; border-radius: 13px; }
QFrame#row { background: #1a202a; border: 1px solid #2c3543; border-radius: 11px; }
QPushButton { background: #252d3a; border: 1px solid #364254; padding: 8px 14px; border-radius: 7px; font-weight: 500; }
QPushButton:hover { background: #303c4d; border-color: #586c81; }
QPushButton:pressed { background: #182331; }
QPushButton:disabled { background: #202631; color: #626f81; border-color: #29323f; }
QPushButton#primary { background: #79ddc2; color: #10221e; border-color: #79ddc2; font-weight: 700; }
QPushButton#primary:hover { background: #99efda; border-color: #99efda; }
QPushButton#primary:disabled { background: #254b43; color: #718c84; border-color: #254b43; }
QPushButton#quiet { background: transparent; border: 0; color: #9caabd; padding: 6px 9px; }
QPushButton#quiet:hover { background: #283342; color: #edf2f8; }
QLineEdit, QPlainTextEdit, QTextEdit, QListWidget { background: #121821; border: 1px solid #303b4b; border-radius: 8px; padding: 9px; selection-background-color: #35685d; }
QLineEdit:focus, QPlainTextEdit:focus { border-color: #79ddc2; }
QComboBox, QSpinBox { background: #121821; border: 1px solid #303b4b; border-radius: 7px; padding: 8px; min-height: 18px; }
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox QAbstractItemView { background: #202835; selection-background-color: #35685d; }
QCheckBox { spacing: 9px; padding: 5px 0; }
QCheckBox::indicator { width: 17px; height: 17px; background: #121821; border: 1px solid #46576a; border-radius: 4px; }
QCheckBox::indicator:checked { background: #79ddc2; border-color: #79ddc2; image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png); }
QProgressBar { background: #303a48; border: 0; border-radius: 3px; min-height: 5px; max-height: 5px; color: transparent; }
QProgressBar::chunk { background: #79ddc2; border-radius: 3px; }
QTabWidget::pane { border: 1px solid #303b4b; border-radius: 8px; background: #1a202a; }
QTabBar::tab { background: transparent; color: #95a2b5; padding: 12px 16px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #79ddc2; border-bottom-color: #79ddc2; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #435166; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QListWidget#queue { border: none; padding: 0; background: transparent; }
QListWidget#queue::item { padding: 0; border: none; }
QToolTip { background: #252f3d; color: #edf2f8; border: 1px solid #4a5b70; padding: 6px; }
QMenu { background: #1a202a; border: 1px solid #364254; }
QMenu::item { padding: 8px 18px; }
QMenu::item:selected { background: #35685d; }
"""
