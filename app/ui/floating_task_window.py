from datetime import date, datetime, time, timedelta

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QSettings,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, TASK_CATEGORIES
from app.services.task_service import TaskService
from app.ui.task_colors import get_task_card_color
from app.utils.time_utils import format_task_time, get_daily_default_deadline, is_task_overdue


FILTER_ALL = "all"
FILTER_TODAY = "today"
FILTER_THREE_DAYS = "three_days"
FILTER_SEVEN_DAYS = "seven_days"

FILTER_ORDER = (FILTER_ALL, FILTER_TODAY, FILTER_THREE_DAYS, FILTER_SEVEN_DAYS)
FILTER_LABELS = {
    FILTER_ALL: "全部",
    FILTER_TODAY: "今日截止",
    FILTER_THREE_DAYS: "近三日",
    FILTER_SEVEN_DAYS: "近七日",
}

OPACITY_MIN = 20
OPACITY_MAX = 100
SNAP_THRESHOLD = 24
AUTO_HIDE_VISIBLE_SIZE = 36
AUTO_HIDE_DELAY_MS = 800

SCROLLBAR_STYLE = """
            QScrollBar:vertical {
                width: 10px;
                background: transparent;
                margin: 4px 2px 4px 2px;
            }

            QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 5px;
                min-height: 40px;
            }

            QScrollBar::handle:vertical:hover {
                background: #9ca3af;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }

            QScrollBar:horizontal {
                height: 0px;
                background: transparent;
            }

            QScrollBar::handle:horizontal {
                background: transparent;
            }
"""

SECTION_ORDER = (
    ("short", "短期任务"),
    ("long", "长期任务"),
    ("daily", "每日任务"),
    ("timed", "定时任务"),
    ("extra", "附加任务"),
)


class FloatingTaskItem(QFrame):
    complete_requested = Signal(int)
    pin_requested = Signal(int)
    expanded_changed = Signal()
    interaction_started = Signal()
    interaction_finished = Signal()

    def __init__(self, task, time_text, category_text, allow_pin=False, is_pinned=False, parent=None):
        super().__init__(parent)
        self.task = task
        self.time_text = time_text
        self.category_text = category_text
        self.allow_pin = allow_pin
        self.is_pinned = is_pinned
        self.is_expanded = False

        self.setObjectName("FloatingTaskItem")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.init_ui()
        self.apply_style()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        checkbox = QLabel("□")
        checkbox.setObjectName("TaskCheck")
        checkbox.setFixedWidth(18)
        checkbox.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self.summary_label = QLabel(f"{self.task.title}（{self.time_text}）")
        self.summary_label.setObjectName("TaskSummary")
        self.summary_label.setWordWrap(True)
        self.summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        row_layout.addWidget(checkbox)
        row_layout.addWidget(self.summary_label, 1)

        if self.allow_pin:
            self.pin_button = QPushButton("♥" if self.is_pinned else "♡")
            self.pin_button.setObjectName("PinTaskButton")
            self.pin_button.setCheckable(True)
            self.pin_button.setChecked(self.is_pinned)
            self.pin_button.setToolTip("取消置顶" if self.is_pinned else "置顶")
            self.pin_button.setFixedSize(24, 24)
            self.pin_button.clicked.connect(
                lambda checked=False: self.pin_requested.emit(self.task.task_id)
            )
            row_layout.addWidget(self.pin_button, 0, Qt.AlignTop)

        layout.addLayout(row_layout)

        self.detail_frame = QFrame()
        self.detail_frame.setObjectName("TaskDetail")
        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(24, 2, 0, 0)
        detail_layout.setSpacing(5)

        detail_title = QLabel(self.task.title)
        detail_title.setObjectName("DetailTitle")
        detail_title.setWordWrap(True)
        detail_layout.addWidget(detail_title)

        if self.task.description:
            detail_description = QLabel(f"描述：{self.task.description}")
            detail_description.setWordWrap(True)
            detail_layout.addWidget(detail_description)

        detail_layout.addWidget(QLabel(f"分类：{self.category_text}"))
        detail_layout.addWidget(QLabel(self.time_text))

        complete_button = QPushButton("完成任务")
        complete_button.setObjectName("CompleteButton")
        complete_button.clicked.connect(
            lambda checked=False: self.complete_requested.emit(self.task.task_id)
        )
        detail_layout.addWidget(complete_button, 0, Qt.AlignRight)
        layout.addWidget(self.detail_frame)

        self.set_expanded(False)

    def apply_style(self):
        border_color, background_color, text_color = get_task_card_color(self.task)
        pin_background = background_color if self.is_pinned else "#ffffff"
        pin_text_color = text_color if self.is_pinned else "#666666"
        pin_border_color = border_color if self.is_pinned else "#666666"
        self.setStyleSheet(f"""
            QFrame#FloatingTaskItem {{
                background-color: {background_color};
                border: 1px solid {border_color};
                border-radius: 7px;
            }}

            QLabel#TaskSummary,
            QLabel#TaskCheck,
            QFrame#TaskDetail,
            QFrame#TaskDetail QLabel {{
                color: {text_color};
                background-color: transparent;
            }}

            QLabel#DetailTitle {{
                font-weight: bold;
                color: {text_color};
            }}

            QPushButton#PinTaskButton {{
                padding: 0;
                border-radius: 6px;
                border: 1px solid {pin_border_color};
                background-color: {pin_background};
                color: {pin_text_color};
                font-size: 15px;
                font-weight: bold;
            }}

            QPushButton#PinTaskButton:hover {{
                border: 1px solid #333333;
            }}

            QPushButton#CompleteButton {{
                padding: 5px 10px;
                border-radius: 5px;
                border: 1px solid #1d4ed8;
                background-color: #2d8cff;
                color: white;
                font-weight: bold;
            }}
        """)

    def contextMenuEvent(self, event):
        if not self.allow_pin:
            return
        menu = QMenu(self)
        menu.addAction("取消置顶" if self.is_pinned else "置顶", lambda: self.pin_requested.emit(self.task.task_id))
        menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.interaction_started.emit()
            self.set_expanded(not self.is_expanded)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.interaction_finished.emit()
        super().mouseReleaseEvent(event)

    def set_expanded(self, expanded):
        self.is_expanded = expanded
        self.detail_frame.setVisible(expanded)
        self.expanded_changed.emit()


class FloatingTaskWindow(QWidget):
    data_changed = Signal()
    show_main_requested = Signal()
    new_task_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_service = TaskService()
        self.settings = QSettings(APP_NAME, "FloatingWindow")
        self.current_filter = FILTER_ALL
        self.is_collapsed = False
        self.is_window_pinned = self.settings.value("pinned", True, type=bool)
        self.pinned_task_ids = set()
        self.drag_start_pos = None
        self.snap_edge = self.normalize_snap_edge(self.settings.value("snap_edge", None))
        self.snap_corner = self.normalize_snap_corner(self.settings.value("snap_corner", None))
        self.is_auto_hidden = False
        self.auto_hide_enabled = self.settings.value("auto_hide_enabled", True, type=bool)
        self.auto_hide_visible_size = AUTO_HIDE_VISIBLE_SIZE
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.apply_auto_hide)
        self.move_animation = QPropertyAnimation(self, b"pos", self)
        self.move_animation.setDuration(180)
        self.move_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.context_menu_open = False
        self._reposition_pending = False
        self._mouse_inside = False
        self._interacting_inside = False

        self.setWindowTitle("任务清单")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.is_window_pinned)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(360, 460)

        self.init_ui()
        self.restore_settings()
        self.refresh_tasks()
        self.apply_collapsed_state()
        self.ensure_inside_screen()
        if self.should_auto_hide_after_snap():
            self.apply_auto_hide()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.root_frame = QFrame()
        self.root_frame.setObjectName("FloatingRoot")
        root_layout.addWidget(self.root_frame)

        self.root_content_layout = QVBoxLayout(self.root_frame)
        self.root_content_layout.setContentsMargins(10, 8, 10, 10)
        self.root_content_layout.setSpacing(8)

        self.title_bar = QFrame()
        self.title_bar.setObjectName("FloatingTitleBar")
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(6)

        self.title_label = QLabel("任务清单")
        self.title_label.setObjectName("FloatingTitle")

        self.collapse_button = QPushButton("▾")
        self.collapse_button.setObjectName("TitleButton")
        self.collapse_button.setFixedSize(32, 26)
        self.collapse_button.clicked.connect(self.toggle_collapsed)

        self.pin_window_button = QPushButton("⌖")
        self.pin_window_button.setObjectName("WindowPinButton")
        self.pin_window_button.setCheckable(True)
        self.pin_window_button.setFixedSize(32, 26)
        self.pin_window_button.clicked.connect(self.toggle_window_pinned)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("TitleButton")
        self.close_button.setFixedSize(32, 26)
        self.close_button.clicked.connect(self.hide_window)

        title_layout.addWidget(self.title_label, 1)
        title_layout.addWidget(self.collapse_button)
        title_layout.addWidget(self.pin_window_button)
        title_layout.addWidget(self.close_button)

        self.filter_frame = QFrame()
        self.filter_frame.setObjectName("FilterFrame")
        filter_layout = QHBoxLayout(self.filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        self.filter_buttons = {}
        for filter_key in FILTER_ORDER:
            button = QPushButton(FILTER_LABELS[filter_key])
            button.setObjectName("FilterButton")
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False, selected=filter_key: self.set_filter(selected))
            self.filter_group.addButton(button)
            self.filter_buttons[filter_key] = button
            filter_layout.addWidget(button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("TaskScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(8)
        self.task_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.task_container)

        self.root_content_layout.addWidget(self.title_bar)
        self.root_content_layout.addWidget(self.filter_frame)
        self.root_content_layout.addWidget(self.scroll_area, 1)

        for widget in (self.root_frame, self.title_bar, self.title_label, self.task_container):
            widget.installEventFilter(self)

        self.update_pin_button_text()
        self.setStyleSheet("""
            QFrame#FloatingRoot {
                background-color: #ffffff;
                border: 1px solid #111111;
                border-radius: 12px;
            }

            QFrame#FloatingTitleBar {
                background-color: transparent;
            }

            QLabel#FloatingTitle {
                font-size: 15px;
                font-weight: bold;
                color: #111827;
                background-color: transparent;
            }

            QPushButton#TitleButton {
                border: 1px solid #111111;
                border-radius: 5px;
                background-color: #ffffff;
                color: #111827;
                font-weight: bold;
                padding: 0;
            }

            QPushButton#TitleButton:hover {
                background-color: #e5e7eb;
            }

            QPushButton#TitleButton:checked {
                background-color: #dbeafe;
                color: #111827;
            }

            QPushButton#WindowPinButton {
                border: 1px solid #333333;
                border-radius: 6px;
                background-color: #ffffff;
                color: #666666;
                font-size: 15px;
                font-weight: bold;
                padding: 0;
            }

            QPushButton#WindowPinButton:hover {
                background-color: #f3f4f6;
                color: #111111;
            }

            QPushButton#WindowPinButton:checked {
                background-color: #DCEBFF;
                color: #111111;
                border: 1px solid #333333;
            }

            QPushButton#FilterButton {
                color: #111827;
                background-color: #ffffff;
                border: 1px solid #111111;
                border-radius: 6px;
                padding: 6px 4px;
                text-align: center;
            }

            QPushButton#FilterButton:checked {
                background-color: #dbeafe;
                color: #111827;
                font-weight: bold;
            }

            QScrollArea#TaskScrollArea {
                border: none;
                background-color: transparent;
            }

            QWidget {
                background-color: transparent;
            }

            QLabel#EmptyLabel {
                color: #111827;
                padding: 16px;
                background-color: transparent;
            }

            QLabel#SectionTitle {
                color: #111827;
                font-size: 14px;
                font-weight: bold;
                padding: 6px 2px 2px 2px;
                background-color: transparent;
            }
        """ + SCROLLBAR_STYLE)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
            self.begin_internal_interaction()
            self.stop_move_animation()
            if self.is_auto_hidden:
                self.show_from_auto_hide(animated=False)
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseMove and self.drag_start_pos is not None and event.buttons() & Qt.LeftButton:
            self.cancel_auto_hide_timer()
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and self.drag_start_pos is not None:
            self.drag_start_pos = None
            self.apply_edge_snap()
            self.save_settings()
            self.end_internal_interaction()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def is_cursor_inside_window(self) -> bool:
        return self.frameGeometry().contains(QCursor.pos())

    def begin_internal_interaction(self) -> None:
        self._mouse_inside = True
        self._interacting_inside = True
        self.cancel_auto_hide_timer()
        if self.is_auto_hidden:
            self.show_from_auto_hide(animated=False)

    def end_internal_interaction(self) -> None:
        self._interacting_inside = False
        self._mouse_inside = self.is_cursor_inside_window()
        if not self._mouse_inside:
            self.schedule_auto_hide()

    def get_current_screen_available_geometry(self):
        screen = QApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

    def current_screen_available_geometry(self):
        return self.get_current_screen_available_geometry()

    def clamp_to_screen(self, x: int, y: int, screen_rect=None):
        screen_rect = screen_rect or self.get_current_screen_available_geometry()
        if screen_rect is None:
            return x, y

        window_rect = self.frameGeometry()
        min_x = screen_rect.x()
        min_y = screen_rect.y()
        max_x = max(min_x, screen_rect.x() + screen_rect.width() - window_rect.width())
        max_y = max(min_y, screen_rect.y() + screen_rect.height() - window_rect.height())
        return max(min_x, min(x, max_x)), max(min_y, min(y, max_y))

    def clamp_normal_position(self, x: int, y: int, screen_rect=None):
        """普通显示状态，完整限制在屏幕可用区域内。"""
        return self.clamp_to_screen(x, y, screen_rect)

    def clamp_auto_hidden_position(self, x: int, y: int, screen_rect=None):
        """半隐藏状态，允许部分出屏，只保证露出区域存在。"""
        screen_rect = screen_rect or self.get_current_screen_available_geometry()
        if screen_rect is None:
            return x, y

        window_rect = self.frameGeometry()
        visible = min(self.auto_hide_visible_size, window_rect.width(), window_rect.height())
        min_x = screen_rect.x() - window_rect.width() + visible
        max_x = screen_rect.x() + screen_rect.width() - visible
        min_y = screen_rect.y() - window_rect.height() + visible
        max_y = screen_rect.y() + screen_rect.height() - visible
        return max(min_x, min(x, max_x)), max(min_y, min(y, max_y))

    def ensure_inside_screen(self):
        if self.is_auto_hidden:
            self.apply_auto_hide()
            return

        window_rect = self.frameGeometry()
        x, y = self.clamp_normal_position(window_rect.x(), window_rect.y())
        if x != window_rect.x() or y != window_rect.y():
            self.move(x, y)

    def schedule_reposition_after_resize(self):
        if self._reposition_pending:
            return
        self._reposition_pending = True
        QTimer.singleShot(0, self.reposition_after_resize)

    def reposition_after_resize(self):
        self._reposition_pending = False
        self.stop_move_animation()

        if self.is_auto_hidden:
            self.apply_auto_hide()
            return

        screen_rect = self.get_current_screen_available_geometry()
        if screen_rect is None:
            return

        window_rect = self.frameGeometry()
        x = window_rect.x()
        y = window_rect.y()
        min_x = screen_rect.x()
        min_y = screen_rect.y()
        max_x = max(min_x, screen_rect.x() + screen_rect.width() - window_rect.width())
        max_y = max(min_y, screen_rect.y() + screen_rect.height() - window_rect.height())

        if self.snap_edge == "left":
            x = min_x
        elif self.snap_edge == "right":
            x = max_x
        elif self.snap_edge == "top":
            y = min_y
        elif self.snap_edge == "bottom":
            y = max_y

        if self.snap_corner in {"left_top", "left_bottom"}:
            x = min_x
        elif self.snap_corner in {"right_top", "right_bottom"}:
            x = max_x

        if self.snap_corner in {"left_top", "right_top"}:
            y = min_y
        elif self.snap_corner in {"left_bottom", "right_bottom"}:
            y = max_y

        x, y = self.clamp_normal_position(x, y, screen_rect)
        if x != window_rect.x() or y != window_rect.y():
            self.move(x, y)

    def stop_move_animation(self):
        if self.move_animation.state() == QAbstractAnimation.Running:
            self.move_animation.stop()

    def animate_move_to(self, target_pos: QPoint, animated: bool = True) -> None:
        self.stop_move_animation()
        if not animated:
            self.move(target_pos)
            return

        self.move_animation.setStartValue(self.pos())
        self.move_animation.setEndValue(target_pos)
        self.move_animation.start()

    def apply_edge_snap(self) -> None:
        """鼠标释放后执行边缘吸附，并记录吸附方向。"""
        screen_rect = self.get_current_screen_available_geometry()
        if screen_rect is None:
            return

        window_rect = self.frameGeometry()

        min_x = screen_rect.x()
        min_y = screen_rect.y()
        max_x = max(min_x, screen_rect.x() + screen_rect.width() - window_rect.width())
        max_y = max(min_y, screen_rect.y() + screen_rect.height() - window_rect.height())

        x = window_rect.x()
        y = window_rect.y()

        screen_left = screen_rect.x()
        screen_top = screen_rect.y()
        screen_right = screen_rect.x() + screen_rect.width()
        screen_bottom = screen_rect.y() + screen_rect.height()

        window_left = window_rect.x()
        window_top = window_rect.y()
        window_right = window_rect.x() + window_rect.width()
        window_bottom = window_rect.y() + window_rect.height()

        # 关键修复：
        # 不要用 abs() 判断距离，否则窗口被拖出屏幕后反而会被认为“不靠近边缘”。
        near_left = window_left <= screen_left + SNAP_THRESHOLD
        near_right = window_right >= screen_right - SNAP_THRESHOLD
        near_top = window_top <= screen_top + SNAP_THRESHOLD
        near_bottom = window_bottom >= screen_bottom - SNAP_THRESHOLD

        self.snap_edge = None
        self.snap_corner = None

        # 角落优先按左右方向处理
        if near_left and near_top:
            self.snap_edge = "left"
            self.snap_corner = "left_top"
        elif near_left and near_bottom:
            self.snap_edge = "left"
            self.snap_corner = "left_bottom"
        elif near_right and near_top:
            self.snap_edge = "right"
            self.snap_corner = "right_top"
        elif near_right and near_bottom:
            self.snap_edge = "right"
            self.snap_corner = "right_bottom"
        elif near_left:
            self.snap_edge = "left"
        elif near_right:
            self.snap_edge = "right"
        elif near_top:
            self.snap_edge = "top"
        elif near_bottom:
            self.snap_edge = "bottom"

        if near_left:
            x = min_x
        elif near_right:
            x = max_x

        if near_top:
            y = min_y
        elif near_bottom:
            y = max_y

        x = max(min_x, min(x, max_x))
        y = max(min_y, min(y, max_y))

        self.move(x, y)
        self.is_auto_hidden = False

        if self.should_auto_hide_after_snap():
            self.apply_auto_hide()

    def apply_auto_hide(self) -> None:
        """根据当前 snap_edge 执行半隐藏。"""
        if (
            not self.should_auto_hide_after_snap()
            or self.drag_start_pos is not None
            or self.context_menu_open
            or self._interacting_inside
            or self._mouse_inside
            or self.is_cursor_inside_window()
        ):
            self.cancel_auto_hide_timer()
            return

        screen_rect = self.get_current_screen_available_geometry()
        if screen_rect is None:
            return

        window_rect = self.frameGeometry()
        visible = min(self.auto_hide_visible_size, window_rect.width(), window_rect.height())
        x, y = self.clamp_normal_position(window_rect.x(), window_rect.y(), screen_rect)

        if self.snap_edge == "left":
            x = screen_rect.x() - window_rect.width() + visible
        elif self.snap_edge == "right":
            x = screen_rect.x() + screen_rect.width() - visible
        elif self.snap_edge == "top":
            y = screen_rect.y() - window_rect.height() + visible
        elif self.snap_edge == "bottom":
            y = screen_rect.y() + screen_rect.height() - visible
        else:
            return

        x, y = self.clamp_auto_hidden_position(x, y, screen_rect)
        self.is_auto_hidden = True
        self.animate_move_to(QPoint(x, y))

    def show_from_auto_hide(self, animated: bool = True) -> None:
        """从半隐藏状态恢复完整显示。"""
        if not self.is_auto_hidden or not self.snap_edge:
            return

        screen_rect = self.get_current_screen_available_geometry()
        if screen_rect is None:
            return

        window_rect = self.frameGeometry()
        x, y = window_rect.x(), window_rect.y()
        if self.snap_edge == "left":
            x = screen_rect.x()
        elif self.snap_edge == "right":
            x = screen_rect.x() + screen_rect.width() - window_rect.width()
        elif self.snap_edge == "top":
            y = screen_rect.y()
        elif self.snap_edge == "bottom":
            y = screen_rect.y() + screen_rect.height() - window_rect.height()

        x, y = self.clamp_normal_position(x, y, screen_rect)
        self.is_auto_hidden = False
        self.animate_move_to(QPoint(x, y), animated=animated)

    def schedule_auto_hide(self) -> None:
        """鼠标离开后延迟半隐藏。"""
        if (
            self.should_auto_hide_after_snap()
            and self.drag_start_pos is None
            and not self.context_menu_open
            and not self._mouse_inside
            and not self._interacting_inside
            and not self.is_cursor_inside_window()
        ):
            self.auto_hide_timer.start(AUTO_HIDE_DELAY_MS)

    def cancel_auto_hide_timer(self) -> None:
        """取消待执行的半隐藏。"""
        if self.auto_hide_timer.isActive():
            self.auto_hide_timer.stop()

    def normalize_snap_edge(self, value):
        if value in {"left", "right", "top", "bottom"}:
            return value
        return None

    def normalize_snap_corner(self, value):
        if value in {"left_top", "left_bottom", "right_top", "right_bottom"}:
            return value
        return None

    def should_auto_hide_after_snap(self) -> bool:
        if not self.auto_hide_enabled:
            return False
        return self.snap_edge in {"left", "right", "top", "bottom"}

    def visible_position_for_saved_settings(self):
        if not self.is_auto_hidden or not self.snap_edge:
            return self.pos()

        screen_rect = self.get_current_screen_available_geometry()
        if screen_rect is None:
            return self.pos()

        window_rect = self.frameGeometry()
        x, y = window_rect.x(), window_rect.y()
        if self.snap_edge == "left":
            x = screen_rect.x()
        elif self.snap_edge == "right":
            x = screen_rect.x() + screen_rect.width() - window_rect.width()
        elif self.snap_edge == "top":
            y = screen_rect.y()
        elif self.snap_edge == "bottom":
            y = screen_rect.y() + screen_rect.height() - window_rect.height()

        x, y = self.clamp_normal_position(x, y, screen_rect)
        return QPoint(x, y)

    def restore_settings(self):
        opacity = self.clamp_opacity(self.settings.value("opacity", 100))
        self.setWindowOpacity(opacity / 100)
        self.settings.setValue("opacity", opacity)
        self.auto_hide_enabled = self.settings.value("auto_hide_enabled", True, type=bool)
        self.snap_edge = self.normalize_snap_edge(self.settings.value("snap_edge", self.snap_edge))
        self.snap_corner = self.normalize_snap_corner(self.settings.value("snap_corner", self.snap_corner))

        pos = self.settings.value("pos")
        if isinstance(pos, QPoint):
            self.move(pos)

        checked_button = self.filter_buttons.get(self.current_filter)
        if checked_button is not None:
            checked_button.setChecked(True)

    def save_settings(self):
        self.settings.setValue("pos", self.visible_position_for_saved_settings())
        self.settings.setValue("opacity", self.clamp_opacity(int(self.windowOpacity() * 100)))
        self.settings.setValue("collapsed", self.is_collapsed)
        self.settings.setValue("filter", self.current_filter)
        self.settings.setValue("visible", self.isVisible())
        self.settings.setValue("pinned", self.is_window_pinned)
        self.settings.setValue("auto_hide_enabled", self.auto_hide_enabled)
        self.settings.setValue("snap_edge", self.snap_edge or "")
        self.settings.setValue("snap_corner", self.snap_corner or "")

    def show_window(self):
        self.refresh_tasks()
        self.show()
        if self.is_auto_hidden:
            self.apply_auto_hide()
        else:
            self.ensure_inside_screen()
        self.raise_()
        self.activateWindow()
        self.settings.setValue("visible", True)

    def hide_window(self):
        self.save_settings()
        self.hide()
        self.settings.setValue("visible", False)

    def should_show_on_startup(self):
        return self.settings.value("visible", False, type=bool)

    def set_filter(self, filter_key):
        if filter_key not in FILTER_LABELS:
            return
        self.current_filter = filter_key
        self.settings.setValue("filter", filter_key)
        button = self.filter_buttons.get(filter_key)
        if button is not None and not button.isChecked():
            button.setChecked(True)
        self.refresh_tasks()

    def refresh_tasks(self):
        self.clear_task_layout()
        tasks = self.get_filtered_tasks()

        if not tasks:
            empty_label = QLabel("当前筛选下没有待办任务")
            empty_label.setObjectName("EmptyLabel")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setWordWrap(True)
            self.task_layout.addWidget(empty_label)
        elif self.current_filter == FILTER_ALL:
            self.add_grouped_tasks(tasks)
        else:
            for task_info in tasks:
                self.add_task_item(task_info, allow_pin=True)

        self.task_layout.addStretch()
        self.update_collapsed_text()
        self.schedule_reposition_after_resize()

    def add_grouped_tasks(self, tasks):
        grouped = {key: [] for key, _ in SECTION_ORDER}
        for task_info in tasks:
            grouped.setdefault(self.get_task_section_key(task_info[0]), []).append(task_info)

        for section_key, section_title in SECTION_ORDER:
            section_tasks = grouped.get(section_key, [])
            if not section_tasks:
                continue

            title = QLabel(section_title)
            title.setObjectName("SectionTitle")
            self.task_layout.addWidget(title)

            for task_info in section_tasks:
                self.add_task_item(task_info, allow_pin=False)

    def add_task_item(self, task_info, allow_pin):
        task, due_value, time_text, category_text = task_info
        is_pinned = task.task_id in self.pinned_task_ids
        item = FloatingTaskItem(
            task,
            time_text,
            category_text,
            allow_pin=allow_pin,
            is_pinned=is_pinned,
        )
        item.complete_requested.connect(self.complete_task)
        item.pin_requested.connect(self.toggle_task_pinned)
        item.expanded_changed.connect(self.handle_task_item_expanded)
        item.interaction_started.connect(self.begin_internal_interaction)
        item.interaction_finished.connect(self.end_internal_interaction)
        self.task_layout.addWidget(item)

    def handle_task_item_expanded(self):
        self.begin_internal_interaction()
        if self.is_auto_hidden:
            self.show_from_auto_hide()
        self.schedule_reposition_after_resize()

    def clear_task_layout(self):
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def get_filtered_tasks(self):
        today = date.today()
        tasks = []
        for task in self.task_service.get_uncompleted_tasks():
            due_value = self.get_task_due_datetime(task)
            due_date = due_value.date() if due_value else None
            if not self.task_matches_filter(task, due_value, due_date, today):
                continue

            tasks.append((
                task,
                due_value,
                self.format_time_text(task, due_value),
                self.get_category_text(task),
            ))

        tasks = sorted(
            tasks,
            key=lambda item: (
                item[1] is None,
                item[1] or datetime.max,
                item[0].created_at or "",
            ),
        )

        if self.current_filter != FILTER_ALL:
            tasks = sorted(
                tasks,
                key=lambda item: (
                    item[0].task_id not in self.pinned_task_ids,
                    item[1] is None,
                    item[1] or datetime.max,
                    item[0].created_at or "",
                ),
            )

        return tasks

    def task_matches_filter(self, task, due_value, due_date, today):
        if self.current_filter == FILTER_ALL:
            return True

        if due_value is None:
            return False

        now = datetime.now()
        if due_value <= now:
            return False

        if self.current_filter == FILTER_TODAY:
            return due_date == today
        if self.current_filter == FILTER_THREE_DAYS:
            return now <= due_value <= now + timedelta(days=3)
        if self.current_filter == FILTER_SEVEN_DAYS:
            return now <= due_value <= now + timedelta(days=7)

        return True

    def get_task_due_datetime(self, task):
        if task.task_type == "daily" or task.category == "daily":
            if task.ddl:
                try:
                    return datetime.fromisoformat(str(task.ddl))
                except ValueError:
                    return get_daily_default_deadline()
            return get_daily_default_deadline()

        value = task.scheduled_at if task.task_type == "timed" or task.category == "timed" else task.ddl
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(str(value))
            if len(str(value)) <= 10:
                return datetime.combine(parsed.date(), time(23, 59))
            return parsed
        except ValueError:
            try:
                return datetime.combine(
                    datetime.fromisoformat(str(value)[:10]).date(),
                    time(23, 59),
                )
            except ValueError:
                return None

    def format_time_text(self, task, due_value):
        if is_task_overdue(task):
            return "已过期"

        if task.task_type == "timed" or task.category == "timed":
            if due_value is None:
                return "时间：未设置"
            return f"时间：{format_task_time(due_value)}"

        if due_value is None:
            return "截止时间：未设置"
        return f"截止时间：{format_task_time(due_value)}"

    def get_category_text(self, task):
        if task.task_type == "timed" or task.category == "timed":
            return "定时任务"
        return TASK_CATEGORIES.get(task.category, "普通任务")

    def get_task_section_key(self, task):
        if task.task_type == "timed" or task.category == "timed":
            return "timed"
        if task.task_type == "daily" or task.category == "daily":
            return "daily"
        if task.category in {"short", "long", "extra"}:
            return task.category
        return "extra"

    def toggle_task_pinned(self, task_id):
        if task_id in self.pinned_task_ids:
            self.pinned_task_ids.remove(task_id)
        else:
            self.pinned_task_ids.add(task_id)
        self.refresh_tasks()

    def complete_task(self, task_id):
        self.task_service.complete_task(task_id)
        self.pinned_task_ids.discard(task_id)
        self.refresh_tasks()
        self.data_changed.emit()

    def update_collapsed_text(self):
        today = date.today()
        today_count = 0

        for task in self.task_service.get_uncompleted_tasks():
            due_value = self.get_task_due_datetime(task)
            if due_value and due_value > datetime.now() and due_value.date() == today:
                today_count += 1

        text = f"今日 {today_count} 项待办" if today_count else "任务清单"
        if self.is_collapsed:
            self.title_label.setText(text)

    def toggle_collapsed(self):
        was_auto_hidden = self.is_auto_hidden
        if was_auto_hidden:
            self.show_from_auto_hide()
        self.cancel_auto_hide_timer()
        self.is_collapsed = not self.is_collapsed
        self.apply_collapsed_state()
        self.reposition_after_resize()
        if was_auto_hidden and self.should_auto_hide_after_snap():
            self.apply_auto_hide()
        self.save_settings()

    def apply_collapsed_state(self):
        self.filter_frame.setVisible(not self.is_collapsed)
        self.scroll_area.setVisible(not self.is_collapsed)
        self.close_button.setVisible(not self.is_collapsed)
        self.collapse_button.setText("▴" if self.is_collapsed else "▾")
        self.title_label.setText("任务清单")
        if self.is_collapsed:
            self.update_collapsed_text()
            self.root_content_layout.setContentsMargins(10, 8, 10, 8)
            self.setFixedSize(260, 46)
        else:
            self.root_content_layout.setContentsMargins(10, 8, 10, 10)
            self.setMinimumWidth(320)
            self.setMaximumWidth(16777215)
            self.setMinimumHeight(300)
            self.setMaximumHeight(16777215)
            self.resize(max(self.width(), 360), 460)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.drag_start_pos is None:
            self.schedule_reposition_after_resize()

    def toggle_window_pinned(self):
        self.is_window_pinned = not self.is_window_pinned
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.is_window_pinned)
        self.update_pin_button_text()
        self.show()
        self.raise_()
        self.save_settings()

    def update_pin_button_text(self):
        self.pin_window_button.setText("⌖")
        self.pin_window_button.setChecked(self.is_window_pinned)
        self.pin_window_button.setToolTip("取消置顶" if self.is_window_pinned else "置顶窗口")

    def apply_context_menu_style(self, menu):
        menu.setObjectName("FloatingContextMenu")
        menu.setStyleSheet("""
            QMenu#FloatingContextMenu, QMenu {
                background-color: #1f1f1f;
                color: white;
                border: 1px solid #666666;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu#FloatingContextMenu::item, QMenu::item {
                color: white;
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu#FloatingContextMenu::item:selected, QMenu::item:selected {
                background-color: #444444;
                color: white;
            }
            QMenu#FloatingContextMenu::separator, QMenu::separator {
                height: 1px;
                background-color: #666666;
                margin: 5px 8px;
            }
        """)

    def create_actions_menu(self):
        menu = QMenu(self)
        self.apply_context_menu_style(menu)
        menu.addAction("进入主程序", self.show_main_requested.emit)
        menu.addAction("新建任务", self.new_task_requested.emit)
        menu.addAction("刷新", self.refresh_tasks)
        menu.addAction("展开" if self.is_collapsed else "折叠", self.toggle_collapsed)
        menu.addAction("取消置顶" if self.is_window_pinned else "置顶", self.toggle_window_pinned)

        opacity_menu = menu.addMenu("透明度")
        self.apply_context_menu_style(opacity_menu)
        for value in (100, 90, 80, 70, 60, 50, 40, 30, 20):
            opacity_menu.addAction(f"{value}%", lambda checked=False, selected=value: self.set_opacity(selected))

        menu.addAction("退出悬浮窗", self.hide_window)
        return menu

    def set_opacity(self, value):
        opacity = self.clamp_opacity(value)
        self.setWindowOpacity(opacity / 100)
        self.settings.setValue("opacity", opacity)

    def clamp_opacity(self, value):
        try:
            opacity = int(value)
        except (TypeError, ValueError):
            opacity = OPACITY_MAX
        return max(OPACITY_MIN, min(OPACITY_MAX, opacity))

    def contextMenuEvent(self, event):
        self.begin_internal_interaction()
        if self.is_auto_hidden:
            self.show_from_auto_hide()
        self.context_menu_open = True
        self.create_actions_menu().exec(event.globalPos())
        self.context_menu_open = False
        self.end_internal_interaction()

    def enterEvent(self, event):
        self._mouse_inside = True
        self.cancel_auto_hide_timer()
        if self.is_auto_hidden:
            self.show_from_auto_hide()
        super().enterEvent(event)

    def leaveEvent(self, event):
        QTimer.singleShot(0, self.handle_possible_mouse_leave)
        super().leaveEvent(event)

    def handle_possible_mouse_leave(self):
        self._mouse_inside = self.is_cursor_inside_window()
        if self._mouse_inside or self._interacting_inside or self.context_menu_open:
            self.cancel_auto_hide_timer()
            return
        self.schedule_auto_hide()

    def mouseDoubleClickEvent(self, event):
        if self.is_collapsed and event.button() == Qt.LeftButton:
            self.toggle_collapsed()
            return
        super().mouseDoubleClickEvent(event)

    def closeEvent(self, event):
        self.hide_window()
        event.ignore()
