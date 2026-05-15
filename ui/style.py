FONT = "SF Mono, Menlo, Monaco, Courier New, monospace"

TERMINAL_QSS = f"""
QDialog, QWidget {{
    background-color: #0d0d0d;
    color: #e6e6e6;
    font-family: {FONT};
    font-size: 13px;
}}

QTabWidget::pane {{
    border: 1px solid #2a2a2a;
    background-color: #0d0d0d;
}}

QTabBar::tab {{
    background-color: #0d0d0d;
    color: #666666;
    border: 1px solid #2a2a2a;
    border-bottom: none;
    padding: 5px 14px;
    font-family: {FONT};
}}

QTabBar::tab:selected {{
    color: #e6e6e6;
    border-top: 1px solid #d97757;
    background-color: #141414;
}}

QTabBar::tab:hover:!selected {{
    color: #aaaaaa;
}}

QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: #141414;
    color: #e6e6e6;
    border: 1px solid #2a2a2a;
    border-radius: 0px;
    padding: 4px 6px;
    selection-background-color: #d97757;
    selection-color: #0d0d0d;
    font-family: {FONT};
}}

QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid #d97757;
}}

QLineEdit::placeholder, QPlainTextEdit[placeholderText] {{
    color: #444444;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: #1e1e1e;
    border: 1px solid #2a2a2a;
    width: 16px;
}}

QSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #888888;
    width: 0px; height: 0px;
}}

QSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888888;
    width: 0px; height: 0px;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888888;
    width: 0px; height: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: #141414;
    color: #e6e6e6;
    border: 1px solid #2a2a2a;
    selection-background-color: #d97757;
    selection-color: #0d0d0d;
    font-family: {FONT};
}}

QPushButton {{
    background-color: #141414;
    color: #e6e6e6;
    border: 1px solid #2a2a2a;
    border-radius: 0px;
    padding: 5px 14px;
    font-family: {FONT};
}}

QPushButton:hover {{
    background-color: #1e1e1e;
    border-color: #d97757;
    color: #d97757;
}}

QPushButton:pressed {{
    background-color: #0a0a0a;
}}

QPushButton:default {{
    border-color: #d97757;
    color: #d97757;
}}

QPushButton:disabled {{
    color: #444444;
    border-color: #1e1e1e;
}}

QScrollArea {{
    border: 1px solid #2a2a2a;
    background-color: #0d0d0d;
}}

QScrollBar:vertical {{
    background-color: #0d0d0d;
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: #2a2a2a;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #3a3a3a;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QLabel {{
    color: #e6e6e6;
    font-family: {FONT};
}}

QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

QFrame[frameShape="1"] {{
    border: 1px solid #2a2a2a;
    background-color: #0d0d0d;
}}
"""


def apply_terminal_style(widget) -> None:
    widget.setStyleSheet(TERMINAL_QSS)
