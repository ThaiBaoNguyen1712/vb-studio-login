"""Thùng rác 30 ngày: xóa mềm kênh/tài khoản, khôi phục nguyên vẹn.

Snapshot giữ nguyên payload cookies đã mã hóa vault (không bao giờ ghi
plaintext ra trash.json). Thư mục profile trình duyệt trên đĩa KHÔNG bị
xóa khi vào thùng rác nên khôi phục xong mở lại bình thường.
"""
import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.core.config import Config
from src.core.logger import logger
from src.repositories.base import BaseRepository

TRASH_FILE = Config.DATA_DIR / "trash.json"
RETENTION_DAYS = 30


class TrashService:
    """Quản lý thùng rác cho kênh và tài khoản (local JSON, độc lập repository)."""

    def __init__(self, repository: BaseRepository, file_path: Optional[Path] = None):
        self.repository = repository
        self.file_path = file_path or TRASH_FILE
        self._lock = threading.Lock()
        self.purge_expired()

    # ---------- storage ----------
    def _read(self) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Lỗi đọc trash.json: {e}")
            return []

    def _write(self, items: List[Dict[str, Any]]):
        Config.ensure_directories()
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    # ---------- trash ----------
    def trash_channel(self, channel_id: str, deleted_by: str = "") -> Dict[str, Any]:
        with self._lock:
            items = self._read()
            if any(x.get("kind") == "channel" and x.get("id") == channel_id for x in items):
                return {"success": False, "message": "Kênh đã nằm trong thùng rác."}
            ch = self.repository.get_channel(channel_id)
            if not ch:
                return {"success": False, "message": "Không tìm thấy kênh."}
            sess = self.repository.get_session(channel_id)
            from dataclasses import asdict
            from enum import Enum
            ch_dict = asdict(ch)
            # datetime/enum -> kiểu JSON hóa được
            for k, v in list(ch_dict.items()):
                if hasattr(v, "isoformat"):
                    ch_dict[k] = v.isoformat()
                elif isinstance(v, Enum):
                    ch_dict[k] = v.value
            # platform enum -> value
            plat = ch_dict.get("platform")
            ch_dict["platform"] = plat.value if hasattr(plat, "value") else str(plat)
            sess_dict = None
            if sess:
                sess_dict = {
                    "cookies_data": sess.cookies_data if isinstance(sess.cookies_data, list) else sess.cookies_data,
                    "health": sess.health,
                    "last_synced_at": sess.last_synced_at.isoformat() if sess.last_synced_at else None,
                }
                # cookies_data từ get_session đã giải mã! Lấy lại raw đã mã hóa để cất.
                raw = self._raw_session(channel_id)
                if raw is not None:
                    sess_dict["cookies_data"] = raw
            items.append({
                "kind": "channel",
                "id": channel_id,
                "name": ch.channel_name,
                "account_id": ch.account_id,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "deleted_by": deleted_by,
                "data": ch_dict,
                "session": sess_dict,
            })
            self._write(items)
        ok = self.repository.delete_channel(channel_id)
        if not ok:
            # rollback snapshot nếu xóa cứng thất bại
            with self._lock:
                self._write([x for x in self._read()
                             if not (x.get("kind") == "channel" and x.get("id") == channel_id)])
            return {"success": False, "message": "Không xóa được kênh."}
        logger.info(f"Đã chuyển kênh '{channel_id}' vào thùng rác.")
        return {"success": True}

    def trash_account(self, account_id: str, deleted_by: str = "") -> Dict[str, Any]:
        with self._lock:
            items = self._read()
            if any(x.get("kind") == "account" and x.get("id") == account_id for x in items):
                return {"success": False, "message": "Tài khoản đã nằm trong thùng rác."}
            accs = [a for a in self.repository.get_accounts() if a.id == account_id]
            if not accs:
                return {"success": False, "message": "Không tìm thấy tài khoản."}
            from dataclasses import asdict
            from enum import Enum
            acc = accs[0]
            acc_dict = asdict(acc)
            for k, v in list(acc_dict.items()):
                if hasattr(v, "isoformat"):
                    acc_dict[k] = v.isoformat()
                elif isinstance(v, Enum):
                    acc_dict[k] = v.value
            # snapshot toàn bộ kênh + session raw của account
            channels, sessions = [], {}
            try:
                all_items = self.repository.get_channels(account_id=account_id)
            except TypeError:
                all_items = [x for x in self.repository.get_channels() if x.channel.account_id == account_id]
            for it in all_items:
                c = asdict(it.channel)
                for k, v in list(c.items()):
                    if hasattr(v, "isoformat"):
                        c[k] = v.isoformat()
                    elif isinstance(v, Enum):
                        c[k] = v.value
                plat = c.get("platform")
                c["platform"] = plat.value if hasattr(plat, "value") else str(plat)
                channels.append(c)
                raw = self._raw_session(it.channel.id)
                if raw is not None:
                    s = self.repository.get_session(it.channel.id)
                    sessions[it.channel.id] = {
                        "cookies_data": raw,
                        "health": s.health if s else None,
                        "last_synced_at": s.last_synced_at.isoformat() if s and s.last_synced_at else None,
                    }
            items.append({
                "kind": "account",
                "id": account_id,
                "name": acc.display_name,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "deleted_by": deleted_by,
                "data": acc_dict,
                "channels": channels,
                "sessions": sessions,
            })
            self._write(items)
        ok = self.repository.delete_account(account_id)
        if not ok:
            with self._lock:
                self._write([x for x in self._read()
                             if not (x.get("kind") == "account" and x.get("id") == account_id)])
            return {"success": False, "message": "Không xóa được tài khoản."}
        logger.info(f"Đã chuyển tài khoản '{account_id}' vào thùng rác.")
        return {"success": True}

    def _raw_session(self, channel_id: str):
        """Lấy payload cookies NGUYÊN BẢN (đã mã hóa) từ repository local."""
        try:
            repo = self.repository
            # LocalJsonRepository: đọc raw trực tiếp
            data = repo._read_raw_data()
            sess = data.get("sessions", {}).get(channel_id)
            if sess is not None:
                return sess.get("cookies_data", [])
        except Exception:
            pass
        try:
            # Postgres: đọc ô jsonb (đã parse) rồi dump lại đúng định dạng vault
            import json as _json
            sess = self.repository.get_session(channel_id)
            if sess is None:
                return None
            from src.core import secure_store
            # Không có raw -> mã hóa lại từ danh sách đã giải mã (vẫn an toàn, không plaintext ra đĩa ở đây)
            return secure_store.protect_json(sess.cookies_data or [])
        except Exception as e:
            logger.warning(f"Không snapshot được session raw '{channel_id}': {e}")
            return None

    # ---------- restore ----------
    def _unique_channel_id(self, base_id: str) -> str:
        existing = set()
        try:
            for it in self.repository.get_channels():
                existing.add(it.channel.id)
        except Exception:
            pass
        if base_id not in existing:
            return base_id
        stamp = datetime.now().strftime("%m%d")
        cand = f"{base_id}_restored_{stamp}"
        i = 2
        while cand in existing:
            cand = f"{base_id}_restored_{stamp}_{i}"
            i += 1
        return cand

    def restore(self, kind: str, item_id: str) -> Dict[str, Any]:
        with self._lock:
            items = self._read()
            idx = next((i for i, x in enumerate(items)
                        if x.get("kind") == kind and x.get("id") == item_id), None)
            if idx is None:
                return {"success": False, "message": "Không tìm thấy trong thùng rác."}
            item = items[idx]
            from src.domain.models import Account, Channel
            from src.core.constants import parse_platform
            try:
                if kind == "account":
                    d = dict(item["data"])
                    for k in ("created_at", "updated_at"):
                        d.pop(k, None)
                    acc = Account(id=d["id"], display_name=d.get("display_name", d["id"]),
                                  email=d.get("email", ""), recovery_email=d.get("recovery_email"),
                                  notes=d.get("notes"), logo=d.get("logo"))
                    if not self.repository.create_account(acc):
                        # đã tồn tại (tạo mới trùng id) -> đổi id sẽ làm rời rạc, báo lỗi rõ
                        return {"success": False,
                                "message": f"ID '{d['id']}' đã tồn tại, không khôi phục được."}
                    for c in item.get("channels", []):
                        ch = Channel(id=c["id"], account_id=acc.id,
                                     platform=parse_platform(c.get("platform")),
                                     channel_name=c.get("channel_name", c["id"]),
                                     studio_url=c.get("studio_url", ""),
                                     login_url=c.get("login_url", ""),
                                     avatar_url=c.get("avatar_url"))
                        self.repository.create_channel(ch)
                        s = item.get("sessions", {}).get(c["id"])
                        if s:
                            self.repository.restore_session_raw(
                                c["id"], s.get("cookies_data", []), s.get("health"))
                    # cập nhật pinned nếu có
                    for c in item.get("channels", []):
                        if c.get("pinned"):
                            ch = self.repository.get_channel(c["id"])
                            if ch:
                                from datetime import datetime as _dt
                                ch.pinned = True
                                ch.pinned_at = _dt.now()
                                self.repository.update_channel(ch)
                else:
                    d = dict(item["data"])
                    new_id = self._unique_channel_id(d["id"])
                    ch = Channel(id=new_id, account_id=d.get("account_id"),
                                 platform=parse_platform(d.get("platform")),
                                 channel_name=d.get("channel_name", new_id),
                                 studio_url=d.get("studio_url", ""),
                                 login_url=d.get("login_url", ""),
                                 avatar_url=d.get("avatar_url"))
                    # account gốc còn không? nếu mất thì từ chối (tránh kênh mồ côi)
                    accs = [a.id for a in self.repository.get_accounts()]
                    if ch.account_id not in accs:
                        return {"success": False,
                                "message": "Tài khoản gốc đã mất — hãy khôi phục tài khoản trước."}
                    if not self.repository.create_channel(ch):
                        return {"success": False, "message": "Không tạo lại được kênh."}
                    if d.get("pinned"):
                        from datetime import datetime as _dt
                        ch2 = self.repository.get_channel(new_id)
                        if ch2:
                            ch2.pinned = True
                            ch2.pinned_at = _dt.now()
                            self.repository.update_channel(ch2)
                    s = item.get("session")
                    if s:
                        self.repository.restore_session_raw(
                            new_id, s.get("cookies_data", []), s.get("health"))
                del items[idx]
                self._write(items)
            except Exception as e:
                logger.error(f"Restore trash {kind}/{item_id} failed: {e}")
                return {"success": False, "message": str(e)}
            logger.info(f"Đã khôi phục {kind} '{item_id}' từ thùng rác.")
            return {"success": True}

    # ---------- purge / list ----------
    def list_items(self) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        out = []
        for x in self._read():
            try:
                deleted = datetime.fromisoformat(x["deleted_at"])
                left = RETENTION_DAYS - (now - deleted).days
            except Exception:
                left = RETENTION_DAYS
            out.append({
                "kind": x.get("kind"), "id": x.get("id"),
                "name": x.get("name") or x.get("id"),
                "account_id": x.get("account_id"),
                "deleted_at": x.get("deleted_at"),
                "deleted_by": x.get("deleted_by", ""),
                "days_left": max(left, 0),
                "detail": f"{len(x.get('channels', []))} kênh" if x.get("kind") == "account" else "",
            })
        out.sort(key=lambda e: e["deleted_at"] or "", reverse=True)
        return out

    def delete_forever(self, kind: str, item_id: str) -> Dict[str, Any]:
        with self._lock:
            items = self._read()
            n = len(items)
            items = [x for x in items
                     if not (x.get("kind") == kind and x.get("id") == item_id)]
            if len(items) == n:
                return {"success": False, "message": "Không tìm thấy trong thùng rác."}
            self._write(items)
        logger.info(f"Đã xóa vĩnh viễn {kind} '{item_id}' khỏi thùng rác.")
        return {"success": True}

    def purge_expired(self, retention_days: int = RETENTION_DAYS) -> int:
        with self._lock:
            items = self._read()
            now = datetime.now(timezone.utc)
            kept = []
            for x in items:
                try:
                    deleted = datetime.fromisoformat(x.get("deleted_at", ""))
                    if (now - deleted) > timedelta(days=retention_days):
                        continue
                except Exception:
                    pass
                kept.append(x)
            if len(kept) != len(items):
                self._write(kept)
                logger.info(f"Đã dọn {len(items) - len(kept)} mục quá hạn khỏi thùng rác.")
            return len(items) - len(kept)
