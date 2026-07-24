import ctypes
import logging
import os
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal


logger = logging.getLogger(__name__)

HOTKEY_DEFAULT = "ctrl_shift_f1"
HOTKEY_OPTIONS = {
    "ctrl_shift_f1": ("Ctrl + Shift + F1", 0x0002 | 0x0004, 0x70),
    "ctrl_alt_f1": ("Ctrl + Alt + F1", 0x0002 | 0x0001, 0x70),
    "ctrl_shift_f2": ("Ctrl + Shift + F2", 0x0002 | 0x0004, 0x71),
    "ctrl_alt_f2": ("Ctrl + Alt + F2", 0x0002 | 0x0001, 0x71),
}
HOTKEY_SETTING_KEY = "floating_window_toggle_hotkey"
WM_HOTKEY = 0x0312
HOTKEY_ID = 0x5341


class _NativeMsg(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
    ]


class _HotkeyNativeEventFilter(QAbstractNativeEventFilter):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, event_type, message):
        return self.manager.handle_native_event(event_type, message)


class GlobalHotkeyManager(QObject):
    activated = Signal(str)

    def __init__(self, parent=None, user32=None):
        QObject.__init__(self, parent)
        self._native_filter = _HotkeyNativeEventFilter(self)
        self.current_id = None
        self._installed = False
        self._user32 = user32
        if self._user32 is None and os.name == "nt":
            self._user32 = ctypes.windll.user32

    @property
    def supported(self):
        return self._user32 is not None

    def start(self, option_id: str) -> str | None:
        if not self.supported:
            self._log_unsupported()
            return None
        if not self._installed:
            app = self._application()
            if app is not None:
                app.installNativeEventFilter(self._native_filter)
                self._installed = True

        if self.replace(option_id):
            return option_id
        if option_id != HOTKEY_DEFAULT and self.replace(HOTKEY_DEFAULT):
            return HOTKEY_DEFAULT
        self.stop()
        return None

    def replace(self, option_id: str) -> bool:
        if option_id not in HOTKEY_OPTIONS:
            return False
        if option_id == self.current_id:
            return True

        previous = self.current_id
        if previous is not None:
            self._unregister()
            self.current_id = None

        if self._register(option_id):
            self.current_id = option_id
            return True

        if previous is not None and self._register(previous):
            self.current_id = previous
            logger.warning("global hotkey replacement failed; restored option=%s", previous)
        else:
            logger.error("global hotkey replacement failed and previous option could not be restored")
        return False

    def stop(self) -> None:
        if self.current_id is not None:
            self._unregister()
            self.current_id = None
        if self._installed:
            app = self._application()
            if app is not None:
                app.removeNativeEventFilter(self._native_filter)
            self._installed = False

    def handle_native_event(self, event_type, message):
        if event_type not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            return False, 0
        try:
            address = int(message)
            native_message = _NativeMsg.from_address(address)
        except (TypeError, ValueError, OSError):
            return False, 0
        if native_message.message == WM_HOTKEY and native_message.wParam == HOTKEY_ID:
            if self.current_id is not None:
                self.activated.emit(self.current_id)
            return True, 0
        return False, 0

    def _register(self, option_id: str) -> bool:
        if not self.supported:
            self._log_unsupported()
            return False
        _, modifiers, virtual_key = HOTKEY_OPTIONS[option_id]
        result = self._user32.RegisterHotKey(None, HOTKEY_ID, modifiers, virtual_key)
        if not result:
            logger.warning("global hotkey registration failed option=%s", option_id)
        return bool(result)

    def _unregister(self) -> None:
        if self.supported:
            self._user32.UnregisterHotKey(None, HOTKEY_ID)

    def _application(self):
        from PySide6.QtWidgets import QApplication

        return QApplication.instance()

    def _log_unsupported(self):
        logger.warning("global hotkeys are only supported on Windows")
