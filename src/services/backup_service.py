"""Sao lưu & khôi phục toàn bộ dữ liệu local thành 1 file zip.

Gồm: local_db.json, settings.json, platforms.json, trash.json, .vault.salt
và tùy chọn profiles/ trình duyệt. Mật khẩu (tùy chọn) dùng AES-256
(pyzipper); file zip vẫn mở được bằng 7-Zip/WinRAR mới (nhập đúng mật khẩu).

Lưu ý: cookies mã hóa DPAPI gắn với user+máy Windows — restore sang máy
khác cần đăng nhập lại để lấy phiên mới (dữ liệu kênh/tài khoản vẫn nguyên).
"""
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.core.config import Config
from src.core.logger import logger

APP_TAG = "VB-Studio Login"
BACKUP_VERSION = 1
DATA_FILES = ["local_db.json", "settings.json", "platforms.json",
              "trash.json", ".vault.salt"]
MANIFEST_NAME = "backup.json"

try:
    import pyzipper
    _HAS_PYZIPPER = True
except ImportError:
    pyzipper = None
    _HAS_PYZIPPER = False


def _open_write(path: Path, password: bytes | None):
    """Zip ghi: AES-256 nếu có mật khẩu (cần pyzipper), ngược lại zip thường."""
    if password:
        if not _HAS_PYZIPPER:
            raise RuntimeError("Cần gói 'pyzipper' để đặt mật khẩu (pip install pyzipper).")
        zf = pyzipper.AESZipFile(path, "w", compression=zipfile.ZIP_DEFLATED,
                                 encryption=pyzipper.WZ_AES)
        zf.setpassword(password)
        return zf
    return zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)


def _open_read(path: Path):
    if _HAS_PYZIPPER:
        return pyzipper.AESZipFile(path, "r")
    return zipfile.ZipFile(path, "r")


def _default_filename() -> str:
    return "VBStudio_backup_" + datetime.now().strftime("%Y%m%d_%H%M") + ".zip"


class BackupService:
    """Export/import zip backup, độc lập repository (làm việc trên file)."""

    def __init__(self, data_dir: Optional[Path] = None, profiles_dir: Optional[Path] = None):
        Config.ensure_directories()
        self.data_dir = data_dir or Config.DATA_DIR
        self.profiles_dir = profiles_dir or Config.PROFILES_DIR

    # ---------- export ----------
    def export_backup(self, save_path: str, include_profiles: bool = False,
                      password: str = "") -> Dict[str, Any]:
        dest = Path(save_path)
        if dest.suffix.lower() != ".zip":
            dest = dest.with_suffix(".zip")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"success": False, "message": f"Không tạo được thư mục đích: {e}"}
        pwd = password.encode("utf-8") if password else None
        files: List[str] = []
        try:
            with _open_write(dest, pwd) as zf:
                for name in DATA_FILES:
                    src = self.data_dir / name
                    if not src.exists():
                        continue
                    arc = f"data/{name}"
                    with open(src, "rb") as f:
                        data = f.read()
                    zf.writestr(arc, data)
                    files.append(arc)
                if include_profiles and self.profiles_dir.exists():
                    for fp in sorted(self.profiles_dir.rglob("*")):
                        if not fp.is_file():
                            continue
                        try:
                            if fp.stat().st_size > 200 * 1024 * 1024:
                                continue  # bỏ file đơn >200MB (cache chromium)
                        except Exception:
                            continue
                        arc = "profiles/" + fp.relative_to(self.profiles_dir).as_posix()
                        try:
                            zf.write(fp, arc)
                            files.append(arc)
                        except Exception as e:
                            logger.warning(f"Bỏ qua file profile khóa/đọc lỗi '{fp}': {e}")
                manifest = {
                    "app": APP_TAG, "backup_version": BACKUP_VERSION,
                    "created_at": datetime.now().isoformat(),
                    "includes_profiles": include_profiles,
                    "password_protected": bool(pwd),
                    "files": files,
                }
                zf.writestr(MANIFEST_NAME,
                            json.dumps(manifest, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Export backup failed: {e}")
            return {"success": False, "message": f"Lỗi xuất backup: {e}"}
        size_mb = dest.stat().st_size / 1024 / 1024 if dest.exists() else 0
        logger.info(f"Đã xuất backup: {dest} ({size_mb:.1f} MB, {len(files)} files).")
        return {"success": True, "path": str(dest),
                "message": f"Đã xuất backup ({size_mb:.1f} MB, {len(files)} files)!"}

    # ---------- validate ----------
    def read_manifest(self, zip_path: str, password: str = "") -> Dict[str, Any]:
        zp = Path(zip_path)
        if not zp.exists():
            return {"success": False, "message": "Không tìm thấy file backup."}
        try:
            with _open_read(zp) as zf:
                try:
                    raw = zf.read(MANIFEST_NAME, pwd=password.encode() if password else None)
                except RuntimeError:
                    return {"success": False,
                            "message": "Backup có mật khẩu hoặc sai mật khẩu."}
                manifest = json.loads(raw.decode("utf-8"))
        except zipfile.BadZipFile:
            return {"success": False, "message": "File không phải zip hợp lệ."}
        except Exception as e:
            return {"success": False, "message": f"Lỗi đọc backup: {e}"}
        if manifest.get("app") != APP_TAG:
            return {"success": False, "message": "File không phải backup của VB-Studio Login."}
        return {"success": True, "manifest": manifest}

    # ---------- import ----------
    def import_backup(self, zip_path: str, password: str = "") -> Dict[str, Any]:
        chk = self.read_manifest(zip_path, password)
        if not chk.get("success"):
            return chk
        manifest = chk["manifest"]
        pwd = password.encode("utf-8") if password else None
        # 1. Safety copy dữ liệu hiện tại
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety = self.data_dir / "safety" / stamp
        try:
            safety.mkdir(parents=True, exist_ok=True)
            for name in DATA_FILES:
                src = self.data_dir / name
                if src.exists():
                    shutil.copy2(src, safety / name)
        except Exception as e:
            return {"success": False, "message": f"Không backup an toàn được dữ liệu hiện tại: {e}"}
        # 2. Giải nén (data trước, profiles best-effort vì có thể bị khóa)
        errors: List[str] = []
        restored = 0
        try:
            with _open_read(zip_path) as zf:
                if pwd:
                    zf.setpassword(pwd)
                for info in zf.infolist():
                    arc = info.filename
                    if arc == MANIFEST_NAME:
                        continue
                    if not (arc.startswith("data/") or arc.startswith("profiles/")):
                        continue
                    try:
                        raw = zf.read(arc)
                    except RuntimeError:
                        return {"success": False,
                                "message": "Sai mật khẩu backup."}
                    if arc.startswith("data/"):
                        name = arc[5:]
                        if "/" in name or name not in DATA_FILES:
                            continue
                        target = self.data_dir / name
                        try:
                            if name.endswith(".json"):
                                json.loads(raw.decode("utf-8"))  # verify JSON hợp lệ
                        except Exception:
                            errors.append(f"{name}: JSON hỏng, bỏ qua")
                            continue
                        target.write_bytes(raw)
                        restored += 1
                    else:
                        target = self.profiles_dir / arc[9:]
                        try:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(raw)
                        except Exception as e:
                            errors.append(f"{arc}: {e}")
        except Exception as e:
            logger.error(f"Import backup failed: {e}")
            return {"success": False, "message": f"Lỗi nhập backup: {e}"}
        msg = f"Đã khôi phục {restored} file dữ liệu (bản cũ lưu tại data/safety/{stamp})."
        if errors:
            msg += f" Bỏ qua {len(errors)} file lỗi."
            logger.warning("Import backup warnings: " + "; ".join(errors[:5]))
        logger.info(msg)
        return {"success": True, "message": msg, "warnings": errors[:10]}
