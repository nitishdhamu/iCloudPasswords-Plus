"""
iCloud Passwords+
================
Ultra-lightweight Windows background service that automatically intercepts
iCloud Passwords 6-digit security codes and types them into your browser.

Architecture:
- Pure Python standard library + Windows Win32 API.
- Zero external runtime dependencies.
- Hardware-level SendInput keystroke injection for microsecond typing speed.
- Dynamic working set memory trimming for ~3 MB RAM idle footprint.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
from typing import Callable, Optional

# -----------------------------------------------------------------------------
# Win32 API Definitions & Fast Input Dispatcher
# -----------------------------------------------------------------------------
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class DUMMYUNIONNAME(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", DUMMYUNIONNAME),
    ]


def _native_click(x: int, y: int) -> None:
    """Sends a hardware-level left click without third-party library overhead."""
    _user32.SetCursorPos(x, y)
    time.sleep(0.02)
    _user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.01)
    _user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP


def _native_type_code(code: str, interval: float = 0.01) -> None:
    """Types digits via direct Win32 SendInput at the hardware level in microseconds."""
    input_keyboard = 1
    keyeventf_keyup = 0x0002

    for char in code:
        vk = ord(char)
        scan = _user32.MapVirtualKeyW(vk, 0)

        # Key Down
        ki_down = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=0, time=0, dwExtraInfo=0)
        inp_down = INPUT(type=input_keyboard, u=DUMMYUNIONNAME(ki=ki_down))
        _user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))

        time.sleep(interval)

        # Key Up
        ki_up = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=keyeventf_keyup, time=0, dwExtraInfo=0)
        inp_up = INPUT(type=input_keyboard, u=DUMMYUNIONNAME(ki=ki_up))
        _user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))

        time.sleep(interval)


def _trim_memory() -> None:
    """Flushes unreferenced pages out of working set memory back to Windows."""
    try:
        h = _kernel32.GetCurrentProcess()
        _kernel32.SetProcessWorkingSetSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
        max_size = ctypes.c_size_t(-1).value
        _kernel32.SetProcessWorkingSetSize(h, max_size, max_size)
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Logging & Pattern Matchers
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("iCloudPasswordsPlus")

ICLOUD_KEYWORDS = [
    "icloud", "apple", "passwords", "keychain",
    "icloudpasswords", "com.apple", "icloud for windows",
    "enable password", "verification code", "autofill",
]
OTP_PATTERN = re.compile(r"\b(\d{3}[\s\-]?\d{3}|\d{6})\b")
WIN32_POLL_INTERVAL = 0.30


def _now() -> float:
    return time.time()


def _clean_otp(raw: str) -> Optional[str]:
    digits = re.sub(r"[\s\-]", "", raw)
    return digits if len(digits) == 6 and digits.isdigit() else None


def _extract_otp(text: str) -> Optional[str]:
    for m in OTP_PATTERN.finditer(text):
        code = _clean_otp(m.group(1))
        if code:
            return code
    return None


def _has_icloud_context(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ICLOUD_KEYWORDS)


# -----------------------------------------------------------------------------
# Window Introspection & Interception
# -----------------------------------------------------------------------------
def _get_process_name_for_hwnd(hwnd: int) -> str:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h_process = _kernel32.OpenProcess(0x1000, False, pid)
    if not h_process:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if _kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
            return Path(buf.value).name.lower()
    except Exception:
        pass
    finally:
        _kernel32.CloseHandle(h_process)
    return ""


def _get_window_text(hwnd: int) -> str:
    n = _user32.GetWindowTextLengthW(hwnd)
    if n == 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _get_class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _collect_all_text(hwnd: int) -> str:
    parts = []
    title = _get_window_text(hwnd)
    if title:
        parts.append(title)

    def _child_cb(child_hwnd, _):
        t = _get_window_text(child_hwnd)
        if t:
            parts.append(t)
        return True

    _user32.EnumChildWindows(hwnd, _WNDENUMPROC(_child_cb), 0)
    return " | ".join(parts)


def _hide_if_icloud_popup(hwnd: int, class_name: str) -> None:
    if class_name == "#32770":
        proc_name = _get_process_name_for_hwnd(hwnd)
        if "icloud" in proc_name or "apple" in proc_name:
            _user32.ShowWindow(hwnd, 0)
            ex_style = _user32.GetWindowLongW(hwnd, -20)
            _user32.SetWindowLongW(hwnd, -20, ex_style | 0x80000)
            _user32.SetLayeredWindowAttributes(hwnd, 0, 0, 2)
            _user32.SetWindowPos(hwnd, 0, -10000, -10000, 0, 0, 0x0015)


def _check_hwnd_for_otp(hwnd: int) -> Optional[tuple]:
    try:
        if not _user32.IsWindow(hwnd):
            return None

        class_name = _get_class_name(hwnd)
        _hide_if_icloud_popup(hwnd, class_name)

        all_text = _collect_all_text(hwnd)
        if not all_text.strip():
            return None

        code = _extract_otp(all_text)
        if not code:
            return None

        if _has_icloud_context(all_text) or _has_icloud_context(class_name):
            title = _get_window_text(hwnd)
            return (code, hwnd, title, class_name)

    except Exception as e:
        log.debug(f"[Win32] check_hwnd error: {e}")
    return None


def _find_extension_popup() -> Optional[dict]:
    candidates = []

    def _enum(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        cls = _get_class_name(hwnd)
        if "Chrome_WidgetWin" not in cls:
            return True
        rect = wintypes.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if 280 < w < 550 and 120 < h < 450 and rect.top < 500:
            candidates.append({
                "hwnd": hwnd, "left": rect.left, "top": rect.top,
                "width": w, "height": h,
            })
        return True

    try:
        _user32.EnumWindows(_WNDENUMPROC(_enum), 0)
    except Exception:
        pass

    if candidates:
        sw = _user32.GetSystemMetrics(0)
        candidates.sort(key=lambda c: abs(c["left"] - sw * 0.6))
        return candidates[0]
    return None


def _focus_extension_popup(popup: dict) -> bool:
    hwnd = popup["hwnd"]
    if not _user32.IsWindow(hwnd):
        return False
    _user32.ShowWindow(hwnd, 9)
    _user32.BringWindowToTop(hwnd)
    _user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    click_x = popup["left"] + int(popup["width"] * 0.25)
    click_y = popup["top"] + int(popup["height"] * 0.55)
    _native_click(click_x, click_y)
    time.sleep(0.05)
    return True


# -----------------------------------------------------------------------------
# Auto-Typer Workflow
# -----------------------------------------------------------------------------
_last_typed_code: Optional[str] = None
_last_typed_time: float = 0.0
_type_lock = threading.Lock()


def _auto_type_worker(code: str, source: str) -> None:
    global _last_typed_code, _last_typed_time
    try:
        with _type_lock:
            if code == _last_typed_code and (_now() - _last_typed_time) < 30:
                log.info(f"[Type] Debounced: {code}")
                return
            _last_typed_code = code
            _last_typed_time = _now()

        popup = _find_extension_popup()
        browser_hwnd = _user32.GetForegroundWindow()

        focused_popup = False
        if popup:
            focused_popup = _focus_extension_popup(popup)

        if not focused_popup and browser_hwnd and _user32.IsWindow(browser_hwnd):
            try:
                _user32.ShowWindow(browser_hwnd, 9)
                _user32.BringWindowToTop(browser_hwnd)
                _user32.SetForegroundWindow(browser_hwnd)
                time.sleep(0.05)
            except Exception:
                pass

        log.info(f"[Type] Typing {code} (source: {source})")
        _native_type_code(code, interval=0.01)
        log.info("[Type] Done.")
        _trim_memory()
    except Exception as e:
        log.exception(f"Error in auto_type thread: {e}")
        with _type_lock:
            _last_typed_code = None


def auto_type(code: str, source: str = "?") -> None:
    threading.Thread(target=_auto_type_worker, args=(code, source), daemon=True).start()


# -----------------------------------------------------------------------------
# Window Monitors
# -----------------------------------------------------------------------------
class WinEventMonitor:
    EVENT_OBJECT_CREATE = 0x8000
    EVENT_OBJECT_SHOW = 0x8002
    WINEVENT_OUTOFCONTEXT = 0x0000
    WINEVENT_SKIPOWNPROCESS = 0x0002

    _WinEventProc = ctypes.WINFUNCTYPE(
        None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG,
        wintypes.LONG, wintypes.DWORD, wintypes.DWORD
    )

    def __init__(self, on_code: Callable[[str, str], None]):
        self._on_code = on_code
        self._hook = None
        self._proc = None
        self._thread = None
        self._thread_id = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="winevent-hook", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._hook:
            _user32.UnhookWinEvent(self._hook)
            self._hook = None
        if self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)

    def _event_callback(self, hook, event, hwnd, id_obj, id_child, thread_id, time_ms) -> None:
        if not hwnd:
            return
        try:
            if event == self.EVENT_OBJECT_CREATE:
                class_name = _get_class_name(hwnd)
                _hide_if_icloud_popup(hwnd, class_name)
            elif event == self.EVENT_OBJECT_SHOW:
                result = _check_hwnd_for_otp(hwnd)
                if result:
                    code, _, _, _ = result
                    log.info(f"[WinEvent] OTP Detected: {code}")
                    self._on_code(code, "WinEvent")
        except Exception:
            pass

    def _run(self) -> None:
        self._thread_id = _kernel32.GetCurrentThreadId()
        self._proc = self._WinEventProc(self._event_callback)
        self._hook = _user32.SetWinEventHook(
            self.EVENT_OBJECT_CREATE, self.EVENT_OBJECT_SHOW, None,
            self._proc, 0, 0, self.WINEVENT_OUTOFCONTEXT | self.WINEVENT_SKIPOWNPROCESS
        )
        if not self._hook:
            return
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))


class Win32WindowScanner:
    def scan(self) -> Optional[tuple]:
        results = []

        def _enum_cb(hwnd, _):
            if not _user32.IsWindowVisible(hwnd):
                return True
            result = _check_hwnd_for_otp(hwnd)
            if result:
                results.append((result[0], result[1]))
            return True

        try:
            _user32.EnumWindows(_WNDENUMPROC(_enum_cb), 0)
        except Exception:
            pass
        return results[0] if results else None


# -----------------------------------------------------------------------------
# Engine Controller
# -----------------------------------------------------------------------------
class EngineController:
    def __init__(self):
        self.enabled = True
        self.stop_event = threading.Event()
        self.detected_code = None
        self.detected_time = 0.0
        self.detect_lock = threading.Lock()
        self.monitor_thread = None

    def _handle_code(self, code: str, source: str) -> None:
        if not self.enabled:
            return
        with self.detect_lock:
            if code == self.detected_code and (_now() - self.detected_time) < 30:
                return
            self.detected_code = code
            self.detected_time = _now()
        auto_type(code, source)

    def _monitor_loop(self) -> None:
        log.info("Started Background Monitor")
        _trim_memory()

        hook_monitor = WinEventMonitor(on_code=self._handle_code)
        hook_monitor.start()
        win32_scanner = Win32WindowScanner()

        tick = 0
        while not self.stop_event.is_set():
            if self.enabled:
                try:
                    res = win32_scanner.scan()
                    if res:
                        self._handle_code(res[0], "Win32")
                except Exception:
                    pass
            tick += 1
            if tick % 100 == 0:
                _trim_memory()
            time.sleep(WIN32_POLL_INTERVAL)
        hook_monitor.stop()

    def start(self) -> None:
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self) -> None:
        self.stop_event.set()


# -----------------------------------------------------------------------------
# Core Application (Single-Instance Enforcer)
# -----------------------------------------------------------------------------
class AppCore:
    def __init__(self):
        self.engine = EngineController()

    def _enforce_single_instance(self) -> None:
        port = 59999
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("127.0.0.1", port))
            s.sendall(b"exit")
            s.close()
            time.sleep(1.5)
        except Exception:
            pass

        def _listen():
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                server.bind(("127.0.0.1", port))
                server.listen(1)
            except Exception:
                return
            while True:
                try:
                    conn, _ = server.accept()
                    msg = conn.recv(1024)
                    if msg == b"exit":
                        conn.close()
                        server.close()
                        self.engine.stop()
                        os._exit(0)
                    conn.close()
                except Exception:
                    break

        threading.Thread(target=_listen, daemon=True).start()

    def run(self) -> None:
        self._enforce_single_instance()
        self.engine.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.engine.stop()


if __name__ == "__main__":
    AppCore().run()
