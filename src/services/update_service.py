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
        self.current_version = self.settings_service.get("app_info", "version", APP_VERSION)
        self.github_repo = os.getenv("GITHUB_REPO") or self.settings_service.get(
            "app_info", "github_repo", DEFAULT_GITHUB_REPO
        )

    def _normalize_version(self, v_str: str) -> str:
        """Chuẩn hóa chuỗi version (bỏ chữ v ở đầu nếu có)"""
        if not v_str:
            return "0.0.0"
        clean = v_str.strip().lstrip("vV")
        return clean

    def check_for_updates(self) -> Dict[str, Any]:
        """
        Kiểm tra phiên bản mới nhất từ GitHub Releases API.
        Trả về dictionary gồm trạng thái, phiên bản mới, ghi chú phát hành, và link tải.
        """
        repo = self.github_repo.strip().strip("/")
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        headers = {
            "User-Agent": "VB-STUDIO-Updater",
            "Accept": "application/vnd.github.v3+json"
        }

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
        updater_bat_path = exe_dir / "apply_update.bat"

        try:
            headers = {"User-Agent": "VB-STUDIO-Updater"}
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

            # Tạo script updater.bat để thay thế exe sau khi app tắt
            # Bat script: chờ app thoát -> ghi đè file exe -> khởi chạy exe mới -> tự xóa updater.bat
            bat_content = f"""@echo off
chcp 65001 >nul
echo Dang cap nhat VB-STUDIO...
timeout /t 2 /nobreak >nul
:loop
move /y "{new_exe_path}" "{current_exe_path}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto loop
)
start "" "{current_exe_path}"
del "%~f0" >nul 2>&1
exit
"""
            with open(updater_bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            # Thực thi updater.bat trong process ngầm tách biệt hoàn toàn
            subprocess.Popen(
                ["cmd.exe", "/c", str(updater_bat_path)],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                close_fds=True,
                shell=False
            )

            return {
                "success": True,
                "message": "Cập nhật thành công! Ứng dụng sẽ tự khởi động lại ngay bây giờ..."
            }

        except Exception as e:
            logger.error(f"Lỗi tải / áp dụng bản cập nhật: {e}")
            if new_exe_path.exists():
                try:
                    new_exe_path.unlink()
                except Exception:
                    pass
            return {
                "success": False,
                "message": f"Không thể cập nhật: {str(e)}"
            }
