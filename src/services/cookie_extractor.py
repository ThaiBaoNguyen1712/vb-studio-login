import os
import sys
import json
import math
import base64
import shutil
import sqlite3
import tempfile
import time
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from src.core.logger import logger


def _unprotect_dpapi(data: bytes) -> bytes:
    """
    Decrypts DPAPI-encrypted data on Windows using CryptUnprotectData from crypt32.dll.
    Uses CryptProtectData flags: CRYPTPROTECT_UI_FORBIDDEN (0x01).
    """
    if sys.platform != "win32":
        raise OSError("Windows DPAPI is only supported on Windows platforms.")

    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte))
        ]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()

    # CRYPTPROTECT_UI_FORBIDDEN = 0x01
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0x01,
        ctypes.byref(blob_out)
    ):
        raise OSError("CryptUnprotectData failed to decrypt payload.")

    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _decode_cookie_bytes(decrypted: bytes) -> str:
    """
    Decodes decrypted cookie bytes to UTF-8 string.
    On Chromium v124+, decrypted bytes may start with a 32-byte SHA-256 integrity header.
    If binary control characters are detected in the first 32 bytes or direct decode fails,
    strips the 32-byte header.
    """
    if len(decrypted) > 32:
        # Check if first 32 bytes contain binary control characters typical of SHA-256 hash or null header
        has_binary_header = any(b < 32 and b not in (9, 10, 13) for b in decrypted[:32])
        if has_binary_header:
            try:
                return decrypted[32:].decode("utf-8")
            except UnicodeDecodeError:
                return decrypted[32:].decode("utf-8", errors="replace")

        try:
            return decrypted.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return decrypted[32:].decode("utf-8")
            except UnicodeDecodeError:
                return decrypted[32:].decode("utf-8", errors="replace")

    try:
        return decrypted.decode("utf-8")
    except UnicodeDecodeError:
        return decrypted.decode("utf-8", errors="replace")


def chromium_to_unix_epoch(expires_utc: Any) -> Optional[float]:
    """
    Converts Chromium timestamp (microseconds since 1601-01-01 UTC)
    to Unix epoch timestamp (seconds since 1970-01-01 UTC).
    Returns None for session cookies (expires_utc <= 0 or invalid).
    Formula: (expires_utc / 1_000_000.0) - 11644473600.0
    """
    if expires_utc is None:
        return None
    try:
        ts = float(expires_utc)
    except (ValueError, TypeError):
        return None

    if math.isnan(ts) or math.isinf(ts) or ts <= 0:
        return None

    unix_ts = (ts / 1_000_000.0) - 11644473600.0
    return unix_ts if unix_ts > 0 else None



class CookieExtractor:
    """
    Safe cookie extraction engine for Chromium profiles (Chrome & Edge).
    Extracts Master Key from Local State using Windows DPAPI,
    safely copies SQLite database to avoid locking conflicts,
    decrypts AES-256-GCM cookies, and normalizes them for vault storage.
    """

    @classmethod
    def get_master_key(cls, profile_path: Union[str, Path]) -> Optional[bytes]:
        """
        Extracts and decrypts the 256-bit (32-byte) AES Master Key from
        <profile_path>/Local State using Windows DPAPI (CryptUnprotectData).
        """
        profile_dir = Path(profile_path).resolve()
        candidates = [
            profile_dir / "Local State",
            profile_dir.parent / "Local State",
        ]

        local_state_file = None
        for cand in candidates:
            if cand.is_file():
                local_state_file = cand
                break

        if not local_state_file:
            logger.debug(f"Local State không tồn tại tại '{profile_dir}'")
            return None

        try:
            with open(local_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            encrypted_key_b64 = data.get("os_crypt", {}).get("encrypted_key")
            if not encrypted_key_b64:
                logger.debug(f"Không tìm thấy 'os_crypt.encrypted_key' trong '{local_state_file}'")
                return None

            raw_key = base64.b64decode(encrypted_key_b64)
            if raw_key.startswith(b"DPAPI"):
                encrypted_payload = raw_key[5:]
            else:
                encrypted_payload = raw_key

            master_key = _unprotect_dpapi(encrypted_payload)
            return master_key
        except Exception as e:
            logger.warning(f"Lỗi khi giải mã Master Key từ '{local_state_file}': {e}")
            return None

    @classmethod
    def decrypt_cookie_value(cls, encrypted_blob: bytes, master_key: Optional[bytes]) -> str:
        """
        Decrypts an encrypted cookie value blob from Chromium SQLite cookies table.
        - v10 / v11 prefix: AES-256-GCM with master key (nonce: 12 bytes, ciphertext + tag: rest).
        - Direct DPAPI fallback for older Chromium versions.
        - Plaintext fallback if unencrypted.
        """
        if not encrypted_blob:
            return ""

        # Modern Chromium (v80+): AES-256-GCM
        if encrypted_blob.startswith(b"v10") or encrypted_blob.startswith(b"v11"):
            if not master_key:
                logger.debug("Không thể giải mã cookie AES-GCM: master_key là None")
                return ""
            try:
                nonce = encrypted_blob[3:15]
                ciphertext_and_tag = encrypted_blob[15:]
                aesgcm = AESGCM(master_key)
                decrypted = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
                return _decode_cookie_bytes(decrypted)
            except Exception as e:
                logger.debug(f"Giải mã AES-GCM thất bại: {e}")
                return ""

        # Legacy Chromium (<v80): Windows DPAPI direct encryption
        if sys.platform == "win32":
            try:
                decrypted = _unprotect_dpapi(encrypted_blob)
                return _decode_cookie_bytes(decrypted)
            except Exception:
                pass

        # Plaintext fallback
        try:
            val = encrypted_blob.decode("utf-8")
            if any(ord(c) < 32 and c not in "\t\n\r" for c in val):
                return ""
            if "\ufffd" in val:
                return ""
            return val
        except Exception:
            return ""

    @classmethod
    def extract_cookies_for_profile(cls, profile_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Safely extracts cookies from a Chromium profile directory.
        1. Finds SQLite Cookies database and Local State Master Key.
        2. Copies Cookies file (and WAL/journal if present) to a temporary directory.
        3. Queries SQLite cookies table in read-only mode (with standard fallback for hot journal).
        4. Decrypts encrypted_value using AES-256-GCM / DPAPI.
        5. Converts 1601 FILETIME timestamps to Unix epoch timestamps.
        6. Returns list of standardized cookie dictionaries.
        """
        profile_dir = Path(profile_path).resolve()
        if not profile_dir.exists():
            logger.debug(f"Thư mục profile không tồn tại: {profile_dir}")
            return []

        # Locate Cookies SQLite file
        candidates = [
            profile_dir / "Default" / "Network" / "Cookies",
            profile_dir / "Network" / "Cookies",
            profile_dir / "Default" / "Cookies",
            profile_dir / "Cookies",
        ]

        cookie_file = None
        for cand in candidates:
            if cand.is_file():
                cookie_file = cand
                break

        if not cookie_file:
            logger.debug(f"Không tìm thấy file Cookies SQLite trong '{profile_dir}'")
            return []

        # Retrieve Master Key
        master_key = cls.get_master_key(profile_dir)

        cookies: List[Dict[str, Any]] = []

        # Safe snapshot to temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            temp_db = temp_dir_path / "Cookies"

            # Copy main Cookies file with retry loop
            copied = False
            for attempt in range(3):
                try:
                    shutil.copy2(cookie_file, temp_db)
                    copied = True
                    break
                except Exception:
                    time.sleep(0.1)

            if not copied:
                logger.warning(f"Không thể sao chép file Cookies sang thư mục tạm: {cookie_file}")
                return []

            # Copy associated WAL / journal / SHM files if present
            for extra_suffix in ("-wal", "-journal", "-shm"):
                extra_src = cookie_file.with_name(f"{cookie_file.name}{extra_suffix}")
                if extra_src.is_file():
                    try:
                        shutil.copy2(extra_src, temp_dir_path / f"Cookies{extra_suffix}")
                    except Exception:
                        pass

            # Query SQLite database in read-only mode, with fallback for hot WAL/journal recovery
            conn = None
            try:
                try:
                    uri = f"file:{temp_db.as_posix()}?mode=ro"
                    conn = sqlite3.connect(uri, uri=True)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM cookies")
                    rows = cursor.fetchall()
                except sqlite3.OperationalError:
                    if conn:
                        try:
                            conn.close()
                        except Exception:
                            pass
                    conn = sqlite3.connect(str(temp_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM cookies")
                    rows = cursor.fetchall()

                samesite_map = {
                    2: "Strict",
                    1: "Lax",
                    0: "None",
                    -1: "Lax"
                }

                for row in rows:
                    keys = row.keys()
                    name = row["name"] if "name" in keys else ""
                    raw_val = row["value"] if "value" in keys else ""
                    encrypted_blob = row["encrypted_value"] if "encrypted_value" in keys else b""

                    if encrypted_blob:
                        val = cls.decrypt_cookie_value(encrypted_blob, master_key)
                        if not val and raw_val:
                            val = raw_val
                    else:
                        val = raw_val or ""

                    domain = row["host_key"] if "host_key" in keys else ""
                    path = row["path"] if "path" in keys else "/"
                    expires_utc = row["expires_utc"] if "expires_utc" in keys else 0

                    expires = chromium_to_unix_epoch(expires_utc)

                    http_only = bool(row["is_httponly"]) if "is_httponly" in keys else False
                    secure = bool(row["is_secure"]) if "is_secure" in keys else False

                    samesite_raw = row["samesite"] if "samesite" in keys else -1
                    same_site = samesite_map.get(samesite_raw, "Lax")

                    if name and domain:
                        cookies.append({
                            "name": str(name),
                            "value": str(val),
                            "domain": str(domain),
                            "path": str(path) if path else "/",
                            "expires": expires,
                            "httpOnly": http_only,
                            "secure": secure,
                            "sameSite": same_site,
                        })

            except Exception as dbe:
                logger.warning(f"Lỗi khi truy vấn SQLite cookies từ '{cookie_file}': {dbe}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        return cookies


# Module-level aliases for convenient importing
extract_cookies_for_profile = CookieExtractor.extract_cookies_for_profile
get_master_key = CookieExtractor.get_master_key
decrypt_cookie_value = CookieExtractor.decrypt_cookie_value


# Ensure SessionService.prune_cookies filters out empty names for complete compatibility
try:
    from src.services.session_service import SessionService

    _orig_prune_cookies = SessionService.prune_cookies

    @classmethod
    def _safe_prune_cookies(cls, cookies):
        filtered = [
            c for c in (cookies or [])
            if not isinstance(c, dict) or (c.get("name") and str(c.get("name")).strip() != "")
        ]
        return _orig_prune_cookies.__func__(cls, filtered)

    SessionService.prune_cookies = _safe_prune_cookies
except Exception:
    pass
