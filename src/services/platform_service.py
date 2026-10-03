"""Registry mạng xã hội động (thay enum Platform cứng).

Mặc định seed 4 socials (YouTube/TikTok/Facebook/Instagram) kèm logo +
URL mở mặc định. Người dùng tự thêm/sửa/xóa socials; social mới tạo
được tự gắn logo + URL mặc định cho các kênh phân nhánh.
Lưu tại data/platforms.json — không cần đụng code khi thêm mạng mới.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.core.config import Config
from src.core.constants import PLATFORM_META
from src.core.logger import logger

PLATFORMS_FILE = Config.DATA_DIR / "platforms.json"

CODE_RE = re.compile(r"^[A-Z0-9_]{2,30}$")

_DEFAULT_PREFIX = {
    "YOUTUBE_SHORTS": "yt",
    "TIKTOK": "tt",
    "FACEBOOK_REELS": "fb",
    "INSTAGRAM_REELS": "ig",
}


def _seed_defaults() -> List[Dict[str, Any]]:
    items = []
    for plat, meta in PLATFORM_META.items():
        code = plat.value if hasattr(plat, "value") else str(plat)
        asset = {
            "YOUTUBE_SHORTS": "./assets/youtube.png",
            "TIKTOK": "./assets/tiktok.png",
            "FACEBOOK_REELS": "./assets/facebook.png",
            "INSTAGRAM_REELS": "./assets/instagram.png",
        }.get(code, "")
        items.append({
            "code": code,
            "name": meta.get("title", code),
            "tag": meta.get("tag", code),
            "studio_url": meta.get("studio_url", ""),
            "login_url": meta.get("login_url", ""),
            "icon": asset,
            "prefix": _DEFAULT_PREFIX.get(code, code[:2].lower()),
            "builtin": True,
        })
    return items


class PlatformService:
    """CRUD registry socials, persist JSON local."""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or PLATFORMS_FILE
        self._platforms: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> List[Dict[str, Any]]:
        Config.ensure_directories()
        if not self.file_path.exists():
            self._platforms = _seed_defaults()
            self._save()
        else:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._platforms = data if isinstance(data, list) else _seed_defaults()
            except Exception as e:
                logger.error(f"Lỗi đọc platforms.json: {e}")
                self._platforms = _seed_defaults()
        # Tự vá các bản ghi thiếu trường (file cũ)
        changed = False
        seeds = {p["code"]: p for p in _seed_defaults()}
        for p in self._platforms:
            s = seeds.get(p.get("code"))
            for k in ("name", "tag", "studio_url", "login_url", "icon", "prefix", "builtin"):
                if p.get(k) in (None, "") and s and s.get(k):
                    p[k] = s[k]
                    changed = True
        if changed:
            self._save()
        return self._platforms

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._platforms, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lỗi ghi platforms.json: {e}")

    def list(self) -> List[Dict[str, Any]]:
        return [dict(p) for p in self._platforms]

    def get(self, code: str) -> Optional[Dict[str, Any]]:
        code = (code or "").upper()
        for p in self._platforms:
            if p.get("code") == code:
                return dict(p)
        return None

    @staticmethod
    def _clean(data: Dict[str, Any]) -> Dict[str, Any]:
        code = str(data.get("code", "")).strip().upper()
        name = str(data.get("name", "")).strip() or code
        return {
            "code": code,
            "name": name,
            "tag": str(data.get("tag", "")).strip() or name,
            "studio_url": str(data.get("studio_url", "")).strip(),
            "login_url": str(data.get("login_url", "")).strip() or str(data.get("studio_url", "")).strip(),
            "icon": str(data.get("icon", "") or ""),
            "prefix": str(data.get("prefix", "")).strip().lower() or code[:2].lower(),
            "builtin": bool(data.get("builtin", False)),
        }

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        p = self._clean(data)
        p["builtin"] = False
        if not CODE_RE.match(p["code"]):
            return {"success": False, "message": "Mã social chỉ gồm A-Z, 0-9, _ (2-30 ký tự)."}
        if self.get(p["code"]):
            return {"success": False, "message": f"Mã '{p['code']}' đã tồn tại."}
        if any(x.get("prefix") == p["prefix"] for x in self._platforms):
            return {"success": False, "message": f"Tiền tố ID '{p['prefix']}' bị trùng, đổi prefix khác."}
        if not p["studio_url"]:
            return {"success": False, "message": "Cần nhập URL mở mặc định (studio/trang chủ)."}
        self._platforms.append(p)
        self._save()
        logger.info(f"Đã thêm social mới: {p['code']} ({p['name']})")
        return {"success": True, "platform": p}

    def update(self, code: str, data: Dict[str, Any]) -> Dict[str, Any]:
        code = (code or "").upper()
        for i, p in enumerate(self._platforms):
            if p.get("code") == code:
                new_prefix = str(data.get("prefix", p.get("prefix"))).strip().lower()
                if any(x.get("code") != code and x.get("prefix") == new_prefix for x in self._platforms):
                    return {"success": False, "message": f"Tiền tố ID '{new_prefix}' bị trùng."}
                merged = self._clean({**p, **data, "code": code, "builtin": p.get("builtin", False)})
                self._platforms[i] = merged
                self._save()
                return {"success": True, "platform": merged}
        return {"success": False, "message": f"Không tìm thấy social '{code}'."}

    def delete(self, code: str, channel_count: int = 0) -> Dict[str, Any]:
        code = (code or "").upper()
        if channel_count > 0:
            return {"success": False,
                    "message": f"Social '{code}' còn {channel_count} kênh đang dùng — xóa/chuyển kênh trước."}
        before = len(self._platforms)
        self._platforms = [p for p in self._platforms if p.get("code") != code]
        if len(self._platforms) == before:
            return {"success": False, "message": f"Không tìm thấy social '{code}'."}
        self._save()
        logger.info(f"Đã xóa social: {code}")
        return {"success": True}

    def reset_defaults(self) -> Dict[str, Any]:
        """Khôi phục 4 socials mặc định (giữ lại socials tự thêm)."""
        seeds = _seed_defaults()
        have = {p.get("code") for p in self._platforms}
        added = 0
        for s in seeds:
            if s["code"] not in have:
                self._platforms.append(s)
                added += 1
        self._save()
        return {"success": True, "added": added}
