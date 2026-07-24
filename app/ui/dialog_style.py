"""Global styling for modal dialogs and message boxes."""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QMenu, QMessageBox


DIALOG_STYLE_SHEET = """
QMessageBox,
QDialog {
    background-color: #0d0d0d;
    color: #ffffff;
}

QMessageBox QLabel,
QDialog QLabel,
QDialog QCheckBox,
QDialog QRadioButton {
    color: #ffffff;
    background-color: transparent;
}

QDialog QLabel#HintLabel {
    color: #b8b8b8;
}

QDialog QCheckBox,
QMessageBox QCheckBox {
    color: #ffffff;
    background-color: transparent;
    spacing: 8px;
}

QDialog QCheckBox::indicator,
QMessageBox QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border: 2px solid #ffffff;
    border-radius: 3px;
    background-color: transparent;
}

QDialog QCheckBox::indicator:hover,
QMessageBox QCheckBox::indicator:hover {
    border-color: #ffffff;
    background-color: #333333;
}

QDialog QCheckBox::indicator:checked,
QMessageBox QCheckBox::indicator:checked {
    border-color: #ffffff;
    background-color: #ffffff;
}

QDialog QCheckBox:disabled,
QMessageBox QCheckBox:disabled {
    color: #999999;
}

QDialog QCheckBox::indicator:disabled,
QMessageBox QCheckBox::indicator:disabled {
    border-color: #777777;
    background-color: #242424;
}

QDialog QCheckBox::indicator:checked:disabled,
QMessageBox QCheckBox::indicator:checked:disabled {
    border-color: #999999;
    background-color: #777777;
}

QMessageBox QPushButton,
QDialog QPushButton {
    min-width: 88px;
    min-height: 32px;
    padding: 4px 14px;
    color: #ffffff;
    background-color: #2b2b2b;
    border: 1px solid #666666;
    border-radius: 7px;
}

QMessageBox QPushButton:hover,
QDialog QPushButton:hover {
    color: #ffffff;
    background-color: #3a3a3a;
    border-color: #999999;
}

QMessageBox QPushButton:pressed,
QDialog QPushButton:pressed {
    color: #ffffff;
    background-color: #555555;
}

QMessageBox QPushButton:default,
QDialog QPushButton:default {
    border: 2px solid #d0d0d0;
}

QMessageBox QPushButton:disabled,
QDialog QPushButton:disabled {
    color: #888888;
    background-color: #1b1b1b;
    border-color: #444444;
}

QDialog QLineEdit,
QDialog QTextEdit,
QDialog QPlainTextEdit,
QDialog QSpinBox,
QDialog QDoubleSpinBox,
QDialog QComboBox,
QDialog QDateEdit,
QDialog QDateTimeEdit,
QDialog QTimeEdit {
    color: #ffffff;
    background-color: #202020;
    border: 1px solid #666666;
    border-radius: 5px;
    padding: 5px;
    selection-background-color: #666666;
    selection-color: #ffffff;
}

QDialog QComboBox QAbstractItemView,
QDialog QCalendarWidget,
QDialog QCalendarWidget QWidget,
QDialog QCalendarWidget QAbstractItemView {
    color: #ffffff;
    background-color: #202020;
    selection-background-color: #555555;
    selection-color: #ffffff;
}

QDialog QGroupBox {
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 6px;
    margin-top: 8px;
}

QDialog QGroupBox::title {
    color: #ffffff;
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

QDialog QScrollArea,
QDialog QScrollArea QWidget {
    background-color: #0d0d0d;
    color: #ffffff;
}

QDialog QToolButton {
    color: #ffffff;
    background-color: #2b2b2b;
    border: 1px solid #666666;
}

QDialog QToolButton:hover {
    background-color: #3a3a3a;
}

QDialog QFrame {
    background-color: #161616;
    color: #ffffff;
}

QDialog QSlider::groove:horizontal {
    height: 6px;
    background-color: #444444;
}

QDialog QSlider::handle:horizontal {
    width: 16px;
    margin: -5px 0;
    background-color: #bdbdbd;
    border: 1px solid #eeeeee;
    border-radius: 8px;
}
"""


DARK_POPUP_STYLE = """
QMenu {
    color: #ffffff;
    background-color: #101010;
    border: 1px solid #555555;
    padding: 5px;
}

QMenu::item {
    color: #ffffff;
    background-color: transparent;
    padding: 7px 26px 7px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    color: #ffffff;
    background-color: #3a3a3a;
}

QMenu::item:pressed {
    color: #ffffff;
    background-color: #555555;
}

QMenu::item:disabled {
    color: #888888;
    background-color: transparent;
}

QMenu::separator {
    height: 1px;
    background-color: #555555;
    margin: 5px 8px;
}

QMenu::indicator {
    width: 16px;
    height: 16px;
}

QMessageBox {
    color: #ffffff;
    background-color: #101010;
}

QMessageBox QLabel {
    color: #ffffff;
    background-color: transparent;
}

QMessageBox QCheckBox,
QMessageBox QRadioButton {
    color: #ffffff;
    background-color: transparent;
}

QMessageBox QPushButton,
QDialog QPushButton,
QDialogButtonBox QPushButton {
    color: #ffffff;
    background-color: #292929;
    border: 1px solid #777777;
    border-radius: 6px;
    min-width: 82px;
    min-height: 30px;
    padding: 3px 12px;
}

QMessageBox QPushButton:hover,
QDialog QPushButton:hover,
QDialogButtonBox QPushButton:hover {
    color: #ffffff;
    background-color: #3b3b3b;
    border-color: #aaaaaa;
}

QMessageBox QPushButton:pressed,
QDialog QPushButton:pressed,
QDialogButtonBox QPushButton:pressed {
    color: #ffffff;
    background-color: #555555;
}

QMessageBox QPushButton:checked,
QDialog QPushButton:checked,
QDialogButtonBox QPushButton:checked,
QMessageBox QPushButton:focus,
QDialog QPushButton:focus,
QDialogButtonBox QPushButton:focus {
    color: #ffffff;
    background-color: #444444;
}

QMessageBox QPushButton:default,
QDialog QPushButton:default,
QDialogButtonBox QPushButton:default {
    color: #ffffff;
    border: 2px solid #dddddd;
}

QMessageBox QPushButton:disabled,
QDialog QPushButton:disabled,
QDialogButtonBox QPushButton:disabled {
    color: #999999;
    background-color: #1b1b1b;
    border-color: #444444;
}

QToolButton {
    color: #ffffff;
    background-color: #292929;
    border: 1px solid #666666;
    border-radius: 5px;
    padding: 4px 8px;
}

QToolButton:hover {
    color: #ffffff;
    background-color: #3b3b3b;
}

QToolButton:pressed,
QToolButton:checked {
    color: #ffffff;
    background-color: #555555;
}
"""


def apply_dark_popup_palette(widget) -> None:
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#101010"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#292929"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#181818"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#444444"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#999999"))
    widget.setPalette(palette)


def apply_dark_popup_style(widget) -> None:
    if isinstance(widget, QMenu):
        widget.setObjectName(widget.objectName() or "darkContextMenu")
        widget.setStyleSheet(DARK_POPUP_STYLE)
    else:
        widget.setStyleSheet(DIALOG_STYLE_SHEET + "\n" + DARK_POPUP_STYLE)
    apply_dark_popup_palette(widget)
    if isinstance(widget, (QDialog, QMessageBox)):
        _apply_checkbox_palette(widget)


def _apply_checkbox_palette(widget) -> None:
    """Keep the check glyph dark on the white checked indicator."""
    for checkbox in widget.findChildren(QCheckBox):
        palette = checkbox.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#111111"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#111111"))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#999999"))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#666666"))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#666666"))
        checkbox.setPalette(palette)


class _DarkPopupFilter(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, (QMenu, QMessageBox, QDialog)):
            apply_dark_popup_style(watched)
        return False


def install_dialog_style(app: QApplication | None = None) -> None:
    """Install modal-dialog rules at QApplication scope."""
    app = app or QApplication.instance()
    if app is None:
        return
    current = app.styleSheet()
    combined = current
    for style in (DIALOG_STYLE_SHEET, DARK_POPUP_STYLE):
        if style not in combined:
            combined += "\n" + style
    if combined != current:
        app.setStyleSheet(combined)
    if not hasattr(app, "_dark_popup_filter"):
        app._dark_popup_filter = _DarkPopupFilter(app)
        app.installEventFilter(app._dark_popup_filter)


def apply_dialog_style(dialog: QDialog) -> None:
    """Apply the shared rules to a custom QDialog that has local styling."""
    apply_dark_popup_style(dialog)


def ask_dark_question(parent, title: str, text: str, buttons, default_button):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(buttons)
    box.setDefaultButton(default_button)
    apply_dark_popup_style(box)
    return box.exec()
