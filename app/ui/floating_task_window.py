from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QPoint,
    QRectF,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME
from app.models.plan import PlanLevel
from app.models.priority import PRIORITY_TEXT_COLOR, normalize_priority, priority_card_color
from app.services.period_service import period_service
from app.services.task_service import DEFAULT_MINIMAL_ACTION, TaskService
from app.ui.completion_flow import prompt_and_complete_task
from app.ui.dialog_style import apply_dark_popup_style
from app.ui.quick_note import QuickNoteView
from app.ui.theme import RADIUS_WINDOW, THEME, floating_window_qss
from app.utils.time_utils import format_task_time


PAGE_TASKS = "tasks"
PAGE_QUICK_NOTE = "quick_note"

PAGE_ORDER = (PAGE_TASKS, PAGE_QUICK_NOTE)
PAGE_LABELS = {
    PAGE_TASKS: "日计划",
    PAGE_QUICK_NOTE: "随手记",
}

OPACITY_MIN = 20
OPACITY_MAX = 100
SNAP_THRESHOLD = 24
AUTO_HIDE_VISIBLE_SIZE = 36
AUTO_HIDE_DELAY_MS = 800
EXPANDED_DEFAULT_WIDTH = 360
EXPANDED_DEFAULT_HEIGHT = 582
EXPANDED_MIN_WIDTH = 320
EXPANDED_MIN_HEIGHT = 420
COLLAPSED_WIDTH = 320
COLLAPSED_HEIGHT = 58

class CurrentPageStack(QStackedWidget):
    def sizeHint(self):
        return QSize(EXPANDED_DEFAULT_WIDTH, EXPANDED_DEFAULT_HEIGHT)

    def minimumSizeHint(self):
        return QSize(0, 0)


class WindowIconButton(QPushButton):
    def __init__(self, icon_name, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setProperty("role", "windowControl")
        self.setFixedSize(34, 34)
        self.setText("")

    def set_icon_name(self, icon_name):
        self.icon_name = icon_name
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        color = QColor(THEME["accent"] if self.isChecked() else "#334155")
        if self.icon_name == "close" and self.underMouse():
            color = QColor(THEME["danger"])
        painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        rect = self.rect()
        cx = rect.center().x()
        cy = rect.center().y()

        if self.icon_name == "collapse":
            path = QPainterPath()
            path.moveTo(cx - 6, cy - 2)
            path.lineTo(cx, cy + 4)
            path.lineTo(cx + 6, cy - 2)
            painter.drawPath(path)
        elif self.icon_name == "expand":
            path = QPainterPath()
            path.moveTo(cx - 6, cy + 3)
            path.lineTo(cx, cy - 3)
            path.lineTo(cx + 6, cy + 3)
            painter.drawPath(path)
        elif self.icon_name == "pin":
            painter.drawLine(cx, cy - 7, cx, cy + 6)
            painter.drawLine(cx - 5, cy - 3, cx + 5, cy - 3)
            painter.drawLine(cx - 3, cy - 7, cx + 3, cy - 7)
            painter.drawLine(cx - 3, cy + 6, cx + 3, cy + 6)
        elif self.icon_name == "close":
            painter.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
            painter.drawLine(cx + 5, cy - 5, cx - 5, cy + 5)


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

        self.summary_label = QLabel(self.summary_text())
        self.summary_label.setObjectName("TaskSummary")
        self.summary_label.setWordWrap(True)
        self.summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.priority_label = QLabel(f"P{normalize_priority(self.task.priority_level)}")
        self.priority_label.setObjectName("PriorityBadge")
        self.priority_label.setFixedWidth(28)
        self.priority_label.setAlignment(Qt.AlignCenter)

        row_layout.addWidget(checkbox)
        row_layout.addWidget(self.summary_label, 1)
        row_layout.addWidget(self.priority_label, 0, Qt.AlignTop)

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

        description = (self.task.description or "").strip() or "我懒得描述"
        detail_description = QLabel(f"描述：{description}")
        detail_description.setWordWrap(True)
        detail_layout.addWidget(detail_description)

        complete_button = QPushButton("完成任务")
        complete_button.setObjectName("CompleteButton")
        complete_button.clicked.connect(
            lambda checked=False: self.complete_requested.emit(self.task.task_id)
        )
        detail_layout.addWidget(complete_button, 0, Qt.AlignRight)
        layout.addWidget(self.detail_frame)

        self.set_expanded(False)

    def summary_text(self):
        minimal_action = (getattr(self.task, "minimal_action", "") or "").strip()
        if not minimal_action:
            minimal_action = (self.task.title or "").strip()[:12] or DEFAULT_MINIMAL_ACTION
        if self.time_text:
            return f"{minimal_action}（{self.time_text}）"
        return minimal_action

    def apply_style(self):
        priority = normalize_priority(self.task.priority_level)
        base_color = QColor(priority_card_color(priority))
        background_color = self.rgba(base_color, 188 if self.task.is_completed else 232)
        border_color = self.rgba(base_color.darker(126), 238)
        hover_color = self.rgba(base_color.lighter(106), 238)
        text_color = PRIORITY_TEXT_COLOR
        pin_background = self.rgba(base_color.lighter(112), 230) if self.is_pinned else "#ffffff"
        pin_text_color = text_color if self.is_pinned else "#666666"
        self.setStyleSheet(f"""
            QFrame#FloatingTaskItem {{
                background-color: {background_color};
                border: 1px solid {border_color};
                border-radius: 7px;
            }}

            QLabel#TaskSummary,
            QLabel#TaskCheck,
            QLabel#PriorityBadge,
            QFrame#TaskDetail,
            QFrame#TaskDetail QLabel {{
                color: {text_color};
                background-color: transparent;
            }}

            QLabel#PriorityBadge {{
                min-height: 20px;
                border-radius: 8px;
                border: 1px solid {border_color};
                background-color: rgba(255, 255, 255, 92);
                font-size: 11px;
                font-weight: 700;
            }}

            QLabel#DetailTitle {{
                font-weight: bold;
                color: {text_color};
            }}

            QPushButton#PinTaskButton {{
                padding: 0;
                border-radius: 7px;
                border: 1px solid #CBD5E1;
                background-color: {pin_background};
                color: {pin_text_color};
                font-size: 15px;
                font-weight: 600;
            }}

            QPushButton#PinTaskButton:hover {{
                border: 1px solid #94A3B8;
                background-color: {hover_color};
            }}

            QPushButton#CompleteButton {{
                min-height: 32px;
                padding: 4px 12px;
                border-radius: 8px;
                border: 1px solid #8FAFD3;
                background-color: #E8F1FC;
                color: #315F98;
                font-weight: 600;
            }}

            QPushButton#CompleteButton:hover {{
                background-color: #D7E7F8;
                border-color: #7FA3CE;
            }}
        """)

    def rgba(self, color, alpha):
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"

    def contextMenuEvent(self, event):
        if not self.allow_pin:
            return
        menu = QMenu(self)
        apply_dark_popup_style(menu)
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
    date_check_requested = Signal()
    show_main_requested = Signal()
    new_task_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_service = TaskService()
        self.settings = QSettings(APP_NAME, "FloatingWindow")
        self.current_page = PAGE_TASKS
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
        self._changing_collapsed_state = False
        self.expanded_size = QSize(EXPANDED_DEFAULT_WIDTH, EXPANDED_DEFAULT_HEIGHT)
        self.task_scroll_position = 0
        self.expanded_task_ids = set()

        self.setWindowTitle("日计划")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.is_window_pinned)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(EXPANDED_MIN_WIDTH, EXPANDED_MIN_HEIGHT)
        self.resize(EXPANDED_DEFAULT_WIDTH, EXPANDED_DEFAULT_HEIGHT)

        self.init_ui()
        self.restore_settings()
        self.refresh_tasks()
        self.apply_collapsed_state()
        if self.is_collapsed:
            self.apply_collapsed_geometry()
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
        self.root_content_layout.setContentsMargins(14, 12, 14, 14)
        self.root_content_layout.setSpacing(12)

        self.title_bar = QFrame()
        self.title_bar.setObjectName("FloatingTitleBar")
        self.title_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.title_bar.setFixedHeight(44)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(6)

        self.title_label = QLabel("日计划")
        self.title_label.setObjectName("FloatingTitle")
        self.title_label.setVisible(False)

        self.page_group = QButtonGroup(self)
        self.page_group.setExclusive(True)
        self.page_buttons = {}
        self.page_switch_frame = QFrame()
        self.page_switch_frame.setObjectName("PageSwitchFrame")
        self.page_switch_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        page_switch_layout = QHBoxLayout(self.page_switch_frame)
        page_switch_layout.setContentsMargins(2, 2, 2, 2)
        page_switch_layout.setSpacing(2)
        for page_key in PAGE_ORDER:
            button = QPushButton(PAGE_LABELS[page_key])
            button.setObjectName("PageButton")
            button.setCheckable(True)
            button.setMinimumWidth(0)
            button.setFixedHeight(32)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False, selected=page_key: self.set_page(selected))
            self.page_group.addButton(button)
            self.page_buttons[page_key] = button
            page_switch_layout.addWidget(button)
        title_layout.addWidget(self.page_switch_frame, 1)

        self.collapse_button = WindowIconButton("collapse")
        self.collapse_button.setObjectName("TitleButton")
        self.collapse_button.clicked.connect(self.toggle_collapsed)

        self.pin_window_button = WindowIconButton("pin")
        self.pin_window_button.setObjectName("WindowPinButton")
        self.pin_window_button.setCheckable(True)
        self.pin_window_button.clicked.connect(self.toggle_window_pinned)

        self.close_button = WindowIconButton("close")
        self.close_button.setObjectName("TitleButton")
        self.close_button.setProperty("role", "dangerWindowControl")
        self.close_button.clicked.connect(self.hide_window)

        title_layout.addWidget(self.collapse_button)
        title_layout.addWidget(self.pin_window_button)
        title_layout.addWidget(self.close_button)

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

        self.quick_note_view = QuickNoteView(self)
        self.quick_note_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.content_stack = CurrentPageStack()
        self.content_stack.setObjectName("FloatingContentStack")
        self.content_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.task_page = QWidget()
        self.task_page.setObjectName("FloatingTaskPage")
        self.task_page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        task_page_layout = QVBoxLayout(self.task_page)
        task_page_layout.setContentsMargins(0, 0, 0, 0)
        task_page_layout.setSpacing(0)
        task_page_layout.addWidget(self.scroll_area, 1)

        self.quick_note_page = QWidget()
        self.quick_note_page.setObjectName("FloatingQuickNotePage")
        self.quick_note_page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        quick_note_page_layout = QVBoxLayout(self.quick_note_page)
        quick_note_page_layout.setContentsMargins(0, 0, 0, 0)
        quick_note_page_layout.setSpacing(0)
        quick_note_page_layout.addWidget(self.quick_note_view, 1)

        self.content_stack.addWidget(self.task_page)
        self.content_stack.addWidget(self.quick_note_page)

        self.root_content_layout.addWidget(self.title_bar, 0)
        self.root_content_layout.addWidget(self.content_stack, 1)

        for widget in (self.root_frame, self.title_bar, self.title_label, self.task_page, self.task_container):
            widget.installEventFilter(self)

        self.update_pin_button_text()
        self.setStyleSheet(floating_window_qss())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS_WINDOW, RADIUS_WINDOW)
        painter.fillPath(path, QColor(248, 250, 252, 225))
        painter.setPen(QPen(QColor(203, 213, 225, 180), 1))
        painter.drawPath(path)
        super().paintEvent(event)

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
        self.is_collapsed = self.settings.value("collapsed", self.is_collapsed, type=bool)

        pos = self.settings.value("pos")
        if isinstance(pos, QPoint):
            self.move(pos)

        checked_page_button = self.page_buttons.get(self.current_page)
        if checked_page_button is not None:
            checked_page_button.setChecked(True)

    def save_settings(self):
        self.settings.setValue("pos", self.visible_position_for_saved_settings())
        self.settings.setValue("opacity", self.clamp_opacity(int(self.windowOpacity() * 100)))
        self.settings.setValue("collapsed", self.is_collapsed)
        self.settings.setValue("page", self.current_page)
        self.settings.setValue("visible", self.isVisible())
        self.settings.setValue("pinned", self.is_window_pinned)
        self.settings.setValue("auto_hide_enabled", self.auto_hide_enabled)
        self.settings.setValue("snap_edge", self.snap_edge or "")
        self.settings.setValue("snap_corner", self.snap_corner or "")

    def show_window(self, activate=True):
        self.date_check_requested.emit()
        if self.current_page == PAGE_QUICK_NOTE:
            self.show_quick_note()
        else:
            self.show_task_list()
            self.refresh_tasks()
        self.show()
        if self.is_auto_hidden:
            self.apply_auto_hide()
        else:
            self.ensure_inside_screen()
        self.raise_()
        if activate:
            self.activateWindow()
        self.settings.setValue("visible", True)

    def hide_window(self):
        self.quick_note_view.final_save()
        self.save_settings()
        self.hide()
        self.settings.setValue("visible", False)

    def should_show_on_startup(self):
        return self.settings.value("visible", False, type=bool)

    def set_page(self, page_key):
        if page_key not in PAGE_LABELS:
            return
        if self.current_page == PAGE_TASKS:
            self.remember_task_page_state()
        elif self.current_page == PAGE_QUICK_NOTE and page_key != PAGE_QUICK_NOTE:
            self.quick_note_view.final_save()

        self.current_page = page_key
        self.settings.setValue("page", page_key)
        button = self.page_buttons.get(page_key)
        if button is not None and not button.isChecked():
            button.setChecked(True)

        if page_key == PAGE_QUICK_NOTE:
            self.show_quick_note()
            return
        self.show_task_list()
        self.refresh_tasks()

    def show_task_list(self):
        self.content_stack.setCurrentWidget(self.task_page)
        self.content_stack.setVisible(not self.is_collapsed)

    def show_quick_note(self):
        self.content_stack.setCurrentWidget(self.quick_note_page)
        self.content_stack.setVisible(not self.is_collapsed)
        if not self.is_collapsed:
            self.quick_note_view.editor.setFocus()
        self.update_collapsed_text()
        self.schedule_reposition_after_resize()

    def refresh_tasks(self):
        if self.current_page != PAGE_TASKS:
            return
        self.remember_task_page_state()
        self.clear_task_layout()
        tasks = self.get_today_plan_tasks()

        if not tasks:
            empty_label = QLabel("今日日计划为空")
            empty_label.setObjectName("EmptyLabel")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setWordWrap(True)
            self.task_layout.addWidget(empty_label)
        else:
            for task_info in tasks:
                self.add_task_item(task_info, allow_pin=True)

        self.task_layout.addStretch()
        self.update_collapsed_text()
        self.restore_task_page_state()
        self.schedule_reposition_after_resize()

    def add_task_item(self, task_info, allow_pin):
        task, time_text, category_text = task_info
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
        item.set_expanded(task.task_id in self.expanded_task_ids)

    def handle_task_item_expanded(self):
        self.remember_expanded_task_items()
        self.begin_internal_interaction()
        if self.is_auto_hidden:
            self.show_from_auto_hide()
        self.schedule_reposition_after_resize()

    def remember_task_page_state(self):
        self.task_scroll_position = self.scroll_area.verticalScrollBar().value()
        self.remember_expanded_task_items()

    def restore_task_page_state(self):
        QTimer.singleShot(0, lambda: self.scroll_area.verticalScrollBar().setValue(self.task_scroll_position))

    def remember_expanded_task_items(self):
        expanded_ids = set()
        for index in range(self.task_layout.count()):
            widget = self.task_layout.itemAt(index).widget()
            if isinstance(widget, FloatingTaskItem) and widget.is_expanded:
                expanded_ids.add(widget.task.task_id)
        self.expanded_task_ids = expanded_ids

    def clear_task_layout(self):
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def get_today_plan_tasks(self):
        today = period_service.get_local_today()
        self.task_service.ensure_daily_plan_tasks_for_date(today)
        tasks = self.task_service.get_current_plan_tasks(PlanLevel.DAY, today)
        tasks = sorted(
            tasks,
            key=self.task_sort_key,
        )
        return [
            (
                task,
                self.floating_time_text(task, today),
                "日计划",
            )
            for task in tasks
        ]

    def task_sort_key(self, task):
        priority = normalize_priority(task.priority_level)
        fixed_time = task.scheduled_at or "9999-12-31 23:59:59"
        if priority != 0:
            fixed_time = "9999-12-31 23:59:59"
        return (
            task.is_completed,
            priority,
            fixed_time,
            task.task_id not in self.pinned_task_ids,
            task.created_at or "",
            task.task_id or 0,
        )

    def floating_time_text(self, task, today):
        if normalize_priority(task.priority_level) == 0 and task.scheduled_at:
            return f"时间：{format_task_time(task.scheduled_at)}"
        return ""

    def toggle_task_pinned(self, task_id):
        if task_id in self.pinned_task_ids:
            self.pinned_task_ids.remove(task_id)
        else:
            self.pinned_task_ids.add(task_id)
        self.refresh_tasks()

    def complete_task(self, task_id):
        if not prompt_and_complete_task(self, self.task_service, task_id):
            return
        self.pinned_task_ids.discard(task_id)
        self.refresh_tasks()
        self.data_changed.emit()

    def update_collapsed_text(self):
        today_count = len(self.task_service.get_current_plan_tasks(PlanLevel.DAY, period_service.get_local_today()))
        text = f"今日 {today_count} 项日计划" if today_count else "日计划"
        if self.is_collapsed:
            self.title_label.setText(text)

    def toggle_collapsed(self):
        self.set_collapsed(not self.is_collapsed)

    def set_collapsed(self, collapsed):
        was_auto_hidden = self.is_auto_hidden
        if was_auto_hidden:
            self.show_from_auto_hide()
        self.cancel_auto_hide_timer()
        if collapsed and not self.is_collapsed:
            self.expanded_size = QSize(
                max(self.width(), EXPANDED_MIN_WIDTH),
                max(self.height(), EXPANDED_MIN_HEIGHT),
            )
        self._changing_collapsed_state = True
        try:
            self.is_collapsed = bool(collapsed)
            self.apply_collapsed_state()
            self.root_content_layout.invalidate()
            self.root_content_layout.activate()
            self.root_frame.updateGeometry()
            self.updateGeometry()
            if self.is_collapsed:
                self.apply_collapsed_geometry()
            else:
                self.restore_expanded_geometry()
        finally:
            self._changing_collapsed_state = False
        self.reposition_after_resize()
        if was_auto_hidden and self.should_auto_hide_after_snap():
            self.apply_auto_hide()
        self.save_settings()

    def apply_collapsed_state(self):
        self.content_stack.setVisible(not self.is_collapsed)
        if self.current_page == PAGE_QUICK_NOTE:
            self.content_stack.setCurrentWidget(self.quick_note_page)
        else:
            self.content_stack.setCurrentWidget(self.task_page)
        self.close_button.setVisible(not self.is_collapsed)
        self.collapse_button.set_icon_name("expand" if self.is_collapsed else "collapse")
        self.title_label.setText("日计划")
        if self.is_collapsed:
            self.update_collapsed_text()
            self.root_content_layout.setContentsMargins(14, 6, 14, 6)
        else:
            self.root_content_layout.setContentsMargins(14, 12, 14, 14)

    def apply_collapsed_geometry(self):
        self.setFixedSize(COLLAPSED_WIDTH, COLLAPSED_HEIGHT)

    def restore_expanded_geometry(self):
        self.setMinimumWidth(EXPANDED_MIN_WIDTH)
        self.setMaximumWidth(16777215)
        self.setMinimumHeight(EXPANDED_MIN_HEIGHT)
        self.setMaximumHeight(16777215)
        target = self.expanded_size if self.expanded_size.isValid() else QSize(
            EXPANDED_DEFAULT_WIDTH,
            EXPANDED_DEFAULT_HEIGHT,
        )
        self.resize(max(target.width(), EXPANDED_MIN_WIDTH), max(target.height(), EXPANDED_MIN_HEIGHT))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.is_collapsed and not self._changing_collapsed_state and self.drag_start_pos is None:
            self.expanded_size = QSize(
                max(self.width(), EXPANDED_MIN_WIDTH),
                max(self.height(), EXPANDED_MIN_HEIGHT),
            )
            self.schedule_reposition_after_resize()

    def showEvent(self, event):
        super().showEvent(event)
        self.date_check_requested.emit()
        if self.current_page == PAGE_TASKS:
            self.refresh_tasks()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow() and self.current_page == PAGE_TASKS:
            self.date_check_requested.emit()
            self.refresh_tasks()

    def toggle_window_pinned(self):
        self.is_window_pinned = not self.is_window_pinned
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.is_window_pinned)
        self.update_pin_button_text()
        self.show()
        self.raise_()
        self.save_settings()

    def update_pin_button_text(self):
        self.pin_window_button.setChecked(self.is_window_pinned)
        self.pin_window_button.setToolTip("取消置顶" if self.is_window_pinned else "置顶窗口")
        self.pin_window_button.update()

    def apply_context_menu_style(self, menu):
        apply_dark_popup_style(menu)

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
