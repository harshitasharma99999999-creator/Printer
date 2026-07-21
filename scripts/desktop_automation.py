"""Small Windows desktop helpers for logged-in browser upload fallbacks."""

from __future__ import annotations

import ctypes
import subprocess
import time
from ctypes import wintypes
from pathlib import Path


USER32 = ctypes.windll.user32
KERNEL32 = ctypes.windll.kernel32

WM_MOUSEWHEEL = 0x020A
WHEEL_DELTA = 120
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

KERNEL32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
KERNEL32.GlobalAlloc.restype = ctypes.c_void_p
KERNEL32.GlobalLock.argtypes = [ctypes.c_void_p]
KERNEL32.GlobalLock.restype = ctypes.c_void_p
KERNEL32.GlobalUnlock.argtypes = [ctypes.c_void_p]
KERNEL32.GlobalUnlock.restype = wintypes.BOOL
USER32.OpenClipboard.argtypes = [wintypes.HWND]
USER32.OpenClipboard.restype = wintypes.BOOL
USER32.EmptyClipboard.argtypes = []
USER32.EmptyClipboard.restype = wintypes.BOOL
USER32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
USER32.SetClipboardData.restype = ctypes.c_void_p
USER32.CloseClipboard.argtypes = []
USER32.CloseClipboard.restype = wintypes.BOOL


def chrome_path() -> str:
    candidate = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"
    if candidate.exists():
        return str(candidate)
    return "chrome.exe"


def set_clipboard(text: str) -> None:
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    if not USER32.OpenClipboard(None):
        raise RuntimeError("Could not open Windows clipboard")
    try:
        USER32.EmptyClipboard()
        handle = KERNEL32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            raise RuntimeError("Could not allocate clipboard memory")
        pointer = KERNEL32.GlobalLock(handle)
        if not pointer:
            raise RuntimeError("Could not lock clipboard memory")
        ctypes.memmove(pointer, data, size)
        KERNEL32.GlobalUnlock(handle)
        if not USER32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("Could not set clipboard data")
    finally:
        USER32.CloseClipboard()


def send_key(vk: int) -> None:
    USER32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.04)
    USER32.keybd_event(vk, 0, 2, 0)


def hotkey(*keys: int) -> None:
    for key in keys:
        USER32.keybd_event(key, 0, 0, 0)
        time.sleep(0.03)
    for key in reversed(keys):
        USER32.keybd_event(key, 0, 2, 0)
        time.sleep(0.03)


def paste_text(text: str) -> None:
    set_clipboard(text)
    time.sleep(0.2)
    hotkey(0x11, 0x56)  # Ctrl+V


def click(x: int, y: int, delay: float = 0.35) -> None:
    USER32.SetCursorPos(x, y)
    time.sleep(0.12)
    USER32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    USER32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(delay)


def scroll(clicks: int) -> None:
    USER32.mouse_event(WM_MOUSEWHEEL, 0, 0, clicks * WHEEL_DELTA, 0)
    time.sleep(0.5)


def foreground_window(title_keywords: tuple[str, ...], timeout: int = 20) -> str:
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    deadline = time.time() + timeout

    while time.time() < deadline:
        matches: list[tuple[int, str]] = []

        def callback(hwnd: int, _lparam: int) -> bool:
            if USER32.IsWindowVisible(hwnd):
                length = USER32.GetWindowTextLengthW(hwnd)
                if length:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    USER32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    lowered = title.lower()
                    if any(keyword.lower() in lowered for keyword in title_keywords):
                        matches.append((hwnd, title))
            return True

        USER32.EnumWindows(enum_proc(callback), 0)
        if matches:
            hwnd, title = matches[0]
            USER32.ShowWindow(hwnd, 3)
            time.sleep(0.5)
            USER32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            return title
        time.sleep(1)
    raise RuntimeError(f"No visible window found for: {', '.join(title_keywords)}")


def open_chrome(url: str, profile_directory: str = "Profile 8") -> None:
    subprocess.Popen([chrome_path(), f"--profile-directory={profile_directory}", url])
    time.sleep(8)


def navigate(url: str) -> None:
    hotkey(0x11, 0x4C)  # Ctrl+L
    paste_text(url)
    send_key(0x0D)
    time.sleep(8)
