from typing import List, Optional, Callable, Dict, Any
from src.core.logger import logger
from src.core.constants import ChannelStatus
from src.domain.models import Account, ChannelItemView
from src.repositories.base import BaseRepository
from src.services.session_service import SessionService
from src.services.browser_service import BrowserService

class AccountService:
    """
    Main Application Service orchestrating Business Logic,
    Concurrency Locks, Session Cookies, and Browser Automation.
    """

    def __init__(
        self,
        repository: BaseRepository,
        session_service: SessionService,
        browser_service: BrowserService
    ):
        self.repository = repository
        self.session_service = session_service
        self.browser_service = browser_service

    def get_accounts(self) -> List[Account]:
        return self.repository.get_accounts()

    def get_channel_items(
        self,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[ChannelItemView]:
        return self.repository.get_channels(platform=platform, account_id=account_id, search=search)

    def force_release_channel(self, channel_id: str) -> bool:
        logger.warning(f"Người dùng thực hiện Force Release cho kênh '{channel_id}'")
        return self.session_service.release_channel(channel_id, "", force=True)

    def release_user_channels(self, user_name: str) -> List[str]:
        """
        Đóng các trình duyệt và giải phóng toàn bộ kênh mà user_name đang chiếm giữ.
        Trả về danh sách channel_id đã giải phóng.
        """
        released = set()
        user_clean = (user_name or "").strip().lower()

        # 1. Đóng các trình duyệt Playwright đang mở cục bộ
        active_ids = list(self.browser_service._active_contexts.keys())
        for ch_id in active_ids:
            self.browser_service.close_channel_browser(ch_id)
            self.force_release_channel(ch_id)
            released.add(ch_id)

        # 2. Quét cơ sở dữ liệu để tìm các kênh đang bị khóa bởi user_name
        try:
            items = self.repository.get_channels()
            for it in items:
                holder = (it.locked_by or "").strip().lower()
                ch_id = it.channel.id
                if (user_clean and holder == user_clean) or ch_id in active_ids:
                    self.force_release_channel(ch_id)
                    released.add(ch_id)
        except Exception as e:
            logger.error(f"Lỗi khi quét kênh đang giam để xả: {e}")

        logger.info(f"Đã giải phóng {len(released)} kênh cho '{user_name}': {list(released)}")
        return list(released)

    def create_account(self, account: Account) -> bool:
        return self.repository.create_account(account)

    def update_account(self, account: Account) -> bool:
        return self.repository.update_account(account)

    def delete_account(self, account_id: str) -> bool:
        return self.repository.delete_account(account_id)

    def create_channel(self, channel) -> bool:
        return self.repository.create_channel(channel)

    def update_channel(self, channel) -> bool:
        return self.repository.update_channel(channel)

    def delete_channel(self, channel_id: str) -> bool:
        return self.repository.delete_channel(channel_id)

    def reset_channel_session(self, channel_id: str) -> bool:
        return self.repository.reset_channel_session(channel_id)

    def heartbeat(self, channel_id: str, user_name: str) -> bool:
        return self.session_service.heartbeat(channel_id, user_name)

    def request_access(self, channel_id: str, requester: str, message: str = ""):
        return self.session_service.request_access(channel_id, requester, message or "")

    def list_access_requests(self, status: str = "pending"):
        return self.session_service.list_access_requests(status=status)

    def resolve_access_request(self, request_id: str, approver: str, action: str):
        return self.session_service.resolve_access_request(request_id, approver, action)

    def launch_channel(
        self,
        channel_id: str,
        user_name: str,
        on_status_change: Optional[Callable[[str, ChannelStatus, Optional[str]], None]] = None,
        on_error: Optional[Callable[[str, str], None]] = None,
        on_autosaved: Optional[Callable[[str, int], None]] = None
    ):
        """
        Coordinates the complete launch workflow:
        1. Lock channel
        2. Query cookies
        3. Determine Studio vs First-Time Setup Login URL
        4. Launch Playwright Chromium
        5. Extract cookies upon close and UPSERT to DB
        6. Release lock and update status
        """
        # Step 1: Concurrency check & acquire lock
        locked, locked_by = self.session_service.try_acquire_channel(channel_id, user_name)
        if not locked:
            msg = f"Kênh đang được sử dụng bởi '{locked_by}'. Vui lòng thử lại sau hoặc chọn mở khóa cưỡng chế nếu phiên bị kẹt."
            logger.warning(f"Từ chối mở kênh '{channel_id}': {msg}")
            if on_error:
                on_error(channel_id, msg)
            return

        # Fetch channel and cookies info
        channel = self.repository.get_channel(channel_id)
        if not channel:
            self.session_service.release_channel(channel_id, user_name)
            if on_error:
                on_error(channel_id, f"Không tìm thấy thông tin kênh '{channel_id}'")
            return

        cookies = self.session_service.get_channel_cookies(channel_id)
        has_cookies = len(cookies) > 0

        # Step 2: Determine target URL
        if has_cookies:
            target_url = channel.studio_url
            logger.info(f"1-Click Launch: Kênh '{channel.channel_name}' đã có cookies -> Mở thẳng Studio: {target_url}")
        else:
            target_url = channel.login_url
            logger.info(f"First-Time Setup: Kênh '{channel.channel_name}' chưa có cookies -> Mở trang Login: {target_url}")

        if on_status_change:
            on_status_change(channel_id, ChannelStatus.IN_USE, user_name)

        # Callbacks for browser lifecycle
        def _on_started():
            logger.info(f"Trình duyệt đã mở thành công cho kênh '{channel_id}'")

        def _on_closed(new_cookies: List[Dict[str, Any]]):
            logger.info(f"Đã đóng trình duyệt cho kênh '{channel_id}'. Bắt đầu đồng bộ dữ liệu...")
            new_cookies = self.session_service.prune_cookies(new_cookies)
            if new_cookies and len(new_cookies) > 0:
                self.session_service.save_channel_cookies(channel_id, new_cookies, user_name)
                final_status = ChannelStatus.READY
            else:
                # Nếu không bắt được cookie mới và trước đó cũng chưa có cookie thì vẫn là NOT_SETUP
                self.session_service.release_channel(channel_id, user_name)
                final_status = ChannelStatus.READY if has_cookies else ChannelStatus.NOT_SETUP

            if on_status_change:
                on_status_change(channel_id, final_status, None)

        def _on_browser_error(exc: Exception):
            logger.error(f"Lỗi BrowserService cho kênh '{channel_id}': {exc}")
            self.session_service.release_channel(channel_id, user_name)
            if on_status_change:
                on_status_change(channel_id, ChannelStatus.READY if has_cookies else ChannelStatus.NOT_SETUP, None)
            if on_error:
                on_error(channel_id, f"Lỗi khởi động trình duyệt: {exc}")

        def _on_autosave(snapshot: List[Dict[str, Any]]):
            # Tự lưu định kỳ khi browser còn mở (giữ lock, refresh heartbeat)
            if snapshot is None:
                return
            pruned = self.session_service.prune_cookies(snapshot)
            if self.session_service.autosave_open_channel(channel_id, pruned, user_name):
                if on_autosaved:
                    on_autosaved(channel_id, len(pruned))

        # Launch in thread
        self.browser_service.launch_channel_browser(
            channel_id=channel_id,
            target_url=target_url,
            cookies=cookies,
            on_started=_on_started,
            on_closed=_on_closed,
            on_error=_on_browser_error,
            on_autosave=_on_autosave
        )
