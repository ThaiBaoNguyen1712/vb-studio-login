import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from src.core.config import Config
from src.core.constants import Platform, ChannelStatus, PLATFORM_META, parse_platform, platform_value
from src.core.logger import logger
from src.core import secure_store
from src.domain.models import Account, Channel, SessionCookie, ChannelItemView
from src.repositories.base import BaseRepository


def _decode_cookies(raw, channel_id: str = "") -> List[Dict[str, Any]]:
    """Giải mã cookies: hỗ trợ cả legacy plaintext (list) và vault string."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw  # legacy plaintext — sẽ được mã hóa ở lần save/migrate
    if isinstance(raw, str) and secure_store.is_protected(raw):
        try:
            data = secure_store.unprotect_json(raw)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Không giải mã được cookies kênh '{channel_id}': {e}")
            return []
    logger.warning(f"Cookies kênh '{channel_id}' ở định dạng lạ, bỏ qua.")
    return []

class LocalJsonRepository(BaseRepository):
    """
    Local JSON file repository implementation for offline/development use.
    Provides identical semantics to PostgreSQL on VPS.
    """

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or Config.LOCAL_DB_FILE
        self._lock = threading.Lock()
        self._init_storage()

    def is_connected(self) -> bool:
        return True

    def _init_storage(self):
        Config.ensure_directories()
        if not self.file_path.exists():
            logger.info("Khởi tạo cơ sở dữ liệu cục bộ rỗng (data/local_db.json)...")
            initial_data = {"accounts": [], "channels": [], "sessions": {}, "access_requests": []}
            self._save_raw_data(initial_data)

    def _ensure_request_store(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        reqs = data.setdefault("access_requests", [])
        return reqs if isinstance(reqs, list) else data.__setitem__("access_requests", []) or data["access_requests"]

    def _generate_default_seed_data(self) -> Dict[str, Any]:
        topics = [
            ("Tech & AI", "Công nghệ và Trí tuệ nhân tạo"),
            ("Đời sống & Du lịch", "Vlog du lịch và trải nghiệm"),
            ("Ẩm thực & Mukbang", "Review quán ăn và nấu nướng"),
            ("Thể thao & Fitness", "Tập gym và sức khỏe"),
            ("Review Phim & Giải trí", "Tóm tắt phim và tin tức showbiz"),
            ("Gaming & Esports", "Highlights game và bình luận"),
            ("Tài chính & Đầu tư", "Quản lý tài chính cá nhân"),
            ("Tin tức & Sự kiện", "Tin tức nhanh 60s"),
            ("Giáo dục & Ngoại ngữ", "Tiếng Anh giao tiếp ngắn"),
            ("Âm nhạc & Podcast", "Giai điệu thư giãn và podcast")
        ]

        accounts = []
        channels = []
        sessions = {}

        for i, (title, note) in enumerate(topics, start=1):
            acc_num = f"{i:02d}"
            acc_id = f"acc_{acc_num}"
            accounts.append({
                "id": acc_id,
                "display_name": f"Google Acc #{acc_num}",
                "email": f"team.vb.account{acc_num}@gmail.com",
                "recovery_email": f"recovery.acc{acc_num}@gmail.com",
                "notes": note,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            })

            # 4 platform channels for each account
            for plat in [Platform.YOUTUBE_SHORTS, Platform.TIKTOK, Platform.FACEBOOK_REELS, Platform.INSTAGRAM_REELS]:
                meta = PLATFORM_META[plat]
                plat_prefix = {
                    Platform.YOUTUBE_SHORTS: "yt",
                    Platform.TIKTOK: "tt",
                    Platform.FACEBOOK_REELS: "fb",
                    Platform.INSTAGRAM_REELS: "ig"
                }[plat]
                ch_id = f"ch_{acc_num}_{plat_prefix}"
                channels.append({
                    "id": ch_id,
                    "account_id": acc_id,
                    "platform": plat.value,
                    "channel_name": f"{meta['tag']} #{acc_num} ({title})",
                    "studio_url": meta["studio_url"],
                    "login_url": meta["login_url"],
                    "avatar_url": None,
                    "status": ChannelStatus.NOT_SETUP.value,
                    "account_display_name": f"Google Acc #{acc_num}",
                    "account_email": f"team.vb.account{acc_num}@gmail.com"
                })
                sessions[ch_id] = {
                    "channel_id": ch_id,
                    "cookies_data": [],
                    "in_use_by": None,
                    "in_use_since": None,
                    "last_synced_at": None,
                    "updated_by": None
                }

        return {
            "accounts": accounts,
            "channels": channels,
            "sessions": sessions
        }

    def _read_raw_data(self) -> Dict[str, Any]:
        with self._lock:
            try:
                with open(self.file_path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Lỗi đọc file local db: {e}")
                return {"accounts": [], "channels": [], "sessions": {}}

    def _save_raw_data(self, data: Dict[str, Any]):
        with self._lock:
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Lỗi ghi file local db: {e}")

    def get_accounts(self) -> List[Account]:
        data = self._read_raw_data()
        accounts = []
        for a in data.get("accounts", []):
            try:
                created = datetime.fromisoformat(a["created_at"]) if a.get("created_at") else None
            except Exception:
                created = None
            try:
                updated = datetime.fromisoformat(a["updated_at"]) if a.get("updated_at") else None
            except Exception:
                updated = None
            accounts.append(Account(
                id=a["id"],
                display_name=a["display_name"],
                email=a["email"],
                recovery_email=a.get("recovery_email"),
                notes=a.get("notes"),
                logo=a.get("logo"),
                created_at=created,
                updated_at=updated
            ))
        return accounts

    def get_channels(
        self,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[ChannelItemView]:
        data = self._read_raw_data()
        accounts_map = {a["id"]: a for a in data.get("accounts", [])}
        sessions_map = data.get("sessions", {})
        results: List[ChannelItemView] = []

        for ch_data in data.get("channels", []):
            if platform and platform != "ALL" and ch_data.get("platform") != platform:
                continue
            if account_id and account_id != "ALL" and ch_data.get("account_id") != account_id:
                continue

            acc_info = accounts_map.get(ch_data.get("account_id"), {})
            acc_name = acc_info.get("display_name", "")
            acc_email = acc_info.get("email", "")

            if search:
                kw = search.lower().strip()
                match = (
                    kw in ch_data.get("channel_name", "").lower()
                    or kw in acc_name.lower()
                    or kw in acc_email.lower()
                    or kw in ch_data.get("id", "").lower()
                )
                if not match:
                    continue

            try:
                pinned_at = datetime.fromisoformat(ch_data["pinned_at"]) if ch_data.get("pinned_at") else None
            except Exception:
                pinned_at = None
            channel = Channel(
                id=ch_data["id"],
                account_id=ch_data["account_id"],
                platform=parse_platform(ch_data["platform"]),
                channel_name=ch_data["channel_name"],
                studio_url=ch_data["studio_url"],
                login_url=ch_data["login_url"],
                avatar_url=ch_data.get("avatar_url"),
                status=ChannelStatus(ch_data.get("status", ChannelStatus.NOT_SETUP.value)),
                account_display_name=acc_name,
                account_email=acc_email,
                pinned=bool(ch_data.get("pinned", False)),
                pinned_at=pinned_at
            )

            sess_raw = sessions_map.get(ch_data["id"])
            session = None
            if sess_raw:
                try:
                    hb = datetime.fromisoformat(sess_raw["last_heartbeat"]) if sess_raw.get("last_heartbeat") else None
                except Exception:
                    hb = None
                session = SessionCookie(
                    channel_id=sess_raw["channel_id"],
                    cookies_data=_decode_cookies(sess_raw.get("cookies_data"), ch_data["id"]),
                    in_use_by=sess_raw.get("in_use_by"),
                    in_use_since=datetime.fromisoformat(sess_raw["in_use_since"]) if sess_raw.get("in_use_since") else None,
                    last_heartbeat=hb,
                    last_synced_at=datetime.fromisoformat(sess_raw["last_synced_at"]) if sess_raw.get("last_synced_at") else None,
                    updated_by=sess_raw.get("updated_by"),
                    health=sess_raw.get("health") if isinstance(sess_raw.get("health"), dict) else None
                )

            results.append(ChannelItemView(channel=channel, session=session))

        return results

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        data = self._read_raw_data()
        for ch_data in data.get("channels", []):
            if ch_data["id"] == channel_id:
                acc_info = next((a for a in data.get("accounts", []) if a["id"] == ch_data.get("account_id")), {})
                try:
                    pinned_at = datetime.fromisoformat(ch_data["pinned_at"]) if ch_data.get("pinned_at") else None
                except Exception:
                    pinned_at = None
                return Channel(
                    id=ch_data["id"],
                    account_id=ch_data["account_id"],
                    platform=parse_platform(ch_data["platform"]),
                    channel_name=ch_data["channel_name"],
                    studio_url=ch_data["studio_url"],
                    login_url=ch_data["login_url"],
                    avatar_url=ch_data.get("avatar_url"),
                    status=ChannelStatus(ch_data.get("status", ChannelStatus.NOT_SETUP.value)),
                    account_display_name=acc_info.get("display_name"),
                    account_email=acc_info.get("email"),
                    pinned=bool(ch_data.get("pinned", False)),
                    pinned_at=pinned_at
                )
        return None

    def get_session(self, channel_id: str) -> Optional[SessionCookie]:
        data = self._read_raw_data()
        sess_raw = data.get("sessions", {}).get(channel_id)
        if not sess_raw:
            return None
        try:
            hb = datetime.fromisoformat(sess_raw["last_heartbeat"]) if sess_raw.get("last_heartbeat") else None
        except Exception:
            hb = None
        return SessionCookie(
            channel_id=sess_raw["channel_id"],
            cookies_data=_decode_cookies(sess_raw.get("cookies_data"), channel_id),
            in_use_by=sess_raw.get("in_use_by"),
            in_use_since=datetime.fromisoformat(sess_raw["in_use_since"]) if sess_raw.get("in_use_since") else None,
            last_heartbeat=hb,
            last_synced_at=datetime.fromisoformat(sess_raw["last_synced_at"]) if sess_raw.get("last_synced_at") else None,
            updated_by=sess_raw.get("updated_by"),
            health=sess_raw.get("health") if isinstance(sess_raw.get("health"), dict) else None
        )

    def save_health(self, channel_id: str, health: Dict[str, Any]) -> bool:
        """Lưu kết quả soi cookies (không động đến cookies/lock)."""
        data = self._read_raw_data()
        sessions = data.setdefault("sessions", {})
        sess = sessions.setdefault(channel_id, {
            "channel_id": channel_id,
            "cookies_data": [],
            "in_use_by": None,
            "in_use_since": None,
            "last_synced_at": None,
            "updated_by": None
        })
        sess["health"] = dict(health or {})
        self._save_raw_data(data)
        return True

    def restore_session_raw(self, channel_id: str, cookies_raw: Any, health: Any = None) -> bool:
        """Khôi phục session từ snapshot thùng rác (giữ nguyên payload đã mã hóa)."""
        data = self._read_raw_data()
        sessions = data.setdefault("sessions", {})
        sess = sessions.setdefault(channel_id, {
            "channel_id": channel_id,
            "cookies_data": [],
            "in_use_by": None,
            "in_use_since": None,
            "last_synced_at": None,
            "updated_by": None
        })
        sess["cookies_data"] = cookies_raw if cookies_raw is not None else []
        sess["in_use_by"] = None
        sess["in_use_since"] = None
        if isinstance(health, dict):
            sess["health"] = health
        self._save_raw_data(data)
        return True

    def acquire_lock(self, channel_id: str, user_name: str) -> Tuple[bool, Optional[str]]:
        data = self._read_raw_data()
        sessions = data.setdefault("sessions", {})
        sess = sessions.setdefault(channel_id, {
            "channel_id": channel_id,
            "cookies_data": [],
            "in_use_by": None,
            "in_use_since": None,
            "last_heartbeat": None,
            "last_synced_at": None,
            "updated_by": None
        })

        current_holder = sess.get("in_use_by")
        if current_holder and current_holder != user_name:
            return False, current_holder

        now = datetime.now().isoformat()
        sess["in_use_by"] = user_name
        sess["in_use_since"] = sess.get("in_use_since") or now
        if current_holder != user_name:
            sess["in_use_since"] = now
        sess["last_heartbeat"] = now
        self._save_raw_data(data)
        logger.info(f"Đã khóa phiên kênh {channel_id} cho người dùng '{user_name}'")
        return True, None

    def heartbeat(self, channel_id: str, user_name: str) -> bool:
        data = self._read_raw_data()
        sess = data.get("sessions", {}).get(channel_id)
        if not sess or sess.get("in_use_by") != user_name:
            return False
        sess["last_heartbeat"] = datetime.now().isoformat()
        self._save_raw_data(data)
        return True

    def release_lock(self, channel_id: str, user_name: str, force: bool = False) -> bool:
        data = self._read_raw_data()
        sessions = data.get("sessions", {})
        if channel_id in sessions:
            sess = sessions[channel_id]
            if force or sess.get("in_use_by") == user_name:
                sess["in_use_by"] = None
                sess["in_use_since"] = None
                sess["last_heartbeat"] = None
                self._save_raw_data(data)
                logger.info(f"Đã giải phóng khóa phiên kênh {channel_id}")
                return True
        return False

    # ---------- Access requests (Xin mở kênh) ----------
    def request_access(self, channel_id: str, requester: str, message: str = "") -> Dict[str, Any]:
        requester = (requester or "").strip() or "Unknown"
        data = self._read_raw_data()
        sess = data.get("sessions", {}).get(channel_id, {})
        holder = sess.get("in_use_by")
        if not holder:
            return {"success": False, "message": "Kênh đang trống, bạn có thể mở trực tiếp."}
        if holder == requester:
            return {"success": False, "message": "Bạn đang giữ kênh này rồi."}
        reqs = self._ensure_request_store(data)
        for r in reqs:
            if r.get("channel_id") == channel_id and r.get("requester") == requester and r.get("status") == "pending":
                return {"success": False, "message": "Bạn đã gửi yêu cầu rồi, vui lòng chờ duyệt."}
        req = {
            "id": f"req_{uuid.uuid4().hex[:8]}",
            "channel_id": channel_id,
            "requester": requester,
            "message": (message or "")[:200],
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "resolved_by": None,
            "resolved_at": None,
        }
        reqs.append(req)
        # Giữ tối đa 200 yêu cầu gần nhất để file JSON gọn
        if len(reqs) > 200:
            reqs[:] = reqs[-200:]
        self._save_raw_data(data)
        logger.info(f"Xin mở kênh '{channel_id}': '{requester}' -> holder '{holder}'")
        return {"success": True, "request_id": req["id"], "holder": holder,
                "message": f"Đã gửi yêu cầu tới {holder}. Vui lòng chờ duyệt."}

    def list_access_requests(self, status: str = "pending") -> List[Dict[str, Any]]:
        data = self._read_raw_data()
        reqs = data.get("access_requests", []) or []
        sessions = data.get("sessions", {})
        channels = {c.get("id"): c for c in data.get("channels", [])}
        out = []
        for r in sorted(reqs, key=lambda x: x.get("created_at", ""), reverse=True)[:100]:
            if status != "ALL" and r.get("status") != status:
                continue
            ch = channels.get(r.get("channel_id"), {})
            out.append({
                **r,
                "channel_name": ch.get("channel_name", r.get("channel_id")),
                "holder": sessions.get(r.get("channel_id"), {}).get("in_use_by"),
            })
        return out

    def resolve_access_request(self, request_id: str, approver: str, action: str) -> Dict[str, Any]:
        data = self._read_raw_data()
        reqs = self._ensure_request_store(data)
        req = next((r for r in reqs if r.get("id") == request_id), None)
        if not req:
            return {"success": False, "message": "Không tìm thấy yêu cầu."}
        if req.get("status") != "pending":
            return {"success": False, "message": f"Yêu cầu đã được xử lý ({req.get('status')})."}
        action = (action or "").lower()
        if action not in ("approve", "deny"):
            return {"success": False, "message": "Hành động không hợp lệ."}
        now = datetime.now().isoformat()
        if action == "deny":
            req["status"] = "denied"
            req["resolved_by"] = approver
            req["resolved_at"] = now
            self._save_raw_data(data)
            return {"success": True, "message": f"Đã từ chối yêu cầu của {req.get('requester')}."}
        # approve = giải phóng khóa để người xin mở ngay
        sessions = data.get("sessions", {})
        sess = sessions.get(req["channel_id"])
        if sess:
            sess["in_use_by"] = None
            sess["in_use_since"] = None
            sess["last_heartbeat"] = None
        req["status"] = "approved"
        req["resolved_by"] = approver
        req["resolved_at"] = now
        self._save_raw_data(data)
        logger.warning(f"Duyệt xin mở kênh '{req['channel_id']}': '{approver}' nhường cho '{req.get('requester')}'")
        return {"success": True, "message": f"Đã nhường kênh cho {req.get('requester')}."}

    def save_cookies(self, channel_id: str, cookies: List[Dict[str, Any]], user_name: str) -> bool:
        data = self._read_raw_data()
        sessions = data.setdefault("sessions", {})
        sess = sessions.setdefault(channel_id, {
            "channel_id": channel_id,
            "cookies_data": [],
            "in_use_by": None,
            "in_use_since": None,
            "last_synced_at": None,
            "updated_by": None
        })

        # MÃ HÓA trước khi ghi đĩa — không bao giờ lưu plaintext mới
        try:
            sess["cookies_data"] = secure_store.protect_json(cookies or [])
        except Exception as e:
            logger.error(f"Không mã hóa được cookies kênh '{channel_id}', HỦY lưu để tránh lộ plaintext: {e}")
            return False
        # Cookies mới = cần kiểm tra lại -> xóa verdict cũ để không kẹt EXPIRED
        sess.pop("health", None)
        sess["in_use_by"] = None
        sess["in_use_since"] = None
        sess["last_heartbeat"] = None
        sess["last_synced_at"] = datetime.now().isoformat()
        sess["updated_by"] = user_name

        # Cập nhật status của channel thành READY
        for ch in data.get("channels", []):
            if ch["id"] == channel_id:
                ch["status"] = ChannelStatus.READY.value
                break

        self._save_raw_data(data)
        logger.info(f"Đã lưu {len(cookies)} cookies mới cho kênh {channel_id} bởi '{user_name}'")
        return True

    def update_cookies_keep_lock(self, channel_id: str, cookies: List[Dict[str, Any]], user_name: str) -> bool:
        """Tự lưu cookies khi browser còn mở: giữ nguyên lock, chỉ refresh dữ liệu + heartbeat."""
        data = self._read_raw_data()
        sessions = data.setdefault("sessions", {})
        sess = sessions.setdefault(channel_id, {
            "channel_id": channel_id,
            "cookies_data": [],
            "in_use_by": None,
            "in_use_since": None,
            "last_synced_at": None,
            "updated_by": None
        })
        # Chỉ lưu khi lock vẫn thuộc về đúng người (tránh ghi đè sau force-unlock)
        if sess.get("in_use_by") and sess.get("in_use_by") != user_name:
            logger.warning(f"Bỏ qua tự lưu cookies '{channel_id}': lock đã thuộc về '{sess.get('in_use_by')}'")
            return False
        try:
            sess["cookies_data"] = secure_store.protect_json(cookies or [])
        except Exception as e:
            logger.error(f"Tự lưu cookies '{channel_id}' lỗi mã hóa: {e}")
            return False
        sess.pop("health", None)
        now = datetime.now().isoformat()
        sess["last_heartbeat"] = now
        sess["last_synced_at"] = now
        sess["updated_by"] = user_name
        for ch in data.get("channels", []):
            if ch["id"] == channel_id:
                ch["status"] = ChannelStatus.READY.value
                break
        self._save_raw_data(data)
        logger.info(f"Tự lưu {len(cookies)} cookies cho kênh đang mở {channel_id}")
        return True

    # ========================================================
    # CRUD Operations for Accounts and Channels
    # ========================================================
    def create_account(self, account: Account) -> bool:
        data = self._read_raw_data()
        accounts = data.setdefault("accounts", [])
        if any(a["id"] == account.id for a in accounts):
            logger.warning(f"Tài khoản '{account.id}' đã tồn tại.")
            return False

        accounts.append({
            "id": account.id,
            "display_name": account.display_name,
            "email": account.email,
            "recovery_email": account.recovery_email,
            "notes": account.notes,
            "logo": getattr(account, "logo", None),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        self._save_raw_data(data)
        logger.info(f"Đã tạo tài khoản Google mới: '{account.display_name}' ({account.id})")
        return True

    def update_account(self, account: Account) -> bool:
        data = self._read_raw_data()
        found = False
        for a in data.get("accounts", []):
            if a["id"] == account.id:
                a["display_name"] = account.display_name
                a["email"] = account.email
                a["recovery_email"] = account.recovery_email
                a["notes"] = account.notes
                if getattr(account, "logo", None) is not None:
                    a["logo"] = account.logo
                a["updated_at"] = datetime.now().isoformat()
                found = True
                break

        if found:
            # Also update account name & email cache on its channels
            for ch in data.get("channels", []):
                if ch.get("account_id") == account.id:
                    ch["account_display_name"] = account.display_name
                    ch["account_email"] = account.email
            self._save_raw_data(data)
            logger.info(f"Đã cập nhật thông tin tài khoản Google: '{account.id}'")
            return True
        return False

    def delete_account(self, account_id: str) -> bool:
        data = self._read_raw_data()
        accounts = data.get("accounts", [])
        orig_count = len(accounts)
        data["accounts"] = [a for a in accounts if a["id"] != account_id]

        if len(data["accounts"]) < orig_count:
            # Cascade delete channels belonging to this account
            del_ch_ids = [ch["id"] for ch in data.get("channels", []) if ch.get("account_id") == account_id]
            data["channels"] = [ch for ch in data.get("channels", []) if ch.get("account_id") != account_id]

            # Remove sessions
            sessions = data.get("sessions", {})
            for ch_id in del_ch_ids:
                sessions.pop(ch_id, None)

            self._save_raw_data(data)
            logger.info(f"Đã xóa tài khoản '{account_id}' và {len(del_ch_ids)} kênh liên quan.")
            return True
        return False

    def create_channel(self, channel: Channel) -> bool:
        data = self._read_raw_data()
        channels = data.setdefault("channels", [])
        if any(ch["id"] == channel.id for ch in channels):
            logger.warning(f"Kênh '{channel.id}' đã tồn tại.")
            return False

        # Find account info
        acc_info = next((a for a in data.get("accounts", []) if a["id"] == channel.account_id), {})

        channels.append({
            "id": channel.id,
            "account_id": channel.account_id,
            "platform": platform_value(channel.platform),
            "channel_name": channel.channel_name,
            "studio_url": channel.studio_url,
            "login_url": channel.login_url,
            "avatar_url": channel.avatar_url,
            "status": ChannelStatus.NOT_SETUP.value,
            "pinned": bool(getattr(channel, "pinned", False)),
            "pinned_at": channel.pinned_at.isoformat() if getattr(channel, "pinned_at", None) else None,
            "account_display_name": acc_info.get("display_name", ""),
            "account_email": acc_info.get("email", "")
        })

        sessions = data.setdefault("sessions", {})
        sessions[channel.id] = {
            "channel_id": channel.id,
            "cookies_data": [],
            "in_use_by": None,
            "in_use_since": None,
            "last_synced_at": None,
            "updated_by": None
        }

        self._save_raw_data(data)
        logger.info(f"Đã tạo kênh mới: '{channel.channel_name}' ({channel.id})")
        return True

    def update_channel(self, channel: Channel) -> bool:
        data = self._read_raw_data()
        found = False
        for ch in data.get("channels", []):
            if ch["id"] == channel.id:
                ch["channel_name"] = channel.channel_name
                ch["studio_url"] = channel.studio_url
                ch["login_url"] = channel.login_url
                ch["account_id"] = channel.account_id
                ch["pinned"] = bool(getattr(channel, "pinned", ch.get("pinned", False)))
                pa = getattr(channel, "pinned_at", None)
                if pa is not None:
                    ch["pinned_at"] = pa.isoformat() if hasattr(pa, "isoformat") else str(pa)
                elif ch["pinned"]:
                    ch["pinned_at"] = ch.get("pinned_at") or datetime.now().isoformat()
                else:
                    ch["pinned_at"] = None
                acc_info = next((a for a in data.get("accounts", []) if a["id"] == channel.account_id), {})
                ch["account_display_name"] = acc_info.get("display_name", "")
                ch["account_email"] = acc_info.get("email", "")
                found = True
                break

        if found:
            self._save_raw_data(data)
            logger.info(f"Đã cập nhật thông tin kênh: '{channel.id}'")
            return True
        return False

    def delete_channel(self, channel_id: str) -> bool:
        data = self._read_raw_data()
        channels = data.get("channels", [])
        orig_count = len(channels)
        data["channels"] = [ch for ch in channels if ch["id"] != channel_id]

        if len(data["channels"]) < orig_count:
            data.get("sessions", {}).pop(channel_id, None)
            self._save_raw_data(data)
            logger.info(f"Đã xóa kênh '{channel_id}'.")
            return True
        return False

    def get_cookie_vault_status(self) -> List[Dict[str, Any]]:
        """Trạng thái vault từng kênh: đã mã hóa chưa, số cookies, lần sync cuối."""
        data = self._read_raw_data()
        sessions = data.get("sessions", {})
        out = []
        for ch in data.get("channels", []):
            raw = sessions.get(ch["id"], {}).get("cookies_data")
            sess = sessions.get(ch["id"], {})
            if isinstance(raw, list):
                count = len(raw)
                encrypted = count == 0  # rỗng thì coi như an toàn
            elif isinstance(raw, str) and secure_store.is_protected(raw):
                count = len(_decode_cookies(raw, ch["id"]))
                encrypted = True
            else:
                count = 0
                encrypted = True
            out.append({
                "channel_id": ch["id"],
                "channel_name": ch.get("channel_name", ch["id"]),
                "cookies_count": count,
                "encrypted": encrypted,
                "in_use_by": sess.get("in_use_by"),
                "last_synced_at": sess.get("last_synced_at"),
            })
        return out

    def migrate_plaintext_cookies(self) -> Dict[str, int]:
        """Mã hóa toàn bộ cookies plaintext cũ. Có backup .bak trước khi ghi."""
        data = self._read_raw_data()
        sessions = data.get("sessions", {})
        migrated, failed, skipped = 0, 0, 0
        for ch_id, sess in sessions.items():
            raw = sess.get("cookies_data")
            if isinstance(raw, list) and len(raw) > 0:
                try:
                    sess["cookies_data"] = secure_store.protect_json(raw)
                    migrated += 1
                except Exception as e:
                    logger.error(f"Migrate cookies '{ch_id}' thất bại: {e}")
                    failed += 1
            else:
                skipped += 1
        if migrated > 0:
            try:
                backup = self.file_path.with_suffix(".json.bak")
                with open(self.file_path, "r", encoding="utf-8-sig") as f:
                    backup.write_text(f.read(), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Không backup được local_db trước migrate: {e}")
            self._save_raw_data(data)
            logger.info(f"Đã mã hóa {migrated} phiên cookies plaintext (bỏ qua {skipped}, lỗi {failed}).")
        return {"migrated": migrated, "failed": failed, "skipped": skipped}

    # ========================================================
    # Health runs (lịch sử + report kiểm tra phiên)
    # ========================================================
    _HEALTH_STATUSES = ("alive", "dead", "error", "skipped", "empty")

    def create_health_run(self, triggered_by: str, total: int, scope: str = "ALL") -> str:
        data = self._read_raw_data()
        runs = data.setdefault("health_runs", [])
        run_id = f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}"
        runs.insert(0, {
            "id": run_id,
            "triggered_by": triggered_by or "",
            "scope": scope or "ALL",
            "total": int(total or 0),
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "stats": {k: 0 for k in self._HEALTH_STATUSES},
            "results": [],
        })
        del runs[30:]  # chỉ giữ 30 đợt gần nhất
        self._save_raw_data(data)
        logger.info(f"Health run '{run_id}' bắt đầu bởi '{triggered_by}' ({total} kênh).")
        return run_id

    def append_health_result(self, run_id: str, channel_id: str, status: str, detail: str = "") -> bool:
        if status not in self._HEALTH_STATUSES:
            status = "error"
        data = self._read_raw_data()
        for r in data.get("health_runs", []):
            if r.get("id") == run_id:
                r.setdefault("results", []).append({
                    "channel_id": channel_id,
                    "status": status,
                    "detail": (detail or "")[:500],
                    "checked_at": datetime.now().isoformat(),
                })
                r.setdefault("stats", {}).setdefault(status, 0)
                r["stats"][status] += 1
                self._save_raw_data(data)
                return True
        return False

    def finish_health_run(self, run_id: str, status: str = "finished") -> bool:
        data = self._read_raw_data()
        for r in data.get("health_runs", []):
            if r.get("id") == run_id:
                r["status"] = status if status in ("finished", "stopped") else "finished"
                r["finished_at"] = datetime.now().isoformat()
                self._save_raw_data(data)
                return True
        return False

    def list_health_runs(self, limit: int = 30) -> List[Dict[str, Any]]:
        data = self._read_raw_data()
        out = []
        for r in (data.get("health_runs", []) or [])[: max(1, int(limit or 30))]:
            out.append({k: v for k, v in r.items() if k != "results"})
        return out

    def get_health_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_raw_data()
        channels = {c.get("id"): c for c in data.get("channels", [])}
        for r in data.get("health_runs", []) or []:
            if r.get("id") == run_id:
                full = dict(r)
                full["results"] = [
                    {**res, "channel_name": channels.get(res.get("channel_id"), {}).get("channel_name", res.get("channel_id"))}
                    for res in r.get("results", [])
                ]
                return full
        return None

    def reset_channel_session(self, channel_id: str) -> bool:
        data = self._read_raw_data()
        sessions = data.get("sessions", {})
        if channel_id in sessions:
            sess = sessions[channel_id]
            sess["cookies_data"] = []
            sess["in_use_by"] = None
            sess["in_use_since"] = None
            sess["last_heartbeat"] = None
            sess["last_synced_at"] = None

        for ch in data.get("channels", []):
            if ch["id"] == channel_id:
                ch["status"] = ChannelStatus.NOT_SETUP.value
                break

        self._save_raw_data(data)
        logger.info(f"Đã reset session & cookies kênh '{channel_id}' về trạng thái Chưa Setup.")
        return True
