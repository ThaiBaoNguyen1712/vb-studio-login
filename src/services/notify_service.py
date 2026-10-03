"""OS-level notify cho app desktop Windows — zero dependency mới.

- Âm thanh dự phòng khi WebView bị mute: winsound (stdlib Windows).
- Nhấp nháy taskbar khi có sự kiện quan trọng mà cửa sổ đang inactive:
  ctypes FlashWindowEx (không cần xin quyền overlay như mobile).
- Ghim cửa sổ lên trên cùng (topmost): SetWindowPos + FindWindowW theo title.
  Win32 desktop không yêu cầu quyền đặc biệt cho 2 API này.
"""
import ctypes
from ctypes import wintypes
from typing import Optional

from src.core.logger import logger

APP_TITLE = "VB-STUDIO \u2022 Multi-Channel Dashboard"


class _FlashInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("dwFlags", wintypes.DWORD),
        ("uCount", wintypes.UINT),
        ("dwTimeout", wintypes.DWORD),
    ]


try:
    _user32 = ctypes.windll.user32
    # Khai báo kiểu Arg rõ ràng — nếu không, ctypes cắt HWND 64-bit còn 32-bit
    # khiến SetWindowPos luôn nhận handle sai và thất bại.
    _user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.FindWindowW.restype = wintypes.HWND
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.FlashWindowEx.argtypes = [ctypes.POINTER(_FlashInfo)]
    _user32.FlashWindowEx.restype = wintypes.BOOL
except Exception:
    _user32 = None


def _main_hwnd() -> Optional[int]:
    if not _user32:
        return None
    try:
        hwnd = _user32.FindWindowW(None, APP_TITLE)
        return hwnd or None
    except Exception as e:
        logger.warning(f"notify: không tìm được HWND: {e}")
        return None


def beep_os(kind: str = "info") -> bool:
    """Beep hệ thống dự phòng (khi Web Audio trong WebView bị tắt/mute)."""
    try:
        import winsound
    except Exception:
        return False
    try:
        if kind == "error":
            winsound.MessageBeep(winsound.MB_ICONHAND)
        elif kind in ("warning", "request"):
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        elif kind == "success":
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            winsound.MessageBeep(winsound.MB_OK)
        return True
    except Exception as e:
        logger.warning(f"notify beep thất bại: {e}")
        return False


def flash_taskbar(count: int = 3) -> bool:
    """Nhấp nháy nút taskbar để gọi sự chú ý khi app đang minimize/inactive."""
    if not _user32:
        return False
    hwnd = _main_hwnd()
    if not hwnd:
        return False
    try:
        FLASHW_ALL = 0x00000003
        info = _FlashInfo(
            cbSize=ctypes.sizeof(_FlashInfo),
            hwnd=hwnd,
            dwFlags=FLASHW_ALL,
            uCount=max(1, min(int(count), 10)),
            dwTimeout=0,
        )
        return bool(_user32.FlashWindowEx(ctypes.byref(info)))
    except Exception as e:
        logger.warning(f"notify flash thất bại: {e}")
        return False


def set_topmost_by_title(title: str, enabled: bool) -> bool:
    """Ghim/bỏ ghim 1 cửa sổ bất kỳ (tìm theo title) lên trên cùng."""
    if not _user32 or not title:
        return False
    try:
        hwnd = _user32.FindWindowW(None, title)
    except Exception as e:
        logger.warning(f"notify topmost-by-title thất bại: {e}")
        return False
    if not hwnd:
        return False
    return _apply_topmost(hwnd, enabled)


def set_always_on_top(enabled: bool) -> bool:
    """Ghim/bỏ ghim cửa sổ app lên trên cùng (topmost). Không cần quyền đặc biệt."""
    if not _user32:
        return False
    hwnd = _main_hwnd()
    if not hwnd:
        logger.warning("notify topmost: không tìm được HWND (cửa sổ chưa mở?)")
        return False
    return _apply_topmost(hwnd, enabled)


def _apply_topmost(hwnd, enabled: bool) -> bool:
    try:
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_SHOWWINDOW = 0x0040
        res = _user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST if enabled else HWND_NOTOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
        return bool(res)
    except Exception as e:
        logger.warning(f"notify topmost thất bại: {e}")
        return False


def notify_os(title: str, message: str, kind: str = "info", flash: bool = True) -> dict:
    """Điểm vào duy nhất cho frontend: beep OS + flash taskbar khi cần.

    Lưu ý: không dùng Windows Toast (Action Center) vì cần đăng ký
    AppUserModelID + shortcut Start Menu — nặng nề cho bản exe portable.
    Flash + beep + toast in-app là đủ cho team 3-4 người, không cần xin thêm quyền.
    """
    _ = title  # giữ tham số để tương lai gắn Toast khi cần
    ok_beep = beep_os(kind)
    ok_flash = flash_taskbar() if flash else False
    logger.info(f"OS notify [{kind}]: {message[:120]} (beep={ok_beep}, flash={ok_flash})")
    return {"success": True, "beep": ok_beep, "flash": ok_flash}
