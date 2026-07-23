import json
import logging
import os
import re
import shutil
import uuid
from pathlib import Path

from PySide6.QtGui import QImage

from app.config import DATA_DIR


logger = logging.getLogger(__name__)


class QuickNoteStorage:
    def __init__(self):
        self.base_dir = DATA_DIR / "quick_note"
        self.image_dir = self.base_dir / "images"
        self.annotation_dir = self.base_dir / "annotations"
        self.document_path = self.base_dir / "document.json"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.annotation_dir.mkdir(parents=True, exist_ok=True)

    def load_document(self):
        default_document = {"html": "", "images": {}}
        if not self.document_path.exists():
            return default_document

        try:
            with self.document_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            logger.exception("Failed to load quick note document")
            return default_document

        if not isinstance(data, dict):
            return default_document

        html = data.get("html") if isinstance(data.get("html"), str) else ""
        images = data.get("images") if isinstance(data.get("images"), dict) else {}
        normalized_images = {}
        for image_id, meta in images.items():
            if isinstance(image_id, str) and isinstance(meta, dict):
                normalized_images[image_id] = {
                    "file": str(meta.get("file") or f"{image_id}.png"),
                    "display_width": self._positive_int(meta.get("display_width")),
                    "natural_width": self._positive_int(meta.get("natural_width")),
                    "natural_height": self._positive_int(meta.get("natural_height")),
                    "in_document": bool(meta.get("in_document", True)),
                    "pending_delete": bool(meta.get("pending_delete", False)),
                }

        return {"html": html, "images": normalized_images}

    def save_document(self, html, images):
        payload = {"html": html or "", "images": images or {}}
        self._atomic_write_json(self.document_path, payload)

    def save_clipboard_image(self, image):
        image_id = uuid.uuid4().hex
        file_name = f"{image_id}.png"
        path = self.image_dir / file_name

        if not image.save(str(path), "PNG"):
            raise OSError(f"Failed to save image: {path}")

        return {
            "id": image_id,
            "file": file_name,
            "path": path,
            "natural_width": image.width(),
            "natural_height": image.height(),
        }

    def import_image_file(self, source_path):
        source = Path(source_path)
        if not source.exists():
            return None

        image = QImage(str(source))
        if image.isNull():
            return None

        image_id = uuid.uuid4().hex
        extension = source.suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}:
            extension = ".png"
        file_name = f"{image_id}{extension}"
        destination = self.image_dir / file_name
        try:
            shutil.copy2(source, destination)
        except Exception:
            logger.exception("Failed to import quick note image")
            return None

        return {
            "id": image_id,
            "file": file_name,
            "path": destination,
            "natural_width": image.width(),
            "natural_height": image.height(),
        }

    def get_image_path(self, image_id, images=None):
        images = images or self.load_document().get("images", {})
        meta = images.get(image_id)
        if not meta:
            return self.image_dir / f"{image_id}.png"
        return self.image_dir / str(meta.get("file") or f"{image_id}.png")

    def load_annotations(self, image_id):
        path = self._annotation_path(image_id)
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            logger.exception("Failed to load quick note annotations for %s", image_id)
            return []

        strokes = data.get("strokes") if isinstance(data, dict) else data
        return strokes if isinstance(strokes, list) else []

    def save_annotations(self, image_id, strokes):
        self._atomic_write_json(self._annotation_path(image_id), {"strokes": strokes or []})

    def clear_removed_images(self, used_image_ids, images):
        used = set(used_image_ids)
        for image_id, meta in images.items():
            is_active = image_id in used
            meta["in_document"] = is_active
            if not is_active:
                meta["pending_delete"] = True

    def extract_image_ids(self, html):
        html = html or ""
        ids = set(re.findall(r"quicknote://image/([0-9a-f-]{32,36})", html, re.I))
        ids.update(re.findall(r"([0-9a-f]{32})\.(?:png|jpg|jpeg|bmp|gif|webp)", html, re.I))
        return ids

    def _annotation_path(self, image_id):
        return self.annotation_dir / f"{image_id}.json"

    def _atomic_write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except Exception:
            logger.exception("Failed to save quick note data to %s", path)
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

    def _positive_int(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, value)
