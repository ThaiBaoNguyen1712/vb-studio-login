from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any
from src.domain.models import Account, Channel, SessionCookie, ChannelItemView

class BaseRepository(ABC):
    """
    Abstract Base Class for Data Access Layer (SOLID: Dependency Inversion & Interface Segregation)
    """

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if repository data store is accessible"""
        pass

    @abstractmethod
    def get_accounts(self) -> List[Account]:
        """Fetch all root Google accounts"""
        pass

    @abstractmethod
    def get_channels(
        self,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[ChannelItemView]:
        """Fetch channels with their current session state, filtered by platform/account/search"""
        pass

    @abstractmethod
    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """Fetch single channel details"""
        pass

    @abstractmethod
    def get_session(self, channel_id: str) -> Optional[SessionCookie]:
        """Get session cookies and lock status for a channel"""
        pass

    @abstractmethod
    def acquire_lock(self, channel_id: str, user_name: str) -> Tuple[bool, Optional[str]]:
        """
        Attempt to acquire lock for a channel.
        Returns: (True, None) if lock acquired successfully,
                 (False, current_holder_name) if already locked by someone else.
        """
        pass

    @abstractmethod
    def release_lock(self, channel_id: str, user_name: str, force: bool = False) -> bool:
        """Release lock on channel (if held by user_name or force=True)"""
        pass

    @abstractmethod
    def heartbeat(self, channel_id: str, user_name: str) -> bool:
        """Gia hạn heartbeat cho kênh đang giữ. Trả về False nếu mất quyền giữ."""
        pass

    @abstractmethod
    def request_access(self, channel_id: str, requester: str, message: str = "") -> Dict[str, Any]:
        """Tạo yêu cầu xin mở kênh đang bị khóa. Trả về {success, request_id/message}."""
        pass

    @abstractmethod
    def list_access_requests(self, status: str = "pending") -> List[Dict[str, Any]]:
        """Liệt kê yêu cầu xin quyền (mặc định chỉ pending)."""
        pass

    @abstractmethod
    def resolve_access_request(self, request_id: str, approver: str, action: str) -> Dict[str, Any]:
        """Duyệt/từ chối yêu cầu. action = approve|deny. Approve = giải phóng khóa."""
        pass

    @abstractmethod
    def save_cookies(self, channel_id: str, cookies: List[Dict[str, Any]], user_name: str) -> bool:
        """UPSERT new cookies extracted from browser and reset in_use_by"""
        pass

    @abstractmethod
    def save_health(self, channel_id: str, health: Dict[str, Any]) -> bool:
        """Persist cookie-forensics verdict without touching cookies/lock"""
        pass

    @abstractmethod
    def restore_session_raw(self, channel_id: str, cookies_raw: Any, health: Any = None) -> bool:
        """Restore session from trash snapshot keeping encrypted payload intact"""
        pass

    @abstractmethod
    def update_cookies_keep_lock(self, channel_id: str, cookies: List[Dict[str, Any]], user_name: str) -> bool:
        """Update stored cookies WITHOUT releasing the channel lock (auto-save while open)"""
        pass

    # ========================================================
    # CRUD Operations for Accounts and Channels
    # ========================================================
    @abstractmethod
    def create_account(self, account: Account) -> bool:
        """Add a new Google Account"""
        pass

    @abstractmethod
    def update_account(self, account: Account) -> bool:
        """Update existing Google Account details"""
        pass

    @abstractmethod
    def delete_account(self, account_id: str) -> bool:
        """Delete an account and its associated channels"""
        pass

    @abstractmethod
    def create_channel(self, channel: Channel) -> bool:
        """Add a new channel to an account"""
        pass

    @abstractmethod
    def update_channel(self, channel: Channel) -> bool:
        """Update existing channel details"""
        pass

    @abstractmethod
    def delete_channel(self, channel_id: str) -> bool:
        """Delete a channel, its cookies, and profile"""
        pass

    @abstractmethod
    def reset_channel_session(self, channel_id: str) -> bool:
        """Purge cookies and reset channel back to NOT_SETUP"""
        pass

    @abstractmethod
    def get_cookie_vault_status(self) -> List[Dict[str, Any]]:
        """Per-channel cookie vault status (count, encrypted flag) — no secret values"""
        pass

    @abstractmethod
    def migrate_plaintext_cookies(self) -> Dict[str, int]:
        """Encrypt all legacy plaintext cookies. Returns {migrated, failed, skipped}"""
        pass

    # ========================================================
    # Health runs (lịch sử + report kiểm tra phiên)
    # ========================================================
    @abstractmethod
    def create_health_run(self, triggered_by: str, total: int, scope: str = "ALL") -> str:
        """Tạo đợt kiểm tra mới, trả về run_id."""
        pass

    @abstractmethod
    def append_health_result(self, run_id: str, channel_id: str, status: str, detail: str = "") -> bool:
        """Ghi kết quả 1 kênh vào đợt kiểm tra. status: alive|dead|error|skipped|empty."""
        pass

    @abstractmethod
    def finish_health_run(self, run_id: str, status: str = "finished") -> bool:
        """Đóng đợt kiểm tra. status: finished|stopped."""
        pass

    @abstractmethod
    def list_health_runs(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Liệt kê các đợt kiểm tra (mới nhất trước, không kèm results)."""
        pass

    @abstractmethod
    def get_health_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Chi tiết 1 đợt kiểm tra kèm results từng kênh."""
        pass
