import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from packaging import version as pkg_version

from src.core.config import Config
from src.core.constants import APP_VERSION
from src.core.logger import logger
from src.services.settings_service import SettingsService

DEFAULT_GITHUB_REPO = "ThaiBaoNguyen1712/vb-studio-login"  # Configurable via GITHUB_REPO env or settings.json



class UpdateService:
    """
    Quản lý kiểm tra phiên bản và tự động cập nhật từ GitHub Releases.
    - So sánh Semantic Versioning (v1.0.0 < v1.0.1).
    - Lấy thông tin release mới nhất (tag, release notes, link tải .exe).
    - Tải bản cập nhật và chạy script thay thế file exe trong nền.
    """

    def __init__(self, settings_service: Optional[SettingsService] = None):
        self.settings_service = settings_service or SettingsService()
        self.current_version = Config.APP_VERSION
        self.github_repo = os.getenv("GITHUB_REPO") or self.settings_service.get(
            "app_info", "github_repo", DEFAULT_GITHUB_REPO
        )
        self.github_token = os.getenv("GITHUB_TOKEN") or self.settings_service.get(
            "app_info", "github_token", ""
        )

    def _normalize_version(self, v_str: str) -> str:
        """Chuẩn hóa chuỗi version (bỏ chữ v ở đầu nếu có)"""
        if not v_str:
            return "0.0.0"
        clean = v_str.strip().lstrip("vV")
        return clean

    def _get_headers(self, is_raw_asset: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": "VB-STUDIO-Updater",
            "Accept": "application/octet-stream" if is_raw_asset else "application/vnd.github.v3+json"
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        return headers

    def check_for_updates(self) -> Dict[str, Any]:
        """
        Kiểm tra phiên bản mới nhất từ GitHub Releases API.
        Trả về dictionary gồm trạng thái, phiên bản mới, ghi chú phát hành, và link tải.
        """
        self.current_version = Config.APP_VERSION
        self.github_repo = os.getenv("GITHUB_REPO") or self.settings_service.get(
            "app_info", "github_repo", DEFAULT_GITHUB_REPO
        )
        self.github_token = os.getenv("GITHUB_TOKEN") or self.settings_service.get(
            "app_info", "github_token", ""
        )
        repo = self.github_repo.strip().strip("/")
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        headers = self._get_headers()

        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:

                if resp.status != 200:
                    return {
                        "has_update": False,
                        "current_version": self.current_version,
                        "latest_version": self.current_version,
                        "message": f"Không thể kết nối GitHub API (HTTP {resp.status}).",
                        "error": True
                    }
                data = json.loads(resp.read().decode("utf-8"))

            tag_name = data.get("tag_name", "")
            release_title = data.get("name") or tag_name
            release_notes = data.get("body", "Không có ghi chú phát hành.")
            html_url = data.get("html_url", f"https://github.com/{repo}/releases")
            published_at = data.get("published_at", "")

            # Tìm file .exe hoặc file .zip đính kèm trong assets
            assets = data.get("assets", [])
            download_url = None
            asset_name = None
            asset_size = 0

            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    asset_name = asset.get("name")
                    asset_size = asset.get("size", 0)
                    break
            
            if not download_url and assets:
                # Nếu không có .exe riêng mà có .zip
                for asset in assets:
                    if asset.get("name", "").lower().endswith(".zip"):
                        download_url = asset.get("browser_download_url")
                        asset_name = asset.get("name")
                        asset_size = asset.get("size", 0)
                        break

            # So sánh version
            curr_v_clean = self._normalize_version(self.current_version)
            latest_v_clean = self._normalize_version(tag_name)

            try:
                has_update = pkg_version.parse(latest_v_clean) > pkg_version.parse(curr_v_clean)
            except Exception:
                has_update = latest_v_clean != curr_v_clean

            if has_update:
                msg = f"Đã có phiên bản mới {tag_name}! (Hiện tại: {self.current_version})"
            else:
                msg = f"Bạn đang sử dụng phiên bản mới nhất ({self.current_version})."

            return {
                "has_update": has_update,
                "current_version": self.current_version,
                "latest_version": tag_name,
                "release_title": release_title,
                "release_notes": release_notes,
                "html_url": html_url,
                "download_url": download_url,
                "asset_name": asset_name,
                "asset_size": asset_size,
                "published_at": published_at,
                "message": msg,
                "error": False
            }

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {
                    "has_update": False,
                    "current_version": self.current_version,
                    "latest_version": self.current_version,
                    "message": f"Chưa tìm thấy bản Release nào trên GitHub ({repo}).",
                    "error": False
                }
            logger.warning(f"Lỗi kiểm tra cập nhật GitHub HTTP {e.code}: {e}")
            return {
                "has_update": False,
                "current_version": self.current_version,
                "latest_version": self.current_version,
                "message": f"Lỗi HTTP {e.code} khi kiểm tra GitHub Releases.",
                "error": True
            }
        except Exception as e:
            logger.warning(f"Lỗi kiểm tra cập nhật: {e}")
            return {
                "has_update": False,
                "current_version": self.current_version,
                "latest_version": self.current_version,
                "message": f"Không thể kiểm tra cập nhật: {str(e)}",
                "error": True
            }

    def open_release_page(self, url: Optional[str] = None) -> bool:
        """Mở trang GitHub Release trên trình duyệt web mặc định"""
        target = url or f"https://github.com/{self.github_repo}/releases/latest"
        try:
            webbrowser.open(target)
            return True
        except Exception as e:
            logger.error(f"Lỗi mở link release: {e}")
            return False

    @staticmethod
    def find_python_runner() -> Optional[str]:
        """Tìm trình thực thi Python trên Windows (ưu tiên pythonw.exe để không mở console)."""
        pw = shutil.which("pythonw")
        if pw:
            return pw
        p = shutil.which("python")
        if p:
            pw_same = Path(p).parent / "pythonw.exe"
            if pw_same.exists():
                return str(pw_same)
            return p
        for attr in ("base_prefix", "exec_prefix"):
            base = getattr(sys, attr, None)
            if base:
                pw_base = Path(base) / "pythonw.exe"
                if pw_base.exists():
                    return str(pw_base)
                p_base = Path(base) / "python.exe"
                if p_base.exists():
                    return str(p_base)
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            py_dir = Path(local_app_data) / "Programs" / "Python"
            if py_dir.exists():
                for sub in sorted(py_dir.glob("Python3*"), reverse=True):
                    pw_cand = sub / "pythonw.exe"
                    if pw_cand.exists():
                        return str(pw_cand)
                    p_cand = sub / "python.exe"
                    if p_cand.exists():
                        return str(p_cand)
        prog_files = os.environ.get("ProgramFiles", "")
        if prog_files:
            py_dir = Path(prog_files) / "Python"
            if py_dir.exists():
                for sub in sorted(py_dir.glob("Python3*"), reverse=True):
                    pw_cand = sub / "pythonw.exe"
                    if pw_cand.exists():
                        return str(pw_cand)
                    p_cand = sub / "python.exe"
                    if p_cand.exists():
                        return str(p_cand)
        return None

    def download_and_apply_update(self, download_url: str, progress_callback=None) -> Dict[str, Any]:
        """
        Tải file exe mới và tạo kịch bản thay thế khi khởi động lại.
        Chỉ thực hiện được khi ứng dụng đang chạy dưới dạng đóng gói (frozen .exe).
        """
        if not getattr(sys, "frozen", False):
            return {
                "success": False,
                "message": "Ứng dụng đang chạy từ source Python. Hãy cập nhật bằng 'git pull'."
            }

        current_exe_path = Path(sys.executable).resolve()
        exe_dir = current_exe_path.parent
        new_exe_path = exe_dir / (current_exe_path.name + ".new")
        updater_py_path = exe_dir / "apply_update.py"

        try:
            headers = self._get_headers(is_raw_asset=True)
            req = urllib.request.Request(download_url, headers=headers)

            logger.info(f"Bắt đầu tải cập nhật từ: {download_url}")
            with urllib.request.urlopen(req, timeout=60) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 1024 * 64

                with open(new_exe_path, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            progress_callback(percent)

            logger.info(f"Đã tải xong file exe mới: {new_exe_path} ({downloaded} bytes)")

            # Tạo script apply_update.py để thay thế exe sau khi app tắt (không dùng file .bat để tránh hiện màn hình console)
            current_pid = os.getpid()
            py_content = f'''# -*- coding: utf-8 -*-
"""
VBLogin Self-Updater Script (No Console Window)
Chờ app tắt -> Thay thế file exe -> Khởi chạy bản mới -> Tự xóa script.
"""
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

# Ẩn console window ngay lập tức nếu vô tình mở bằng python.exe
try:
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)
except Exception:
    pass

OLD_PID = {current_pid}
CURRENT_EXE = r"{current_exe_path}"
NEW_EXE = r"{new_exe_path}"

def wait_for_process_exit(pid: int, timeout_sec: float = 20.0):
    if pid <= 0:
        return
    SYNCHRONIZE = 0x00100000
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return
        exit_code = ctypes.c_ulong()
        if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            if exit_code.value != 259:  # 259 = STILL_ACTIVE
                ctypes.windll.kernel32.CloseHandle(handle)
                return
        ctypes.windll.kernel32.CloseHandle(handle)
        time.sleep(0.15)
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=3)
    except Exception:
        pass

def main():
    wait_for_process_exit(OLD_PID)
    time.sleep(0.5)

    replaced = False
    for _ in range(30):
        try:
            if os.path.exists(NEW_EXE):
                if os.path.exists(CURRENT_EXE):
                    try:
                        os.remove(CURRENT_EXE)
                    except Exception:
                        pass
                os.replace(NEW_EXE, CURRENT_EXE)
                replaced = True
                break
        except Exception:
            time.sleep(0.5)

    if replaced and os.path.exists(CURRENT_EXE):
        try:
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            flags = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            subprocess.Popen([CURRENT_EXE], creationflags=flags, close_fds=True)
        except Exception:
            try:
                os.startfile(CURRENT_EXE)
            except Exception:
                pass

    try:
        self_path = Path(__file__).resolve()
        time.sleep(0.3)
        self_path.unlink(missing_ok=True)
    except Exception:
        pass

if __name__ == "__main__":
    main()
'''
            with open(updater_py_path, "w", encoding="utf-8") as f:
                f.write(py_content)

            # Thực thi apply_update.py trong process ngầm tách biệt hoàn toàn, không tạo console
            runner = self.find_python_runner()
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            flags = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            if runner:
                cmd = [runner, str(updater_py_path)]
            else:
                cmd = [
                    "powershell.exe",
                    "-WindowStyle", "Hidden",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    f"python '{updater_py_path}'"
                ]

            subprocess.Popen(
                cmd,
                creationflags=flags,
                startupinfo=startupinfo,
                close_fds=True,
                shell=False
            )

            return {
                "success": True,
                "message": "Cập nhật thành công! Ứng dụng sẽ tự khởi động lại ngay..."
            }

        except Exception as e:
            logger.error(f"Lỗi tải / áp dụng bản cập nhật: {e}")
            if new_exe_path.exists():
                try:
                    new_exe_path.unlink()
                except Exception:
                    pass
            if updater_py_path.exists():
                try:
                    updater_py_path.unlink()
                except Exception:
                    pass
            return {
                "success": False,
                "message": f"Không thể cập nhật: {str(e)}"
            }

