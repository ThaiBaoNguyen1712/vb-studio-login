import os
import sys
import json
import sqlite3
import base64
import ctypes
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    AESGCM = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
SPEC_PATHS = [PROJECT_ROOT / "VB-Login.spec", PROJECT_ROOT / "VBLogin.spec"]
BUILD_SCRIPTS_PATHS = [
    PROJECT_ROOT / "build_exe.ps1",
    PROJECT_ROOT / ".github" / "workflows" / "release.yml"
]

def is_windows() -> bool:
    return sys.platform.startswith("win")

def dpapi_encrypt(data: bytes) -> bytes:
    """Encrypts bytes using Windows DPAPI CryptProtectData."""
    if not is_windows():
        return b"MOCK_DPAPI_" + data

    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte))
        ]

    buf = (ctypes.c_byte * len(data))(*data)
    blob_in = DATA_BLOB(len(data), buf)
    blob_out = DATA_BLOB()

    # CryptProtectData(pDataIn, szDataDescr, pOptionalEntropy, pvReserved, pPromptStruct, dwFlags, pDataOut)
    res = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out)
    )
    if not res:
        raise RuntimeError(f"CryptProtectData failed with error {ctypes.GetLastError()}")

    try:
        encrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return encrypted_bytes
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)

def dpapi_decrypt(data: bytes) -> bytes:
    """Decrypts bytes using Windows DPAPI CryptUnprotectData."""
    if not is_windows():
        if data.startswith(b"MOCK_DPAPI_"):
            return data[len(b"MOCK_DPAPI_"):]
        return data

    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte))
        ]

    buf = (ctypes.c_byte * len(data))(*data)
    blob_in = DATA_BLOB(len(data), buf)
    blob_out = DATA_BLOB()

    res = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out)
    )
    if not res:
        raise RuntimeError(f"CryptUnprotectData failed with error {ctypes.GetLastError()}")

    try:
        decrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return decrypted_bytes
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)

def create_synthetic_profile(
    profile_dir: Path,
    master_key: Optional[bytes] = None,
    cookies: Optional[List[Dict[str, Any]]] = None,
    header_32: bool = False,
    with_wal: bool = False,
    with_journal: bool = False,
    subpath: str = "Default/Network"
) -> Path:
    """
    Creates a realistic Chromium profile directory structure with:
    - Local State containing DPAPI-encrypted 256-bit AES master key
    - <subpath>/Cookies SQLite database with cookies table populated
    """
    profile_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create Local State
    if master_key is not None:
        raw_dpapi = dpapi_encrypt(master_key)
        encrypted_key_payload = b"DPAPI" + raw_dpapi
        b64_key = base64.b64encode(encrypted_key_payload).decode("ascii")
        local_state_data = {
            "os_crypt": {
                "encrypted_key": b64_key
            }
        }
        local_state_file = profile_dir / "Local State"
        local_state_file.write_text(json.dumps(local_state_data), encoding="utf-8")

    # 2. Create Cookies SQLite DB
    cookies_dir = profile_dir / subpath
    cookies_dir.mkdir(parents=True, exist_ok=True)
    cookies_db_path = cookies_dir / "Cookies"

    conn = sqlite3.connect(str(cookies_db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE cookies (
            creation_utc INTEGER NOT NULL,
            host_key TEXT NOT NULL,
            top_frame_site_key TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            encrypted_value BLOB NOT NULL,
            path TEXT NOT NULL,
            expires_utc INTEGER NOT NULL,
            is_secure INTEGER NOT NULL,
            is_httponly INTEGER NOT NULL,
            last_access_utc INTEGER NOT NULL DEFAULT 0,
            has_expires INTEGER NOT NULL DEFAULT 1,
            is_persistent INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 1,
            samesite INTEGER NOT NULL DEFAULT -1,
            source_scheme INTEGER NOT NULL DEFAULT 2,
            source_port INTEGER NOT NULL DEFAULT 443,
            is_same_party INTEGER NOT NULL DEFAULT 0,
            last_update_utc INTEGER NOT NULL DEFAULT 0
        )
    """)

    if cookies:
        for ck in cookies:
            c_name = ck.get("name", "test_cookie")
            c_val = ck.get("value", "sample_val")
            c_host = ck.get("domain", ".google.com")
            c_path = ck.get("path", "/")
            c_secure = 1 if ck.get("secure", True) else 0
            c_http_only = 1 if ck.get("httpOnly", False) else 0
            c_samesite = ck.get("sameSite", -1)
            if isinstance(c_samesite, str):
                c_samesite = {"none": 0, "lax": 1, "strict": 2}.get(c_samesite.lower(), -1)

            # Calculate expires_utc from Unix timestamp
            unix_exp = ck.get("expires", 0.0)
            if unix_exp and unix_exp > 0:
                expires_utc = int((unix_exp + 11644473600.0) * 1_000_000)
            else:
                expires_utc = 0

            # Encryption handling
            is_plaintext = ck.get("plaintext", False)
            if master_key and not is_plaintext and AESGCM is not None:
                nonce = os.urandom(12)
                raw_payload = c_val.encode("utf-8")
                if header_32 or ck.get("header_32", False):
                    # Chromium 124+ 32-byte integrity signature prefix
                    raw_payload = b"\x00" * 32 + raw_payload
                aes = AESGCM(master_key)
                ciphertext = aes.encrypt(nonce, raw_payload, None)
                encrypted_blob = b"v10" + nonce + ciphertext
                plain_val = ""
            else:
                encrypted_blob = b""
                plain_val = c_val

            cursor.execute("""
                INSERT INTO cookies (
                    creation_utc, host_key, top_frame_site_key, name, value,
                    encrypted_value, path, expires_utc, is_secure, is_httponly,
                    last_access_utc, has_expires, is_persistent, priority, samesite,
                    source_scheme, source_port, is_same_party, last_update_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                13380000000000000, c_host, "", c_name, plain_val,
                encrypted_blob, c_path, expires_utc, c_secure, c_http_only,
                13380000000000000, 1 if expires_utc > 0 else 0, 1, 1, c_samesite,
                2, 443, 0, 13380000000000000
            ))

    if with_wal:
        conn.execute("PRAGMA journal_mode=WAL")

    conn.commit()
    conn.close()

    if with_journal:
        # For testing journal copying, a valid journal header or dummy file when not in WAL mode
        pass

    return profile_dir


class DummyProcess:
    """Mock process object simulating subprocess.Popen."""
    def __init__(self, pid: int = 12345, args: Optional[List[str]] = None):
        self.pid = pid
        self.args = args or []
        self.returncode = None
        self._terminated = False

    def poll(self) -> Optional[int]:
        return self.returncode

    def wait(self, timeout: Optional[float] = None) -> int:
        if self.returncode is None:
            if timeout is not None:
                import time
                time.sleep(min(timeout, 0.02))
                raise subprocess.TimeoutExpired(self.args, timeout)
            self.returncode = 0
        return self.returncode

    def terminate(self) -> None:
        self._terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self._terminated = True
        self.returncode = -9
