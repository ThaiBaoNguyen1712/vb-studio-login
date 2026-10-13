from typing import List, Optional, Callable, Dict, Any
from src.core.config import Config
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
        browser_service: BrowserService,
        sync_service=None
    ):
        self.repository = repository
        self.session_service = session_service
        self.browser_service = browser_service
        # Sync online lien may (optional): chan mo trung + inbox xin mo.
        # None = che do local-only (giu nguyen hanh vi cu khi offline).
        self.sync_service = sync_service
        self.on_session_auto_released = None
        self._watchdog_thread = None
        self._watchdog_stop = None

    def _sync_machine(self) -> str:
        try:
            return self.sync_service.machine_id if self.sync_service else ""
        except Exception:
            return ""

    def _remote_lock_other(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Lock remote con fresh cua may KHAC (None neu tu do/offline/cua minh)."""
        sync = self.sync_service
        if not sync or not sync.is_online():
            return None
        try:
            rl = sync.remote_lock_of(channel_id)
        except Exception:
            return None
        if not rl:
            return None
        if (rl.get("machine") or "") == self._sync_machine():
            return None
        # Khac may la may khac giu — KE CA khi trung ten (2 may dung chung gmail).
        # May giu duoc phan biet bang machine id, khong phai ten.
        return rl

    def get_accounts(self) -> List[Account]:
        return self.repository.get_accounts()

    def get_channel_items(
        self,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[ChannelItemView]:
        return self.repository.get_channels(platform=platform, account_id=account_id, search=search)

    def force_release_channel(self, channel_id: str, remote_force: bool = False) -> bool:
        logger.warning(f"Người dùng thực hiện Force Release cho kênh '{channel_id}'")
        ok = self.session_service.release_channel(channel_id, "", force=True)
        # Xa ca lock remote (neu online). force=False chi xoa khi lock la cua may nay.
        sync = self.sync_service
        if sync and sync.is_online():
            try:
                sync.release_lock(channel_id, force=remote_force)
            except Exception as e:
                logger.debug(f"Xa lock remote '{channel_id}' bo qua: {e}")
        return ok

    def release_all_sessions(self, user_name: Optional[str] = None) -> List[str]:
        """
        Đóng toàn bộ trình duyệt đang mở và giải phóng phiên cho người dùng (hoặc toàn bộ kênh trên máy này khi tắt app).
        Bảo toàn cookies: trích xuất và cập nhật cookies mới nhất trước khi xả lock.
        """
        released = set()
        user_clean = (user_name or "").strip().lower() if user_name else ""

        # 1. Đóng các trình duyệt đang mở cục bộ
        active_ids = list(self.browser_service._active_contexts.keys())
        if active_ids:
            from concurrent.futures import ThreadPoolExecutor

            def _close_and_release(ch_id: str) -> str:
                try:
                    self.browser_service.close_channel_browser(ch_id)
                except Exception as e:
                    logger.warning(f"Đóng trình duyệt kênh '{ch_id}' lỗi: {e}")

                try:
                    from src.services.cookie_extractor import CookieExtractor
                    profile_dir = Config.get_profile_path(ch_id)
                    cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
                    if cookies:
                        pruned = self.session_service.prune_cookies(cookies)
                        self.session_service.save_channel_cookies(ch_id, pruned, user_name or "")
                except Exception as ce:
                    logger.debug(f"Trích xuất backup cookies kênh '{ch_id}': {ce}")

                try:
                    self.force_release_channel(ch_id)
                except Exception as e:
                    logger.error(f"Xả lock DB kênh '{ch_id}' lỗi: {e}")
                return ch_id

            try:
                with ThreadPoolExecutor(
                    max_workers=min(8, len(active_ids)),
                    thread_name_prefix="Release"
                ) as ex:
                    for ch_id in ex.map(_close_and_release, active_ids):
                        released.add(ch_id)
            except Exception as e:
                logger.error(f"Lỗi khi đóng song song {len(active_ids)} trình duyệt: {e}")
                for ch_id in active_ids:
                    try:
                        self.browser_service.close_channel_browser(ch_id)
                    except Exception:
                        pass
                    try:
                        self.force_release_channel(ch_id)
                    except Exception:
                        pass
                    released.add(ch_id)

        # 2. Quét cơ sở dữ liệu để tìm các kênh đang bị khóa cần xả
        try:
            items = self.repository.get_channels()
            for it in items:
                holder = (it.locked_by or "").strip().lower()
                ch_id = it.channel.id
                if not holder:
                    continue
                if (not user_clean) or (holder == user_clean) or (ch_id in active_ids):
                    self.force_release_channel(ch_id)
                    released.add(ch_id)
        except Exception as e:
            logger.error(f"Lỗi khi quét kênh đang giam để xả: {e}")

        logger.info(f"Đã giải phóng {len(released)} kênh: {list(released)}")
        return list(released)

    def release_user_channels(self, user_name: str) -> List[str]:
        """
        Đóng các trình duyệt và giải phóng toàn bộ kênh mà user_name đang chiếm giữ.
        """
        return self.release_all_sessions(user_name=user_name)

    def cleanup_on_shutdown(self, user_name: Optional[str] = None) -> List[str]:
        """
        Cơ chế dọn dẹp và giải phóng toàn bộ phiên khi tắt app.
        Bao gồm đóng trình duyệt, lưu cookies, xả khóa cục bộ, và dừng sync service.
        """
        logger.info("Bắt đầu giải phóng toàn bộ phiên làm việc khi tắt app...")
        released = self.release_all_sessions(user_name=user_name)
        if self.sync_service is not None:
            try:
                self.sync_service.stop()
            except Exception as e:
                logger.debug(f"Dừng sync service khi shutdown lỗi: {e}")
        logger.info(f"Hoàn tất giải phóng phiên khi tắt app ({len(released)} kênh).")
        return released

    def recover_orphaned_locks(self) -> List[str]:
        """
        Khôi phục các khóa mồ côi (orphaned locks) còn sót lại từ lần chạy trước
        khi app bị tắt đột ngột (crash, taskkill, mất điện).
        """
        recovered = []
        try:
            items = self.repository.get_channels()
            active_ids = set(self.browser_service.get_active_channel_ids())
            for it in items:
                holder = it.locked_by
                ch_id = it.channel.id
                if not holder:
                    continue
                # Nếu có sync_service online và máy khác đang giữ fresh thì không chạm vào
                if self.sync_service is not None and self.sync_service.is_online():
                    rl = self._remote_lock_other(ch_id)
                    if rl:
                        continue  # Máy khác đang giữ hợp lệ
                # Kênh đang bị khóa nhưng trình duyệt không chạy trên máy này -> lock mồ côi
                if ch_id not in active_ids:
                    logger.warning(f"Phát hiện khóa mồ côi từ phiên trước cho kênh '{ch_id}' (giữ bởi '{holder}'). Đang giải phóng...")
                    self.session_service.release_channel(ch_id, "", force=True)
                    if self.sync_service is not None:
                        try:
                            self.sync_service.release_lock(ch_id, force=True)
                        except Exception:
                            pass
                    recovered.append(ch_id)
        except Exception as e:
            logger.error(f"Lỗi khi khôi phục khóa mồ côi: {e}")
        if recovered:
            logger.info(f"Đã khôi phục thành công {len(recovered)} khóa mồ côi: {recovered}")
        return recovered

    def start_watchdog(self, interval_sec: float = 5.0):
        """
        Khởi chạy luồng giám sát phiên nền (Watchdog):
        Định kỳ quét trạng thái tiến trình và heartbeat.
        Nếu tiến trình browser đã tắt hoặc mất heartbeat quá hạn -> tự động xả ngay lập tức.
        """
        if getattr(self, "_watchdog_thread", None) and self._watchdog_thread.is_alive():
            return
        import threading
        self._watchdog_stop = threading.Event()

        def _watchdog_loop():
            while not self._watchdog_stop.wait(interval_sec):
                try:
                    self._watchdog_tick()
                except Exception as e:
                    logger.debug(f"Watchdog tick error: {e}")

        self._watchdog_thread = threading.Thread(
            target=_watchdog_loop,
            name="SessionWatchdogThread",
            daemon=True
        )
        self._watchdog_thread.start()
        logger.info(f"Session Watchdog đã được kích hoạt (quét xả phiên chết mỗi {interval_sec}s).")

    def stop_watchdog(self):
        if hasattr(self, "_watchdog_stop") and self._watchdog_stop:
            self._watchdog_stop.set()

    def _watchdog_tick(self):
        # 1. Dọn dẹp tiến trình chết trong browser_service
        self.browser_service._clean_dead_processes()
        active_ids = set(self.browser_service.get_active_channel_ids())

        # 2. Quét DB: bất kỳ kênh nào đang in_use_by mà browser không chạy trên máy này
        try:
            items = self.repository.get_channels()
            for it in items:
                ch_id = it.channel.id
                holder = it.locked_by
                if not holder:
                    continue
                # Nếu browser không mở kênh này trên máy này
                if ch_id not in active_ids:
                    # Kiểm tra xem có phải máy khác đang giữ hợp lệ qua sync không
                    if self.sync_service is not None and self.sync_service.is_online():
                        rl = self._remote_lock_other(ch_id)
                        if rl:
                            continue
                    # Kiểm tra xem phiên có phải do máy này mở hoặc đã bị stale không
                    sess = self.repository.get_session(ch_id)
                    is_stale = False
                    if sess:
                        raw_sess = {
                            "in_use_by": sess.in_use_by,
                            "in_use_since": sess.in_use_since.isoformat() if sess.in_use_since else None,
                            "last_heartbeat": sess.last_heartbeat.isoformat() if sess.last_heartbeat else None
                        }
                        if hasattr(self.repository, "_is_lock_stale"):
                            is_stale = self.repository._is_lock_stale(raw_sess)

                    # Tự động xả nếu lock stale hoặc nếu kênh từng được gán trong channel_locks cục bộ
                    if is_stale or (ch_id in getattr(self.browser_service, "_channel_locks", {})):
                        logger.warning(f"Watchdog phát hiện phiên bị giữ đột ngột cho kênh '{ch_id}' (holder: '{holder}'). Đang tự động xả...")
                        self.force_release_channel(ch_id, remote_force=True)
                        if getattr(self, "on_session_auto_released", None):
                            try:
                                self.on_session_auto_released(ch_id)
                            except Exception:
                                pass
        except Exception as e:
            logger.debug(f"Watchdog tick scan error: {e}")

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
        ok = self.session_service.heartbeat(channel_id, user_name)
        # Keepalive lock remote (giu fresh < STALE 45s). Best-effort, khong block.
        if ok and self.sync_service is not None:
            try:
                if self.sync_service.is_online():
                    self.sync_service.refresh_lock(channel_id, user_name, self._sync_machine())
            except Exception:
                pass
        return ok

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
        4. Launch Native Browser (Chrome/Edge)
        5. Extract cookies upon close and UPSERT to DB
        6. Release lock and update status
        """
        # Step 0: Chan mo trung lien may (neu online). May nao giu fresh thi thang,
        # ke ca trung ten (2 may dung chung gmail) — phan biet bang machine id.
        sync = self.sync_service
        if sync is not None:
            try:
                rl = self._remote_lock_other(channel_id)
            except Exception:
                rl = None
            if rl:
                msg = (f"Kênh đang được '{rl.get('holder')}' giữ trên máy khác "
                       f"({rl.get('machine')}). Bấm 'Xin mở' để gửi yêu cầu.")
                logger.warning(f"Từ chối mở kênh '{channel_id}' (remote lock): {msg}")
                if on_error:
                    on_error(channel_id, msg)
                return

        # Step 1: Concurrency check & acquire lock
        locked, locked_by = self.session_service.try_acquire_channel(channel_id, user_name)
        if not locked:
            msg = f"Kênh đang được sử dụng bởi '{locked_by}'. Vui lòng thử lại sau hoặc chọn mở khóa cưỡng chế nếu phiên bị kẹt."
            logger.warning(f"Từ chối mở kênh '{channel_id}': {msg}")
            if on_error:
                on_error(channel_id, msg)
            return

        # Step 1b: Giu lock remote (best-effort). Neu thua race ( False ) -> nha local.
        if sync is not None and sync.is_online():
            try:
                if not sync.claim_lock(channel_id, user_name, self._sync_machine()):
                    self.session_service.release_channel(channel_id, user_name, force=True)
                    rl = self._remote_lock_other(channel_id) or {}
                    msg = (f"Kênh vừa bị '{rl.get('holder', '?')}' giữ trên máy khác "
                           f"({rl.get('machine', '?')}). Bấm 'Xin mở' để gửi yêu cầu.")
                    if on_error:
                        on_error(channel_id, msg)
                    return
            except Exception as e:
                logger.debug(f"claim remote '{channel_id}' bo qua: {e}")

        # Fetch channel and cookies info
        channel = self.repository.get_channel(channel_id)
        if not channel:
            self.session_service.release_channel(channel_id, user_name)
            if sync is not None:
                try:
                    sync.release_lock(channel_id)
                except Exception:
                    pass
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

        def _release_remote():
            if sync is not None:
                try:
                    sync.release_lock(channel_id)
                except Exception:
                    pass

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

            _release_remote()
            if on_status_change:
                on_status_change(channel_id, final_status, None)

        def _on_browser_error(exc: Exception):
            logger.error(f"Lỗi BrowserService cho kênh '{channel_id}': {exc}")
            self.session_service.release_channel(channel_id, user_name)
            _release_remote()
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
                if sync is not None:
                    try:
                        sync.refresh_lock(channel_id, user_name, self._sync_machine())
                    except Exception:
                        pass
                if on_autosaved:
                    on_autosaved(channel_id, len(pruned))

        def _on_heartbeat():
            self.heartbeat(channel_id, user_name)

        # Launch in thread
        self.browser_service.launch_channel_browser(
            channel_id=channel_id,
            target_url=target_url,
            cookies=cookies,
            on_started=_on_started,
            on_closed=_on_closed,
            on_error=_on_browser_error,
            on_autosave=_on_autosave,
            on_heartbeat=_on_heartbeat
        )
