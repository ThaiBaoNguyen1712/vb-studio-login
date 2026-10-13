"""
Script tạo Shortcut cho VBLogin ra Desktop người dùng (không mở màn hình console).
Hỗ trợ chạy trực tiếp với python.exe, pythonw.exe hoặc double-click file .py/.pyw.
"""
import ctypes
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def hide_console_window():
    """Ẩn cửa sổ console nếu script bị gọi bởi python.exe thay vì pythonw.exe."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def show_message(text: str, title: str = "VBLogin", is_error: bool = False):
    """Hiển thị hộp thoại thông báo Windows không cần console."""
    try:
        icon_flag = 0x10 if is_error else 0x40  # MB_ICONERROR or MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(0, text, title, icon_flag)
    except Exception:
        pass


def find_target_exe() -> Path | None:
    """Tìm file VBLogin.exe trong các thư mục lân cận."""
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "VBLogin.exe",
        script_dir.parent / "VBLogin.exe",
        script_dir.parent / "dist" / "VBLogin.exe",
        script_dir.parent / "dist" / "VBLogin-pkg" / "VBLogin.exe",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return None


def get_desktop_dir() -> Path:
    """Lấy đường dẫn Desktop của người dùng hiện tại."""
    candidates = [
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("ONEDRIVE", "")) / "Desktop" if os.environ.get("ONEDRIVE") else None,
        Path.home() / "Desktop",
    ]
    for d in candidates:
        if d and d.exists():
            return d.resolve()
    return Path.home() / "Desktop"


def create_shortcut(silent: bool = False) -> bool:
    hide_console_window()

    exe_path = find_target_exe()
    if not exe_path:
        if not silent:
            show_message(
                "Không tìm thấy file 'VBLogin.exe' trong thư mục ứng dụng.\n"
                "Vui lòng đảm bảo script nằm cùng hoặc gần thư mục chứa VBLogin.exe.",
                title="VBLogin - Lỗi tạo Shortcut",
                is_error=True
            )
        return False

    desktop_dir = get_desktop_dir()
    shortcut_file = desktop_dir / "VBLogin.lnk"

    vbs = (
        f'Set oWS = WScript.CreateObject("WScript.Shell")\r\n'
        f'sLinkFile = "{shortcut_file}"\r\n'
        f'Set oLink = oWS.CreateShortcut(sLinkFile)\r\n'
        f'oLink.TargetPath = "{exe_path}"\r\n'
        f'oLink.WorkingDirectory = "{exe_path.parent}"\r\n'
        f'oLink.Description = "VBLogin Manager"\r\n'
        f'oLink.IconLocation = "{exe_path},0"\r\n'
        f'oLink.Save\r\n'
    )

    tmp_vbs = Path(tempfile.gettempdir()) / f"create_vblogin_shortcut_{os.getpid()}.vbs"
    try:
        tmp_vbs.write_text(vbs, encoding="utf-8")
        # Chạy qua wscript.exe (GUI host, không có console)
        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(
            ["wscript.exe", "//nologo", str(tmp_vbs)],
            creationflags=CREATE_NO_WINDOW,
            timeout=5
        )
    except Exception as e:
        if not silent:
            show_message(f"Không thể tạo Shortcut: {e}", title="VBLogin - Lỗi", is_error=True)
        return False
    finally:
        try:
            tmp_vbs.unlink(missing_ok=True)
        except Exception:
            pass

    if shortcut_file.exists():
        if not silent:
            show_message(
                "Đã tạo thành công Shortcut 'VBLogin' ngoài Desktop!\n\n"
                "Bạn có thể mở ứng dụng bất cứ lúc nào từ màn hình Desktop.",
                title="VBLogin - Thành công"
            )
        return True
    else:
        if not silent:
            show_message("Không thể lưu file Shortcut trên Desktop.", title="VBLogin - Lỗi", is_error=True)
        return False


if __name__ == "__main__":
    silent_mode = "--silent" in sys.argv
    create_shortcut(silent=silent_mode)
