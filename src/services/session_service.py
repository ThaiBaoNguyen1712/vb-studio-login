from typing import List, Dict, Any, Optional, Tuple
from src.core.logger import logger
from src.repositories.base import BaseRepository

class SessionService:
    """
    Manages session lifecycle, concurrency locking, and cookie persistence.
    """

    def __init__(self, repository: BaseRepository):
        self.repository = repository

    def try_acquire_channel(self, channel_id: str, user_name: str) -> Tuple[bool, Optional[str]]:
        """
        Attempts to acquire channel lock for the user.
        Returns: (True, None) if successful, or (False, "name_of_user_occupying")
        """
        return self.repository.acquire_lock(channel_id, user_name)

    def release_channel(self, channel_id: str, user_name: str, force: bool = False) -> bool:
        """
        Releases the lock on the channel.
        """
        return self.repository.release_lock(channel_id, user_name, force=force)

    def heartbeat(self, channel_id: str, user_name: str) -> bool:
        try:
            return self.repository.heartbeat(channel_id, user_name)
        except Exception:
            return False

    def request_access(self, channel_id: str, requester: str, message: str = "") -> Dict[str, Any]:
        return self.repository.request_access(channel_id, requester, message or "")

    def list_access_requests(self, status: str = "pending") -> List[Dict[str, Any]]:
        try:
            return self.repository.list_access_requests(status=status)
        except Exception as e:
            logger.error(f"list_access_requests failed: {e}")
            return []

    def resolve_access_request(self, request_id: str, approver: str, action: str) -> Dict[str, Any]:
        return self.repository.resolve_access_request(request_id, approver, action)

    def get_channel_cookies(self, channel_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves stored cookies for injection.
        """
        session = self.repository.get_session(channel_id)
        if session and session.cookies_data:
            return session.cookies_data
        return []

    def save_channel_cookies(self, channel_id: str, cookies: List[Dict[str, Any]], user_name: str) -> bool:
        """
        Saves updated cookies and unlocks the channel.
        """
        return self.repository.save_cookies(channel_id, cookies, user_name)

    def autosave_open_channel(self, channel_id: str, cookies: List[Dict[str, Any]], user_name: str) -> bool:
        """
        Tự lưu cookies của kênh đang mở, giữ nguyên lock.
        """
        try:
            return self.repository.update_cookies_keep_lock(channel_id, cookies, user_name)
        except AttributeError:
            logger.warning(f"Repository chưa hỗ trợ tự lưu, bỏ qua '{channel_id}'")
            return False

    # Giới hạn chống phình DB: mỗi lần lưu là ghi đè toàn bộ mảng nên không
    # bao giờ nối dài, nhưng browser tích lũy cookies rác theo thời gian.
    MAX_COOKIES_PER_CHANNEL = 1500

    @classmethod
    def prune_cookies(cls, cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Lọc cookies trước khi lưu: bỏ thiếu trường, hết hạn, trùng
        (name, domain, path) giữ bản cuối, cắt trần số lượng.
        """
        import time as _time
        now = _time.time()
        seen = set()
        kept_reversed = []
        for c in reversed(cookies or []):
            if not isinstance(c, dict):
                continue
            name, value, domain = c.get("name"), c.get("value"), c.get("domain")
            if name is None or value is None or domain is None:
                continue
            exp = c.get("expires")
            if isinstance(exp, (int, float)) and exp > 0 and exp < now - 60:
                continue  # hết hạn quá 60s -> rác
            key = (str(domain).lower(), str(c.get("path", "/")), str(name))
            if key in seen:
                continue  # trùng -> giữ bản mới nhất (duyệt ngược)
            seen.add(key)
            kept_reversed.append(c)
        kept = list(reversed(kept_reversed))
        dropped = len(cookies or []) - len(kept)
        if len(kept) > cls.MAX_COOKIES_PER_CHANNEL:
            kept = kept[-cls.MAX_COOKIES_PER_CHANNEL:]
            dropped = len(cookies or []) - len(kept)
        if dropped > 0:
            logger.info(f"Prune cookies: bỏ {dropped} mục rác/trùng/hết hạn.")
        return kept
