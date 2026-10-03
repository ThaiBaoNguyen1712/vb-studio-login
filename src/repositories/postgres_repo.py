import json
import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from src.core.config import Config
from src.core.constants import Platform, ChannelStatus, parse_platform, platform_value
from src.core.logger import logger
from src.core import secure_store
from src.domain.models import Account, Channel, SessionCookie, ChannelItemView
from src.repositories.base import BaseRepository


def _decode_cookies(raw, channel_id: str = ""):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw  # legacy plaintext
    if isinstance(raw, str):
        if secure_store.is_protected(raw):
            try:
                data = secure_store.unprotect_json(raw)
                return data if isinstance(data, list) else []
            except Exception as e:
                logger.error(f"Không giải mã được cookies kênh '{channel_id}': {e}")
                return []
        return []  # chuỗi lạ — không đoán
    if isinstance(raw, dict):
        return []  # JSONB object không phải cookies
    return []

class PostgresRepository(BaseRepository):
    """
    PostgreSQL on VPS implementation of BaseRepository.
    Enables remote 2-way cookies sync and multi-user concurrency control.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        sslmode: Optional[str] = None
    ):
        self.host = host or Config.DB_HOST
        self.port = port or Config.DB_PORT
        self.dbname = dbname or Config.DB_NAME
        self.user = user or Config.DB_USER
        self.password = password or Config.DB_PASSWORD
        self.sslmode = sslmode or Config.DB_SSLMODE

    def _get_connection(self):
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("psycopg2-binary chưa được cài đặt trong môi trường Python.")
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            sslmode=self.sslmode,
            connect_timeout=5
        )

    def is_connected(self) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    return True
        except Exception as e:
            logger.warning(f"Không thể kết nối PostgreSQL trên VPS ({self.host}:{self.port}): {e}")
            return False

    def _ensure_extra_columns(self):
        """Tự thêm cột mở rộng (pinned, health) cho DB cũ — chạy 1 lần/instance."""
        if getattr(self, "_extra_ok", False):
            return
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("ALTER TABLE channels ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE;")
                    cur.execute("ALTER TABLE channels ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMPTZ;")
                    cur.execute("ALTER TABLE session_cookies ADD COLUMN IF NOT EXISTS health JSONB;")
                    cur.execute("ALTER TABLE session_cookies ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMPTZ;")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS channel_access_requests (
                            id VARCHAR(50) PRIMARY KEY,
                            channel_id VARCHAR(50) NOT NULL,
                            requester VARCHAR(100) NOT NULL,
                            message TEXT DEFAULT '',
                            status VARCHAR(20) DEFAULT 'pending',
                            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                            resolved_by VARCHAR(100),
                            resolved_at TIMESTAMPTZ
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_access_channel ON channel_access_requests(channel_id);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_access_status ON channel_access_requests(status);")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS health_runs (
                            id VARCHAR(50) PRIMARY KEY,
                            triggered_by VARCHAR(100) DEFAULT '',
                            scope VARCHAR(50) DEFAULT 'ALL',
                            total INT DEFAULT 0,
                            status VARCHAR(20) DEFAULT 'running',
                            started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                            finished_at TIMESTAMPTZ,
                            alive INT DEFAULT 0, dead INT DEFAULT 0,
                            error INT DEFAULT 0, skipped INT DEFAULT 0, empty INT DEFAULT 0
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS health_results (
                            id SERIAL PRIMARY KEY,
                            run_id VARCHAR(50) REFERENCES health_runs(id) ON DELETE CASCADE,
                            channel_id VARCHAR(50),
                            status VARCHAR(20),
                            detail TEXT DEFAULT '',
                            checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_health_results_run ON health_results(run_id);")
                    conn.commit()
            self._extra_ok = True
        except Exception as e:
            logger.warning(f"Không tự migrate cột mở rộng PG: {e}")

    def get_accounts(self) -> List[Account]:
        # logo là cột mới — DB cũ chưa có thì fallback không logo
        results = []
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    cur.execute("SELECT id, display_name, email, recovery_email, notes, logo, created_at, updated_at FROM accounts ORDER BY id ASC;")
                    rows = cur.fetchall()
                except Exception:
                    conn.rollback()
                    cur.execute("SELECT id, display_name, email, recovery_email, notes, created_at, updated_at FROM accounts ORDER BY id ASC;")
                    rows = cur.fetchall()
                    rows = [{**r, "logo": None} for r in rows]
                for row in rows:
                    results.append(Account(
                        id=row["id"],
                        display_name=row["display_name"],
                        email=row["email"],
                        recovery_email=row["recovery_email"],
                        notes=row["notes"],
                        logo=row.get("logo"),
                        created_at=row.get("created_at"),
                        updated_at=row.get("updated_at")
                    ))
        return results

    def get_channels(
        self,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[ChannelItemView]:
        self._ensure_extra_columns()
        query = """
            SELECT
                c.id, c.account_id, c.platform, c.channel_name, c.studio_url, c.login_url, c.avatar_url, c.status,
                c.pinned, c.pinned_at,
                a.display_name AS account_display_name, a.email AS account_email,
                s.cookies_data, s.in_use_by, s.in_use_since, s.last_heartbeat, s.last_synced_at, s.updated_by, s.health
            FROM channels c
            JOIN accounts a ON c.account_id = a.id
            LEFT JOIN session_cookies s ON c.id = s.channel_id
            WHERE 1=1
        """
        params = []
        if platform and platform != "ALL":
            query += " AND c.platform = %s"
            params.append(platform)
        if account_id and account_id != "ALL":
            query += " AND c.account_id = %s"
            params.append(account_id)
        if search:
            query += " AND (c.channel_name ILIKE %s OR a.display_name ILIKE %s OR a.email ILIKE %s)"
            kw = f"%{search}%"
            params.extend([kw, kw, kw])

        query += " ORDER BY c.id ASC;"

        items = []
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                for row in cur.fetchall():
                    ch = Channel(
                        id=row["id"],
                        account_id=row["account_id"],
                        platform=parse_platform(row["platform"]),
                        channel_name=row["channel_name"],
                        studio_url=row["studio_url"],
                        login_url=row["login_url"],
                        avatar_url=row["avatar_url"],
                        status=ChannelStatus(row["status"]) if row["status"] in ChannelStatus._value2member_map_ else ChannelStatus.NOT_SETUP,
                        account_display_name=row["account_display_name"],
                        account_email=row["account_email"],
                        pinned=bool(row.get("pinned", False)),
                        pinned_at=row.get("pinned_at")
                    )
                    sess = None
                    if row["cookies_data"] is not None or row["in_use_by"] is not None:
                        cookies_raw = row["cookies_data"]
                        if isinstance(cookies_raw, str):
                            try:
                                cookies_raw = json.loads(cookies_raw)
                            except Exception:
                                pass
                        sess = SessionCookie(
                            channel_id=row["id"],
                            cookies_data=_decode_cookies(cookies_raw, row["id"]),
                            in_use_by=row["in_use_by"],
                            in_use_since=row["in_use_since"],
                            last_heartbeat=row.get("last_heartbeat"),
                            last_synced_at=row["last_synced_at"],
                            updated_by=row["updated_by"],
                            health=dict(row["health"]) if isinstance(row.get("health"), dict) else None
                        )
                    items.append(ChannelItemView(channel=ch, session=sess))
        return items

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        query = """
            SELECT c.*, a.display_name AS account_display_name, a.email AS account_email
            FROM channels c
            JOIN accounts a ON c.account_id = a.id
            WHERE c.id = %s;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (channel_id,))
                row = cur.fetchone()
                if not row:
                    return None
                self._ensure_extra_columns()
                return Channel(
                    id=row["id"],
                    account_id=row["account_id"],
                    platform=parse_platform(row["platform"]),
                    channel_name=row["channel_name"],
                    studio_url=row["studio_url"],
                    login_url=row["login_url"],
                    avatar_url=row["avatar_url"],
                    status=ChannelStatus(row["status"]) if row["status"] in ChannelStatus._value2member_map_ else ChannelStatus.NOT_SETUP,
                    account_display_name=row["account_display_name"],
                    account_email=row["account_email"],
                    pinned=bool(row.get("pinned", False)),
                    pinned_at=row.get("pinned_at")
                )

    def get_session(self, channel_id: str) -> Optional[SessionCookie]:
        query = "SELECT * FROM session_cookies WHERE channel_id = %s;"
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (channel_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cookies_raw = row["cookies_data"]
                if isinstance(cookies_raw, str):
                    try:
                        cookies_raw = json.loads(cookies_raw)
                    except Exception:
                        pass
                return SessionCookie(
                    channel_id=row["channel_id"],
                    cookies_data=_decode_cookies(cookies_raw, row["channel_id"]),
                    in_use_by=row["in_use_by"],
                    in_use_since=row["in_use_since"],
                    last_heartbeat=row.get("last_heartbeat"),
                    last_synced_at=row["last_synced_at"],
                    updated_by=row["updated_by"],
                    health=dict(row["health"]) if isinstance(row.get("health"), dict) else None
                )

    def restore_session_raw(self, channel_id: str, cookies_raw: Any, health: Any = None) -> bool:
        """Khôi phục session từ snapshot thùng rác (giữ nguyên payload đã mã hóa)."""
        self._ensure_extra_columns()
        if isinstance(cookies_raw, str):
            cookies_json = json.dumps(cookies_raw)
        else:
            cookies_json = json.dumps(cookies_raw if cookies_raw is not None else [])
        health_json = json.dumps(health) if isinstance(health, dict) else None
        query = """
            INSERT INTO session_cookies (channel_id, cookies_data, health)
            VALUES (%s, %s::jsonb, %s::jsonb)
            ON CONFLICT (channel_id) DO UPDATE SET
                cookies_data = EXCLUDED.cookies_data,
                in_use_by = NULL,
                in_use_since = NULL,
                health = EXCLUDED.health;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (channel_id, cookies_json, health_json))
                conn.commit()
                return True

    def save_health(self, channel_id: str, health: Dict[str, Any]) -> bool:
        """Lưu kết quả soi cookies (không động đến cookies/lock)."""
        self._ensure_extra_columns()
        query = """
            INSERT INTO session_cookies (channel_id, health)
            VALUES (%s, %s::jsonb)
            ON CONFLICT (channel_id) DO UPDATE SET health = EXCLUDED.health;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (channel_id, json.dumps(dict(health or {}))))
                conn.commit()
                return True

    def acquire_lock(self, channel_id: str, user_name: str) -> Tuple[bool, Optional[str]]:
        self._ensure_extra_columns()
        # Atomic lock using UPDATE ... WHERE (in_use_by IS NULL OR in_use_by = user_name)
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First check current holder
                cur.execute("SELECT in_use_by FROM session_cookies WHERE channel_id = %s;", (channel_id,))
                row = cur.fetchone()
                if row and row["in_use_by"] and row["in_use_by"] != user_name:
                    return False, row["in_use_by"]

                # Perform Upsert Lock
                upsert_query = """
                    INSERT INTO session_cookies (channel_id, in_use_by, in_use_since, last_heartbeat)
                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (channel_id) DO UPDATE
                    SET in_use_by = EXCLUDED.in_use_by,
                        in_use_since = CASE WHEN session_cookies.in_use_by IS NULL THEN CURRENT_TIMESTAMP ELSE session_cookies.in_use_since END,
                        last_heartbeat = CURRENT_TIMESTAMP
                    WHERE session_cookies.in_use_by IS NULL OR session_cookies.in_use_by = %s;
                """
                cur.execute(upsert_query, (channel_id, user_name, user_name))
                conn.commit()
                return True, None

    def heartbeat(self, channel_id: str, user_name: str) -> bool:
        self._ensure_extra_columns()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE session_cookies SET last_heartbeat = CURRENT_TIMESTAMP WHERE channel_id = %s AND in_use_by = %s;",
                    (channel_id, user_name)
                )
                conn.commit()
                return cur.rowcount > 0

    def release_lock(self, channel_id: str, user_name: str, force: bool = False) -> bool:
        self._ensure_extra_columns()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if force:
                    cur.execute(
                        "UPDATE session_cookies SET in_use_by = NULL, in_use_since = NULL, last_heartbeat = NULL WHERE channel_id = %s;",
                        (channel_id,)
                    )
                else:
                    cur.execute(
                        "UPDATE session_cookies SET in_use_by = NULL, in_use_since = NULL, last_heartbeat = NULL WHERE channel_id = %s AND in_use_by = %s;",
                        (channel_id, user_name)
                    )
                conn.commit()
                return True

    def request_access(self, channel_id: str, requester: str, message: str = "") -> Dict[str, Any]:
        self._ensure_extra_columns()
        requester = (requester or "").strip() or "Unknown"
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT in_use_by FROM session_cookies WHERE channel_id = %s;", (channel_id,))
                row = cur.fetchone()
                holder = row["in_use_by"] if row else None
                if not holder:
                    return {"success": False, "message": "Kênh đang trống, bạn có thể mở trực tiếp."}
                if holder == requester:
                    return {"success": False, "message": "Bạn đang giữ kênh này rồi."}
                cur.execute(
                    "SELECT id FROM channel_access_requests WHERE channel_id = %s AND requester = %s AND status = 'pending';",
                    (channel_id, requester)
                )
                if cur.fetchone():
                    return {"success": False, "message": "Bạn đã gửi yêu cầu rồi, vui lòng chờ duyệt."}
                req_id = f"req_{uuid.uuid4().hex[:8]}"
                cur.execute(
                    "INSERT INTO channel_access_requests (id, channel_id, requester, message, status) VALUES (%s, %s, %s, %s, 'pending');",
                    (req_id, channel_id, requester, (message or "")[:200])
                )
                conn.commit()
                return {"success": True, "request_id": req_id, "holder": holder,
                        "message": f"Đã gửi yêu cầu tới {holder}. Vui lòng chờ duyệt."}

    def list_access_requests(self, status: str = "pending") -> List[Dict[str, Any]]:
        self._ensure_extra_columns()
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if status == "ALL":
                    cur.execute(
                        """SELECT r.*, c.channel_name, s.in_use_by AS holder
                           FROM channel_access_requests r
                           LEFT JOIN channels c ON c.id = r.channel_id
                           LEFT JOIN session_cookies s ON s.channel_id = r.channel_id
                           ORDER BY r.created_at DESC LIMIT 100;"""
                    )
                else:
                    cur.execute(
                        """SELECT r.*, c.channel_name, s.in_use_by AS holder
                           FROM channel_access_requests r
                           LEFT JOIN channels c ON c.id = r.channel_id
                           LEFT JOIN session_cookies s ON s.channel_id = r.channel_id
                           WHERE r.status = %s ORDER BY r.created_at DESC LIMIT 100;""",
                        (status,)
                    )
                rows = cur.fetchall()
                out = []
                for r in rows:
                    out.append({
                        "id": r["id"],
                        "channel_id": r["channel_id"],
                        "channel_name": r.get("channel_name") or r["channel_id"],
                        "requester": r["requester"],
                        "message": r.get("message") or "",
                        "status": r["status"],
                        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                        "resolved_by": r.get("resolved_by"),
                        "resolved_at": r["resolved_at"].isoformat() if r.get("resolved_at") else None,
                        "holder": r.get("holder"),
                    })
                return out

    def resolve_access_request(self, request_id: str, approver: str, action: str) -> Dict[str, Any]:
        self._ensure_extra_columns()
        action = (action or "").lower()
        if action not in ("approve", "deny"):
            return {"success": False, "message": "Hành động không hợp lệ."}
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM channel_access_requests WHERE id = %s;", (request_id,))
                req = cur.fetchone()
                if not req:
                    return {"success": False, "message": "Không tìm thấy yêu cầu."}
                if req["status"] != "pending":
                    return {"success": False, "message": f"Yêu cầu đã được xử lý ({req['status']})."}
                if action == "deny":
                    cur.execute(
                        "UPDATE channel_access_requests SET status='denied', resolved_by=%s, resolved_at=CURRENT_TIMESTAMP WHERE id=%s;",
                        (approver, request_id)
                    )
                    conn.commit()
                    return {"success": True, "message": f"Đã từ chối yêu cầu của {req['requester']}."}
                cur.execute(
                    "UPDATE session_cookies SET in_use_by=NULL, in_use_since=NULL, last_heartbeat=NULL WHERE channel_id=%s;",
                    (req["channel_id"],)
                )
                cur.execute(
                    "UPDATE channel_access_requests SET status='approved', resolved_by=%s, resolved_at=CURRENT_TIMESTAMP WHERE id=%s;",
                    (approver, request_id)
                )
                conn.commit()
                logger.warning(f"Duyệt xin mở kênh '{req['channel_id']}': '{approver}' nhường cho '{req['requester']}'")
                return {"success": True, "message": f"Đã nhường kênh cho {req['requester']}."}

    def save_cookies(self, channel_id: str, cookies: List[Dict[str, Any]], user_name: str) -> bool:
        # MÃ HÓA trước khi ghi — cột JSONB sẽ chứa chuỗi vault thay vì mảng plaintext
        try:
            protected = secure_store.protect_json(cookies or [])
        except Exception as e:
            logger.error(f"Không mã hóa được cookies kênh '{channel_id}', HỦY lưu: {e}")
            return False
        cookies_json = json.dumps(protected)
        query = """
            INSERT INTO session_cookies (channel_id, cookies_data, in_use_by, in_use_since, last_synced_at, updated_by)
            VALUES (%s, %s::jsonb, NULL, NULL, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (channel_id) DO UPDATE SET
                cookies_data = EXCLUDED.cookies_data,
                in_use_by = NULL,
                in_use_since = NULL,
                last_synced_at = CURRENT_TIMESTAMP,
                updated_by = EXCLUDED.updated_by,
                health = NULL;
        """
        update_ch_query = "UPDATE channels SET status = 'READY', updated_at = CURRENT_TIMESTAMP WHERE id = %s;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (channel_id, cookies_json, user_name))
                cur.execute(update_ch_query, (channel_id,))
                conn.commit()
                return True

    def update_cookies_keep_lock(self, channel_id: str, cookies: List[Dict[str, Any]], user_name: str) -> bool:
        """Tự lưu cookies khi browser còn mở: giữ nguyên lock, chỉ refresh dữ liệu."""
        try:
            protected = secure_store.protect_json(cookies or [])
        except Exception as e:
            logger.error(f"Tự lưu cookies '{channel_id}' lỗi mã hóa: {e}")
            return False
        cookies_json = json.dumps(protected)
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE session_cookies SET cookies_data = %s::jsonb, health = NULL,
                       last_synced_at = CURRENT_TIMESTAMP, updated_by = %s
                       WHERE channel_id = %s AND (in_use_by IS NULL OR in_use_by = %s);""",
                    (cookies_json, user_name, channel_id, user_name)
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    logger.warning(f"Bỏ qua tự lưu cookies '{channel_id}': lock không còn thuộc về '{user_name}'")
                    return False
                cur.execute("UPDATE channels SET status = 'READY', updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                            (channel_id,))
                conn.commit()
                logger.info(f"Tự lưu {len(cookies)} cookies cho kênh đang mở {channel_id}")
                return True

    # ========================================================
    # CRUD Operations for Accounts and Channels
    # ========================================================
    def create_account(self, account: Account) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """INSERT INTO accounts (id, display_name, email, recovery_email, notes, logo, created_at, updated_at)
                           VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                           ON CONFLICT (id) DO NOTHING;""",
                        (account.id, account.display_name, account.email, account.recovery_email, account.notes, getattr(account, "logo", None))
                    )
                except Exception:
                    conn.rollback()
                    cur.execute(
                        """INSERT INTO accounts (id, display_name, email, recovery_email, notes, created_at, updated_at)
                           VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                           ON CONFLICT (id) DO NOTHING;""",
                        (account.id, account.display_name, account.email, account.recovery_email, account.notes)
                    )
                conn.commit()
                return cur.rowcount > 0

    def update_account(self, account: Account) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """UPDATE accounts
                           SET display_name = %s, email = %s, recovery_email = %s, notes = %s, logo = %s, updated_at = CURRENT_TIMESTAMP
                           WHERE id = %s;""",
                        (account.display_name, account.email, account.recovery_email, account.notes, getattr(account, "logo", None), account.id)
                    )
                except Exception:
                    conn.rollback()
                    cur.execute(
                        """UPDATE accounts
                           SET display_name = %s, email = %s, recovery_email = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
                           WHERE id = %s;""",
                        (account.display_name, account.email, account.recovery_email, account.notes, account.id)
                    )
                conn.commit()
                return cur.rowcount > 0

    def delete_account(self, account_id: str) -> bool:
        query = "DELETE FROM accounts WHERE id = %s;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (account_id,))
                conn.commit()
                return cur.rowcount > 0

    def create_channel(self, channel: Channel) -> bool:
        query = """
            INSERT INTO channels (id, account_id, platform, channel_name, studio_url, login_url, avatar_url, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'NOT_SETUP', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO NOTHING;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                plat_val = platform_value(channel.platform)
                cur.execute(query, (channel.id, channel.account_id, plat_val, channel.channel_name, channel.studio_url, channel.login_url, channel.avatar_url))
                conn.commit()
                return cur.rowcount > 0

    def update_channel(self, channel: Channel) -> bool:
        self._ensure_extra_columns()
        query = """
            UPDATE channels
            SET channel_name = %s, studio_url = %s, login_url = %s, account_id = %s,
                pinned = %s, pinned_at = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (channel.channel_name, channel.studio_url, channel.login_url,
                                    channel.account_id, bool(getattr(channel, "pinned", False)),
                                    getattr(channel, "pinned_at", None), channel.id))
                conn.commit()
                return cur.rowcount > 0

    def delete_channel(self, channel_id: str) -> bool:
        query = "DELETE FROM channels WHERE id = %s;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (channel_id,))
                conn.commit()
                return cur.rowcount > 0

    _HEALTH_STATUSES = ("alive", "dead", "error", "skipped", "empty")

    def create_health_run(self, triggered_by: str, total: int, scope: str = "ALL") -> str:
        self._ensure_extra_columns()
        run_id = f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO health_runs (id, triggered_by, scope, total, status) VALUES (%s, %s, %s, %s, 'running');",
                    (run_id, triggered_by or "", scope or "ALL", int(total or 0))
                )
                # Chỉ giữ 30 đợt gần nhất
                cur.execute(
                    "DELETE FROM health_runs WHERE id NOT IN (SELECT id FROM health_runs ORDER BY started_at DESC LIMIT 30);"
                )
                conn.commit()
                return run_id

    def append_health_result(self, run_id: str, channel_id: str, status: str, detail: str = "") -> bool:
        self._ensure_extra_columns()
        if status not in self._HEALTH_STATUSES:
            status = "error"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO health_results (run_id, channel_id, status, detail) VALUES (%s, %s, %s, %s);",
                    (run_id, channel_id, status, (detail or "")[:500])
                )
                cur.execute(f"UPDATE health_runs SET {status} = {status} + 1 WHERE id = %s;", (run_id,))
                conn.commit()
                return True

    def finish_health_run(self, run_id: str, status: str = "finished") -> bool:
        self._ensure_extra_columns()
        st = status if status in ("finished", "stopped") else "finished"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE health_runs SET status = %s, finished_at = CURRENT_TIMESTAMP WHERE id = %s;",
                    (st, run_id)
                )
                conn.commit()
                return True

    def list_health_runs(self, limit: int = 30) -> List[Dict[str, Any]]:
        self._ensure_extra_columns()
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT *, (SELECT COUNT(*) FROM health_results r WHERE r.run_id = health_runs.id) AS result_count "
                    "FROM health_runs ORDER BY started_at DESC LIMIT %s;",
                    (max(1, int(limit or 30)),)
                )
                out = []
                for r in cur.fetchall():
                    d = dict(r)
                    for k in ("started_at", "finished_at"):
                        d[k] = d[k].isoformat() if d.get(k) else None
                    d["stats"] = {k: d.pop(k, 0) for k in self._HEALTH_STATUSES}
                    out.append(d)
                return out

    def get_health_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_extra_columns()
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM health_runs WHERE id = %s;", (run_id,))
                run = cur.fetchone()
                if not run:
                    return None
                d = dict(run)
                for k in ("started_at", "finished_at"):
                    d[k] = d[k].isoformat() if d.get(k) else None
                d["stats"] = {k: d.pop(k, 0) for k in self._HEALTH_STATUSES}
                cur.execute(
                    """SELECT r.channel_id, c.channel_name, r.status, r.detail, r.checked_at
                       FROM health_results r LEFT JOIN channels c ON c.id = r.channel_id
                       WHERE r.run_id = %s ORDER BY r.id ASC;""",
                    (run_id,)
                )
                results = []
                for row in cur.fetchall():
                    rd = dict(row)
                    rd["checked_at"] = rd["checked_at"].isoformat() if rd.get("checked_at") else None
                    rd["channel_name"] = rd.get("channel_name") or rd.get("channel_id")
                    results.append(rd)
                d["results"] = results
                return d

    def reset_channel_session(self, channel_id: str) -> bool:
        query = "DELETE FROM session_cookies WHERE channel_id = %s;"
        update_ch = "UPDATE channels SET status = 'NOT_SETUP' WHERE id = %s;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (channel_id,))
                cur.execute(update_ch, (channel_id,))
                conn.commit()
                return True

    def get_cookie_vault_status(self) -> List[Dict[str, Any]]:
        query = """
            SELECT c.id, c.channel_name, s.cookies_data, s.in_use_by, s.last_synced_at
            FROM channels c LEFT JOIN session_cookies s ON c.id = s.channel_id
            ORDER BY c.id ASC;
        """
        out = []
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                for row in cur.fetchall():
                    raw = row["cookies_data"]
                    if isinstance(raw, str):
                        try:
                            raw = json.loads(raw)
                        except Exception:
                            pass
                    if isinstance(raw, list):
                        count, encrypted = len(raw), len(raw) == 0
                    elif isinstance(raw, str) and secure_store.is_protected(raw):
                        count, encrypted = len(_decode_cookies(raw, row["id"])), True
                    else:
                        count, encrypted = 0, True
                    last = row["last_synced_at"]
                    out.append({
                        "channel_id": row["id"],
                        "channel_name": row["channel_name"],
                        "cookies_count": count,
                        "encrypted": encrypted,
                        "in_use_by": row["in_use_by"],
                        "last_synced_at": last.isoformat() if last else None,
                    })
        return out

    def migrate_plaintext_cookies(self) -> Dict[str, int]:
        """Mã hóa các hàng cookies còn ở dạng mảng plaintext."""
        migrated, failed, skipped = 0, 0, 0
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT channel_id, cookies_data FROM session_cookies "
                    "WHERE jsonb_typeof(cookies_data) = 'array' AND jsonb_array_length(cookies_data) > 0;"
                )
                rows = cur.fetchall()
                for row in rows:
                    raw = row["cookies_data"]
                    if isinstance(raw, str):
                        try:
                            raw = json.loads(raw)
                        except Exception:
                            continue
                    if not isinstance(raw, list) or not raw:
                        skipped += 1
                        continue
                    try:
                        protected = secure_store.protect_json(raw)
                        cur.execute(
                            "UPDATE session_cookies SET cookies_data = to_jsonb(%s::text) WHERE channel_id = %s;",
                            (protected, row["channel_id"])
                        )
                        migrated += 1
                    except Exception as e:
                        logger.error(f"Migrate cookies '{row['channel_id']}' thất bại: {e}")
                        failed += 1
                conn.commit()
        if migrated:
            logger.info(f"Đã mã hóa {migrated} phiên cookies plaintext trên Postgres (lỗi {failed}).")
        return {"migrated": migrated, "failed": failed, "skipped": skipped}
