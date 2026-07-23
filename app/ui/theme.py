THEME = {
    "text_primary": "#1F2937",
    "text_secondary": "#64748B",
    "surface": "rgba(255, 255, 255, 220)",
    "surface_soft": "rgba(248, 250, 252, 225)",
    "surface_hover": "rgba(248, 250, 252, 235)",
    "panel": "rgba(248, 250, 252, 225)",
    "border": "#CBD5E1",
    "border_light": "#E2E8F0",
    "border_hover": "#94A3B8",
    "accent": "#4F7DBA",
    "accent_light": "#E8F1FC",
    "accent_pressed": "#D7E7F8",
    "accent_border": "#8FAFD3",
    "danger": "#DC5A5A",
    "danger_light": "#FDECEC",
    "danger_border": "#E9A0A0",
}

RADIUS_WINDOW = 14
RADIUS_BUTTON = 8
RADIUS_INPUT = 8
RADIUS_EDITOR = 10

SCROLLBAR_QSS = """
QScrollBar:vertical {
    width: 8px;
    margin: 3px;
    background: transparent;
}
QScrollBar::handle:vertical {
    min-height: 28px;
    background: rgba(100, 116, 139, 110);
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(79, 125, 186, 160);
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
    background: transparent;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    height: 8px;
    margin: 3px;
    background: transparent;
}
QScrollBar::handle:horizontal {
    min-width: 28px;
    background: rgba(100, 116, 139, 95);
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(79, 125, 186, 150);
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    background: transparent;
}
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""


def apply_dark_context_menu_style(menu):
    menu.setStyleSheet("""
        QMenu {
            background-color: #101010;
            color: #B8B8B8;
            border: 1px solid #363636;
            border-radius: 8px;
            padding: 5px;
        }

        QMenu::item {
            color: #B8B8B8;
            background-color: transparent;
            padding: 6px 28px 6px 12px;
            margin: 1px 2px;
            border-radius: 5px;
        }

        QMenu::item:selected {
            color: #E0E0E0;
            background-color: #2A2A2A;
        }

        QMenu::item:disabled {
            color: #606060;
            background-color: transparent;
        }

        QMenu::separator {
            height: 1px;
            background-color: #303030;
            margin: 5px 8px;
        }

        QMenu::indicator {
            width: 14px;
            height: 14px;
        }
    """)


def floating_window_qss():
    return f"""
QFrame#FloatingRoot {{
    background-color: transparent;
    border: none;
}}
QFrame#FloatingTitleBar,
QFrame#FilterFrame {{
    background-color: transparent;
}}
QFrame#PageSwitchFrame {{
    background-color: rgba(226, 232, 240, 130);
    border: 1px solid {THEME["border_light"]};
    border-radius: {RADIUS_BUTTON}px;
}}
QLabel#FloatingTitle {{
    font-family: "Microsoft YaHei UI";
    font-size: 16px;
    font-weight: 600;
    color: {THEME["text_primary"]};
    background-color: transparent;
}}
QPushButton[role="windowControl"],
QPushButton[role="dangerWindowControl"] {{
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    padding: 0;
    background-color: rgba(255, 255, 255, 185);
    border: 1px solid {THEME["border"]};
    border-radius: {RADIUS_BUTTON}px;
}}
QPushButton[role="windowControl"]:hover,
QPushButton[role="dangerWindowControl"]:hover {{
    background-color: {THEME["accent_light"]};
    border-color: {THEME["accent_border"]};
}}
QPushButton[role="windowControl"]:pressed,
QPushButton[role="windowControl"]:checked,
QPushButton[role="dangerWindowControl"]:pressed {{
    background-color: {THEME["accent_pressed"]};
    border-color: {THEME["accent_border"]};
}}
QPushButton[role="dangerWindowControl"]:hover {{
    background-color: {THEME["danger_light"]};
    border-color: {THEME["danger_border"]};
}}
QPushButton#PageButton {{
    min-width: 0;
    min-height: 32px;
    max-height: 32px;
    padding: 0 8px;
    color: #475569;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}}
QPushButton#PageButton:hover {{
    background-color: rgba(255, 255, 255, 120);
    border-color: transparent;
}}
QPushButton#PageButton:checked {{
    color: #315F98;
    background-color: {THEME["accent_light"]};
    border: 1px solid {THEME["accent_border"]};
    font-weight: 600;
}}
QPushButton#FilterButton {{
    min-width: 68px;
    max-width: 68px;
    min-height: 32px;
    max-height: 32px;
    padding: 0 2px;
    color: #334155;
    background-color: rgba(255, 255, 255, 180);
    border: 1px solid {THEME["border"]};
    border-radius: {RADIUS_BUTTON}px;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}}
QPushButton#FilterButton:hover {{
    background-color: #F1F5F9;
    border-color: {THEME["border_hover"]};
}}
QPushButton#FilterButton:checked {{
    color: #315F98;
    background-color: {THEME["accent_light"]};
    border: 1px solid {THEME["accent_border"]};
    font-weight: 600;
}}
QScrollArea#TaskScrollArea {{
    border: none;
    background-color: transparent;
}}
QWidget {{
    background-color: transparent;
}}
QLabel#EmptyLabel {{
    color: {THEME["text_secondary"]};
    padding: 16px;
    background-color: transparent;
}}
QLabel#SectionTitle {{
    color: {THEME["text_primary"]};
    font-size: 14px;
    font-weight: 600;
    padding: 6px 2px 2px 2px;
    background-color: transparent;
}}
{SCROLLBAR_QSS}
"""


def quick_note_qss():
    return f"""
QFrame#QuickNoteToolbar {{
    background-color: rgba(255, 255, 255, 155);
    border: 1px solid {THEME["border_light"]};
    border-radius: 7px;
}}
QTextEdit#QuickNoteEditor {{
    color: {THEME["text_primary"]};
    background-color: rgba(255, 255, 255, 210);
    border: 1px solid {THEME["border"]};
    border-radius: {RADIUS_EDITOR}px;
    padding: 12px;
    selection-background-color: #BFD7F2;
    selection-color: {THEME["text_primary"]};
    font-family: "Microsoft YaHei UI";
    font-size: 14px;
}}
QTextEdit#QuickNoteEditor:focus {{
    border: 1px solid #7FA3CE;
    background-color: rgba(255, 255, 255, 230);
}}
QComboBox#NoteFontCombo,
QComboBox#NoteSizeCombo {{
    min-height: 28px;
    max-height: 28px;
    padding: 0 2px;
    color: #334155;
    background-color: rgba(255, 255, 255, 220);
    border: 1px solid {THEME["border"]};
    border-radius: 7px;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}}
QComboBox#NoteFontCombo {{
    min-width: 70px;
    max-width: 70px;
}}
QComboBox#NoteSizeCombo {{
    min-width: 46px;
    max-width: 46px;
}}
QComboBox#NoteFontCombo:hover,
QComboBox#NoteSizeCombo:hover {{
    border-color: {THEME["border_hover"]};
    background-color: #FFFFFF;
}}
QComboBox#NoteFontCombo:focus,
QComboBox#NoteSizeCombo:focus {{
    border: 1px solid #6F98C7;
}}
QComboBox::drop-down {{
    width: 14px;
    border: none;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
}}
QToolButton#NoteToggleButton {{
    min-width: 32px;
    max-width: 32px;
    min-height: 28px;
    max-height: 28px;
    color: #334155;
    background-color: rgba(255, 255, 255, 210);
    border: 1px solid {THEME["border"]};
    border-radius: 7px;
    font-size: 14px;
}}
QToolButton#NoteToggleButton:hover {{
    background-color: #F1F5F9;
    border-color: {THEME["border_hover"]};
}}
QToolButton#NoteToggleButton:checked {{
    color: #315F98;
    background-color: {THEME["accent_light"]};
    border-color: #7FA3CE;
}}
QToolButton#NoteCommandButton {{
    min-width: 50px;
    max-width: 50px;
    min-height: 28px;
    max-height: 28px;
    color: #334155;
    background-color: rgba(255, 255, 255, 200);
    border: 1px solid {THEME["border"]};
    border-radius: 7px;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}}
QToolButton#NoteCommandButton:hover {{
    color: #315F98;
    background-color: #EDF4FC;
    border-color: {THEME["accent_border"]};
}}
QToolButton#NoteCommandButton:pressed {{
    background-color: #DDEBFA;
}}
{SCROLLBAR_QSS}
"""


def preview_dialog_qss():
    return f"""
QDialog {{
    background-color: {THEME["surface_soft"]};
    color: {THEME["text_primary"]};
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}}
QFrame#PreviewToolbar {{
    background-color: rgba(255, 255, 255, 165);
    border: 1px solid {THEME["border_light"]};
    border-radius: 10px;
    padding: 8px;
}}
QPushButton, QSpinBox {{
    min-height: 34px;
    border: 1px solid {THEME["border"]};
    border-radius: {RADIUS_BUTTON}px;
    background-color: rgba(255, 255, 255, 210);
    color: #334155;
    padding: 2px 10px;
}}
QPushButton:hover {{
    background-color: #F1F5F9;
    border-color: {THEME["border_hover"]};
}}
QPushButton:checked {{
    color: #315F98;
    background-color: {THEME["accent_light"]};
    border-color: #7FA3CE;
    font-weight: 600;
}}
QSlider::groove:horizontal {{
    height: 6px;
    border-radius: 3px;
    background: {THEME["border_light"]};
}}
QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
    background: {THEME["accent"]};
}}
{SCROLLBAR_QSS}
"""
