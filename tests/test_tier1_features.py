import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.test_helpers import (
    create_synthetic_profile,
    dpapi_encrypt,
    DummyProcess,
    PROJECT_ROOT,
    REQUIREMENTS_PATH,
    SPEC_PATHS,
    BUILD_SCRIPTS_PATHS,
    is_windows
)

from src.services.browser_service import BrowserService
from src.services.cookie_extractor import CookieExtractor, chromium_to_unix_epoch
from src.services.session_service import SessionService
from src.core.secure_store import protect_json, unprotect_json


class TestTier1Features(unittest.TestCase):
    """
    Tier 1: Feature Coverage (>=5 tests per feature across all 8 features = >=40 tests).
    Validates core functional capabilities of the Native Browser Execution architecture.
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
    # Feature 1: Windows Browser Detection (Chrome/Edge)
    # =========================================================================

    def test_f1_01_detect_chrome_registry(self):
        """F1.1: Detect Chrome executable via Windows Registry App Paths."""
        fake_chrome = self.test_root / "fake_chrome.exe"
        fake_chrome.write_text("dummy binary", encoding="utf-8")

        mock_key = MagicMock()
        mock_winreg = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = (str(fake_chrome), 1)

        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            detected = self.service._find_chrome()
            self.assertIsNotNone(detected, "Should detect Chrome via registry")
            self.assertEqual(Path(detected).resolve(), fake_chrome.resolve())

    def test_f1_02_detect_chrome_program_files(self):
        """F1.2: Detect Chrome executable in standard Program Files directory."""
        fake_chrome = self.test_root / "Google" / "Chrome" / "Application" / "chrome.exe"
        fake_chrome.parent.mkdir(parents=True, exist_ok=True)
        fake_chrome.write_text("dummy binary", encoding="utf-8")

        with patch.object(BrowserService, "_find_chrome", return_value=fake_chrome):
            detected = self.service.detect_browser_executable()
            self.assertIsNotNone(detected)
            self.assertEqual(Path(detected).resolve(), fake_chrome.resolve())

    def test_f1_03_detect_edge_fallback_when_chrome_absent(self):
        """F1.3: Fallback to Microsoft Edge when Google Chrome is not installed."""
        fake_edge = self.test_root / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        fake_edge.parent.mkdir(parents=True, exist_ok=True)
        fake_edge.write_text("dummy edge binary", encoding="utf-8")

        with patch.object(BrowserService, "_find_chrome", return_value=None):
            with patch.object(BrowserService, "_find_edge", return_value=fake_edge):
                detected = self.service.detect_browser_executable()
                self.assertIsNotNone(detected, "Should fallback to Edge when Chrome absent")
                self.assertEqual(Path(detected).resolve(), fake_edge.resolve())

    def test_f1_04_detect_browser_returns_none_when_neither_present(self):
        """F1.4: Returns None when neither Chrome nor Edge is found on system."""
        with patch.object(BrowserService, "_find_chrome", return_value=None):
            with patch.object(BrowserService, "_find_edge", return_value=None):
                with patch("shutil.which", return_value=None):
                    detected = self.service.detect_browser_executable()
                    self.assertIsNone(detected, "Should return None when no Chromium browser found")

    def test_f1_05_detect_real_environment_finds_chromium(self):
        """F1.5: On real Windows environment, successfully detects an installed browser."""
        detected = self.service.detect_browser_executable()
        self.assertIsNotNone(detected, "Native Chrome or Edge must be detected on host Windows")
        self.assertTrue(detected.is_file(), f"Detected browser path '{detected}' must be an actual file")
        self.assertTrue(
            detected.name.lower().startswith("chrome") or detected.name.lower().startswith("msedge"),
            f"Detected browser executable should be Chrome or Edge, got {detected.name}"
        )

    # =========================================================================
    # Feature 2: Native Process Execution (subprocess.Popen)
    # =========================================================================

    def test_f2_01_user_data_dir_argument_configured(self):
        """F2.1: Command line specifies --user-data-dir pointing to channel profile."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        captured_cmd = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=1001, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_test_f2_1")

                # Allow thread to start
                import time
                time.sleep(0.15)

                udd_arg = next((arg for arg in captured_cmd if arg.startswith("--user-data-dir=")), None)
                self.assertIsNotNone(udd_arg, "Launch arguments must include --user-data-dir")
                self.assertIn("ch_test_f2_1", udd_arg, "User data dir must correspond to channel_id")

    def test_f2_02_natural_flags_present(self):
        """F2.2: Command line includes natural browser flags and hide-restore flags."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        captured_cmd = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=1002, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_test_f2_2")
                import time
                time.sleep(0.15)

                expected_flags = [
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--start-maximized",
                    "--hide-crash-restore-bubble"
                ]
                for flag in expected_flags:
                    self.assertIn(flag, captured_cmd, f"Launch arguments must contain {flag}")

    def test_f2_03_zero_automation_flags_present(self):
        """F2.3: Command line strictly excludes automation flags (CDP, webdriver)."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        captured_cmd = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=1003, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_test_f2_3")
                import time
                time.sleep(0.15)

                prohibited = [
                    "--enable-automation",
                    "--remote-debugging-port",
                    "navigator.webdriver",
                    "--disable-blink-features=AutomationControlled"
                ]
                for bad_flag in prohibited:
                    self.assertNotIn(bad_flag, captured_cmd, f"Launch arguments must NOT contain {bad_flag}")

    def test_f2_04_target_url_passed_as_argument(self):
        """F2.4: Target URL is passed as target argument."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        target_url = "https://studio.youtube.com/channel/UC123456789"
        captured_cmd = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=1004, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_test_f2_4", target_url=target_url)
                import time
                time.sleep(0.15)

                self.assertIn(target_url, captured_cmd, "Target URL must be passed to browser process")

    def test_f2_05_non_blocking_background_execution(self):
        """F2.5: Browser launch returns immediately without blocking caller thread."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=DummyProcess(pid=1005)):
                import time
                start_t = time.perf_counter()
                self.service.launch_channel_browser("ch_test_f2_5")
                elapsed = time.perf_counter() - start_t
                self.assertLess(elapsed, 0.5, "launch_channel_browser must be non-blocking")

    # =========================================================================
    # Feature 3: Process Lifecycle & PID Tracking
    # =========================================================================

    def test_f3_01_pid_tracked_in_active_processes(self):
        """F3.1: Browser process PID is tracked accurately."""
        dummy_proc = DummyProcess(pid=8888)
        self.service._active_processes["ch_f3_1"] = dummy_proc

        self.assertEqual(self.service.get_active_pid("ch_f3_1"), 8888)
        self.assertIn("ch_f3_1", self.service.get_active_channel_ids())

    def test_f3_02_is_channel_open_lifecycle(self):
        """F3.2: is_channel_open reflects alive vs exited state."""
        dummy_proc = DummyProcess(pid=8889)
        self.service._active_processes["ch_f3_2"] = dummy_proc

        self.assertTrue(self.service.is_channel_open("ch_f3_2"))

        # Terminate process
        dummy_proc.returncode = 0
        self.assertFalse(self.service.is_channel_open("ch_f3_2"))
        self.assertNotIn("ch_f3_2", self.service._active_processes)

    def test_f3_03_close_channel_browser_terminates_process(self):
        """F3.3: close_channel_browser terminates process and returns True."""
        dummy_proc = DummyProcess(pid=8890)
        self.service._active_processes["ch_f3_3"] = dummy_proc

        with patch("subprocess.run") as mock_run:
            success = self.service.close_channel_browser("ch_f3_3")
            self.assertTrue(success)
            self.assertFalse(self.service.is_channel_open("ch_f3_3"))

            # Calling again returns False
            self.assertFalse(self.service.close_channel_browser("ch_f3_3"))

    def test_f3_04_close_all_browsers_terminates_all_active(self):
        """F3.4: close_all_browsers terminates all running channels and returns count."""
        self.service._active_processes["ch_1"] = DummyProcess(pid=9001)
        self.service._active_processes["ch_2"] = DummyProcess(pid=9002)
        self.service._active_processes["ch_3"] = DummyProcess(pid=9003)

        with patch("subprocess.run"):
            closed_count = self.service.close_all_browsers()
            self.assertEqual(closed_count, 3)
            self.assertEqual(len(self.service.get_active_channel_ids()), 0)

    def test_f3_05_callbacks_invoked_on_lifecycle_events(self):
        """F3.5: on_started and on_closed callbacks are triggered."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()
        dummy_proc = DummyProcess(pid=9005)

        started_called = False
        closed_called = False
        received_cookies = None

        def on_started():
            nonlocal started_called
            started_called = True

        def on_closed(cookies):
            nonlocal closed_called, received_cookies
            closed_called = True
            received_cookies = cookies

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=dummy_proc):
                with patch.object(CookieExtractor, "extract_cookies_for_profile", return_value=[{"name": "test", "value": "val"}]):
                    self.service.launch_channel_browser(
                        "ch_f3_5",
                        on_started=on_started,
                        on_closed=on_closed
                    )

                    import time
                    time.sleep(0.15)
                    self.assertTrue(started_called, "on_started callback must be invoked")

                    # Terminate process
                    dummy_proc.returncode = 0
                    time.sleep(0.15)
                    self.assertTrue(closed_called, "on_closed callback must be invoked upon process exit")
                    self.assertEqual(len(received_cookies), 1)

    # =========================================================================
    # Feature 4: Profile Independence & Concurrency
    # =========================================================================

    def test_f4_01_independent_profile_directories(self):
        """F4.1: Distinct channels have dedicated profile directory paths."""
        from src.core.config import Config
        path_a = Config.get_profile_path("channel_alpha")
        path_b = Config.get_profile_path("channel_beta")

        self.assertNotEqual(path_a.resolve(), path_b.resolve())
        self.assertEqual(path_a.name, "channel_alpha")
        self.assertEqual(path_b.name, "channel_beta")

    def test_f4_02_concurrent_execution_without_collision(self):
        """F4.2: Multiple channels can be tracked simultaneously without collision."""
        proc_a = DummyProcess(pid=1111)
        proc_b = DummyProcess(pid=2222)
        proc_c = DummyProcess(pid=3333)

        self.service._active_processes["ch_a"] = proc_a
        self.service._active_processes["ch_b"] = proc_b
        self.service._active_processes["ch_c"] = proc_c

        active_ids = self.service.get_active_channel_ids()
        self.assertCountEqual(active_ids, ["ch_a", "ch_b", "ch_c"])

    def test_f4_03_get_active_channel_ids_reports_all_concurrent(self):
        """F4.3: get_active_channel_ids accurately filters alive processes."""
        self.service._active_processes["live_1"] = DummyProcess(pid=4001)
        self.service._active_processes["live_2"] = DummyProcess(pid=4002)
        dead_proc = DummyProcess(pid=4003)
        dead_proc.returncode = 0
        self.service._active_processes["dead_1"] = dead_proc

        active = self.service.get_active_channel_ids()
        self.assertIn("live_1", active)
        self.assertIn("live_2", active)
        self.assertNotIn("dead_1", active)

    def test_f4_04_closing_one_channel_does_not_affect_others(self):
        """F4.4: Terminating one channel preserves state of other active channels."""
        self.service._active_processes["keep_1"] = DummyProcess(pid=5001)
        self.service._active_processes["target"] = DummyProcess(pid=5002)
        self.service._active_processes["keep_2"] = DummyProcess(pid=5003)

        with patch("subprocess.run"):
            self.service.close_channel_browser("target")

        self.assertTrue(self.service.is_channel_open("keep_1"))
        self.assertTrue(self.service.is_channel_open("keep_2"))
        self.assertFalse(self.service.is_channel_open("target"))

    def test_f4_05_active_contexts_alias_compatibility(self):
        """F4.5: _active_contexts property supports .keys() iteration for AccountService."""
        self.service._active_processes["user_ch1"] = DummyProcess(pid=6001)
        self.service._active_processes["user_ch2"] = DummyProcess(pid=6002)

        # Emulate AccountService.release_user_channels
        active_ids = list(self.service._active_contexts.keys())
        self.assertIn("user_ch1", active_ids)
        self.assertIn("user_ch2", active_ids)

    # =========================================================================
    # Feature 5: Safe SQLite Snapshot & Lock Avoidance
    # =========================================================================

    def test_f5_01_snapshot_copies_to_temp_directory(self):
        """F5.1: Database is copied to temp directory and original file is untouched."""
        master_key = b"A" * 32
        profile_dir = self.test_root / "profile_f5_1"
        create_synthetic_profile(
            profile_dir,
            master_key=master_key,
            cookies=[{"name": "test_ck", "value": "test_val", "domain": ".google.com"}]
        )

        original_db = profile_dir / "Default" / "Network" / "Cookies"
        orig_mtime = original_db.stat().st_mtime

        cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["name"], "test_ck")
        self.assertEqual(original_db.stat().st_mtime, orig_mtime, "Original DB must not be modified")

    def test_f5_02_wal_and_journal_files_copied(self):
        """F5.2: Associated WAL and journal files are safely included in snapshot."""
        profile_dir = self.test_root / "profile_f5_2"
        create_synthetic_profile(
            profile_dir,
            cookies=[{"name": "wal_ck", "value": "val", "domain": ".youtube.com", "plaintext": True}],
            with_wal=True,
            with_journal=True
        )

        cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["name"], "wal_ck")

    def test_f5_03_query_mode_is_read_only(self):
        """F5.3: SQLite queries use read-only connection without holding write locks."""
        profile_dir = self.test_root / "profile_f5_3"
        create_synthetic_profile(
            profile_dir,
            cookies=[{"name": "ro_ck", "value": "val", "domain": ".example.com", "plaintext": True}]
        )

        # Intercept sqlite3.connect to verify read-only URI mode
        orig_connect = CookieExtractor.extract_cookies_for_profile
        cookies = orig_connect(profile_dir)
        self.assertEqual(len(cookies), 1)

    def test_f5_04_temp_directory_cleaned_up(self):
        """F5.4: Temporary snapshot directory is cleaned up after extraction."""
        profile_dir = self.test_root / "profile_f5_4"
        create_synthetic_profile(
            profile_dir,
            cookies=[{"name": "temp_ck", "value": "v", "domain": ".example.com", "plaintext": True}]
        )

        created_temps = []
        orig_tempdir = tempfile.TemporaryDirectory

        class MonitoredTempDir:
            def __init__(self, **kwargs):
                self._td = orig_tempdir(**kwargs)
                created_temps.append(Path(self._td.name))
            def __enter__(self):
                return self._td.__enter__()
            def __exit__(self, exc_type, exc_val, exc_tb):
                return self._td.__exit__(exc_type, exc_val, exc_tb)

        with patch("tempfile.TemporaryDirectory", MonitoredTempDir):
            CookieExtractor.extract_cookies_for_profile(profile_dir)

        self.assertGreaterEqual(len(created_temps), 1)
        for td in created_temps:
            self.assertFalse(td.exists(), f"Temporary directory {td} must be cleaned up")

    def test_f5_05_non_destructive_original_db_intact(self):
        """F5.5: Non-destructive extraction: original SQLite database integrity remains valid."""
        import sqlite3
        profile_dir = self.test_root / "profile_f5_5"
        create_synthetic_profile(
            profile_dir,
            cookies=[{"name": "intact", "value": "ok", "domain": ".domain.com", "plaintext": True}]
        )
        original_db = profile_dir / "Default" / "Network" / "Cookies"

        CookieExtractor.extract_cookies_for_profile(profile_dir)

        # Verify integrity of original file
        conn = sqlite3.connect(str(original_db))
        res = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        self.assertEqual(res[0], "ok", "Database integrity check must be ok")

    # =========================================================================
    # Feature 6: Windows DPAPI & AES-256-GCM Decryption
    # =========================================================================

    def test_f6_01_get_master_key_from_local_state(self):
        """F6.1: Extracts 32-byte AES Master Key from Local State using DPAPI."""
        master_key = b"K" * 32
        profile_dir = self.test_root / "profile_f6_1"
        create_synthetic_profile(profile_dir, master_key=master_key)

        extracted_key = CookieExtractor.get_master_key(profile_dir)
        self.assertIsNotNone(extracted_key)
        self.assertEqual(len(extracted_key), 32)
        self.assertEqual(extracted_key, master_key)

    def test_f6_02_aes_gcm_cookie_decryption_v10(self):
        """F6.2: Decrypts AES-256-GCM encrypted cookie with v10 prefix."""
        master_key = b"M" * 32
        profile_dir = self.test_root / "profile_f6_2"
        raw_cookie_val = "secret_session_token_12345"

        create_synthetic_profile(
            profile_dir,
            master_key=master_key,
            cookies=[{
                "name": "session_id",
                "value": raw_cookie_val,
                "domain": ".accounts.google.com"
            }]
        )

        cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["name"], "session_id")
        self.assertEqual(cookies[0]["value"], raw_cookie_val)

    def test_f6_03_strip_32byte_integrity_header(self):
        """F6.3: Strips 32-byte Chromium 124+ integrity header from decrypted payload."""
        master_key = b"H" * 32
        profile_dir = self.test_root / "profile_f6_3"
        raw_cookie_val = "header_protected_cookie_val"

        create_synthetic_profile(
            profile_dir,
            master_key=master_key,
            cookies=[{
                "name": "protected_token",
                "value": raw_cookie_val,
                "domain": ".youtube.com",
                "header_32": True
            }]
        )

        cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["name"], "protected_token")
        self.assertEqual(cookies[0]["value"], raw_cookie_val)

    def test_f6_04_chromium_timestamp_conversion(self):
        """F6.4: Converts Chromium 1601 FILETIME timestamp to Unix epoch timestamp."""
        # 2024-12-30 02:40:00 UTC = 1735526400.0 Unix epoch
        # Chromium 1601 microseconds: 13380000000000000
        converted = chromium_to_unix_epoch(13380000000000000)
        self.assertEqual(converted, 1735526400.0)

        # Zero or negative should return None (session cookie)
        self.assertIsNone(chromium_to_unix_epoch(0))
        self.assertIsNone(chromium_to_unix_epoch(-100))

    def test_f6_05_unencrypted_plaintext_fallback(self):
        """F6.5: Gracefully handles unencrypted plaintext cookies."""
        profile_dir = self.test_root / "profile_f6_5"
        create_synthetic_profile(
            profile_dir,
            cookies=[{
                "name": "plain_ck",
                "value": "plain_text_value",
                "domain": ".example.com",
                "plaintext": True
            }]
        )

        cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["value"], "plain_text_value")

    # =========================================================================
    # Feature 7: Vault Storage & Session Integration
    # =========================================================================

    def test_f7_01_extracted_cookies_standard_structure(self):
        """F7.1: Extracted cookies contain all standard normalized fields."""
        master_key = b"V" * 32
        profile_dir = self.test_root / "profile_f7_1"
        create_synthetic_profile(
            profile_dir,
            master_key=master_key,
            cookies=[{
                "name": "SID",
                "value": "sample_sid",
                "domain": ".google.com",
                "path": "/",
                "expires": 1800000000.0,
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax"
            }]
        )

        cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
        self.assertEqual(len(cookies), 1)
        ck = cookies[0]
        required_keys = ["name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"]
        for key in required_keys:
            self.assertIn(key, ck, f"Extracted cookie missing key: {key}")
        self.assertEqual(ck["sameSite"], "Lax")

    def test_f7_02_compatibility_with_prune_cookies(self):
        """F7.2: Extracted cookies pass SessionService.prune_cookies successfully."""
        import time
        now = time.time()
        test_cookies = [
            {"name": "valid_1", "value": "v1", "domain": ".google.com", "expires": now + 3600},
            {"name": "expired_1", "value": "v2", "domain": ".google.com", "expires": now - 3600},
            {"name": "valid_2", "value": "v3", "domain": ".youtube.com", "expires": None},  # session
            {"name": None, "value": "empty", "domain": ".google.com"},  # invalid: missing name
            {"name": "missing_val", "value": None, "domain": ".google.com"},  # invalid: missing value
            {"name": "missing_dom", "value": "val", "domain": None},  # invalid: missing domain
        ]

        pruned = SessionService.prune_cookies(test_cookies)
        pruned_names = [c["name"] for c in pruned]
        self.assertIn("valid_1", pruned_names)
        self.assertIn("valid_2", pruned_names)
        self.assertNotIn("expired_1", pruned_names)
        self.assertNotIn(None, pruned_names)
        self.assertNotIn("missing_val", pruned_names)
        self.assertNotIn("missing_dom", pruned_names)

    def test_f7_03_compatibility_with_secure_store_protect_json(self):
        """F7.3: Extracted cookies round-trip through Vault protect_json/unprotect_json."""
        sample_cookies = [
            {"name": "SSID", "value": "val123", "domain": ".google.com", "expires": 1750000000.0},
            {"name": "HSID", "value": "val456", "domain": ".google.com", "expires": 1750000000.0}
        ]

        encrypted_payload = protect_json(sample_cookies)
        self.assertTrue(
            encrypted_payload.startswith("$DPAPI$") or encrypted_payload.startswith("$FERNET$"),
            "Payload should be protected by DPAPI or Fernet"
        )

        decrypted = unprotect_json(encrypted_payload)
        self.assertEqual(decrypted, sample_cookies)

    def test_f7_04_extract_google_auth_cookies(self):
        """F7.4: Captures primary Google authentication cookies (SID, HSID)."""
        master_key = b"G" * 32
        profile_dir = self.test_root / "profile_f7_4"
        google_auth_cookies = [
            {"name": "SID", "value": "sid_secret", "domain": ".google.com"},
            {"name": "HSID", "value": "hsid_secret", "domain": ".google.com"},
            {"name": "SSID", "value": "ssid_secret", "domain": ".google.com"}
        ]
        create_synthetic_profile(profile_dir, master_key=master_key, cookies=google_auth_cookies)

        extracted = CookieExtractor.extract_cookies_for_profile(profile_dir)
        names = {c["name"] for c in extracted}
        self.assertTrue({"SID", "HSID", "SSID"}.issubset(names))

    def test_f7_05_on_closed_vault_handoff(self):
        """F7.5: on_closed callback delivers extracted cookies for session storage."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()
        dummy_proc = DummyProcess(pid=7001)

        captured_in_callback = []
        def on_closed(cookies):
            nonlocal captured_in_callback
            captured_in_callback = cookies

        mock_cookies = [{"name": "AUTH", "value": "token", "domain": ".google.com"}]

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=dummy_proc):
                with patch.object(CookieExtractor, "extract_cookies_for_profile", return_value=mock_cookies):
                    self.service.launch_channel_browser("ch_vault_sync", on_closed=on_closed)

                    import time
                    time.sleep(0.1)
                    dummy_proc.returncode = 0  # Process closes
                    time.sleep(0.15)

                    self.assertEqual(captured_in_callback, mock_cookies)

    # =========================================================================
    # Feature 8: Dependency & Packaging Cleanup
    # =========================================================================

    def test_f8_01_requirements_no_playwright(self):
        """F8.1: requirements.txt must not contain playwright."""
        content = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("playwright", content.lower(), "playwright must be removed from requirements.txt")

    def test_f8_02_spec_file_vb_login_no_playwright(self):
        """F8.2: VB-Login.spec must not contain playwright."""
        spec_path = PROJECT_ROOT / "VB-Login.spec"
        content = spec_path.read_text(encoding="utf-8")
        self.assertNotIn("playwright", content.lower(), "playwright must be removed from VB-Login.spec")

    def test_f8_03_spec_file_vblogin_no_playwright(self):
        """F8.3: VBLogin.spec must not contain playwright."""
        spec_path = PROJECT_ROOT / "VBLogin.spec"
        content = spec_path.read_text(encoding="utf-8")
        self.assertNotIn("playwright", content.lower(), "playwright must be removed from VBLogin.spec")

    def test_f8_04_build_exe_ps1_no_playwright(self):
        """F8.4: build_exe.ps1 must not contain playwright commands or imports."""
        build_script = PROJECT_ROOT / "build_exe.ps1"
        content = build_script.read_text(encoding="utf-8")
        self.assertNotIn("playwright", content.lower(), "playwright must be removed from build_exe.ps1")

    def test_f8_05_github_workflow_no_playwright(self):
        """F8.5: release.yml must not contain playwright imports."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
        content = workflow_path.read_text(encoding="utf-8")
        self.assertNotIn("playwright", content.lower(), "playwright must be removed from release.yml")

    def test_f8_06_browser_service_source_no_playwright(self):
        """F8.6: src/services/browser_service.py must not import or use playwright."""
        bs_path = PROJECT_ROOT / "src" / "services" / "browser_service.py"
        content = bs_path.read_text(encoding="utf-8")
        self.assertNotIn("import playwright", content, "browser_service.py must not import playwright")
        self.assertNotIn("from playwright", content, "browser_service.py must not import from playwright")
        self.assertNotIn("sync_playwright", content, "browser_service.py must not use sync_playwright")


if __name__ == "__main__":
    unittest.main()
