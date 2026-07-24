"""Windows DPAPI-backed storage for user secrets."""

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

from app.config import CONFIG_DIR


SECRETS_PATH = CONFIG_DIR / "secrets.dat"
CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _crypt32():
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI 仅在 Windows 上可用")
    return ctypes.WinDLL("Crypt32.dll", use_last_error=True)


def _kernel32():
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI 仅在 Windows 上可用")
    return ctypes.WinDLL("Kernel32.dll", use_last_error=True)


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def _protect(value: str) -> str:
    raw = value.encode("utf-8")
    input_blob, input_buffer = _blob(raw)
    output_blob = _DataBlob()
    crypt32 = _crypt32()
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        ctypes.POINTER(_DataBlob),
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32 = _kernel32()
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    try:
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        if output_blob.pbData:
            kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def _unprotect(encoded: str) -> str:
    encrypted = base64.b64decode(encoded.encode("ascii"), validate=True)
    input_blob, input_buffer = _blob(encrypted)
    output_blob = _DataBlob()
    crypt32 = _crypt32()
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        ctypes.POINTER(_DataBlob),
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32 = _kernel32()
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    try:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8")
    finally:
        if output_blob.pbData:
            kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def _read_store() -> dict[str, str]:
    if not SECRETS_PATH.exists():
        return {}
    try:
        data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_store(data: dict[str, str]) -> None:
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SECRETS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    os.replace(temporary, SECRETS_PATH)


def save_secret(name: str, value: str) -> None:
    if not name or not isinstance(value, str):
        raise ValueError("密钥名称和值不能为空")
    data = _read_store()
    data[name] = _protect(value)
    _write_store(data)


def load_secret(name: str) -> str:
    if not name:
        return ""
    encoded = _read_store().get(name)
    if not encoded:
        return ""
    try:
        return _unprotect(str(encoded))
    except (ValueError, TypeError, OSError, UnicodeError):
        return ""


def delete_secret(name: str) -> None:
    data = _read_store()
    if name in data:
        del data[name]
        if data:
            _write_store(data)
        elif SECRETS_PATH.exists():
            SECRETS_PATH.unlink()
