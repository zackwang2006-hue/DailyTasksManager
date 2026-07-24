from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPixmap

from app.config import ASSETS_DIR


PICTURE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
PICTURES_DIR = ASSETS_DIR / "pictures"
KAITI_CANDIDATES = ("KaiTi", "楷体", "STKaiti")

_pixmap_cache: dict[str, QPixmap | None] = {}


@dataclass(frozen=True)
class PlanCardPalette:
    background: str
    border: str
    text: str
    secondary_text: str
    button_background: str
    button_hover: str
    button_pressed: str
    button_text: str
    completed_background: str
    completed_border: str
    completed_text: str
    shadow: str


def make_kaiti_font(point_size=None, bold=False):
    available = {family.lower(): family for family in QFontDatabase.families()}
    font = None
    for candidate in KAITI_CANDIDATES:
        matched = available.get(candidate.lower())
        if matched:
            font = QFont(matched)
            break
    if font is None:
        font = QFont()
        font.setStyleHint(QFont.Serif)

    if point_size is not None:
        font.setPointSize(point_size)
    font.setBold(bold)
    return font


def find_plan_picture(title: str) -> Path | None:
    safe_title = str(title).strip()
    if not safe_title:
        return None

    try:
        picture_dir = PICTURES_DIR.resolve()
    except OSError:
        picture_dir = PICTURES_DIR

    for extension in PICTURE_EXTENSIONS:
        candidate = picture_dir / f"{safe_title}{extension}"
        try:
            if candidate.exists() and candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def load_plan_pixmap(title: str) -> QPixmap | None:
    path = find_plan_picture(title)
    if path is None:
        return None

    cache_key = str(path)
    if cache_key not in _pixmap_cache:
        try:
            pixmap = QPixmap(cache_key)
            _pixmap_cache[cache_key] = None if pixmap.isNull() else pixmap
        except (OSError, RuntimeError):
            _pixmap_cache[cache_key] = None
    return _pixmap_cache[cache_key]


def _rgba(color: QColor, alpha: int = 255) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {max(0, min(255, alpha))})"


def _relative_luminance(color: QColor) -> float:
    def channel(value):
        value = value / 255
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color.red())
        + 0.7152 * channel(color.green())
        + 0.0722 * channel(color.blue())
    )


def _readable_text_for(color: QColor) -> str:
    return "#f8fbff" if _relative_luminance(color) < 0.42 else "#111827"


def _sample_image(pixmap: QPixmap | None):
    if pixmap is None or pixmap.isNull():
        return {
            "average": QColor(45, 58, 72),
            "brightness": 72,
            "saturation": 70,
            "complexity": 0,
        }

    image = pixmap.toImage().convertToFormat(QImage.Format_RGB32)
    if image.isNull():
        return {
            "average": QColor(45, 58, 72),
            "brightness": 72,
            "saturation": 70,
            "complexity": 0,
        }

    image = image.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    total_r = total_g = total_b = total_luma = total_sat = 0
    center_luma = 0
    center_count = 0
    lumas = []
    count = max(1, image.width() * image.height())
    center_left = image.width() * 0.18
    center_right = image.width() * 0.82
    center_top = image.height() * 0.22
    center_bottom = image.height() * 0.88

    for y in range(image.height()):
        for x in range(image.width()):
            color = QColor(image.pixel(x, y))
            r, g, b = color.red(), color.green(), color.blue()
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            total_r += r
            total_g += g
            total_b += b
            total_luma += luma
            total_sat += color.saturation()
            lumas.append(luma)
            if center_left <= x <= center_right and center_top <= y <= center_bottom:
                center_luma += luma
                center_count += 1

    average_luma = total_luma / count
    local_luma = center_luma / max(1, center_count)
    variance = sum((luma - average_luma) ** 2 for luma in lumas) / count
    return {
        "average": QColor(total_r // count, total_g // count, total_b // count),
        "brightness": average_luma * 0.65 + local_luma * 0.35,
        "saturation": total_sat / count,
        "complexity": variance ** 0.5,
    }


def build_plan_card_palette(pixmap: QPixmap | None) -> PlanCardPalette:
    sample = _sample_image(pixmap)
    average = sample["average"]
    background_brightness = sample["brightness"]
    average_saturation = sample["saturation"]
    complexity = sample["complexity"]

    hue = average.hsvHue()
    if hue < 0:
        hue = 210
    if 45 <= hue <= 85:
        hue = (hue + 165) % 360
    elif 85 < hue <= 155:
        hue = (hue + 95) % 360
    else:
        hue = (hue + 28) % 360

    saturation = int(max(120, min(220, average_saturation + 58)))
    value = 74 if background_brightness > 150 else 108
    if complexity > 54:
        value = max(66, value - 8)
    base = QColor.fromHsv(hue, saturation, value)
    text = _readable_text_for(base)
    text_is_light = text == "#f8fbff"

    border = base.lighter(155 if text_is_light else 85)
    button = base.lighter(135 if text_is_light else 78)
    completed = QColor.fromHsv((hue + 12) % 360, max(70, saturation - 50), max(48, value - 28))

    alpha = 236 if complexity > 54 else 222
    return PlanCardPalette(
        background=_rgba(base, alpha),
        border=_rgba(border, 238),
        text=text,
        secondary_text="rgba(248, 251, 255, 210)" if text_is_light else "rgba(17, 24, 39, 210)",
        button_background=_rgba(button, 230),
        button_hover=_rgba(button.lighter(116), 242),
        button_pressed=_rgba(button.darker(114), 242),
        button_text=text,
        completed_background=_rgba(completed, 210),
        completed_border=_rgba(completed.lighter(145), 230),
        completed_text="rgba(248, 251, 255, 205)" if _readable_text_for(completed) == "#f8fbff" else "rgba(17, 24, 39, 205)",
        shadow="rgba(0, 0, 0, 80)" if background_brightness > 150 else "rgba(0, 0, 0, 45)",
    )
