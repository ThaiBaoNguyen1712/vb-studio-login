"""Kiểm tra phiên đăng nhập còn sống không — KHÔNG chạm trình duyệt, KHÔNG gọi mạng.

Cơ chế: soi cookies đã lưu trong vault (cookie forensics).
- Mỗi nền tảng có 1-2 cookie phiên bắt buộc (VD Google: SID/HSID, Facebook: c_user/xs).
- Thiếu cookie bắt buộc -> chết chắc (đã logout hoặc bị thu hồi).
- Cookie bắt buộc còn hạn -> sống (không cần mở browser để biết).
- Tuyệt đối an toàn: không automation flag, không IP lạ, không nguy cơ khóa acc.

Ca nghi ngờ: bấm "Mở Studio" (trình duyệt thật, profile persistent, headed)
để mắt thường xác minh — đó chính là luồng launch_channel có sẵn.
"""
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

from src.core.logger import logger
from src.services.session_service import SessionService
from src.repositories.base import BaseRepository

# Cookie phiên bắt buộc của từng nền tảng (vắng mặt = đã logout/thu hồi).
REQUIRED_AUTH_COOKIES = {
    "YOUTUBE_SHORTS": ["SID", "HSID"],
    "TIKTOK": ["sessionid"],
    "FACEBOOK_REELS": ["c_user", "xs"],
    "INSTAGRAM_REELS": ["sessionid"],
}


def _by_name(cookies: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
    return [c for c in cookies or [] if c.get("name") == name]


def _is_fresh(cookie: Dict[str, Any], now: float) -> bool:
    """True nếu cookie session (không expires) hoặc còn hạn."""
    exp = cookie.get("expires", 0)
    if not isinstance(exp, (int, float)) or exp <= 0:
        return True  # session-cookie: còn tồn tại = còn dùng được
    return exp > now


def _fmt_exp(exp: float) -> str:
    try:
        return datetime.fromtimestamp(exp).strftime("%d/%m/%Y")
    except Exception:
        return "?"


class HealthService:
    """Soi cookies để kết luận sống/chết. Không browser, không network."""

    def __init__(self, repository: BaseRepository, session_service: SessionService):
        self.repository = repository
        self.session_service = session_service

    def check_channel(self, channel_id: str) -> Dict[str, Any]:
        """Phân tích cookies 1 kênh, lưu verdict, trả kết quả."""
        channel = self.repository.get_channel(channel_id)
        if not channel:
            return {"success": False, "message": f"Không tìm thấy kênh '{channel_id}'."}
        session = self.repository.get_session(channel_id)
        if session and session.in_use_by:
            return {"success": False, "skipped": True,
                    "message": f"Kênh đang mở bởi '{session.in_use_by}', bỏ qua."}
        cookies = self.session_service.get_channel_cookies(channel_id)
        if not cookies:
            self._save(channel_id, "unknown", "chưa có cookies để phân tích", None)
            return {"success": True, "status": "empty", "message": "Kênh chưa có cookies."}

        plat = channel.platform.value if hasattr(channel.platform, "value") else str(channel.platform)
        required = REQUIRED_AUTH_COOKIES.get(str(plat).upper(), [])
        now = time.time()

        if not required:
            verdict = self._heuristic(cookies, now)
        else:
            verdict = self._by_required(cookies, required, now)

        self._save(channel_id, verdict["status"], verdict["detail"], verdict.get("expires_at"))
        ok_msg = (f"Kênh '{channel.channel_name}' còn sống ({verdict['detail']})."
                  if verdict["status"] == "alive" else
                  f"Kênh '{channel.channel_name}' đã hết hạn ({verdict['detail']}).")
        return {"success": verdict["status"] in ("alive", "dead"),
                "status": verdict["status"], "message": ok_msg}

    def _by_required(self, cookies: List[Dict[str, Any]], required: List[str], now: float) -> Dict[str, Any]:
        missing = [n for n in required if not _by_name(cookies, n)]
        if missing:
            return {"status": "dead",
                    "detail": f"thiếu cookie phiên: {', '.join(missing)} (đã logout hoặc bị thu hồi)",
                    "expires_at": None}
        # Đủ cookie bắt buộc -> xem hạn
        timed = []
        for n in required:
            for c in _by_name(cookies, n):
                exp = c.get("expires", 0)
                if isinstance(exp, (int, float)) and exp > 0:
                    timed.append(exp)
        if timed and all(e < now for e in timed):
            return {"status": "dead",
                    "detail": f"cookie {', '.join(required)} đều đã quá hạn",
                    "expires_at": None}
        if timed:
            nearest = min(e for e in timed if e > now)
            return {"status": "alive",
                    "detail": f"cookie {', '.join(required)} còn hạn đến {_fmt_exp(nearest)}",
                    "expires_at": nearest}
        return {"status": "alive",
                "detail": f"đủ cookie phiên {', '.join(required)} (session)",
                "expires_at": None}

    def _heuristic(self, cookies: List[Dict[str, Any]], now: float) -> Dict[str, Any]:
        """Nền tảng lạ/không có quy tắc riêng: còn cookie chưa hết hạn là còn sống."""
        fresh = [c for c in cookies if _is_fresh(c, now)]
        if not fresh:
            return {"status": "dead", "detail": "toàn bộ cookies đã quá hạn", "expires_at": None}
        timed = [c["expires"] for c in fresh
                 if isinstance(c.get("expires"), (int, float)) and c["expires"] > 0]
        detail = (f"còn {len(fresh)} cookie, hạn đến {_fmt_exp(min(timed))} (quy tắc chung)"
                  if timed else f"còn {len(fresh)} cookie phiên (quy tắc chung)")
        return {"status": "alive", "detail": detail,
                "expires_at": min(timed) if timed else None}

    def _save(self, channel_id: str, status: str, detail: str, expires_at):
        try:
            self.repository.save_health(channel_id, {
                "status": status,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "detail": detail,
                "method": "cookies",
                "expires_at": expires_at,
            })
        except Exception as e:
            logger.error(f"Lưu health '{channel_id}' lỗi: {e}")
