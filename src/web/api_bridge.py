import json
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
import webview

from src.core.logger import logger
from src.core.constants import Platform, ChannelStatus, PLATFORM_META, parse_platform, platform_value
from src.domain.models import Account, Channel
from src.services.account_service import AccountService
from src.services.settings_service import SettingsService
from src.services.firebase_auth_service import FirebaseAuthService
from src.services.platform_service import PlatformService
from src.services.update_service import UpdateService
from src.repositories.local_repo import LocalJsonRepository

from src.repositories.postgres_repo import PostgresRepository

class WebBridge:
    """
    Bidirectional bridge between Python backend and Modern Web Frontend.
    Methods called via window.pywebview.api.<method_name>()
    Note: All internal dependencies are prefixed with '_' so pywebview
    does not recursively traverse internal Python / WinForms objects.
    """

    # Nền tảng có thể phân nhánh khi thêm tài khoản (đồng bộ với modal frontend)
    _ALL_BRANCH_PLATFORMS = [
        (Platform.YOUTUBE_SHORTS, "yt", "YouTube"),
        (Platform.TIKTOK, "tt", "TikTok"),
        (Platform.FACEBOOK_REELS, "fb", "Facebook"),
        (Platform.INSTAGRAM_REELS, "ig", "Instagram"),
    ]

    def __init__(self, account_service: AccountService, settings_service: SettingsService):
        self._account_service = account_service
        self._settings_service = settings_service
        self._platform_service = PlatformService()
        self._bulk_stop = threading.Event()
        self._bulk_running = False
        self._window = None  # Injected after window creation
        self._popups = {}  # request_id -> popup Window (overlay nổi trên mọi app)
        self._auth_service = FirebaseAuthService(
            settings_service=self._settings_service,
            on_auth_success=self._on_auth_success
        )
        self._update_service = UpdateService(settings_service=self._settings_service)


    def _branch_platforms(self) -> List[Dict[str, Any]]:
        """Danh sách socials động từ registry (thay _ALL_BRANCH_PLATFORMS cứng)."""
        try:
            plats = self._platform_service.list()
            if plats:
                return plats
        except Exception as e:
            logger.warning(f"Platform registry lỗi, dùng mặc định cứng: {e}")
        return [
            {"code": p.value, "tag": t, "prefix": px,
             "studio_url": PLATFORM_META[p]["studio_url"],
             "login_url": PLATFORM_META[p]["login_url"]}
            for p, px, t in self._ALL_BRANCH_PLATFORMS
        ]

    def _on_auth_success(self, user_info: Dict[str, Any]):
        self.notify_frontend("auth_state_changed", user_info)

    def set_window(self, window):
        self._window = window

    def notify_frontend(self, event_name: str, payload: Any = None):
        """Dispatches custom event to frontend JavaScript"""
        if self._window:
            js = f"window.dispatchEvent(new CustomEvent('{event_name}', {{ detail: {json.dumps(payload)} }}));"
            try:
                self._window.evaluate_js(js)
            except Exception as e:
                logger.warning(f"Lỗi evaluate_js: {e}")

    # ========================================================
    # Data Fetching
    # ========================================================
    def get_initial_data(self) -> Dict[str, Any]:
        """Loads all initial data in a single rapid request (never throws to JS)"""
        try:
            accounts = self.get_accounts()
            channels = self.get_channels("ALL", "ALL", "")
            settings = self._settings_service.settings
            storage_mode = self._settings_service.get("database", "storage_mode", "LOCAL")
            auth_state = self._auth_service.get_auth_state()

            try:
                trash_count = len(self._trash_service().list_items())
            except Exception:
                trash_count = 0
            try:
                access_requests = self._account_service.list_access_requests(status="pending")
            except Exception:
                access_requests = []
            return {
                "accounts": accounts,
                "channels": channels,
                "platforms": self._branch_platforms(),
                "settings": settings,
                "storage_mode": storage_mode,
                "auth_state": auth_state,
                "trash_count": trash_count,
                "access_requests": access_requests
            }
        except Exception as e:
            logger.error(f"get_initial_data failed: {e}")
            return {"accounts": [], "channels": [], "settings": {}, "storage_mode": "LOCAL", "error": str(e)}

    def get_accounts(self) -> List[Dict[str, Any]]:
        accounts = self._account_service.get_accounts()
        out = []
        for a in accounts:
            try:
                created = a.created_at.isoformat() if getattr(a, "created_at", None) else None
            except Exception:
                created = None
            out.append({
                "id": a.id,
                "display_name": a.display_name,
                "email": a.email,
                "recovery_email": a.recovery_email,
                "notes": a.notes,
                "logo": getattr(a, "logo", None),
                "created_at": created
            })
        return out

    def _presence_payload(self) -> List[Dict[str, Any]]:
        try:
            return self._account_service.list_access_requests(status="pending")
        except Exception as e:
            logger.warning(f"list_access_requests failed: {e}")
            return []

    def get_channels(self, platform: str = "ALL", account_id: str = "ALL", search: str = "") -> List[Dict[str, Any]]:
        items = self._account_service.get_channel_items(
            platform=platform if platform != "ALL" else None,
            account_id=account_id if account_id != "ALL" else None,
            search=search if search else None
        )
        try:
            pending = self._account_service.list_access_requests(status="pending")
        except Exception:
            pending = []
        pend_by_ch: Dict[str, List[Dict[str, Any]]] = {}
        for r in pending:
            pend_by_ch.setdefault(r.get("channel_id"), []).append(r)
        results = []
        for it in items:
            ch = it.channel
            sess = it.session
            try:
                since = sess.in_use_since.isoformat() if sess and sess.in_use_since else None
            except Exception:
                since = None
            try:
                hb = sess.last_heartbeat.isoformat() if sess and getattr(sess, "last_heartbeat", None) else None
            except Exception:
                hb = None
            results.append({
                "id": ch.id,
                "account_id": ch.account_id,
                "platform": platform_value(ch.platform),
                "channel_name": ch.channel_name,
                "studio_url": ch.studio_url,
                "login_url": ch.login_url,
                "account_display_name": ch.account_display_name,
                "account_email": ch.account_email,
                "status": it.current_status.value,
                "locked_by": it.locked_by,
                "in_use_since": since,
                "last_heartbeat": hb,
                "pending_requests": pend_by_ch.get(ch.id, []),
                "pinned": bool(getattr(ch, "pinned", False)),
                "cookies_count": len(sess.cookies_data) if sess and sess.cookies_data else 0,
                "last_synced_at": sess.last_synced_at.strftime("%H:%M %d/%m") if sess and sess.last_synced_at else None
            })
        return results

    # ---------- Presence + Xin mở kênh (Đợt 1) ----------
    def heartbeat(self, channel_id: str, user_name: str) -> Dict[str, Any]:
        try:
            ok = self._account_service.heartbeat(channel_id, user_name)
            return {"success": bool(ok)}
        except Exception as e:
            logger.error(f"heartbeat {channel_id} failed: {e}")
            return {"success": False, "message": str(e)}

    def get_access_requests(self, status: str = "pending") -> List[Dict[str, Any]]:
        try:
            return self._account_service.list_access_requests(status=status or "pending")
        except Exception as e:
            logger.error(f"get_access_requests failed: {e}")
            return []

    def request_access(self, channel_id: str, requester: str, message: str = "") -> Dict[str, Any]:
        try:
            res = self._account_service.request_access(channel_id, requester, message or "")
            if res.get("success"):
                self.notify_frontend("access_request_changed", {
                    "channel_id": channel_id,
                    "requester": requester,
                    "holder": res.get("holder"),
                })
                try:
                    items = self._account_service.get_channel_items()
                    it = next((x for x in items if x.channel.id == channel_id), None)
                    if it and it.session:
                        self.notify_frontend("channel_status_changed", {
                            "channel_id": channel_id,
                            "status": it.current_status.value,
                            "locked_by": it.locked_by,
                        })
                except Exception:
                    pass
            return res
        except Exception as e:
            logger.error(f"request_access {channel_id} failed: {e}")
            return {"success": False, "message": str(e)}

    def resolve_access_request(self, request_id: str, approver: str, action: str) -> Dict[str, Any]:
        try:
            # Lấy channel_id trước khi resolve để push event sau
            ch_id = None
            try:
                for r in self._account_service.list_access_requests(status="pending"):
                    if r.get("id") == request_id:
                        ch_id = r.get("channel_id")
                        break
            except Exception:
                pass
            res = self._account_service.resolve_access_request(request_id, approver, action)
            if res.get("success"):
                self.notify_frontend("access_request_changed", {
                    "request_id": request_id, "action": action, "approver": approver,
                    "channel_id": ch_id,
                })
                if action == "approve" and ch_id:
                    self.notify_frontend("channel_status_changed", {
                        "channel_id": ch_id,
                        "status": ChannelStatus.READY.value,
                        "locked_by": None
                    })
            return res
        except Exception as e:
            logger.error(f"resolve_access_request {request_id} failed: {e}")
            return {"success": False, "message": str(e)}

    def toggle_pin(self, channel_id: str) -> Dict[str, Any]:
        """Ghim/bỏ ghim kênh yêu thích."""
        try:
            ch = self._account_service.repository.get_channel(channel_id)
            if not ch:
                return {"success": False, "message": "Không tìm thấy kênh."}
            ch.pinned = not bool(getattr(ch, "pinned", False))
            ch.pinned_at = datetime.now() if ch.pinned else None
            ok = self._account_service.repository.update_channel(ch)
            return {"success": ok, "pinned": ch.pinned}
        except Exception as e:
            logger.error(f"toggle_pin {channel_id} failed: {e}")
            return {"success": False, "message": str(e)}

    # ========================================================
    # Channel Actions (1-Click Launch, Unlock, Reset)
    # ========================================================
    def launch_channel(self, channel_id: str, user_name: str) -> Dict[str, Any]:
        """Launches Playwright Chromium session in a background thread (non-blocking, never throws to JS)"""
        def _on_status_change(ch_id, new_status, in_use_by):
            self.notify_frontend("channel_status_changed", {
                "channel_id": ch_id,
                "status": new_status.value,
                "locked_by": in_use_by
            })

        def _on_error(ch_id, error_msg):
            self.notify_frontend("channel_error", {
                "channel_id": ch_id,
                "error": error_msg
            })

        try:
            if not channel_id or not user_name:
                return {"success": False, "message": "Thiếu channel_id hoặc user_name."}
            def _on_autosaved(ch_id, cookies_count):
                self.notify_frontend("session_autosaved", {
                    "channel_id": ch_id,
                    "cookies_count": cookies_count
                })

            self._account_service.launch_channel(
                channel_id=channel_id,
                user_name=user_name,
                on_status_change=_on_status_change,
                on_error=_on_error,
                on_autosaved=_on_autosaved
            )
            return {"success": True, "message": f"Đang khởi động trình duyệt cho kênh {channel_id}..."}
        except Exception as e:
            logger.error(f"launch_channel {channel_id} failed: {e}")
            return {"success": False, "message": f"Lỗi khởi động trình duyệt: {e}"}

    def force_unlock(self, channel_id: str, reason: str = "", user_name: str = "") -> Dict[str, Any]:
        who = (user_name or "").strip()
        if reason:
            logger.warning(f"Force unlock kênh '{channel_id}' bởi '{who or '?'}' — lý do: {reason[:200]}")
        success = self._account_service.force_release_channel(channel_id)
        if success:
            self.notify_frontend("channel_status_changed", {
                "channel_id": channel_id,
                "status": ChannelStatus.READY.value,
                "locked_by": None
            })
            self.notify_frontend("access_request_changed", {
                "channel_id": channel_id, "action": "force_unlock", "approver": who,
            })
            self._push_channel_status(channel_id)
        return {"success": success}

    def release_my_sessions(self, user_name: str = "") -> Dict[str, Any]:
        """
        Đóng các trình duyệt và xả toàn bộ khóa phiên do người dùng hiện tại đang giam.
        """
        who = (user_name or self._current_user()).strip()
        released_ids = self._account_service.release_user_channels(who)
        logger.info(f"Người dùng '{who}' đã xả {len(released_ids)} phiên: {released_ids}")
        for ch_id in released_ids:
            self.notify_frontend("channel_status_changed", {
                "channel_id": ch_id,
                "status": ChannelStatus.READY.value,
                "locked_by": None
            })
            self._push_channel_status(ch_id)
        return {
            "success": True,
            "released_count": len(released_ids),
            "released_ids": released_ids
        }

    # Giãn cách giữa các lần mở hàng loạt: nền tảng đánh dấu hành vi đều đặn
    # như máy (mở dồn dập đúng chu kỳ) -> nghỉ ngẫu nhiên để giống người dùng.
    BULK_DELAY_BASE = 6.0
    BULK_DELAY_JITTER = 6.0

    def launch_account_channels(self, account_id: str, user_name: str) -> Dict[str, Any]:
        """Mở nối tiếp các kênh READY của 1 tài khoản (có thể dừng giữa chừng)."""
        if self._bulk_running:
            return {"success": False, "message": "Đang có 1 đợt mở hàng loạt chạy rồi."}
        try:
            items = self._account_service.get_channel_items(account_id=account_id)
        except Exception as e:
            return {"success": False, "message": str(e)}
        targets = [it.channel.id for it in items if it.current_status == ChannelStatus.READY]
        skipped = len(items) - len(targets)
        if not targets:
            return {"success": False, "message": "Không có kênh nào ở trạng thái Sẵn sàng."}
        self._bulk_stop.clear()
        self._bulk_running = True

        def _on_status_change(ch_id, new_status, in_use_by):
            self.notify_frontend("channel_status_changed", {
                "channel_id": ch_id,
                "status": new_status.value,
                "locked_by": in_use_by
            })

        def _on_error(ch_id, error_msg):
            self.notify_frontend("channel_error", {
                "channel_id": ch_id,
                "error": error_msg
            })

        def _worker():
            done, opened = 0, 0
            try:
                for ch_id in targets:
                    if self._bulk_stop.is_set():
                        break
                    self.notify_frontend("bulk_progress", {
                        "account_id": account_id,
                        "done": done, "total": len(targets),
                        "current_id": ch_id, "stopped": False, "finished": False
                    })
                    try:
                        self._account_service.launch_channel(
                            channel_id=ch_id, user_name=user_name,
                            on_status_change=_on_status_change, on_error=_on_error,
                            on_autosaved=lambda cid, n: self.notify_frontend(
                                "session_autosaved", {"channel_id": cid, "cookies_count": n})
                        )
                        opened += 1
                    except Exception as e:
                        logger.error(f"Bulk open {ch_id} failed: {e}")
                    done += 1
                    # Nghỉ ngẫu nhiên giữa các kênh (giống người dùng, tránh bị
                    # đánh dấu hành vi tự động). Chia nhỏ để nút Dừng phản hồi nhanh.
                    import random as _random
                    pause = self.BULK_DELAY_BASE + _random.uniform(0, self.BULK_DELAY_JITTER)
                    steps = max(1, int(pause / 0.1))
                    for _ in range(steps):
                        if self._bulk_stop.is_set():
                            break
                        self._bulk_stop.wait(0.1)
                self.notify_frontend("bulk_progress", {
                    "account_id": account_id,
                    "done": done, "total": len(targets),
                    "current_id": None,
                    "stopped": self._bulk_stop.is_set(), "finished": True,
                    "opened": opened, "skipped": skipped
                })
            finally:
                self._bulk_running = False

        threading.Thread(target=_worker, name=f"BulkOpen-{account_id}", daemon=True).start()
        return {"success": True, "total": len(targets), "skipped": skipped}

    def stop_bulk_launch(self) -> Dict[str, Any]:
        """Dừng đợt mở hàng loạt đang chạy (nếu có)."""
        self._bulk_stop.set()
        return {"success": True, "was_running": self._bulk_running}

    # ========================================================
    # Health Checker (soi cookies offline — không browser, không mạng, không nguy cơ khóa acc)
    # ========================================================
    def _health_service(self):
        from src.services.health_service import HealthService
        return HealthService(
            repository=self._account_service.repository,
            session_service=self._account_service.session_service
        )

    @staticmethod
    def _health_status_of(res: Dict[str, Any]) -> tuple:
        """Chuẩn hóa kết quả check thành (status, detail)."""
        if res.get("skipped"):
            return "skipped", res.get("message", "bỏ qua")
        if res.get("success"):
            return res.get("status") or "empty", res.get("message", "")
        return "error", res.get("message", "lỗi kiểm tra")

    def _record_health_result(self, run_id: str, channel_id: str, res: Dict[str, Any]) -> str:
        st, detail = self._health_status_of(res)
        # detail kỹ thuật nằm trong health verdict của kênh; report giữ message gọn
        try:
            sess = self._account_service.session_service.repository.get_session(channel_id)
            tech = (sess.health or {}).get("detail") if sess and sess.health else ""
            if tech:
                detail = f"{detail} ({tech})" if detail else tech
        except Exception:
            pass
        try:
            self._account_service.repository.append_health_result(run_id, channel_id, st, detail)
        except Exception as e:
            logger.error(f"append_health_result {channel_id} failed: {e}")
        return st

    def _push_channel_status(self, channel_id: str):
        try:
            items = self._account_service.get_channel_items()
            it = next((x for x in items if x.channel.id == channel_id), None)
            if it:
                self.notify_frontend("channel_status_changed", {
                    "channel_id": channel_id,
                    "status": it.current_status.value,
                    "locked_by": it.locked_by
                })
        except Exception as e:
            logger.error(f"health notify {channel_id} failed: {e}")

    def check_channel(self, channel_id: str, user_name: str = "") -> Dict[str, Any]:
        """Kiểm tra 1 kênh (ghi report run riêng), chạy thread riêng."""
        svc = self._health_service()
        try:
            run_id = self._account_service.repository.create_health_run(
                triggered_by=user_name or "", total=1, scope=channel_id)
        except Exception as e:
            logger.error(f"create_health_run failed: {e}")
            return {"success": False, "message": str(e)}

        def _worker():
            try:
                res = svc.check_channel(channel_id)
                self._record_health_result(run_id, channel_id, res)
                self._push_channel_status(channel_id)
                if not res.get("success") and not res.get("skipped"):
                    self.notify_frontend("channel_error", {
                        "channel_id": channel_id,
                        "error": res.get("message", "Lỗi kiểm tra.")
                    })
            except Exception as e:
                logger.error(f"check_channel worker {channel_id} failed: {e}")
                try:
                    self._account_service.repository.append_health_result(run_id, channel_id, "error", str(e))
                except Exception:
                    pass
            finally:
                try:
                    self._account_service.repository.finish_health_run(run_id, "finished")
                except Exception:
                    pass
                self.notify_frontend("health_run_finished", {"run_id": run_id, "scope": channel_id})

        threading.Thread(target=_worker, name=f"Health-{channel_id}", daemon=True).start()
        return {"success": True, "run_id": run_id, "message": f"Đang kiểm tra kênh {channel_id}..."}

    def check_all_channels(self, user_name: str = "") -> Dict[str, Any]:
        """Kiểm tra nối tiếp các kênh có cookies (bỏ qua đang mở), ghi report, có thể dừng."""
        if getattr(self, "_health_running", False):
            return {"success": False, "message": "Đang có 1 đợt kiểm tra chạy rồi."}
        try:
            items = self._account_service.get_channel_items()
        except Exception as e:
            return {"success": False, "message": str(e)}
        targets = [it.channel.id for it in items
                   if (it.session and it.session.cookies_data) and not it.locked_by]
        if not targets:
            return {"success": False, "message": "Không có kênh nào có cookies để kiểm tra."}
        try:
            run_id = self._account_service.repository.create_health_run(
                triggered_by=user_name or "", total=len(targets), scope="ALL")
        except Exception as e:
            return {"success": False, "message": str(e)}
        self._health_stop = threading.Event()
        self._health_running = True
        svc = self._health_service()
        stat = {"alive": 0, "dead": 0, "error": 0, "skipped": 0, "empty": 0}

        def _worker():
            done = 0
            try:
                for ch_id in targets:
                    if self._health_stop.is_set():
                        break
                    self.notify_frontend("health_run_progress", {
                        "run_id": run_id,
                        "done": done, "total": len(targets),
                        "current_id": ch_id, "stopped": False, "finished": False,
                        **stat
                    })
                    try:
                        res = svc.check_channel(ch_id)
                        st = self._record_health_result(run_id, ch_id, res)
                        if st in stat:
                            stat[st] += 1
                        self._push_channel_status(ch_id)
                    except Exception as e:
                        stat["error"] += 1
                        logger.error(f"check_all {ch_id} failed: {e}")
                    done += 1
                stopped = self._health_stop.is_set()
                try:
                    self._account_service.repository.finish_health_run(
                        run_id, "stopped" if stopped else "finished")
                except Exception as e:
                    logger.error(f"finish_health_run failed: {e}")
                self.notify_frontend("health_run_progress", {
                    "run_id": run_id,
                    "done": done, "total": len(targets),
                    "current_id": None,
                    "stopped": stopped, "finished": True,
                    **stat
                })
                self.notify_frontend("health_run_finished", {"run_id": run_id, "scope": "ALL"})
            finally:
                self._health_running = False

        threading.Thread(target=_worker, name="HealthAll", daemon=True).start()
        return {"success": True, "run_id": run_id, "total": len(targets)}

    def stop_health_check(self) -> Dict[str, Any]:
        """Dừng đợt kiểm tra đang chạy (nếu có)."""
        if hasattr(self, "_health_stop"):
            self._health_stop.set()
        return {"success": True, "was_running": getattr(self, "_health_running", False)}

    def get_health_runs(self, limit: int = 30) -> List[Dict[str, Any]]:
        try:
            return self._account_service.repository.list_health_runs(limit=int(limit or 30))
        except Exception as e:
            logger.error(f"get_health_runs failed: {e}")
            return []

    def get_health_run(self, run_id: str) -> Dict[str, Any]:
        try:
            return self._account_service.repository.get_health_run(run_id) or {}
        except Exception as e:
            logger.error(f"get_health_run failed: {e}")
            return {}

    def reset_channel_session(self, channel_id: str) -> Dict[str, Any]:
        success = self._account_service.reset_channel_session(channel_id)
        if success:
            self.notify_frontend("channel_status_changed", {
                "channel_id": channel_id,
                "status": ChannelStatus.NOT_SETUP.value,
                "locked_by": None
            })
        return {"success": success}

    # ========================================================
    # CRUD Operations
    # ========================================================
    def update_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        acc = Account(
            id=data.get("id"),
            display_name=data.get("display_name"),
            email=data.get("email"),
            recovery_email=data.get("recovery_email"),
            notes=data.get("notes"),
            logo=data.get("logo")
        )
        success = self._account_service.update_account(acc)
        return {"success": success}

    def create_account(self, data: Dict[str, Any], auto_channels: Any = True) -> Dict[str, Any]:
        acc = Account(
            id=data.get("id"),
            display_name=data.get("display_name"),
            email=data.get("email"),
            recovery_email=data.get("recovery_email"),
            notes=data.get("notes"),
            logo=data.get("logo")
        )
        if not self._account_service.create_account(acc):
            return {"success": False, "message": "Tài khoản đã tồn tại hoặc dữ liệu không hợp lệ!"}

        # auto_channels tương thích ngược: True = tất cả socials, False/None/rỗng = không tạo,
        # list mã nền tảng (VD ["YOUTUBE_SHORTS", "TIKTOK"]) = chỉ tạo các kênh được chọn
        branch = self._branch_platforms()
        if auto_channels is True:
            wanted = [p["code"] for p in branch]
        elif isinstance(auto_channels, (list, tuple)):
            wanted = [str(p) for p in auto_channels]
        else:
            wanted = []

        created = 0
        if wanted:
            acc_num = acc.id.replace("acc_", "")
            for p in branch:
                if p["code"] not in wanted:
                    continue
                ch_id = self._next_channel_id(acc.id, acc_num, p["prefix"])
                ch = Channel(
                    id=ch_id,
                    account_id=acc.id,
                    platform=parse_platform(p["code"]),
                    channel_name=f"{p.get('tag') or p.get('name')} #{acc_num} ({acc.notes or acc.display_name})",
                    studio_url=p.get("studio_url", ""),
                    login_url=p.get("login_url", "") or p.get("studio_url", "")
                )
                if self._account_service.create_channel(ch):
                    created += 1

        if created:
            msg = f"Đã tạo tài khoản {acc.display_name} + {created} kênh phân nhánh!"
        else:
            msg = f"Đã tạo tài khoản {acc.display_name} (chưa tạo kênh nào)!"
        return {"success": True, "message": msg, "created_channels": created}

    def _next_channel_id(self, account_id: str, acc_num: str, prefix: str) -> str:
        """Sinh ID kênh duy nhất: ch_{num}_{prefix}, trùng thì thêm hậu tố số."""
        base = f"ch_{acc_num}_{prefix or 'ch'}"
        candidate = base
        i = 2
        try:
            # repository.get_channels trả về ChannelItemView -> lấy id qua .channel
            existing = {it.channel.id for it in self._account_service.get_channel_items()}
        except Exception as e:
            logger.warning(f"_next_channel_id fallback: {e}")
            existing = set()
        while candidate in existing:
            candidate = f"{base}_{i}"
            i += 1
        return candidate

    def add_account_channel(self, account_id: str, platform_code: str) -> Dict[str, Any]:
        """Thêm 1 kênh lẻ cho tài khoản theo social (tự gắn logo/URL mặc định từ registry)."""
        plats = {p["code"]: p for p in self._branch_platforms()}
        p = plats.get(str(platform_code).upper())
        if not p:
            return {"success": False, "message": f"Không tìm thấy social '{platform_code}'."}
        accounts = {a.id: a for a in self._account_service.get_accounts()}
        acc = accounts.get(account_id)
        if not acc:
            return {"success": False, "message": "Không tìm thấy tài khoản."}
        acc_num = acc.id.replace("acc_", "")
        ch_id = self._next_channel_id(acc.id, acc_num, p.get("prefix", "ch"))
        ch = Channel(
            id=ch_id,
            account_id=acc.id,
            platform=parse_platform(p["code"]),
            channel_name=f"{p.get('tag') or p.get('name')} #{acc_num}",
            studio_url=p.get("studio_url", ""),
            login_url=p.get("login_url", "") or p.get("studio_url", "")
        )
        if self._account_service.create_channel(ch):
            return {"success": True, "message": f"Đã thêm kênh {ch.channel_name}!", "channel_id": ch_id}
        return {"success": False, "message": "ID kênh bị trùng, thử lại."}

    def update_channel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ch = Channel(
            id=data.get("id"),
            account_id=data.get("account_id"),
            platform=parse_platform(data.get("platform")),
            channel_name=data.get("channel_name"),
            studio_url=data.get("studio_url"),
            login_url=data.get("login_url")
        )
        success = self._account_service.update_channel(ch)
        return {"success": success}

    def delete_channel(self, channel_id: str) -> Dict[str, Any]:
        """Xóa kênh vào thùng rác (khôi phục được trong 30 ngày)."""
        try:
            res = self._trash_service().trash_channel(
                channel_id, deleted_by=self._settings_service.get("general", "default_user", ""))
            if res.get("success"):
                return {"success": True, "message": "Đã chuyển kênh vào thùng rác (khôi phục trong 30 ngày)."}
            return {"success": False, "message": res.get("message", "Không xóa được kênh.")}
        except Exception as e:
            logger.error(f"delete_channel {channel_id} failed: {e}")
            return {"success": False, "message": str(e)}

    def delete_account(self, account_id: str) -> Dict[str, Any]:
        """Xóa tài khoản (kèm các kênh) vào thùng rác."""
        try:
            res = self._trash_service().trash_account(
                account_id, deleted_by=self._settings_service.get("general", "default_user", ""))
            if res.get("success"):
                return {"success": True, "message": "Đã chuyển tài khoản vào thùng rác (khôi phục trong 30 ngày)."}
            return {"success": False, "message": res.get("message", "Không xóa được tài khoản.")}
        except Exception as e:
            logger.error(f"delete_account {account_id} failed: {e}")
            return {"success": False, "message": str(e)}

    # ========================================================
    # Trash (thùng rác 30 ngày)
    # ========================================================
    def _trash_service(self):
        from src.services.trash_service import TrashService
        if not hasattr(self, "_trash"):
            self._trash = TrashService(repository=self._account_service.repository)
        else:
            # repository có thể đã đổi (LOCAL<->POSTGRES) sau save_settings
            self._trash.repository = self._account_service.repository
        return self._trash

    def get_trash(self) -> List[Dict[str, Any]]:
        try:
            return self._trash_service().list_items()
        except Exception as e:
            logger.error(f"get_trash failed: {e}")
            return []

    def restore_trash(self, kind: str, item_id: str) -> Dict[str, Any]:
        try:
            return self._trash_service().restore(kind, item_id)
        except Exception as e:
            logger.error(f"restore_trash failed: {e}")
            return {"success": False, "message": str(e)}

    def delete_trash_forever(self, kind: str, item_id: str) -> Dict[str, Any]:
        try:
            return self._trash_service().delete_forever(kind, item_id)
        except Exception as e:
            logger.error(f"delete_trash_forever failed: {e}")
            return {"success": False, "message": str(e)}

    def purge_trash(self) -> Dict[str, Any]:
        try:
            n = self._trash_service().purge_expired()
            return {"success": True, "purged": n}
        except Exception as e:
            logger.error(f"purge_trash failed: {e}")
            return {"success": False, "message": str(e)}

    # ========================================================
    # Platform Registry (quản lý socials)
    # ========================================================
    def get_platforms(self) -> List[Dict[str, Any]]:
        return self._branch_platforms()

    def create_platform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._platform_service.create(data or {})

    def update_platform(self, code: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._platform_service.update(code, data or {})

    def delete_platform(self, code: str) -> Dict[str, Any]:
        try:
            count = sum(1 for it in self._account_service.get_channel_items()
                        if platform_value(it.channel.platform) == str(code).upper())
        except Exception:
            count = 0
        return self._platform_service.delete(code, channel_count=count)

    def reset_platforms(self) -> Dict[str, Any]:
        return self._platform_service.reset_defaults()

    # ========================================================
    # Cookie Vault (quản lý + mã hóa cookies)
    # ========================================================
    def get_cookie_vault_status(self) -> List[Dict[str, Any]]:
        try:
            return self._account_service.repository.get_cookie_vault_status()
        except Exception as e:
            logger.error(f"get_cookie_vault_status failed: {e}")
            return []

    def encrypt_all_cookies(self) -> Dict[str, Any]:
        try:
            result = self._account_service.repository.migrate_plaintext_cookies()
            return {"success": True, **result}
        except Exception as e:
            logger.error(f"encrypt_all_cookies failed: {e}")
            return {"success": False, "message": str(e)}

    def clear_channel_cookies(self, channel_id: str) -> Dict[str, Any]:
        try:
            ok = self._account_service.reset_channel_session(channel_id)
            if ok:
                self.notify_frontend("channel_status_changed", {
                    "channel_id": channel_id,
                    "status": ChannelStatus.NOT_SETUP.value,
                    "locked_by": None
                })
            return {"success": ok}
        except Exception as e:
            logger.error(f"clear_channel_cookies failed: {e}")
            return {"success": False, "message": str(e)}

    # ========================================================
    # Settings & Database
    # ========================================================
    def get_settings(self) -> Dict[str, Any]:
        return self._settings_service.settings

    def save_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        # Deep-merge từng section để patch 1 key không xóa các key khác
        # (VD {general:{enable_sound}} không được làm mất default_user).
        for section, values in (new_settings or {}).items():
            if isinstance(values, dict) and isinstance(self._settings_service.settings.get(section), dict):
                self._settings_service.settings[section].update(values)
            else:
                self._settings_service.settings[section] = values
        self._settings_service.save_settings()

        # Check repository re-init
        mode = self._settings_service.get("database", "storage_mode", "LOCAL")
        if mode == "POSTGRES":
            pg = PostgresRepository(
                host=self._settings_service.get("database", "host"),
                port=self._settings_service.get("database", "port"),
                dbname=self._settings_service.get("database", "dbname"),
                user=self._settings_service.get("database", "user"),
                password=self._settings_service.get("database", "password"),
                sslmode=self._settings_service.get("database", "sslmode", "prefer")
            )
            if pg.is_connected():
                self._account_service.repository = pg
                self._account_service.session_service.repository = pg
                logger.info("Đã chuyển sang PostgreSQL VPS!")
            else:
                logger.warning("Không thể kết nối VPS! Giữ Local.")
        else:
            local_repo = LocalJsonRepository()
            self._account_service.repository = local_repo
            self._account_service.session_service.repository = local_repo

        return {"success": True}

    def test_db_connection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ok, msg = self._settings_service.test_postgres_connection(
            host=data.get("host"),
            port=data.get("port", 5432),
            dbname=data.get("dbname"),
            user=data.get("user"),
            password=data.get("password"),
            sslmode=data.get("sslmode", "prefer")
        )
        return {"success": ok, "message": msg}

    def test_firebase_connection(self, firebase_url: Optional[str] = None) -> Dict[str, Any]:
        ok, msg = self._settings_service.test_firebase_connection(firebase_url)
        return {"success": ok, "message": msg}

    # ========================================================
    # OS Notify (âm thanh hệ thống + flash taskbar + ghim topmost)
    # ========================================================
    def notify_os(self, title: str = "", message: str = "", kind: str = "info", flash: bool = True) -> Dict[str, Any]:
        """Beep hệ thống + nhấp nháy taskbar (dùng khi cửa sổ minimize/inactive)."""
        try:
            from src.services.notify_service import notify_os as _notify
            return _notify(title or "VB-Studio", message or "", kind or "info", bool(flash))
        except Exception as e:
            logger.error(f"notify_os failed: {e}")
            return {"success": False, "message": str(e)}

    def flash_taskbar(self, count: int = 3) -> Dict[str, Any]:
        try:
            from src.services.notify_service import flash_taskbar as _flash
            return {"success": bool(_flash(int(count or 3)))}
        except Exception as e:
            logger.error(f"flash_taskbar failed: {e}")
            return {"success": False, "message": str(e)}

    def set_always_on_top(self, enabled: bool) -> Dict[str, Any]:
        """Ghim/bỏ ghim cửa sổ app lên trên cùng. Không cần quyền overlay."""
        try:
            from src.services.notify_service import set_always_on_top as _top
            ok = _top(bool(enabled))
            return {"success": ok, "enabled": bool(enabled) if ok else False}
        except Exception as e:
            logger.error(f"set_always_on_top failed: {e}")
            return {"success": False, "message": str(e)}

    # ========================================================
    # Popup overlay: cửa sổ nhỏ NỔI TRÊN MỌI APP khi có yêu cầu
    # xin mở kênh gửi tới mình (duyệt ngay không cần mở app chính)
    # ========================================================
    def _current_user(self) -> str:
        try:
            auth = self._auth_service.get_auth_state().get("user") or {}
            if auth.get("displayName"):
                return auth["displayName"]
        except Exception:
            pass
        return self._settings_service.get("general", "default_user", "") or ""

    def _render_popup_html(self, req: Dict[str, Any]) -> str:
        from src.core.config import Config
        tpl_path = Config.BASE_DIR / "src" / "web" / "popup.html"
        try:
            tpl = tpl_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"popup template missing: {e}")
            tpl = "<html><body><script>var REQ = __VB_REQ_JSON__;</script></body></html>"
        safe = {
            "id": req.get("id", ""),
            "channel_id": req.get("channel_id", ""),
            "channel_name": req.get("channel_name") or req.get("channel_id", ""),
            "requester": req.get("requester", ""),
            "message": (req.get("message") or "")[:200],
        }
        return tpl.replace("__VB_REQ_JSON__", json.dumps(safe, ensure_ascii=False))

    def show_request_popup(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Mở popup overlay topmost cho 1 yêu cầu xin mở. Gọi từ máy của người giữ kênh."""
        req_id = (req or {}).get("id", "")
        if not req_id:
            return {"success": False, "message": "Thiếu request id."}
        existing = self._popups.get(req_id)
        try:
            if existing:
                existing[0].show()
                existing[0].restore()
                return {"success": True, "reused": True}
        except Exception:
            self._popups.pop(req_id, None)
        title = f"VB-Studio \u2022 Xin mở kênh ({(req.get('channel_name') or req.get('channel_id', ''))[:30]})"
        try:
            html = self._render_popup_html(req)
            win = webview.create_window(
                title=title,
                html=html,
                js_api=self,
                width=400, height=330,
                resizable=False,
                on_top=True,
            )
            self._popups[req_id] = (win, req.get("channel_id", ""))
            # Đai an toàn: ép topmost qua Win32 nếu backend webview chưa áp on_top
            try:
                from src.services.notify_service import set_topmost_by_title
                set_topmost_by_title(title, True)
            except Exception:
                pass
            from src.services.notify_service import beep_os
            beep_os("request")
            logger.info(f"Popup overlay yêu cầu '{req_id}' đã mở nổi trên mọi app.")
            return {"success": True, "reused": False}
        except Exception as e:
            logger.error(f"show_request_popup failed: {e}")
            try:
                from src.services.notify_service import notify_os as _notify
                _notify("VB-Studio", f"{req.get('requester')} xin mở {req.get('channel_id')}", "request", True)
            except Exception:
                pass
            return {"success": False, "message": f"Không mở được popup: {e}"}

    def _destroy_popup(self, req_id: str):
        item = self._popups.pop(req_id, None)
        if not item:
            return
        try:
            item[0].destroy()
        except Exception as e:
            logger.warning(f"destroy popup {req_id} failed: {e}")

    def popup_dismiss(self, request_id: str) -> Dict[str, Any]:
        """Đóng popup (để sau) — yêu cầu vẫn pending trong chuông."""
        self._destroy_popup(request_id or "")
        return {"success": True}

    def close_request_popup(self, request_id: str) -> Dict[str, Any]:
        self._destroy_popup(request_id or "")
        return {"success": True}

    def close_channel_popups(self, channel_id: str) -> Dict[str, Any]:
        """Đóng mọi popup thuộc 1 kênh (sau khi duyệt/từ chối/force unlock)."""
        for req_id, item in [kv for kv in list(self._popups.items())]:
            try:
                if not channel_id or item[1] == channel_id:
                    self._destroy_popup(req_id)
            except Exception:
                pass
        return {"success": True}

    def popup_focus_main(self) -> Dict[str, Any]:
        """Đưa cửa sổ app chính lên trước."""
        try:
            if self._window:
                self._window.show()
                self._window.restore()
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def popup_resolve(self, request_id: str, action: str) -> Dict[str, Any]:
        """Duyệt/từ chối ngay từ popup overlay."""
        me = self._current_user()
        try:
            res = self._account_service.resolve_access_request(request_id, me, action)
        except Exception as e:
            logger.error(f"popup_resolve failed: {e}")
            return {"success": False, "message": str(e)}
        self._destroy_popup(request_id)
        if res.get("success"):
            ch_id = None
            try:
                for r in self._account_service.list_access_requests(status="ALL"):
                    if r.get("id") == request_id:
                        ch_id = r.get("channel_id")
                        break
            except Exception:
                pass
            if ch_id:
                self.close_channel_popups(ch_id)
                if action == "approve":
                    self.notify_frontend("channel_status_changed", {
                        "channel_id": ch_id,
                        "status": ChannelStatus.READY.value,
                        "locked_by": None
                    })
            self.notify_frontend("access_request_changed", {
                "request_id": request_id, "action": action, "approver": me,
                "channel_id": ch_id,
            })
        return res

    def check_for_updates(self) -> Dict[str, Any]:
        """Checks for software updates from GitHub Releases"""
        return self._update_service.check_for_updates()

    def open_release_page(self, url: Optional[str] = None) -> bool:
        """Opens GitHub Release page in browser"""
        return self._update_service.open_release_page(url)

    def download_and_apply_update(self, download_url: str) -> Dict[str, Any]:
        """Downloads updated exe and applies it"""
        def on_progress(pct: int):
            self.notify_frontend("update_download_progress", {"percent": pct})
        return self._update_service.download_and_apply_update(download_url, progress_callback=on_progress)


    def browse_folder(self) -> Optional[str]:
        """Opens native Windows folder selection dialog"""
        if self._window:
            result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if result and len(result) > 0:
                return result[0]
        return None

    # ========================================================
    # Backup (xuất/nhập zip, người dùng chọn path)
    # ========================================================
    def _backup_service(self):
        from src.services.backup_service import BackupService
        return BackupService()

    def pick_save_backup_path(self) -> Optional[str]:
        """Hộp thoại chọn nơi lưu file backup."""
        if not self._window:
            return None
        from src.services.backup_service import _default_filename
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=_default_filename())
            if result:
                return result if isinstance(result, str) else result[0]
        except Exception as e:
            logger.error(f"pick_save_backup_path failed: {e}")
        return None

    def pick_backup_file(self) -> Optional[str]:
        """Hộp thoại chọn file backup để nhập."""
        if not self._window:
            return None
        try:
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=("Zip files (*.zip)",))
            if result:
                return result if isinstance(result, str) else result[0]
        except Exception:
            try:  # fallback không lọc loại file (bản webview cũ)
                result = self._window.create_file_dialog(webview.OPEN_DIALOG)
                if result:
                    return result if isinstance(result, str) else result[0]
            except Exception as e:
                logger.error(f"pick_backup_file failed: {e}")
        return None

    def export_backup(self, save_path: str, include_profiles: bool = False,
                      password: str = "") -> Dict[str, Any]:
        """Xuất backup ra path người dùng đã chọn."""
        if not save_path:
            return {"success": False, "message": "Chưa chọn nơi lưu backup."}
        try:
            return self._backup_service().export_backup(
                save_path, include_profiles=bool(include_profiles),
                password=password or "")
        except Exception as e:
            logger.error(f"export_backup failed: {e}")
            return {"success": False, "message": str(e)}

    def import_backup(self, zip_path: str, password: str = "") -> Dict[str, Any]:
        """Nhập backup từ file zip (có safety copy + reload settings)."""
        if not zip_path:
            return {"success": False, "message": "Chưa chọn file backup."}
        try:
            res = self._backup_service().import_backup(zip_path, password or "")
            if res.get("success"):
                # Nạp lại settings từ file vừa khôi phục
                try:
                    self._settings_service.load_settings()
                except Exception as e:
                    logger.warning(f"Reload settings sau restore lỗi: {e}")
            return res
        except Exception as e:
            logger.error(f"import_backup failed: {e}")
            return {"success": False, "message": str(e)}

    # ========================================================
    # Firebase Google Authentication Bridge Methods
    # ========================================================
    def get_firebase_auth_state(self) -> Dict[str, Any]:
        """Lấy trạng thái tài khoản Google đang đăng nhập và cấu hình Firebase"""
        return self._auth_service.get_auth_state()

    def start_google_auth(self) -> Dict[str, Any]:
        """Mở luồng đăng nhập Google qua loopback server"""
        return self._auth_service.start_auth_flow()

    def logout_google_auth(self) -> Dict[str, Any]:
        """Đăng xuất tài khoản Google hiện tại"""
        self._settings_service.clear_auth_user()
        self.notify_frontend("auth_state_changed", None)
        return {"success": True}

    def save_firebase_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Lưu cấu hình Firebase Web SDK và Realtime Database"""
        ok = self._settings_service.save_firebase_config(config_data)
        return {"success": ok}

    def save_firebase_auth_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Lưu thông tin tài khoản đã xác thực từ webview"""
        ok = self._settings_service.save_auth_user(user_data)
        if ok and user_data.get("displayName"):
            self._settings_service.settings.setdefault("general", {})["default_user"] = user_data["displayName"]
            self._settings_service.save_settings()
        self._on_auth_success(user_data)
        return {"success": ok}

