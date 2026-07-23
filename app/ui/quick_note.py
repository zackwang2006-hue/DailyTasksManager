import math
from copy import deepcopy

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QSignalBlocker, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextImageFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.services.quick_note_storage import QuickNoteStorage
from app.ui.flow_layout import FlowLayout
from app.ui.theme import apply_dark_context_menu_style, quick_note_qss, preview_dialog_qss


MIN_IMAGE_WIDTH = 80
SAVE_DEBOUNCE_MS = 500
IMAGE_ID_PROPERTY = QTextFormat.UserProperty + 1
IMAGE_URL_PREFIX = "quicknote://image/"
NOTE_FONTS = (
    ("默认", ""),
    ("宋体", "SimSun"),
    ("黑体", "SimHei"),
    ("楷体", "KaiTi"),
)


class QuickNoteToolbar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QuickNoteToolbar")
        self.init_ui()

    def init_ui(self):
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.font_combo = QComboBox()
        self.font_combo.setObjectName("NoteFontCombo")
        self.font_combo.setFixedWidth(70)
        self.font_combo.setMinimumContentsLength(6)
        self.font_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.font_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.init_font_options()

        self.size_combo = QComboBox()
        self.size_combo.setObjectName("NoteSizeCombo")
        self.size_combo.setFixedWidth(46)
        for size in (9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32):
            self.size_combo.addItem(str(size), size)
        self.size_combo.setCurrentText("12")

        self.bold_button = QToolButton()
        self.bold_button.setText("B")
        self.bold_button.setObjectName("NoteToggleButton")
        self.bold_button.setCheckable(True)
        self.bold_button.setToolTip("加粗")
        self.bold_button.setFixedSize(32, 28)
        bold_font = self.bold_button.font()
        bold_font.setBold(True)
        self.bold_button.setFont(bold_font)

        self.italic_button = QToolButton()
        self.italic_button.setText("I")
        self.italic_button.setObjectName("NoteToggleButton")
        self.italic_button.setCheckable(True)
        self.italic_button.setToolTip("斜体")
        self.italic_button.setFixedSize(32, 28)
        italic_font = self.italic_button.font()
        italic_font.setItalic(True)
        self.italic_button.setFont(italic_font)

        self.title_button = QToolButton()
        self.title_button.setText("标题")
        self.title_button.setObjectName("NoteCommandButton")
        self.title_button.setToolTip("标题")
        self.title_button.setFixedSize(50, 28)

        self.body_button = QToolButton()
        self.body_button.setText("正文")
        self.body_button.setObjectName("NoteCommandButton")
        self.body_button.setToolTip("正文")
        self.body_button.setFixedSize(50, 28)

        for widget in (
            self.font_combo,
            self.size_combo,
            self.bold_button,
            self.italic_button,
            self.title_button,
            self.body_button,
        ):
            layout.addWidget(widget)
        layout.addStretch(1)

    def init_font_options(self):
        default_family = QApplication.font().family()
        available_families = set(QFontDatabase.families())
        for display_name, family_name in NOTE_FONTS:
            family = default_family if display_name == "默认" else family_name
            if display_name == "默认" or family_name in available_families:
                self.font_combo.addItem(display_name, family)
            else:
                self.font_combo.addItem(display_name, default_family)


class QuickNoteEditor(QTextEdit):
    image_inserted = Signal(str)
    image_selected = Signal(str)
    image_selection_cleared = Signal()
    image_resize_requested = Signal(str, float)
    image_preview_requested = Signal(str)

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.images = {}
        self.selected_image_id = None
        self.setObjectName("QuickNoteEditor")
        self.setAcceptRichText(True)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.document().setUndoRedoEnabled(True)
        self.document().setDocumentMargin(12)

    def image_url(self, image_id):
        return f"{IMAGE_URL_PREFIX}{image_id}"

    def canInsertFromMimeData(self, source):
        return source.hasImage() or source.hasUrls() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage) and not image.isNull():
                self.insert_saved_image(image)
                return

        if source.hasUrls():
            inserted = False
            for url in source.urls():
                if not url.isLocalFile():
                    continue
                saved = self.storage.import_image_file(url.toLocalFile())
                if saved:
                    self.insert_image_meta(saved)
                    inserted = True
            if inserted:
                return

        super().insertFromMimeData(source)

    def insert_saved_image(self, image):
        saved = self.storage.save_clipboard_image(image)
        self.insert_image_meta(saved)

    def insert_image_meta(self, saved):
        image_id = saved["id"]
        display_width = min(
            saved["natural_width"],
            max(MIN_IMAGE_WIDTH, self.available_image_width()),
        )
        self.images[image_id] = {
            "file": saved["file"],
            "display_width": display_width,
            "natural_width": saved["natural_width"],
            "natural_height": saved["natural_height"],
            "in_document": True,
            "pending_delete": False,
        }

        image_format = QTextImageFormat()
        image_format.setName(self.image_url(image_id))
        image_format.setProperty(IMAGE_ID_PROPERTY, image_id)
        image_format.setWidth(display_width)
        self.document().addResource(
            QTextDocument.ImageResource,
            QUrl(image_format.name()),
            QImage(str(saved["path"])),
        )
        self.textCursor().insertImage(image_format)
        self.image_inserted.emit(image_id)

    def mousePressEvent(self, event):
        image_id = self.image_id_at_position(event.position().toPoint())
        if image_id:
            self.select_image(image_id, event.position().toPoint())
            self.image_selected.emit(image_id)
            event.accept()
            return
        self.clear_image_selection()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        image_id = self.image_id_at_position(event.position().toPoint())
        if image_id:
            self.select_image(image_id, event.position().toPoint())
            self.image_preview_requested.emit(image_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        image_id = self.image_id_at_position(event.position().toPoint())
        if image_id and image_id == self.selected_image_id:
            steps = event.angleDelta().y() / 120
            if steps:
                self.image_resize_requested.emit(image_id, 1.08 ** steps)
                event.accept()
                return
        super().wheelEvent(event)

    def contextMenuEvent(self, event):
        image_id = self.image_id_at_position(event.pos())
        if image_id:
            self.select_image(image_id, event.pos())
            self.image_selected.emit(image_id)
        menu = self.createStandardContextMenu()
        apply_dark_context_menu_style(menu)
        if menu.actions():
            menu.exec(event.globalPos())

    def select_image(self, image_id, position=None):
        self.selected_image_id = image_id
        if position is None:
            return
        cursor = self.cursorForPosition(position)
        if not cursor.charFormat().toImageFormat().isValid():
            cursor.movePosition(QTextCursor.Left)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)

    def current_image_id(self):
        cursor = self.textCursor()
        image_format = cursor.charFormat().toImageFormat()
        if not image_format.isValid():
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
            image_format = cursor.charFormat().toImageFormat()
        if not image_format.isValid():
            return None
        return self.resolve_image_id(image_format)

    def selected_image_format(self):
        cursor = self.textCursor()
        image_format = cursor.charFormat().toImageFormat()
        if image_format.isValid():
            return image_format
        cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
        image_format = cursor.charFormat().toImageFormat()
        return image_format if image_format.isValid() else None

    def clear_image_selection(self):
        if self.selected_image_id is None:
            return
        self.selected_image_id = None
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.image_selection_cleared.emit()

    def image_id_at_position(self, position):
        cursor = self.cursorForPosition(position)
        image_format = cursor.charFormat().toImageFormat()
        if image_format.isValid():
            return self.resolve_image_id(image_format)
        cursor.movePosition(QTextCursor.Left)
        image_format = cursor.charFormat().toImageFormat()
        if image_format.isValid():
            return self.resolve_image_id(image_format)
        return None

    def set_image_display_width(self, image_id, width):
        meta = self.images.get(image_id)
        if not meta:
            return
        meta["display_width"] = max(MIN_IMAGE_WIDTH, int(width))
        self.apply_image_widths()

    def available_image_width(self):
        return max(MIN_IMAGE_WIDTH, self.viewport().width() - 24)

    def apply_image_widths(self):
        available_width = self.available_image_width()
        cursor = QTextCursor(self.document())
        block = self.document().begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    image_format = fragment.charFormat().toImageFormat()
                    if image_format.isValid():
                        image_id = self.resolve_image_id(image_format)
                        meta = self.images.get(image_id)
                        if meta:
                            width = max(MIN_IMAGE_WIDTH, min(meta.get("display_width", available_width), available_width))
                            cursor.setPosition(fragment.position())
                            cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.KeepAnchor)
                            image_format.setName(self.image_url(image_id))
                            image_format.setProperty(IMAGE_ID_PROPERTY, image_id)
                            image_format.setWidth(width)
                            cursor.setCharFormat(image_format)
                            self.add_image_resource(image_id, image_format)
                iterator += 1
            block = block.next()

    def resolve_image_id(self, image_format):
        image_id = image_format.property(IMAGE_ID_PROPERTY)
        if image_id:
            return str(image_id)
        image_id = self.extract_image_id(image_format.name())
        if image_id:
            return image_id
        return self.find_image_id_by_path(image_format.name())

    def extract_image_id(self, name):
        name = str(name or "")
        if name.startswith(IMAGE_URL_PREFIX):
            return name[len(IMAGE_URL_PREFIX):]
        for image_id in self.images:
            if image_id and image_id in name:
                return image_id
        return None

    def find_image_id_by_path(self, name):
        name = str(name or "").replace("\\", "/").lower()
        for image_id, meta in self.images.items():
            file_name = str(meta.get("file") or "").replace("\\", "/").lower()
            if file_name and file_name in name:
                return image_id
        return None

    def add_image_resource(self, image_id, image_format):
        meta = self.images.get(image_id)
        if not meta:
            return False
        image_path = self.storage.get_image_path(image_id, self.images)
        image = QImage(str(image_path))
        if image.isNull():
            return False
        self.document().addResource(
            QTextDocument.ImageResource,
            QUrl(image_format.name()),
            image,
        )
        return True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.apply_image_widths)


class AnnotationCanvas(QWidget):
    changed = Signal()
    zoom_changed = Signal(float)

    def __init__(self, image, strokes=None, parent=None):
        super().__init__(parent)
        self.image = image
        self.strokes = strokes or []
        self.redo_stack = []
        self.tool = "pen"
        self.color = "#000000"
        self.pen_width = 4
        self.zoom = 1.0
        self.current_stroke = None
        self.undo_stack = []
        self.pan_offset = QPointF(0, 0)
        self.drag_start_pos = None
        self.drag_start_pan = QPointF(0, 0)
        self._space_pressed = False
        self.setMinimumSize(360, 260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.update_cursor()

    def set_tool(self, tool):
        self.tool = tool
        self.update_cursor()

    def set_color(self, color):
        self.color = color
        self.tool = "pen"
        self.update_cursor()

    def set_pen_width(self, width):
        self.pen_width = max(1, min(50, int(width)))
        self.update_cursor()

    def set_zoom(self, zoom, anchor_pos=None):
        old_rect = self.image_rect()
        anchor = anchor_pos if anchor_pos is not None else old_rect.center()
        anchor_ratio = None
        if not old_rect.isEmpty() and old_rect.contains(anchor):
            anchor_ratio = QPointF(
                (anchor.x() - old_rect.left()) / old_rect.width(),
                (anchor.y() - old_rect.top()) / old_rect.height(),
            )
        new_zoom = max(0.1, min(5.0, float(zoom)))
        if abs(new_zoom - self.zoom) < 0.001:
            return
        self.zoom = new_zoom
        if anchor_ratio is not None:
            new_rect = self.image_rect()
            mapped = QPointF(
                new_rect.left() + anchor_ratio.x() * new_rect.width(),
                new_rect.top() + anchor_ratio.y() * new_rect.height(),
            )
            self.pan_offset += anchor - mapped
        self.update()
        self.zoom_changed.emit(self.zoom)

    def image_rect(self):
        if self.image.isNull():
            return QRectF()
        available = self.rect().adjusted(8, 8, -8, -8)
        base = QSize(self.image.width(), self.image.height())
        base.scale(available.size(), Qt.KeepAspectRatio)
        size = base * self.zoom
        x = available.center().x() - size.width() / 2
        y = available.center().y() - size.height() / 2
        return QRectF(x + self.pan_offset.x(), y + self.pan_offset.y(), size.width(), size.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        painter.fillRect(self.rect(), QColor("#F8FAFC"))
        rect = self.image_rect()
        if self.image.isNull() or rect.isEmpty():
            painter.setPen(QColor("#991b1b"))
            painter.drawText(self.rect(), Qt.AlignCenter, "图片加载失败")
            return

        painter.drawImage(rect, self.image)
        for stroke in self.strokes:
            self.draw_stroke(painter, stroke, rect)
        if self.current_stroke:
            self.draw_stroke(painter, self.current_stroke, rect)

    def draw_stroke(self, painter, stroke, rect):
        points = stroke.get("points") or []
        if len(points) < 2:
            return
        width = max(1, float(stroke.get("width", 4))) * rect.width() / max(1, self.image.width())
        pen = QPen(QColor(stroke.get("color", "#000000")), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        previous = self.to_widget_point(points[0], rect)
        for point in points[1:]:
            current = self.to_widget_point(point, rect)
            painter.drawLine(previous, current)
            previous = current

    def to_widget_point(self, point, rect):
        return QPointF(rect.left() + float(point["x"]) * rect.width(), rect.top() + float(point["y"]) * rect.height())

    def to_normalized_point(self, position):
        rect = self.image_rect()
        if rect.isEmpty() or not rect.contains(position):
            return None
        return {
            "x": max(0.0, min(1.0, (position.x() - rect.left()) / rect.width())),
            "y": max(0.0, min(1.0, (position.y() - rect.top()) / rect.height())),
        }

    def mousePressEvent(self, event):
        if event.button() not in (Qt.LeftButton, Qt.MiddleButton):
            return
        self.setFocus()
        if event.button() == Qt.MiddleButton or self._space_pressed:
            self.drag_start_pos = event.position()
            self.drag_start_pan = QPointF(self.pan_offset)
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() != Qt.LeftButton:
            return
        point = self.to_normalized_point(event.position())
        if point is None:
            return
        if self.tool == "eraser":
            self.erase_at(point)
            event.accept()
            return
        self.current_stroke = {
            "tool": "pen",
            "color": self.color,
            "width": self.pen_width,
            "points": [point],
        }
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and event.buttons() & (Qt.LeftButton | Qt.MiddleButton):
            self.pan_offset = self.drag_start_pan + (event.position() - self.drag_start_pos)
            self.update()
            event.accept()
            return
        if not self.current_stroke or not (event.buttons() & Qt.LeftButton):
            self.update_cursor(event.position())
            return
        point = self.to_normalized_point(event.position())
        if point is None:
            return
        points = self.current_stroke["points"]
        if not points or self.point_distance(points[-1], point) > 0.001:
            points.append(point)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.MiddleButton) and self.drag_start_pos is not None:
            self.drag_start_pos = None
            self.update_cursor(event.position())
            event.accept()
            return
        if event.button() == Qt.LeftButton and self.current_stroke:
            if len(self.current_stroke["points"]) > 1:
                self.strokes.append(self.current_stroke)
                self.undo_stack.append(("draw", deepcopy(self.current_stroke)))
                self.redo_stack.clear()
                self.changed.emit()
            self.current_stroke = None
            self.update()

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120
        if steps:
            self.set_zoom(self.zoom * (1.1 ** steps), event.position())
            event.accept()
            return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def update_cursor(self, position=None):
        if self.drag_start_pos is not None:
            self.setCursor(Qt.ClosedHandCursor)
            return
        if self._space_pressed:
            self.setCursor(Qt.OpenHandCursor)
            return
        if position is not None and not self.image_rect().contains(position):
            self.setCursor(Qt.ArrowCursor)
            return
        if self.tool == "eraser":
            self.setCursor(self.create_eraser_cursor())
        else:
            self.setCursor(self.create_pen_cursor())

    def create_pen_cursor(self):
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        painter.setPen(QPen(QColor("#111827"), 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(6, 18, 18, 6)
        painter.drawEllipse(QPointF(6, 18), 2, 2)
        painter.end()
        return QCursor(pixmap, 6, 18)

    def create_eraser_cursor(self):
        size = max(12, min(28, self.pen_width + 10))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        painter.setPen(QPen(QColor("#111827"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(2, 2, size - 5, size - 5)
        painter.end()
        hotspot = size // 2
        return QCursor(pixmap, hotspot, hotspot)

    def erase_at(self, point):
        hit_index = None
        tolerance = max(0.01, self.pen_width / max(1, max(self.image.width(), self.image.height())) * 3)
        for index in range(len(self.strokes) - 1, -1, -1):
            if self.stroke_hit(self.strokes[index], point, tolerance):
                hit_index = index
                break
        if hit_index is not None:
            stroke = self.strokes.pop(hit_index)
            self.undo_stack.append(("erase", hit_index, deepcopy(stroke)))
            self.redo_stack.clear()
            self.changed.emit()
            self.update()

    def stroke_hit(self, stroke, point, tolerance):
        points = stroke.get("points") or []
        for first, second in zip(points, points[1:]):
            if self.distance_to_segment(point, first, second) <= tolerance:
                return True
        return False

    def undo(self):
        if not self.undo_stack:
            return
        action = self.undo_stack.pop()
        if action[0] == "draw":
            if self.strokes:
                self.strokes.pop()
        elif action[0] == "erase":
            _, index, stroke = action
            self.strokes.insert(min(index, len(self.strokes)), deepcopy(stroke))
        elif action[0] == "clear":
            self.strokes[:] = deepcopy(action[1])
        self.redo_stack.append(action)
        self.changed.emit()
        self.update()

    def redo(self):
        if not self.redo_stack:
            return
        action = self.redo_stack.pop()
        if action[0] == "draw":
            self.strokes.append(deepcopy(action[1]))
        elif action[0] == "erase":
            _, index, stroke = action
            if 0 <= index < len(self.strokes):
                self.strokes.pop(index)
            else:
                self.strokes = [item for item in self.strokes if item != stroke]
        elif action[0] == "clear":
            self.strokes.clear()
        self.undo_stack.append(action)
        self.changed.emit()
        self.update()

    def clear_strokes(self):
        if not self.strokes:
            return
        previous = deepcopy(self.strokes)
        self.strokes.clear()
        self.undo_stack.append(("clear", previous))
        self.redo_stack.clear()
        self.changed.emit()
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            self.update_cursor()
            event.accept()
            return
        if event.matches(QKeySequence.Undo):
            self.undo()
            return
        if event.matches(QKeySequence.Redo):
            self.redo()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            if self.drag_start_pos is None:
                self.update_cursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self._space_pressed = False
        self.drag_start_pos = None
        self.drag_start_pan = QPointF(self.pan_offset)
        self.current_stroke = None
        self.update_cursor()
        super().focusOutEvent(event)

    def point_distance(self, a, b):
        return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))

    def distance_to_segment(self, point, first, second):
        px, py = float(point["x"]), float(point["y"])
        ax, ay = float(first["x"]), float(first["y"])
        bx, by = float(second["x"]), float(second["y"])
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class ImagePreviewDialog(QDialog):
    def __init__(self, storage, image_id, image_path, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.image_id = image_id
        self.image = QImage(str(image_path))
        self.setWindowTitle("图片预览")
        self.resize(820, 620)
        self.limit_to_screen()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        toolbar = QFrame()
        toolbar.setObjectName("PreviewToolbar")
        toolbar_layout = FlowLayout(toolbar, margin=0, spacing=6)

        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for label, color in (("黑", "#000000"), ("红", "#dc2626"), ("蓝", "#2563eb"), ("绿", "#16a34a")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setMinimumSize(34, 30)
            button.setProperty("color", color)
            button.setObjectName("AnnotationToolButton")
            button.clicked.connect(lambda checked=False, selected=color: self.select_color(selected))
            self.color_group.addButton(button)
            toolbar_layout.addWidget(button)

        self.eraser_button = QPushButton("橡皮")
        self.eraser_button.setObjectName("AnnotationToolButton")
        self.eraser_button.setCheckable(True)
        self.eraser_button.clicked.connect(self.select_eraser)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 50)
        self.width_spin.setValue(4)
        self.width_spin.setSuffix(" px")
        self.width_spin.setMinimumWidth(78)
        self.width_spin.setToolTip("画笔粗细")

        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 50)
        self.width_slider.setValue(4)
        self.width_slider.setMinimumWidth(120)
        self.width_slider.valueChanged.connect(self.sync_width_from_slider)
        self.width_spin.valueChanged.connect(self.sync_width_from_spin)

        undo_button = QPushButton("撤销")
        undo_button.clicked.connect(lambda: self.canvas.undo())
        redo_button = QPushButton("重做")
        redo_button.clicked.connect(lambda: self.canvas.redo())
        clear_button = QPushButton("清除")
        clear_button.clicked.connect(self.confirm_clear)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setMinimumWidth(120)
        self.zoom_slider.valueChanged.connect(lambda value: self.canvas.set_zoom(value / 100))

        toolbar_layout.addWidget(self.eraser_button)
        toolbar_layout.addWidget(QLabel("粗细"))
        toolbar_layout.addWidget(self.width_slider)
        toolbar_layout.addWidget(self.width_spin)
        toolbar_layout.addWidget(undo_button)
        toolbar_layout.addWidget(redo_button)
        toolbar_layout.addWidget(clear_button)
        toolbar_layout.addWidget(QLabel("缩放"))
        toolbar_layout.addWidget(self.zoom_slider)

        self.canvas = AnnotationCanvas(self.image, self.storage.load_annotations(self.image_id))
        self.canvas.changed.connect(self.save_annotations)
        self.canvas.zoom_changed.connect(self.sync_zoom_slider)
        first_button = self.color_group.buttons()[0]
        first_button.setChecked(True)

        layout.addWidget(toolbar)
        layout.addWidget(self.canvas, 1)
        self.apply_style()

        undo_action = QAction(self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.canvas.undo)
        self.addAction(undo_action)
        redo_action = QAction(self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.canvas.redo)
        self.addAction(redo_action)

    def select_color(self, color):
        self.eraser_button.setChecked(False)
        self.canvas.set_color(color)

    def select_eraser(self):
        for button in self.color_group.buttons():
            button.setChecked(False)
        self.eraser_button.setChecked(True)
        self.canvas.set_tool("eraser")

    def set_pen_width(self, width):
        self.canvas.set_pen_width(width)

    def sync_width_from_slider(self, width):
        self.width_spin.blockSignals(True)
        self.width_spin.setValue(width)
        self.width_spin.blockSignals(False)
        self.set_pen_width(width)

    def sync_width_from_spin(self, width):
        self.width_slider.blockSignals(True)
        self.width_slider.setValue(width)
        self.width_slider.blockSignals(False)
        self.set_pen_width(width)

    def sync_zoom_slider(self, zoom):
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(round(zoom * 100))
        self.zoom_slider.blockSignals(False)

    def confirm_clear(self):
        if QMessageBox.question(
            self,
            "清除笔迹",
            "确定清除这张图片上的全部笔迹吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.canvas.clear_strokes()

    def save_annotations(self):
        self.storage.save_annotations(self.image_id, self.canvas.strokes)

    def closeEvent(self, event):
        self.save_annotations()
        super().closeEvent(event)

    def limit_to_screen(self):
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        self.resize(min(self.width(), available.width() - 80), min(self.height(), available.height() - 80))

    def apply_style(self):
        self.setStyleSheet(preview_dialog_qss())


class QuickNoteView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.storage = QuickNoteStorage()
        self.images = {}
        self.loading = False
        self.current_image_id = None
        self.syncing_images = False
        self.sync_images_timer = QTimer(self)
        self.sync_images_timer.setSingleShot(True)
        self.sync_images_timer.timeout.connect(self.sync_document_images)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_now)
        self.init_ui()
        self.load_note()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.toolbar = QuickNoteToolbar()
        self.editor = QuickNoteEditor(self.storage)
        self.editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.editor.textChanged.connect(self.schedule_save)
        self.editor.cursorPositionChanged.connect(self.sync_toolbar_state)
        self.editor.image_inserted.connect(self.on_image_inserted)
        self.editor.image_selected.connect(self.on_image_selected)
        self.editor.image_selection_cleared.connect(self.on_image_selection_cleared)
        self.editor.image_resize_requested.connect(self.adjust_image)
        self.editor.image_preview_requested.connect(self.preview_image)

        layout.addWidget(self.toolbar, 0)
        layout.addWidget(self.editor, 1)

        self.toolbar.font_combo.currentIndexChanged.connect(self.set_font_family)
        self.toolbar.size_combo.currentIndexChanged.connect(self.set_font_size)
        self.toolbar.bold_button.clicked.connect(self.set_bold)
        self.toolbar.italic_button.clicked.connect(self.set_italic)
        self.toolbar.title_button.clicked.connect(self.apply_title_style)
        self.toolbar.body_button.clicked.connect(self.apply_body_style)
        self.add_format_shortcuts()
        self.add_edit_shortcuts()

        self.apply_style()

    def add_format_shortcuts(self):
        bold_action = QAction(self)
        bold_action.setShortcut(QKeySequence.Bold)
        bold_action.triggered.connect(lambda: self.toolbar.bold_button.click())
        self.addAction(bold_action)

        italic_action = QAction(self)
        italic_action.setShortcut(QKeySequence.Italic)
        italic_action.triggered.connect(lambda: self.toolbar.italic_button.click())
        self.addAction(italic_action)

    def add_edit_shortcuts(self):
        undo_shortcut = QShortcut(QKeySequence.Undo, self.editor)
        undo_shortcut.activated.connect(self.undo_note_edit)
        redo_shortcut = QShortcut(QKeySequence.Redo, self.editor)
        redo_shortcut.activated.connect(self.redo_note_edit)

    def load_note(self):
        self.loading = True
        data = self.storage.load_document()
        self.images = data.get("images", {})
        self.editor.images = self.images
        self.editor.blockSignals(True)
        self.editor.setHtml(data.get("html", ""))
        self.editor.blockSignals(False)
        self.sync_document_images()
        self.editor.apply_image_widths()
        self.loading = False
        self.editor.document().setModified(False)
        self.sync_toolbar_state()

    def schedule_save(self):
        if self.loading:
            return
        self.sync_images_timer.start(0)
        self.save_timer.start(SAVE_DEBOUNCE_MS)

    def save_now(self):
        if self.loading:
            return
        self.sync_document_images()
        self.storage.save_document(self.editor.toHtml(), self.images)
        self.editor.document().setModified(False)

    def undo_note_edit(self):
        self.editor.undo()
        QTimer.singleShot(0, self.sync_document_images)

    def redo_note_edit(self):
        self.editor.redo()
        QTimer.singleShot(0, self.sync_document_images)

    def sync_document_images(self):
        if self.syncing_images:
            return
        self.syncing_images = True
        active_image_ids = set()
        document = self.editor.document()
        block = document.begin()

        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    image_format = fragment.charFormat().toImageFormat()
                    if image_format.isValid():
                        image_id = self.editor.resolve_image_id(image_format)
                        if image_id:
                            image_id = str(image_id)
                            active_image_ids.add(image_id)
                            self.ensure_image_resource(image_id, image_format)
                iterator += 1
            block = block.next()

        for image_id, record in self.images.items():
            is_active = image_id in active_image_ids
            record["in_document"] = is_active
            if is_active:
                record["pending_delete"] = False
            else:
                record["pending_delete"] = True

        self.syncing_images = False

    def ensure_image_resource(self, image_id, image_format):
        record = self.images.get(image_id)
        if record is None:
            return False
        image_path = self.storage.get_image_path(image_id, self.images)
        image = QImage(str(image_path))
        if image.isNull():
            return False
        self.editor.document().addResource(
            QTextDocument.ImageResource,
            QUrl(image_format.name()),
            image,
        )
        record["in_document"] = True
        record["pending_delete"] = False
        return True

    def final_save(self):
        if self.save_timer.isActive():
            self.save_timer.stop()
        self.save_now()

    def on_image_inserted(self, image_id):
        self.current_image_id = image_id
        self.editor.apply_image_widths()
        self.editor.select_image(image_id)
        self.schedule_save()

    def on_image_selected(self, image_id):
        if image_id not in self.images:
            return
        self.current_image_id = image_id

    def on_image_selection_cleared(self):
        self.current_image_id = None

    def adjust_image(self, image_id, factor):
        meta = self.images.get(image_id)
        if not meta:
            return
        natural_width = meta.get("natural_width") or self.editor.available_image_width()
        new_width = int(meta.get("display_width", natural_width) * factor)
        new_width = max(MIN_IMAGE_WIDTH, min(new_width, natural_width, self.editor.available_image_width()))
        self.editor.set_image_display_width(image_id, new_width)
        self.current_image_id = image_id
        self.schedule_save()

    def preview_image(self, image_id=None):
        image_id = image_id or self.current_image_id or self.editor.current_image_id()
        if not image_id:
            return
        image_format = self.editor.selected_image_format()
        if image_format is not None:
            self.ensure_image_resource(image_id, image_format)
        image_path = self.storage.get_image_path(image_id, self.images)
        dialog = ImagePreviewDialog(self.storage, image_id, image_path, self)
        dialog.exec()

    def set_font_family(self, index=None):
        if not isinstance(index, int):
            index = self.toolbar.font_combo.currentIndex()
        family = self.toolbar.font_combo.itemData(index) or QApplication.font().family()
        if not family:
            return
        fmt = QTextCharFormat()
        fmt.setFontFamily(family)
        self.merge_format(fmt)

    def set_font_size(self, *_):
        size = self.toolbar.size_combo.currentData()
        if not size:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self.merge_format(fmt)

    def set_bold(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if checked else QFont.Normal)
        self.merge_format(fmt)

    def set_italic(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self.merge_format(fmt)

    def apply_title_style(self):
        self.apply_named_style(font_family="SimSun", font_size=16, bold=True, italic=False)

    def apply_body_style(self):
        self.apply_named_style(font_family="SimSun", font_size=12, bold=False, italic=False)

    def apply_named_style(self, font_family, font_size, bold, italic):
        fmt = QTextCharFormat()
        fmt.setFontFamily(font_family)
        fmt.setFontPointSize(float(font_size))
        fmt.setFontWeight(QFont.Bold if bold else QFont.Normal)
        fmt.setFontItalic(italic)
        self.merge_format(fmt)
        self.sync_toolbar_to_values(font_family, font_size, bold, italic)

    def merge_format(self, fmt):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            self.editor.mergeCurrentCharFormat(fmt)
        else:
            cursor.mergeCharFormat(fmt)
            self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()
        self.schedule_save()

    def sync_toolbar_state(self):
        fmt = self.editor.currentCharFormat()
        blockers = [
            QSignalBlocker(self.toolbar.bold_button),
            QSignalBlocker(self.toolbar.italic_button),
            QSignalBlocker(self.toolbar.size_combo),
        ]
        self.toolbar.bold_button.setChecked(fmt.fontWeight() >= QFont.Bold)
        self.toolbar.italic_button.setChecked(fmt.fontItalic())
        family = fmt.font().family()
        self.sync_font_combo(family)
        size = int(fmt.fontPointSize()) if fmt.fontPointSize() > 0 else 12
        index = self.toolbar.size_combo.findText(str(size))
        if index >= 0:
            self.toolbar.size_combo.setCurrentIndex(index)
        del blockers

    def sync_toolbar_to_values(self, font_family, font_size, bold, italic):
        blockers = [
            QSignalBlocker(self.toolbar.bold_button),
            QSignalBlocker(self.toolbar.italic_button),
            QSignalBlocker(self.toolbar.size_combo),
        ]
        self.toolbar.bold_button.setChecked(bold)
        self.toolbar.italic_button.setChecked(italic)
        self.sync_font_combo(font_family)
        size_index = self.toolbar.size_combo.findText(str(font_size))
        if size_index >= 0:
            self.toolbar.size_combo.setCurrentIndex(size_index)
        del blockers

    def sync_font_combo(self, font_family):
        default_family = QApplication.font().family()
        mapping = {
            default_family: "默认",
            "Microsoft YaHei UI": "默认",
            "Microsoft YaHei": "默认",
            "YaHei UI": "默认",
            "SimSun": "宋体",
            "宋体": "宋体",
            "SimHei": "黑体",
            "黑体": "黑体",
            "KaiTi": "楷体",
            "楷体": "楷体",
        }
        target_text = mapping.get(font_family, "默认")
        blocker = QSignalBlocker(self.toolbar.font_combo)
        index = self.toolbar.font_combo.findText(target_text)
        if index >= 0:
            self.toolbar.font_combo.setCurrentIndex(index)
        del blocker

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.editor.apply_image_widths()

    def apply_style(self):
        self.setStyleSheet(quick_note_qss())
