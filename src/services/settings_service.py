import json
from pathlib import Path
from typing import Dict, Any, Optional
from src.core.config import Config
from src.core.constants import APP_NAME, APP_VERSION
from src.core.logger import logger

SETTINGS_FILE = Config.DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "general": {
        "app_title": APP_NAME,
        "theme_mode": "Dark",
        "default_user": "Nam",
        "auto_refresh_seconds": 15,
        "language": "vi",
        "enable_sound_notifications": True,
        "enable_request_popup": True
    },
    "app_info": {
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "github_repo": "ThaiBaoNguyen1712/vb-studio-login",
        "release_stage": "Release"
    },

    "firebase": {
        "url": "https://vb-studio-login-sync-default-rtdb.asia-southeast1.firebasedatabase.app/",
        "api_key": "AIzaSyCRJzx8Z8--dzQBgxbTsbYaygyifxj4waY",
        "auth_domain": "vb-studio-login-sync.firebaseapp.com",
        "project_id": "vb-studio-login-sync",
        "app_id": "1:81737086298:web:f042b83f2a9b16d91aef63",
        "storage_bucket": "vb-studio-login-sync.firebasestorage.app",
        "enabled": True,
        "auth_user": None
    },
    "browser": {
        "profiles_dir": "./profiles",
        "headless": False,
        "window_mode": "maximized",  # "maximized" or "custom"
        "custom_width": 1280,
        "custom_height": 800,
        "disable_bot_detection": True,
        "clear_cache_on_exit": False
    }
}

class SettingsService:
    """
    Manages persistent application settings,
    Firebase configuration, and runtime customization.
    """

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or SETTINGS_FILE
        self.settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        Config.ensure_directories()
        if not self.file_path.exists():
            self.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
            self.settings["general"]["default_user"] = Config.CURRENT_USER_NAME
            self.save_settings()
        else:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # Merge with default settings to ensure all keys exist
                    self.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
                    for section, values in saved.items():
                        if section in self.settings and isinstance(values, dict):
                            self.settings[section].update(values)
                        else:
                            self.settings[section] = values
            except Exception as e:
                logger.error(f"Lỗi đọc file settings.json: {e}")
                self.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        return self.settings

    def save_settings(self) -> bool:
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            logger.info("Đã lưu cấu hình cài đặt thành công.")
            return True
        except Exception as e:
            logger.error(f"Lỗi ghi file settings.json: {e}")
            return False

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.settings.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        if section not in self.settings:
            self.settings[section] = {}
        self.settings[section][key] = value

    def get_auth_user(self, include_token: bool = False) -> Optional[Dict[str, Any]]:
        """Trả user đã lưu; idToken được giải mã khi include_token=True (chỉ backend dùng)."""
        from src.core import secure_store
        user = self.get("firebase", "auth_user")
        if not user:
            return None
        user = dict(user)
        tok = user.get("idToken")
        if isinstance(tok, str) and secure_store.is_protected(tok):
            try:
                user["idToken"] = secure_store.unprotect(tok).decode("utf-8")
            except Exception:
                user["idToken"] = None
        if not include_token:
            user.pop("idToken", None)
        return user

    def save_auth_user(self, user_data: Dict[str, Any]) -> bool:
        from src.core import secure_store
        if "firebase" not in self.settings:
            self.settings["firebase"] = {}
        stored = dict(user_data or {})
        tok = stored.get("idToken")
        # Mã hóa bearer token trước khi ghi đĩa
        if isinstance(tok, str) and tok and not secure_store.is_protected(tok):
            try:
                stored["idToken"] = secure_store.protect(tok.encode("utf-8"))
            except Exception:
                stored.pop("idToken", None)
        self.settings["firebase"]["auth_user"] = stored
        return self.save_settings()

    def clear_auth_user(self) -> bool:
        if "firebase" in self.settings:
            self.settings["firebase"]["auth_user"] = None
        return self.save_settings()

    def save_firebase_config(self, config_data: Dict[str, Any]) -> bool:
        if "firebase" not in self.settings:
            self.settings["firebase"] = {}
        for k in ("url", "api_key", "auth_domain", "project_id", "app_id", "enabled"):
            if k in config_data:
                self.settings["firebase"][k] = config_data[k]
        return self.save_settings()

    def test_firebase_connection(self, firebase_url: Optional[str] = None) -> tuple[bool, str]:
        """
        Test connecting to Firebase Realtime Database with optional auth token.
        """
        target_url = firebase_url or self.get("firebase", "url", "")
        if not target_url or not target_url.startswith("http"):
            return False, "URL Firebase không hợp lệ! Vui lòng nhập link dạng https://...firebasedatabase.app/"
        try:
            import urllib.request
            url = target_url.rstrip("/") + "/.json"
            auth_user = self.get_auth_user(include_token=True)
            if auth_user and auth_user.get("idToken"):
                url += f"?auth={auth_user['idToken']}"
            req = urllib.request.Request(url, headers={"User-Agent": "VB-Studio/1.0"})
            with urllib.request.urlopen(req, timeout=5) as res:
                if res.status in (200, 204):
                    user_tag = f" (Xác thực: {auth_user['email']})" if auth_user and auth_user.get("email") else ""
                    return True, f"Kết nối Firebase Realtime thành công (200 OK){user_tag}!"
                return False, f"Mã phản hồi từ Firebase: {res.status}"
        except Exception as e:
            return False, f"Lỗi kết nối Firebase: {str(e)}"
