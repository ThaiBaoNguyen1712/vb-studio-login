"""
Secure vault for sensitive data at rest (browser cookies, tokens).

Strategy (Windows-first, this app ships on WebView2/Windows):
  1. Windows DPAPI (CryptProtectData, user scope) via ctypes — no key to
     manage, only the same Windows user can decrypt. No new dependency.
  2. Fallback: Fernet (AES-128-CBC + HMAC) with a machine-bound key derived
     via PBKDF2 from (machine id + username) and a random per-install salt
     file. Used on non-Windows or if DPAPI fails.

Wire format (string stored in JSON / Postgres JSONB):
  "$DPAPI$<base64>"   or   "$FERNET$<token>"

Legacy plaintext (list/dict) is still readable so old databases keep
working — it gets re-encrypted on the next save or via an explicit
migration. Plaintext is NEVER written by new code.
"""
import base64
import binascii
import getpass
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

DPAPI_PREFIX = "$DPAPI$"
FERNET_PREFIX = "$FERNET$"

_ENTROPY = b"VB-STUDIO-Login|cookie-vault|v1"


def is_protected(value) -> bool:
    return (
        isinstance(value, str)
        and (value.startswith(DPAPI_PREFIX) or value.startswith(FERNET_PREFIX))
    )


def protect(data: bytes) -> str:
    """Encrypt bytes, return storable string. Raises on total failure."""
    if sys.platform == "win32":
        try:
            return DPAPI_PREFIX + _dpapi_protect(data)
        except Exception:
            pass  # fall through to Fernet
    return FERNET_PREFIX + _fernet_protect(data)


def unprotect(token: str) -> bytes:
    if token.startswith(DPAPI_PREFIX):
        return _dpapi_unprotect(token[len(DPAPI_PREFIX):])
    if token.startswith(FERNET_PREFIX):
        return _fernet_unprotect(token[len(FERNET_PREFIX):])
    raise ValueError("Chuỗi không phải dữ liệu vault đã mã hóa.")


def protect_json(obj) -> str:
    return protect(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def unprotect_json(token: str):
    return json.loads(unprotect(token).decode("utf-8"))


# ============================================================
# Windows DPAPI (ctypes, stdlib only)
# ============================================================
def _dpapi_blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    blob_entropy = DATA_BLOB()
    blob_out = DATA_BLOB()
    entropy_buf = None
    if _ENTROPY:
        entropy_buf = ctypes.create_string_buffer(_ENTROPY, len(_ENTROPY))
        blob_entropy = DATA_BLOB(len(_ENTROPY),
                                 ctypes.cast(entropy_buf, ctypes.POINTER(ctypes.c_byte)))
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptProtectData(
        ctypes.byref(blob_in), None,
        ctypes.byref(blob_entropy) if _ENTROPY else None,
        None, None, 0x01, ctypes.byref(blob_out)
    ):
        raise OSError("CryptProtectData thất bại.")
    try:
        protected = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    # keep refs alive until here
    _ = (buf, entropy_buf)
    return base64.b64encode(protected).decode("ascii")


def _dpapi_protect(data: bytes) -> str:
    return _dpapi_blob(data)


def _dpapi_unprotect(b64: str) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))]

    try:
        raw = base64.b64decode(b64.encode("ascii"))
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"Vault base64 không hợp lệ: {e}")
    buf = ctypes.create_string_buffer(raw, len(raw))
    blob_in = DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    entropy_buf = ctypes.create_string_buffer(_ENTROPY, len(_ENTROPY))
    blob_entropy = DATA_BLOB(len(_ENTROPY),
                             ctypes.cast(entropy_buf, ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None,
        ctypes.byref(blob_entropy),
        None, None, 0x01, ctypes.byref(blob_out)
    ):
        raise OSError("CryptUnprotectData thất bại (sai user/máy hoặc dữ liệu hỏng).")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


# ============================================================
# Fernet fallback (needs `cryptography` package)
# ============================================================
def _vault_salt_file() -> Path:
    from src.core.config import Config
    Config.ensure_directories()
    return Config.DATA_DIR / ".vault.salt"


def _fernet_key() -> bytes:
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as e:
        raise RuntimeError(
            "Thiếu gói 'cryptography' cho vault fallback. Cài: pip install cryptography"
        ) from e
    salt_file = _vault_salt_file()
    if salt_file.exists():
        salt = salt_file.read_bytes()
    else:
        salt = os.urandom(16)
        salt_file.write_bytes(salt)
        try:
            os.chmod(salt_file, 0o600)
        except Exception:
            pass
    machine = f"{uuid.getnode()}|{platform_node()}|{getpass.getuser()}".encode("utf-8")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000)
    return base64.urlsafe_b64encode(kdf.derive(machine))


def platform_node() -> str:
    import platform
    try:
        return platform.node() or "unknown-host"
    except Exception:
        return "unknown-host"


def _fernet_protect(data: bytes) -> str:
    from cryptography.fernet import Fernet
    return Fernet(_fernet_key()).encrypt(data).decode("ascii")


def _fernet_unprotect(token: str) -> bytes:
    from cryptography.fernet import Fernet, InvalidToken
    try:
        return Fernet(_fernet_key()).decrypt(token.encode("ascii"))
    except InvalidToken as e:
        raise ValueError("Vault token sai khóa/hỏng (khác máy hoặc salt đã đổi).") from e
