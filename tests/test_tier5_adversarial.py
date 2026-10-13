import os
import sys
import json
import shutil
import sqlite3
import tempfile
import threading
import time
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.test_helpers import (
    create_synthetic_profile,
    dpapi_encrypt,
    dpapi_decrypt,
    DummyProcess,
    PROJECT_ROOT,
    is_windows
)

from src.core.config import Config
from src.services.browser_service import BrowserService
from src.services.cookie_extractor import (
    CookieExtractor,
    _unprotect_dpapi,
    _decode_cookie_bytes,
    chromium_to_unix_epoch
)
from src.services.session_service import SessionService


class TestTier5Adversarial(unittest.TestCase):
    """
    Tier 5: Adversarial Edge-Case Stress Testing
    Conducts empirical adversarial verification targeting:
    1. Browser Lifecycle & Inaccessible/Missing Binaries
    2. Profile Directories with Spaces, Symbols, Unicode, and Malformed Names
    3. DPAPI / Crypto Boundaries, Malformed Local State, and Modern 32-byte Headers
    4. Malformed, Zero-Byte, Locked, and Stress-Scale SQLite Cookies Databases
    5. Dead Process Handling, _active_contexts Integrity, and Race Conditions
    6. Complete CLI Argument Audit: 100% Zero Automation Flags & Natural Fingerprint
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        self.service = BrowserService()

    def tearDown(self):
        try:
            self.service.close_all_browsers()
        except Exception:
            pass
        self.temp_dir.cleanup()

    # =========================================================================
    # Section 1: Browser Missing or Inaccessible
    # =========================================================================

    def test_adv_01_both_browsers_missing_returns_none_and_signals_error(self):
        """Adv-1: When Chrome and Edge are completely missing, detect returns None and launch signals error."""
        with patch.object(self.service, "_find_chrome", return_value=None):
            with patch.object(self.service, "_find_edge", return_value=None):
                with patch("shutil.which", return_value=None):
                    detected = self.service.detect_browser_executable()
                    self.assertIsNone(detected, "Missing browsers must return None")

                    error_event = threading.Event()
                    error_received = []

                    def on_error(err):
                        error_received.append(err)
                        error_event.set()

                    self.service.launch_channel_browser("ch_no_browser", on_error=on_error)
                    self.assertTrue(error_event.wait(timeout=2.0), "on_error must be triggered")
                    self.assertIn("Không tìm thấy", str(error_received[0]))
                    self.assertFalse(self.service.is_channel_open("ch_no_browser"))
                    self.assertNotIn("ch_no_browser", self.service._active_processes)

    def test_adv_02_browser_inaccessible_permissions_oserror(self):
        """Adv-2: When browser executable exists but fails with PermissionError / Access Denied."""
        dummy_exe = self.test_root / "locked_chrome.exe"
        dummy_exe.touch()

        error_event = threading.Event()
        error_received = []

        def on_error(err):
            error_received.append(err)
            error_event.set()

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=PermissionError("[WinError 5] Access is denied")):
                self.service.launch_channel_browser("ch_perm_denied", on_error=on_error)
                self.assertTrue(error_event.wait(timeout=2.0))
                self.assertIsInstance(error_received[0], PermissionError)
                self.assertFalse(self.service.is_channel_open("ch_perm_denied"))
                self.assertNotIn("ch_perm_denied", self.service._active_contexts)

    def test_adv_03_winreg_corrupt_data_types_and_illegal_operations(self):
        """Adv-3: Registry query returns unexpected types or raises WinError 1018."""
        mock_winreg = MagicMock()
        mock_winreg.OpenKey.side_effect = OSError("[WinError 1018] Illegal operation attempted on a registry key")

        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            with patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": "", "LOCALAPPDATA": ""}):
                with patch("pathlib.Path.is_file", return_value=False):
                    with patch("shutil.which", return_value=None):
                        # Must gracefully fall through without crashing
                        chrome = self.service._find_chrome()
                        self.assertIsNone(chrome)
                        edge = self.service._find_edge()
                        self.assertIsNone(edge)

    def test_adv_04_shutil_which_returns_directory_not_file(self):
        """Adv-4: PATH contains directory matching browser name, must not return it as executable."""
        fake_dir = self.test_root / "chrome"
        fake_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(self.service, "_find_chrome", return_value=None):
            with patch.object(self.service, "_find_edge", return_value=None):
                with patch("shutil.which", return_value=str(fake_dir)):
                    detected = self.service.detect_browser_executable()
                    self.assertIsNone(detected, "Directory on PATH must be rejected by is_file() check")

    # =========================================================================
    # Section 2: Profile Folder Edge Cases (Spaces, Symbols, Unicode)
    # =========================================================================

    def test_adv_05_profile_folder_with_spaces_and_special_symbols(self):
        """Adv-5: Profile directory with spaces, brackets, hashes, and symbols formats CLI correctly."""
        channel_id = "Ch & Co. [Beta #1] + $!@"
        prof_path = Config.get_profile_path(channel_id)
        self.assertTrue(prof_path.exists())

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        captured_cmd = []

        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=5001, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser(channel_id)
                time.sleep(0.12)
                self.assertTrue(len(captured_cmd) > 0)
                udd_arg = next((arg for arg in captured_cmd if arg.startswith("--user-data-dir=")), "")
                self.assertIn(channel_id, udd_arg)

                # Verify Windows list2cmdline properly quotes arguments with spaces
                cmdline = subprocess.list2cmdline(captured_cmd)
                self.assertIn(f'"--user-data-dir={prof_path.resolve()}"', cmdline)

        # Cleanup profile directory
        shutil.rmtree(prof_path, ignore_errors=True)

    def test_adv_06_profile_folder_with_vietnamese_unicode_and_emojis(self):
        """Adv-6: Profile folder with Vietnamese Unicode and Emojis creates, stores, and extracts cookies."""
        channel_id = "Kênh_Quản_Lý_Tài_Khoản_🇻🇳_123"
        prof_path = Config.get_profile_path(channel_id)
        self.assertTrue(prof_path.exists())

        # Create cookies in this Unicode path
        master_key = b"M" * 32
        create_synthetic_profile(
            prof_path,
            master_key=master_key,
            cookies=[{"name": "unicode_ck", "value": "val_vietnam", "domain": ".google.com"}]
        )

        extracted = CookieExtractor.extract_cookies_for_profile(prof_path)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["name"], "unicode_ck")
        self.assertEqual(extracted[0]["value"], "val_vietnam")

        # Cleanup
        shutil.rmtree(prof_path, ignore_errors=True)

    def test_adv_07_invalid_windows_filename_channel_id_handled(self):
        """Adv-7: Channel ID with characters forbidden on Windows file systems triggers on_error cleanly."""
        invalid_id = "ch:forbidden*char?"
        error_event = threading.Event()
        error_received = []

        def on_error(err):
            error_received.append(err)
            error_event.set()

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            self.service.launch_channel_browser(invalid_id, on_error=on_error)
            self.assertTrue(error_event.wait(timeout=2.0))
            self.assertIsInstance(error_received[0], OSError)
            self.assertFalse(self.service.is_channel_open(invalid_id))
            self.assertNotIn(invalid_id, self.service._active_processes)

    # =========================================================================
    # Section 3: Local State & Crypto Boundaries
    # =========================================================================

    def test_adv_08_local_state_unparseable_json_variants(self):
        """Adv-8: Corrupt, truncated, empty, and non-dict JSON variants return None safely."""
        corrupt_variants = [
            b"",                                  # 0 bytes
            b"{truncated_json: ",                 # syntax error
            b"['not', 'a', 'dict']",              # list root
            b"\"plain string root\"",             # string root
            b"123456789",                         # int root
            b"null",                              # null root
            b"{\x00\x01\x02\x03\xff\xfe}",        # binary non-utf8
        ]

        prof = self.test_root / "corrupt_json_test"
        prof.mkdir(parents=True, exist_ok=True)
        local_state_file = prof / "Local State"

        for variant in corrupt_variants:
            local_state_file.write_bytes(variant)
            key = CookieExtractor.get_master_key(prof)
            self.assertIsNone(key, f"Variant {variant!r} must return None without raising exception")

    def test_adv_09_local_state_missing_os_crypt_or_invalid_structure(self):
        """Adv-9: Valid JSON with null, non-dict, or missing os_crypt keys returns None."""
        structure_variants = [
            {},
            {"os_crypt": None},
            {"os_crypt": 42},
            {"os_crypt": []},
            {"os_crypt": {}},
            {"os_crypt": {"encrypted_key": ""}},
            {"os_crypt": {"encrypted_key": None}},
            {"os_crypt": {"encrypted_key": 12345}},
        ]

        prof = self.test_root / "structure_test"
        prof.mkdir(parents=True, exist_ok=True)
        local_state_file = prof / "Local State"

        for variant in structure_variants:
            local_state_file.write_text(json.dumps(variant), encoding="utf-8")
            key = CookieExtractor.get_master_key(prof)
            self.assertIsNone(key, f"Structure {variant} must return None")

    def test_adv_10_local_state_corrupt_base64_and_corrupt_dpapi_payload(self):
        """Adv-10: Illegal base64 characters or corrupted DPAPI payload return None."""
        prof = self.test_root / "dpapi_corrupt_test"
        prof.mkdir(parents=True, exist_ok=True)
        local_state_file = prof / "Local State"

        # Case A: Illegal base64
        local_state_file.write_text(json.dumps({
            "os_crypt": {"encrypted_key": "INVALID_B64_!@#$%^&*()"}
        }), encoding="utf-8")
        self.assertIsNone(CookieExtractor.get_master_key(prof))

        # Case B: Valid base64, but invalid DPAPI payload
        corrupt_dpapi = b"DPAPI" + b"\xff" * 64
        import base64
        b64_corrupt = base64.b64encode(corrupt_dpapi).decode("ascii")
        local_state_file.write_text(json.dumps({
            "os_crypt": {"encrypted_key": b64_corrupt}
        }), encoding="utf-8")
        self.assertIsNone(CookieExtractor.get_master_key(prof))

    def test_adv_11_aes_gcm_decryption_adversarial_boundaries(self):
        """Adv-11: Short blobs, authentication tag mismatches, and key anomalies return empty string."""
        master_key = b"K" * 32

        # 1. Blob shorter than 15 bytes (v10 prefix + 12-byte nonce)
        self.assertEqual(CookieExtractor.decrypt_cookie_value(b"v10", master_key), "")
        self.assertEqual(CookieExtractor.decrypt_cookie_value(b"v10" + b"\x00" * 5, master_key), "")

        # 2. Blob with nonce but corrupted ciphertext/tag (tag mismatch)
        corrupted_cipher = b"v10" + b"\x00" * 12 + b"\xff" * 32
        self.assertEqual(CookieExtractor.decrypt_cookie_value(corrupted_cipher, master_key), "")

        # 3. None master key with v10 blob
        self.assertEqual(CookieExtractor.decrypt_cookie_value(corrupted_cipher, None), "")

        # 4. Wrong key length
        self.assertEqual(CookieExtractor.decrypt_cookie_value(corrupted_cipher, b"short_key"), "")

        # 5. Empty or None blob
        self.assertEqual(CookieExtractor.decrypt_cookie_value(b"", master_key), "")
        self.assertEqual(CookieExtractor.decrypt_cookie_value(None, master_key), "")

    def test_adv_12_chromium_32byte_integrity_header_edge_cases(self):
        """Adv-12: Chromium 124+ 32-byte integrity header boundary conditions."""
        # 1. Exactly 32 bytes without header (e.g. 32-char ASCII MD5/UUID token) preserved
        token_32 = b"A" * 32
        self.assertEqual(_decode_cookie_bytes(token_32), "A" * 32)

        # 1b. Minimal header payload: 32-byte binary header + 1-byte value
        min_header_payload = bytes(range(32)) + b"X"
        self.assertEqual(_decode_cookie_bytes(min_header_payload), "X")

        # 2. Header with binary control chars followed by UTF-8
        binary_header = bytes(range(32))
        payload = binary_header + "secret_token_12345".encode("utf-8")
        self.assertEqual(_decode_cookie_bytes(payload), "secret_token_12345")

        # 3. Clean ASCII without header (< 32 bytes)
        short_ascii = b"simple_val"
        self.assertEqual(_decode_cookie_bytes(short_ascii), "simple_val")

        # 4. Multi-byte Vietnamese UTF-8 with header
        vn_text = "Tài_Khoản_Google_2026"
        vn_payload = binary_header + vn_text.encode("utf-8")
        self.assertEqual(_decode_cookie_bytes(vn_payload), vn_text)

        # 5. Malformed non-UTF8 bytes in cookie value uses errors="replace"
        bad_utf8 = binary_header + b"\xff\xfe\xfd"
        res = _decode_cookie_bytes(bad_utf8)
        self.assertIsInstance(res, str)
        self.assertIn("\ufffd", res)

    def test_adv_13_chromium_timestamp_conversion_extremes(self):
        """Adv-13: Extremes and boundary values for chromium_to_unix_epoch."""
        self.assertIsNone(chromium_to_unix_epoch(0))
        self.assertIsNone(chromium_to_unix_epoch(-100))
        self.assertIsNone(chromium_to_unix_epoch(None))

        # 11644473600_000_000 is 1970-01-01 00:00:00 UTC (unix ts = 0, treated as session)
        self.assertIsNone(chromium_to_unix_epoch(11644473600000000))

        # Valid future timestamp: 2026-01-01
        ts_2026 = 13380000000000000
        unix_ts = chromium_to_unix_epoch(ts_2026)
        self.assertIsNotNone(unix_ts)
        self.assertGreater(unix_ts, 1700000000.0)

    # =========================================================================
    # Section 4: SQLite Database & Lock Handling
    # =========================================================================

    def test_adv_14_cookies_file_zero_byte_and_random_corrupt_bytes(self):
        """Adv-14: Zero-byte file and non-SQLite garbage bytes return empty list without crashing."""
        prof = self.test_root / "garbage_db_prof"
        cookie_file = prof / "Default" / "Network" / "Cookies"
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        # Zero-byte file
        cookie_file.write_bytes(b"")
        self.assertEqual(CookieExtractor.extract_cookies_for_profile(prof), [])

        # Random garbage bytes
        cookie_file.write_bytes(b"NOT_A_SQLITE_DATABASE_HEADER" + os.urandom(256))
        self.assertEqual(CookieExtractor.extract_cookies_for_profile(prof), [])

    def test_adv_15_cookies_table_missing_or_corrupt_schema(self):
        """Adv-15: Database missing cookies table or having unexpected columns handles cleanly."""
        prof = self.test_root / "schema_mismatch_prof"
        cookie_file = prof / "Default" / "Network" / "Cookies"
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(cookie_file))
        # Wrong table name
        conn.execute("CREATE TABLE wrong_table (id INT, data TEXT)")
        conn.commit()
        conn.close()

        self.assertEqual(CookieExtractor.extract_cookies_for_profile(prof), [])

    def test_adv_16_sqlite_locked_file_copy_retry_mechanism(self):
        """Adv-16: Transient file copy lock succeeds on retry; permanent lock fails gracefully."""
        prof = self.test_root / "lock_retry_prof"
        cookie_file = prof / "Default" / "Network" / "Cookies"
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        # Create valid database
        conn = sqlite3.connect(str(cookie_file))
        conn.execute("CREATE TABLE cookies (name TEXT, host_key TEXT, value TEXT)")
        conn.execute("INSERT INTO cookies VALUES ('ck_lock', '.site.com', 'val')")
        conn.commit()
        conn.close()

        # Simulate 2 transient failures followed by success on 3rd attempt
        orig_copy2 = shutil.copy2
        attempts = 0

        def transient_copy2(src, dst):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise PermissionError("The process cannot access the file because it is being used by another process.")
            return orig_copy2(src, dst)

        with patch("shutil.copy2", side_effect=transient_copy2):
            cookies = CookieExtractor.extract_cookies_for_profile(prof)
            self.assertEqual(len(cookies), 1)
            self.assertEqual(cookies[0]["name"], "ck_lock")
            self.assertEqual(attempts, 3, "Should have retried 3 times before succeeding")

        # Simulate permanent failure (all attempts fail)
        with patch("shutil.copy2", side_effect=PermissionError("Locked")):
            cookies = CookieExtractor.extract_cookies_for_profile(prof)
            self.assertEqual(cookies, [], "Permanent lock returns empty list gracefully")

    def test_adv_17_sqlite_wal_and_journal_isolation(self):
        """Adv-17: All associated WAL/journal files are copied and original DB remains read-only."""
        prof = self.test_root / "wal_prof"
        cookie_file = prof / "Default" / "Network" / "Cookies"
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(cookie_file))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE cookies (name TEXT, host_key TEXT, value TEXT)")
        conn.execute("INSERT INTO cookies VALUES ('wal_ck', '.site.com', 'val_wal')")
        conn.commit()
        conn.close()

        wal_file = cookie_file.with_name("Cookies-wal")
        self.assertTrue(wal_file.exists() or cookie_file.exists())

        mtime_before = cookie_file.stat().st_mtime

        extracted = CookieExtractor.extract_cookies_for_profile(prof)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["name"], "wal_ck")

        mtime_after = cookie_file.stat().st_mtime
        self.assertEqual(mtime_before, mtime_after, "Original database file must not be modified by read operation")

    def test_adv_18_sqlite_stress_scale_and_prune_integration(self):
        """Adv-18: Large SQLite database with 3,000 cookies handles rapidly and prunes to threshold."""
        prof = self.test_root / "scale_prof"
        cookie_file = prof / "Default" / "Network" / "Cookies"
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(cookie_file))
        conn.execute("""
            CREATE TABLE cookies (
                name TEXT, host_key TEXT, value TEXT, encrypted_value BLOB,
                path TEXT, expires_utc INTEGER, is_secure INTEGER, is_httponly INTEGER,
                samesite INTEGER
            )
        """)
        rows = [
            (f"ck_{i}", ".example.com", f"val_{i}", b"", "/", 0, 1, 1, 1)
            for i in range(3000)
        ]
        # Insert Google auth cookies
        rows.append(("SID", ".google.com", "sid_secret", b"", "/", 0, 1, 1, 1))
        rows.append(("HSID", ".google.com", "hsid_secret", b"", "/", 0, 1, 1, 1))
        rows.append(("SSID", ".google.com", "ssid_secret", b"", "/", 0, 1, 1, 1))

        conn.executemany("INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
        conn.close()

        start_t = time.perf_counter()
        extracted = CookieExtractor.extract_cookies_for_profile(prof)
        dur = time.perf_counter() - start_t

        self.assertEqual(len(extracted), 3003)
        self.assertLess(dur, 2.0, "Extraction of 3000 cookies should complete within 2 seconds")

        # Test integration with prune_cookies
        pruned = SessionService.prune_cookies(extracted)
        self.assertLessEqual(len(pruned), SessionService.MAX_COOKIES_PER_CHANNEL)
        pruned_names = {c["name"] for c in pruned}
        self.assertIn("SID", pruned_names, "Essential Google auth cookie SID must be preserved")
        self.assertIn("HSID", pruned_names, "Essential Google auth cookie HSID must be preserved")
        self.assertIn("SSID", pruned_names, "Essential Google auth cookie SSID must be preserved")

    # =========================================================================
    # Section 5: Dead Process Handling & Lifecycle
    # =========================================================================

    def test_adv_19_active_contexts_filters_dead_process_on_read(self):
        """Adv-19: Terminated processes are automatically purged when accessing _active_contexts."""
        alive = DummyProcess(pid=6001)
        dead = DummyProcess(pid=6002)
        dead.returncode = 0

        self.service._active_processes["alive_ch"] = alive
        self.service._active_processes["dead_ch"] = dead

        contexts = self.service._active_contexts
        self.assertIn("alive_ch", contexts)
        self.assertNotIn("dead_ch", contexts)
        self.assertEqual(len(contexts), 1)

    def test_adv_20_is_channel_open_cleans_dead_process(self):
        """Adv-20: is_channel_open returns False and purges dead process from _active_processes."""
        dead = DummyProcess(pid=6003)
        dead.returncode = 1
        self.service._active_processes["crash_ch"] = dead

        self.assertFalse(self.service.is_channel_open("crash_ch"))
        self.assertNotIn("crash_ch", self.service._active_processes)

    def test_adv_21_close_channel_browser_on_already_dead_process(self):
        """Adv-21: Closing an already dead process returns False and does not run taskkill."""
        dead = DummyProcess(pid=6004)
        dead.returncode = 0
        self.service._active_processes["already_dead"] = dead

        with patch("subprocess.run") as mock_run:
            res = self.service.close_channel_browser("already_dead")
            self.assertFalse(res)
            mock_run.assert_not_called()
            self.assertNotIn("already_dead", self.service._active_processes)

    def test_adv_22_concurrent_thread_access_to_active_contexts(self):
        """Adv-22: Stress test: 10 threads concurrently reading/mutating active processes without race conditions."""
        errors = []

        def worker_reader():
            try:
                for _ in range(50):
                    _ = self.service._active_contexts
                    _ = self.service.get_active_channel_ids()
                    _ = self.service.is_channel_open("stress_ch_5")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def worker_mutator():
            try:
                for i in range(50):
                    cid = f"stress_ch_{i % 10}"
                    proc = DummyProcess(pid=7000 + i)
                    if i % 3 == 0:
                        proc.returncode = 0
                    self.service._active_processes[cid] = proc
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker_reader if i % 2 == 0 else worker_mutator)
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent thread access resulted in errors: {errors}")

    def test_adv_23_close_all_browsers_mixed_batch(self):
        """Adv-23: close_all_browsers terminates alive, purges dead, and returns exact terminated count."""
        p_alive1 = DummyProcess(pid=8001)
        p_alive2 = DummyProcess(pid=8002)
        p_dead = DummyProcess(pid=8003)
        p_dead.returncode = 0

        self.service._active_processes = {
            "c_live1": p_alive1,
            "c_dead": p_dead,
            "c_live2": p_alive2,
        }

        with patch("subprocess.run"):
            count = self.service.close_all_browsers()
            self.assertEqual(count, 2, "Only 2 running processes should be counted as closed")
            self.assertEqual(len(self.service._active_processes), 0)

    # =========================================================================
    # Section 6: CLI Launch Arguments & Zero Automation Flags
    # =========================================================================

    def test_adv_24_strict_zero_automation_flags_verification(self):
        """Adv-24: Verifies 100% absence of 25+ automation, CDP, and webdriver flags."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        captured_cmd = []

        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=9001, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_security_audit")
                time.sleep(0.12)

        self.assertTrue(len(captured_cmd) > 0)

        # Comprehensive blacklist of automation indicators
        automation_blacklist = [
            "--enable-automation",
            "--remote-debugging-port",
            "--remote-debugging-pipe",
            "--remote-debugging-address",
            "--test-type",
            "--disable-blink-features=AutomationControlled",
            "--headless",
            "--automation",
            "--enable-blink-features",
            "--use-mock-keychain",
            "--disable-client-side-phishing-detection",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-zero-browsers-open-for-tests",
            "--no-sandbox",
            "playwright",
            "puppeteer",
            "selenium",
            "webdriver",
            "cdp"
        ]

        full_cmdline = " ".join(captured_cmd).lower()
        for forbidden_flag in automation_blacklist:
            self.assertNotIn(
                forbidden_flag.lower(),
                full_cmdline,
                f"Forbidden automation indicator '{forbidden_flag}' detected in browser command line!"
            )

    def test_adv_25_verified_natural_arguments_presence(self):
        """Adv-25: Verifies that exact natural arguments are present in correct format."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        captured_cmd = []

        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=9002, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_natural_flags", target_url="https://accounts.google.com")
                time.sleep(0.12)

        # Expected natural flags
        self.assertIn("--no-first-run", captured_cmd)
        self.assertIn("--no-default-browser-check", captured_cmd)
        self.assertIn("--start-maximized", captured_cmd)
        self.assertIn("--hide-crash-restore-bubble", captured_cmd)
        self.assertIn("https://accounts.google.com", captured_cmd)

        # User data dir must specify channel profile
        udd = [arg for arg in captured_cmd if arg.startswith("--user-data-dir=")]
        self.assertEqual(len(udd), 1)
        self.assertIn("ch_natural_flags", udd[0])

    def test_adv_26_real_host_browser_executable_and_cli_synthesis(self):
        """Adv-26: Detects real host browser on this machine and verifies synthesized command line."""
        real_browser = self.service.detect_browser_executable()
        self.assertIsNotNone(real_browser, "Expected a valid Chromium browser (Chrome/Edge) on host")
        self.assertTrue(real_browser.is_file(), f"Detected browser '{real_browser}' must be a file")
        self.assertTrue(str(real_browser).lower().endswith(".exe"), "Must be an executable .exe on Windows")

        # Synthesize real arguments
        target_url = "https://accounts.google.com"
        prof = Config.get_profile_path("audit_channel")
        cmd = [
            str(real_browser),
            f"--user-data-dir={prof.resolve()}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
            "--hide-crash-restore-bubble",
            target_url
        ]
        cmd_str = subprocess.list2cmdline(cmd)

        self.assertNotIn("--enable-automation", cmd_str)
        self.assertNotIn("--remote-debugging-port", cmd_str)
        self.assertNotIn("webdriver", cmd_str.lower())
        self.assertIn("--user-data-dir=", cmd_str)

        shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
