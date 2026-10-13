"""Dong bo online lien may qua Firebase Realtime Database (REST, stdlib-only).

Pham vi (co tinh, da thong nhat voi user):
- Hien dien: may nao dang online + dang giu kenh nao.
- Khoa lien may: mo kenh bi chan neu may khac dang giu (fresh), cu khi stale.
- Hop thu xin mo: inbox theo ten nguoi giu + node request dung chung de 2 ben
  deu thay duoc approve/deny.

KHONG dong bo cookies: vault ma hoa DPAPI gan voi user+may Windows, may khac
khong giai ma duoc. Cookies van nam local tung may.

Chinh sach xung dot:
- Remote fresh (< STALE_AFTER_S) + holder khac minh -> tu choi mo local.
- Remote stale -> coi nhu tu do, ben acquire sau ghi de (takeover, co log).
- Force unlock -> xoa lock remote bat chap (quyen admin, co log).
- Mat mang / het token / tat sync -> che do local-only (fail-open, giu UX cu).

Moi network I/O chay trong background thread; duong doc hien thi (bridge)
chi doc cache in-memory, khong bao gio block UI.
"""
import base64
import json
import threading
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from src.core.logger import logger

ROOT = "vbsync"
POLL_SEC = 10.0
STALE_AFTER_S = 45.0
HTTP_TIMEOUT = 8.0


def _safe_key(name: str) -> str:
    """Ma hoa ten holder thanh key RTDB hop le (cam . $ # [ ] /)."""
    raw = (name or "").strip().encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unsafekey(key: str) -> str:
    pad = "=" * (-len(key) % 4)
    try:
        return base64.urlsafe_b64decode((key + pad).encode("ascii")).decode("utf-8")
    except Exception:
        return key


def _now_ms() -> int:
    return int(time.time() * 1000)


def _is_fresh(ts_ms: Any, now_ms: Optional[int] = None) -> bool:
    try:
        ts = float(ts_ms)
    except (TypeError, ValueError):
        return False
    now = float(now_ms if now_ms is not None else _now_ms())
    return (now - ts) <= STALE_AFTER_S * 1000.0


class SyncService:
    """Client dong bo RTDB. Thread-safe o muc cache; network luon background."""

    def __init__(
        self,
        settings_service,
        machine_id: Optional[str] = None,
        on_remote_request: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_request_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_release_signal: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_locks_changed: Optional[Callable[[List[str]], None]] = None,
        on_sync_state: Optional[Callable[[bool], None]] = None,
    ):
        self.settings_service = settings_service
        self._machine_id = machine_id or self._load_machine_id()
        self.on_remote_request = on_remote_request
        self.on_request_update = on_request_update
        self.on_release_signal = on_release_signal
        self.on_locks_changed = on_locks_changed
        self.on_sync_state = on_sync_state

        self._lock = threading.RLock()
        self._remote_locks: Dict[str, Dict[str, Any]] = {}
        self._remote_health: Dict[str, Dict[str, Any]] = {}
        self._inbox: List[Dict[str, Any]] = []       # request pending gui TOI
        self._outbox: Dict[str, Dict[str, Any]] = {}  # request TOI gui di (theo doi kq)
        self._seen_inbox: set = set()

        self._online = False
        self._last_ok: Optional[float] = None
        self._last_error: str = ""
        self._auth_warned = False
        self._owned: Dict[str, Dict[str, str]] = {}  # channel_id -> {holder} lock may nay dang giu

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._identity: Callable[[], Dict[str, str]] = lambda: {"user": "", "email": ""}
        self._holders: Callable[[], Dict[str, str]] = lambda: {}

    # ================= identity / machine =================
    @property
    def machine_id(self) -> str:
        return self._machine_id

    @staticmethod
    def _load_machine_id() -> str:
        """ID may on dinh: platform.node + hau to luu 1 lan trong data/."""
        import platform as _plat
        from src.core.config import Config
        node = "".join(c if (c.isalnum() or c in "-_") else "-" for c in (_plat.node() or "pc"))[:16] or "pc"
        try:
            Config.ensure_directories()
            f = Config.DATA_DIR / ".machine_id"
            if f.exists():
                suffix = f.read_text(encoding="utf-8").strip()[:8] or uuid.uuid4().hex[:8]
            else:
                suffix = uuid.uuid4().hex[:8]
                try:
                    f.write_text(suffix, encoding="utf-8")
                except Exception:
                    pass
        except Exception:
            suffix = uuid.uuid4().hex[:8]
        return f"{node}-{suffix}"

    def set_providers(
        self,
        identity: Callable[[], Dict[str, str]],
        holders: Callable[[], Dict[str, str]],
    ) -> None:
        """identity -> {user, email}; holders -> {channel_id: iso_ts} dang giu local."""
        self._identity = identity
        self._holders = holders

    # ================= cau hinh / trang thai =================
    def _base_url(self) -> str:
        try:
            url = (self.settings_service.get("firebase", "url", "") or "").rstrip("/")
        except Exception:
            url = ""
        return url

    def _enabled(self) -> bool:
        try:
            return bool(self.settings_service.get("firebase", "enabled", True))
        except Exception:
            return True

    def _token(self) -> str:
        try:
            u = self.settings_service.get_auth_user(include_token=True) or {}
            return u.get("idToken") or ""
        except Exception:
            return ""

    def is_online(self) -> bool:
        with self._lock:
            if not self._online:
                return False
            if self._last_ok and (time.time() - self._last_ok) < 30.0:
                return True
            return False

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._enabled(),
                "online": self.is_online(),
                "machine_id": self._machine_id,
                "last_ok": self._last_ok,
                "last_error": self._last_error,
                "remote_locks": len(self._remote_locks),
                "inbox_pending": len(self._inbox),
            }

    # ================= transport =================
    def _req(self, method: str, path: str, data: Any = None) -> Any:
        base = self._base_url()
        if not base.startswith("http"):
            raise RuntimeError("URL Firebase chua cau hinh.")
        token = self._token()
        if not token:
            raise RuntimeError("Thieu idToken (chua dang nhap Google?).")
        url = f"{base}/{ROOT}/{path}.json?auth={token}"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
        req = urllib.request.Request(
            url, data=body, method=method,
            headers={"Content-Type": "application/json", "User-Agent": "VB-Studio/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as res:
                raw = res.read().decode("utf-8")
                self._mark_ok()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                self._mark_auth_fail()
            else:
                self._mark_error(f"HTTP {e.code}")
            raise

    def _mark_ok(self) -> None:
        with self._lock:
            was = self._online
            self._online = True
            self._last_ok = time.time()
            self._last_error = ""
            self._auth_warned = False
        if not was and self.on_sync_state:
            try:
                self.on_sync_state(True)
            except Exception:
                pass

    def _mark_error(self, msg: str) -> None:
        with self._lock:
            self._online = False
            self._last_error = msg
        if self.on_sync_state:
            try:
                self.on_sync_state(False)
            except Exception:
                pass

    def _mark_auth_fail(self) -> None:
        self._mark_error("401/403: token het han hoac bi tu choi — dang nhap Google lai.")
        with self._lock:
            warned = self._auth_warned
            self._auth_warned = True
        if not warned:
            logger.warning("Sync offline: idToken het han/bi tu choi. Dang nhap Google lai de sync.")

    # ================= locks =================
    def remote_lock_of(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Lock remote con fresh cua kenh, None neu tu do/stale/offline."""
        with self._lock:
            info = self._remote_locks.get(channel_id)
        if not info or not _is_fresh(info.get("ts")):
            return None
        return dict(info)

    def remote_locks_snapshot(self) -> Dict[str, Dict[str, Any]]:
        now = _now_ms()
        with self._lock:
            return {c: dict(i) for c, i in self._remote_locks.items() if _is_fresh(i.get("ts"), now)}

    def claim_lock(self, channel_id: str, holder: str, machine: str) -> bool:
        """Giu lock remote neu dang tu do/stale/cua minh. Tra False neu may khac giu fresh."""
        try:
            cur = self._req("GET", f"locks/{channel_id}")
        except Exception as e:
            logger.warning(f"claim_lock {channel_id} loi mang (cho phep local): {e}")
            return True  # fail-open: offline thi van cho mo local
        if cur and _is_fresh(cur.get("ts")):
            if (cur.get("machine") or "") == self._machine_id:
                pass  # cua minh -> refresh
            elif (cur.get("holder") or "").strip().lower() != (holder or "").strip().lower():
                with self._lock:
                    self._remote_locks[channel_id] = dict(cur)
                return False
        payload = {"holder": holder, "machine": machine,
                   "since": (cur or {}).get("since") or datetime.now(timezone.utc).isoformat(),
                   "ts": _now_ms()}
        try:
            self._req("PUT", f"locks/{channel_id}", payload)
            with self._lock:
                self._remote_locks[channel_id] = dict(payload)
                self._owned[channel_id] = {"holder": holder}
            return True
        except Exception as e:
            logger.warning(f"claim_lock PUT {channel_id} loi: {e}")
            return True  # fail-open

    def refresh_lock(self, channel_id: str, holder: str, machine: str) -> None:
        try:
            cur = self._req("GET", f"locks/{channel_id}")
        except Exception:
            return
        if cur and (cur.get("machine") or "") != self._machine_id:
            return  # khong refresh lock cua may khac
        try:
            payload = {"holder": holder, "machine": machine,
                       "since": (cur or {}).get("since") or datetime.now(timezone.utc).isoformat(),
                       "ts": _now_ms()}
            self._req("PUT", f"locks/{channel_id}", payload)
            with self._lock:
                self._remote_locks[channel_id] = dict(payload)
        except Exception:
            pass

    def release_lock(self, channel_id: str, force: bool = False) -> None:
        """Xoa lock remote neu la cua minh; force=True xoa bat chap (admin override)."""
        deleted = False
        try:
            if not force:
                cur = self._req("GET", f"locks/{channel_id}")
                if cur and (cur.get("machine") or "") != self._machine_id and _is_fresh(cur.get("ts")):
                    with self._lock:
                        self._remote_locks[channel_id] = dict(cur)
                    return
            self._req("DELETE", f"locks/{channel_id}")
            deleted = True
        except Exception as e:
            logger.debug(f"release_lock remote {channel_id} bo qua: {e}")
        finally:
            if deleted:
                with self._lock:
                    self._remote_locks.pop(channel_id, None)
                    self._owned.pop(channel_id, None)

    # ================= presence =================
    def push_presence(self, holders: Dict[str, str]) -> None:
        ident = self._identity()
        payload = {"user": ident.get("user", ""), "email": ident.get("email", ""),
                   "machine": self._machine_id, "holders": holders or {}, "ts": _now_ms()}
        try:
            self._req("PUT", f"presence/{self._machine_id}", payload)
        except Exception as e:
            logger.debug(f"push_presence bo qua: {e}")

    def clear_presence(self) -> None:
        """Xóa trạng thái hiện diện online khỏi Firebase RTDB khi tắt app."""
        try:
            self._req("DELETE", f"presence/{self._machine_id}")
        except Exception as e:
            logger.debug(f"clear_presence bo qua: {e}")

    # ================= inbox xin mo =================
    def send_request(self, holder: str, payload: Dict[str, Any]) -> Optional[str]:
        req_id = f"q_{self._machine_id}_{uuid.uuid4().hex[:8]}"
        body = {"id": req_id, "channel_id": payload.get("channel_id", ""),
                "requester": payload.get("requester", ""),
                "requester_machine": self._machine_id,
                "message": (payload.get("message") or "")[:200],
                "status": "pending", "created_at": datetime.now(timezone.utc).isoformat(),
                "resolved_by": None, "resolved_at": None}
        try:
            self._req("PUT", f"requests/{req_id}", body)
            self._req("PUT", f"inbox/{_safe_key(holder)}/{req_id}", True)
            with self._lock:
                self._outbox[req_id] = dict(body)
            return req_id
        except Exception as e:
            logger.warning(f"send_request loi: {e}")
            return None

    def outbox_snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._outbox.values()]

    def inbox_snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._inbox]

    def resolve_request(self, req_id: str, action: str, by: str) -> bool:
        action = (action or "").lower()
        if action not in ("approve", "deny"):
            return False
        try:
            cur = self._req("GET", f"requests/{req_id}")
        except Exception as e:
            logger.warning(f"resolve_request doc loi: {e}")
            return False
        if not cur or cur.get("status") != "pending":
            return False
        body = dict(cur)
        body["status"] = "approved" if action == "approve" else "denied"
        body["resolved_by"] = by
        body["resolved_at"] = datetime.now(timezone.utc).isoformat()
        try:
            self._req("PUT", f"requests/{req_id}", body)
            try:
                self._req("DELETE", f"inbox/{_safe_key(body.get('holder', ''))}/{req_id}")
            except Exception:
                pass
            with self._lock:
                self._inbox = [r for r in self._inbox if r.get("id") != req_id]
            return True
        except Exception as e:
            logger.warning(f"resolve_request ghi loi: {e}")
            return False

    # ================= health verdicts =================
    def push_health(self, channel_id: str, verdict: Dict[str, Any], by: str) -> None:
        try:
            self._req("PUT", f"health/{channel_id}",
                      {"status": verdict.get("status"), "detail": verdict.get("detail", "")[:300],
                       "checked_at": datetime.now(timezone.utc).isoformat(), "by": by or ""})
        except Exception as e:
            logger.debug(f"push_health bo qua: {e}")

    def health_snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {c: dict(v) for c, v in self._remote_health.items()}

    def forget_lock(self, channel_id: str) -> None:
        """Xoa cache lock (sau khi tu dong nhuong / biet chac da giai phong)."""
        with self._lock:
            self._remote_locks.pop(channel_id, None)
            self._owned.pop(channel_id, None)

    # ================= tin hieu nhuong (approve tu may khac) =================
    def send_release_signal(self, machine: str, channel_id: str, requester: str) -> None:
        """Bao may `machine` tu dong dong browser + nha kenh (ban giao)."""
        if not machine or machine == self._machine_id:
            return
        try:
            self._req("PUT", f"signals/{machine}/{channel_id}",
                      {"channel_id": channel_id, "requester": requester or "",
                       "ts": _now_ms()})
        except Exception as e:
            logger.debug(f"send_release_signal bo qua: {e}")

    def _fetch_release_signals(self) -> None:
        try:
            box = self._req("GET", f"signals/{self._machine_id}") or {}
        except Exception:
            return
        if not isinstance(box, dict) or not box:
            return
        try:
            self._req("DELETE", f"signals/{self._machine_id}")
        except Exception:
            pass
        for ch_id, sig in box.items():
            if not isinstance(sig, dict):
                sig = {}
            cb = self.on_release_signal
            if cb:
                try:
                    cb({"channel_id": ch_id,
                        "requester": sig.get("requester", "")})
                except Exception:
                    pass

    # ================= background loop =================
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="SyncThread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        # Xả mọi lock online mà máy này đang sở hữu
        try:
            with self._lock:
                owned_ids = list(self._owned.keys())
            for ch_id in owned_ids:
                try:
                    self.release_lock(ch_id, force=False)
                except Exception:
                    pass
        except Exception:
            pass
        # Xóa hiện diện khỏi RTDB
        try:
            self.clear_presence()
        except Exception:
            pass
        if self._thread and self._thread.is_alive() and threading.current_thread() != self._thread:
            try:
                self._thread.join(timeout=1.0)
            except Exception:
                pass

    def _loop(self) -> None:
        while not self._stop.wait(POLL_SEC):
            try:
                self.tick()
            except Exception as e:
                logger.debug(f"sync tick loi: {e}")

    def tick(self) -> None:
        """1 chu ky: day presence + keo locks/health/inbox + theo doi outbox."""
        if not self._enabled() or not self._base_url().startswith("http") or not self._token():
            with self._lock:
                self._online = False
            return
        ident = self._identity()
        try:
            self.push_presence(self._holders())
        except Exception:
            pass
        # keepalive cac lock may nay dang giu (giu fresh, tranh bi may khac takeover)
        try:
            with self._lock:
                owned = dict(self._owned)
            for ch_id, info in owned.items():
                try:
                    self.refresh_lock(ch_id, info.get("holder", ""), self._machine_id)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            locks = self._req("GET", "locks") or {}
            # Tự động dọn dẹp remote lock mồ côi trên RTDB nếu thuộc máy này nhưng không còn chạy
            if isinstance(locks, dict):
                holders_now = self._holders()
                for c_id, lk in list(locks.items()):
                    if isinstance(lk, dict) and (lk.get("machine") or "") == self._machine_id:
                        if c_id not in holders_now:
                            logger.warning(f"Phát hiện remote lock mồ côi trên RTDB cho kênh '{c_id}'. Đang tự xả...")
                            self.release_lock(c_id, force=True)
                            locks.pop(c_id, None)

            with self._lock:
                new_locks = {c: v for c, v in locks.items() if isinstance(v, dict)}
                old_sig = {c: ((v.get("holder") or ""), (v.get("machine") or ""))
                           for c, v in self._remote_locks.items()}
                new_sig = {c: ((v.get("holder") or ""), (v.get("machine") or ""))
                           for c, v in new_locks.items()}
                self._remote_locks = new_locks
                changed = [c for c in (set(old_sig) | set(new_sig)) if old_sig.get(c) != new_sig.get(c)]
            if changed and self.on_locks_changed:
                try:
                    self.on_locks_changed(changed)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            health = self._req("GET", "health") or {}
            with self._lock:
                self._remote_health = {c: v for c, v in health.items() if isinstance(v, dict)}
        except Exception:
            pass
        # inbox gui TOI: quet cac alias ten (key RTDB luon la _safe_key(ten))
        aliases = [a.strip() for a in (ident.get("aliases") or []) if (a or "").strip()]
        for extra in (ident.get("user", ""), ident.get("email", "")):
            if (extra or "").strip() and extra.strip() not in aliases:
                aliases.append(extra.strip())
        fresh_inbox: List[Dict[str, Any]] = []
        for alias in aliases:
            try:
                box = self._req("GET", f"inbox/{_safe_key(alias)}") or {}
            except Exception:
                continue
            ids = [rid for rid, v in box.items() if v] if isinstance(box, dict) else []
            for rid in ids:
                try:
                    req = self._req("GET", f"requests/{rid}")
                except Exception:
                    continue
                if req and req.get("status") == "pending":
                    fresh_inbox.append(req)
        new_ones = [r for r in fresh_inbox if r.get("id") not in self._seen_inbox]
        with self._lock:
            self._inbox = fresh_inbox
            for r in fresh_inbox:
                self._seen_inbox.add(r.get("id"))
            self._seen_inbox = {r.get("id") for r in fresh_inbox} | set(list(self._seen_inbox)[-200:])
        for req in new_ones:
            if self.on_remote_request:
                try:
                    self.on_remote_request(req)
                except Exception:
                    pass
        # theo doi outbox: lock remote duoc giai phong / request duoc resolve
        done_ids = []
        with self._lock:
            outbox = dict(self._outbox)
        for rid, req in outbox.items():
            try:
                cur = self._req("GET", f"requests/{rid}")
            except Exception:
                continue
            if not cur:
                continue
            if cur.get("status") in ("approved", "denied"):
                done_ids.append(rid)
                if self.on_request_update:
                    try:
                        self.on_request_update(cur)
                    except Exception:
                        pass
                continue
            # approved = holder da giai phong -> lock remote trong
            lock = self.remote_lock_of(req.get("channel_id", ""))
            if cur.get("status") == "pending" and not lock:
                # holder tu giai phong (force) ma chua resolve -> coi nhu granted
                upd = dict(cur)
                upd["status"] = "approved"
                done_ids.append(rid)
                if self.on_request_update:
                    try:
                        self.on_request_update(upd)
                    except Exception:
                        pass
        if done_ids:
            with self._lock:
                for rid in done_ids:
                    self._outbox.pop(rid, None)
        # tin hieu nhuong gui TOI (approve tu may holder khac)
        try:
            self._fetch_release_signals()
        except Exception:
            pass
