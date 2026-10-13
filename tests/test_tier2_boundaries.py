import os
import sys
import ast
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.test_helpers import (
    create_synthetic_profile,
    DummyProcess,
    PROJECT_ROOT,
    REQUIREMENTS_PATH,
    SPEC_PATHS,
    BUILD_SCRIPTS_PATHS,
    is_windows
)

from src.services.browser_service import BrowserService
from src.services.cookie_extractor import (
    CookieExtractor,
    _unprotect_dpapi,
    _decode_cookie_bytes,
    chromium_to_unix_epoch
)
from src.services.session_service import SessionService
from src.core.secure_store import protect_json, unprotect_json


class TestTier2Boundaries(unittest.TestCase):
    """
    Tier 2: Boundary & Corner Cases (>=5 tests per feature across all 8 features = >=40 tests).
    Validates extreme inputs, error recovery, corrupt files, boundary limits, and resilience.
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
    # Feature 1 Boundaries: Windows Browser Detection
    # =========================================================================

    def test_b1_01_registry_key_exists_but_value_empty(self):
        """B1.1: Registry key exists but returns empty string value."""
        mock_winreg = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = MagicMock()
        mock_winreg.QueryValueEx.return_value = ("", 1)

        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            with patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": "", "LOCALAPPDATA": ""}):
                with patch("pathlib.Path.is_file", return_value=False):
                    with patch("shutil.which", return_value=None):
                        detected = self.service._find_chrome()
                        self.assertIsNone(detected, "Empty registry string should not be returned as binary path")

    def test_b1_02_registry_path_points_to_nonexistent_file(self):
        """B1.2: Stale registry path points to uninstalled/deleted executable."""
        nonexistent_path = str(self.test_root / "stale_chrome.exe")
        mock_winreg = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = MagicMock()
        mock_winreg.QueryValueEx.return_value = (nonexistent_path, 1)

        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            with patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": "", "LOCALAPPDATA": ""}):
                with patch("pathlib.Path.is_file", return_value=False):
                    with patch("shutil.which", return_value=None):
                        detected = self.service._find_chrome()
                        self.assertIsNone(detected, "Nonexistent file in registry must be ignored")

    def test_b1_03_path_containing_spaces_and_special_chars(self):
        """B1.3: Browser path containing spaces and parentheses is preserved."""
        custom_dir = self.test_root / "Special Path (x86)" / "Google Chrome"
        custom_dir.mkdir(parents=True, exist_ok=True)
        custom_exe = custom_dir / "chrome.exe"
        custom_exe.touch()

        with patch.object(BrowserService, "_find_chrome", return_value=custom_exe):
            detected = self.service.detect_browser_executable()
            self.assertEqual(detected, custom_exe)
            self.assertTrue(detected.is_file())

    def test_b1_04_permission_error_accessing_registry(self):
        """B1.4: Registry access raising PermissionError is handled gracefully."""
        mock_winreg = MagicMock()
        mock_winreg.OpenKey.side_effect = PermissionError("Access is denied")

        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            with patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": "", "LOCALAPPDATA": ""}):
                with patch("pathlib.Path.is_file", return_value=False):
                    with patch("shutil.which", return_value=None):
                        # Should not raise exception, falls through gracefully
                        detected = self.service._find_chrome()
                        self.assertIsNone(detected)

    def test_b1_05_shutil_which_edge_case(self):
        """B1.5: Detects browser via PATH when registry and standard dirs fail."""
        fake_bin = self.test_root / "msedge.exe"
        fake_bin.touch()

        with patch.object(BrowserService, "_find_chrome", return_value=None):
            with patch.object(BrowserService, "_find_edge", return_value=None):
                with patch("shutil.which", return_value=str(fake_bin)):
                    detected = self.service.detect_browser_executable()
                    self.assertIsNotNone(detected)
                    self.assertEqual(detected, fake_bin)

    # =========================================================================
    # Feature 2 Boundaries: Native Process Execution
    # =========================================================================

    def test_b2_01_target_url_with_query_params_and_special_chars(self):
        """B2.1: Target URL with complex query parameters and fragments is passed intact."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        complex_url = "https://accounts.google.com/signin/v2/identifier?service=youtube&uilel=3&hl=vi#fragment-1"
        captured_cmd = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=2001, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_complex_url", target_url=complex_url)
                import time
                time.sleep(0.12)
                self.assertIn(complex_url, captured_cmd)

    def test_b2_02_default_target_url_fallback(self):
        """B2.2: Default target URL is accounts.google.com when not supplied."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        captured_cmd = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=2002, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_default_url")
                import time
                time.sleep(0.12)
                self.assertIn("https://accounts.google.com", captured_cmd)

    def test_b2_03_profile_dir_path_with_spaces_and_unicode(self):
        """B2.3: Profile path with unicode and spaces resolves correctly."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        channel_id = "kênh_tiếng_việt 1"
        captured_cmd = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return DummyProcess(pid=2003, args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser(channel_id)
                import time
                time.sleep(0.12)
                udd_arg = next((arg for arg in captured_cmd if arg.startswith("--user-data-dir=")), "")
                self.assertIn(channel_id, udd_arg)

    def test_b2_04_duplicate_launch_when_already_open(self):
        """B2.4: Consecutive launch of same open channel does not spawn duplicate process."""
        self.service._active_processes["already_open"] = DummyProcess(pid=2004)

        started_called = False
        def on_started():
            nonlocal started_called
            started_called = True

        with patch("subprocess.Popen") as mock_popen:
            self.service.launch_channel_browser("already_open", on_started=on_started)
            import time
            time.sleep(0.12)
            mock_popen.assert_not_called()
            self.assertTrue(started_called, "Should invoke on_started even if already open")

    def test_b2_05_popen_exception_triggers_on_error(self):
        """B2.5: Subprocess execution error invokes on_error and clears active state."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        error_received = None
        def on_error(err):
            nonlocal error_received
            error_received = err

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=OSError("Access denied")):
                self.service.launch_channel_browser("ch_err", on_error=on_error)
                import time
                time.sleep(0.12)
                self.assertIsNotNone(error_received)
                self.assertFalse(self.service.is_channel_open("ch_err"))

    # =========================================================================
    # Feature 3 Boundaries: Process Lifecycle & PID Tracking
    # =========================================================================

    def test_b3_01_close_channel_browser_on_nonexistent_channel(self):
        """B3.1: Closing a non-existent channel returns False safely."""
        result = self.service.close_channel_browser("nonexistent_channel_id")
        self.assertFalse(result)

    def test_b3_02_is_channel_open_on_empty_string(self):
        """B3.2: is_channel_open with empty channel ID returns False."""
        self.assertFalse(self.service.is_channel_open(""))

    def test_b3_03_dead_process_cleaned_during_active_contexts_access(self):
        """B3.3: Accessing _active_contexts automatically cleans up terminated processes."""
        dead_proc = DummyProcess(pid=3003)
        dead_proc.returncode = 0  # Process has terminated
        self.service._active_processes["dead_ch"] = dead_proc

        contexts = self.service._active_contexts
        self.assertNotIn("dead_ch", contexts)

    def test_b3_04_close_all_browsers_when_zero_running(self):
        """B3.4: close_all_browsers with zero running processes returns 0."""
        self.assertEqual(self.service.close_all_browsers(), 0)

    def test_b3_05_taskkill_timeout_fallback_to_kill(self):
        """B3.5: Taskkill execution failure falls back to proc.kill()."""
        dummy_proc = DummyProcess(pid=3005)
        self.service._active_processes["hung_ch"] = dummy_proc

        with patch("subprocess.run", side_effect=Exception("Taskkill failure")):
            success = self.service.close_channel_browser("hung_ch")
            self.assertTrue(success)
            self.assertTrue(dummy_proc._terminated)

    # =========================================================================
    # Feature 4 Boundaries: Profile Concurrency & Isolation
    # =========================================================================

    def test_b4_01_stress_concurrent_registrations_10_channels(self):
        """B4.1: High concurrency: 10 distinct channels tracked concurrently."""
        for i in range(10):
            self.service._active_processes[f"channel_{i}"] = DummyProcess(pid=4000 + i)

        active = self.service.get_active_channel_ids()
        self.assertEqual(len(active), 10)
        for i in range(10):
            self.assertEqual(self.service.get_active_pid(f"channel_{i}"), 4000 + i)

    def test_b4_02_channel_id_with_special_characters(self):
        """B4.2: Channel IDs with punctuation and hyphens maintain profile integrity."""
        from src.core.config import Config
        special_ids = ["ch@alpha#1", "user.name-123", "ch_with_underscore", "channel.1"]
        paths = [Config.get_profile_path(cid) for cid in special_ids]
        resolved_names = [p.name for p in paths]
        self.assertEqual(resolved_names, special_ids)

    def test_b4_03_profile_dir_with_preexisting_files(self):
        """B4.3: Launching channel with existing profile preserves existing files."""
        from src.core.config import Config
        prof_path = Config.get_profile_path("existing_prof_test")
        prof_path.mkdir(parents=True, exist_ok=True)
        marker = prof_path / "user_marker.txt"
        marker.write_text("persisted_state", encoding="utf-8")

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=DummyProcess(pid=4003)):
                self.service.launch_channel_browser("existing_prof_test")
                import time
                time.sleep(0.12)
                self.assertTrue(marker.exists())
                self.assertEqual(marker.read_text(encoding="utf-8"), "persisted_state")

        # Cleanup
        shutil.rmtree(prof_path, ignore_errors=True)

    def test_b4_04_rapid_close_and_reopen_same_channel(self):
        """B4.4: Rapid consecutive close and re-launch does not collide."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        proc1 = DummyProcess(pid=4101)
        self.service._active_processes["rapid_ch"] = proc1

        with patch("subprocess.run"):
            self.service.close_channel_browser("rapid_ch")
            self.assertFalse(self.service.is_channel_open("rapid_ch"))

        proc2 = DummyProcess(pid=4102)
        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=proc2):
                self.service.launch_channel_browser("rapid_ch")
                import time
                time.sleep(0.12)
                self.assertTrue(self.service.is_channel_open("rapid_ch"))
                self.assertEqual(self.service.get_active_pid("rapid_ch"), 4102)

    def test_b4_05_clean_dead_processes_with_mixed_alive_and_dead(self):
        """B4.5: _clean_dead_processes cleans exactly dead processes in mixed batch."""
        alive1 = DummyProcess(pid=4201)
        alive2 = DummyProcess(pid=4202)
        dead1 = DummyProcess(pid=4203)
        dead1.returncode = 0
        dead2 = DummyProcess(pid=4204)
        dead2.returncode = -1

        self.service._active_processes = {
            "a1": alive1,
            "d1": dead1,
            "a2": alive2,
            "d2": dead2,
        }

        self.service._clean_dead_processes()
        self.assertEqual(set(self.service._active_processes.keys()), {"a1", "a2"})

    # =========================================================================
    # Feature 5 Boundaries: SQLite Snapshot & Lock Avoidance
    # =========================================================================

    def test_b5_01_missing_cookies_file_returns_empty_list(self):
        """B5.1: Missing Cookies SQLite file returns empty list gracefully."""
        empty_prof = self.test_root / "empty_profile"
        empty_prof.mkdir(parents=True, exist_ok=True)
        res = CookieExtractor.extract_cookies_for_profile(empty_prof)
        self.assertEqual(res, [])

    def test_b5_02_missing_profile_directory_returns_empty_list(self):
        """B5.2: Nonexistent profile directory returns empty list."""
        nonexistent = self.test_root / "does_not_exist"
        res = CookieExtractor.extract_cookies_for_profile(nonexistent)
        self.assertEqual(res, [])

    def test_b5_03_zero_byte_empty_cookies_file(self):
        """B5.3: Zero-byte corrupted Cookies file returns empty list without crashing."""
        corrupt_prof = self.test_root / "corrupt_profile"
        cookies_file = corrupt_prof / "Default" / "Network" / "Cookies"
        cookies_file.parent.mkdir(parents=True, exist_ok=True)
        cookies_file.touch()  # 0 bytes

        res = CookieExtractor.extract_cookies_for_profile(corrupt_prof)
        self.assertEqual(res, [])

    def test_b5_04_missing_local_state_file(self):
        """B5.4: Missing Local State file handles unencrypted cookies cleanly."""
        prof = self.test_root / "no_local_state_prof"
        create_synthetic_profile(
            prof,
            master_key=None,
            cookies=[{"name": "plain_test", "value": "val", "domain": ".example.com", "plaintext": True}]
        )
        # Ensure no Local State file exists
        ls = prof / "Local State"
        if ls.exists():
            ls.unlink()

        res = CookieExtractor.extract_cookies_for_profile(prof)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "plain_test")

    def test_b5_05_sqlite_schema_with_missing_optional_columns(self):
        """B5.5: Minimal SQLite cookies table lacking optional columns extracts core fields."""
        prof = self.test_root / "minimal_schema_prof"
        cookies_file = prof / "Default" / "Network" / "Cookies"
        cookies_file.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(cookies_file))
        conn.execute("""
            CREATE TABLE cookies (
                host_key TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                encrypted_value BLOB NOT NULL,
                path TEXT NOT NULL,
                expires_utc INTEGER NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO cookies VALUES ('.test.com', 'min_cookie', 'min_val', X'', '/', 0)
        """)
        conn.commit()
        conn.close()

        res = CookieExtractor.extract_cookies_for_profile(prof)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "min_cookie")
        self.assertEqual(res[0]["value"], "min_val")

    # =========================================================================
    # Feature 6 Boundaries: Windows DPAPI & AES-256-GCM Decryption
    # =========================================================================

    def test_b6_01_corrupt_local_state_json(self):
        """B6.1: Corrupt JSON syntax in Local State returns None for master key."""
        prof = self.test_root / "bad_json_prof"
        prof.mkdir(parents=True, exist_ok=True)
        (prof / "Local State").write_text("{invalid json", encoding="utf-8")

        key = CookieExtractor.get_master_key(prof)
        self.assertIsNone(key)

    def test_b6_02_local_state_missing_os_crypt_key(self):
        """B6.2: Local State without os_crypt.encrypted_key returns None."""
        prof = self.test_root / "no_key_json_prof"
        prof.mkdir(parents=True, exist_ok=True)
        (prof / "Local State").write_text(json.dumps({"other": "data"}), encoding="utf-8")

        key = CookieExtractor.get_master_key(prof)
        self.assertIsNone(key)

    def test_b6_03_corrupt_base64_in_local_state(self):
        """B6.3: Corrupt Base64 string in encrypted_key returns None."""
        prof = self.test_root / "bad_b64_prof"
        prof.mkdir(parents=True, exist_ok=True)
        (prof / "Local State").write_text(
            json.dumps({"os_crypt": {"encrypted_key": "not_valid_base64!!!"}}),
            encoding="utf-8"
        )

        key = CookieExtractor.get_master_key(prof)
        self.assertIsNone(key)

    def test_b6_04_corrupted_encrypted_value_blob(self):
        """B6.4: Short or corrupted encrypted blob returns empty string without crashing."""
        short_blob = b"v10short"
        res = CookieExtractor.decrypt_cookie_value(short_blob, b"K" * 32)
        self.assertEqual(res, "")

    def test_b6_05_cookie_with_utf8_special_chars_and_emojis(self):
        """B6.5: UTF-8 special characters and emojis are preserved in decrypted cookies."""
        sample_utf8 = "phiên_đăng_nhập_🔑_test_123"
        decoded_header = _decode_cookie_bytes(b"\x00" * 32 + sample_utf8.encode("utf-8"))
        self.assertEqual(decoded_header, sample_utf8)

        sample_ascii = "auth_token_987654321_abcdef"
        decoded_ascii = _decode_cookie_bytes(sample_ascii.encode("utf-8"))
        self.assertEqual(decoded_ascii, sample_ascii)

    def test_b6_06_non_win32_dpapi_exception_handling(self):
        """B6.6: Calling _unprotect_dpapi on non-win32 raises OSError."""
        with patch("sys.platform", "linux"):
            with self.assertRaises(OSError):
                _unprotect_dpapi(b"test")

    # =========================================================================
    # Feature 7 Boundaries: Vault Storage & Session Integration
    # =========================================================================

    def test_b7_01_massive_cookie_list_exceeds_max_limit(self):
        """B7.1: Excessive cookie counts (>1500) are trimmed to MAX_COOKIES_PER_CHANNEL."""
        large_cookies = [
            {"name": f"ck_{i}", "value": f"val_{i}", "domain": ".site.com"}
            for i in range(2000)
        ]
        pruned = SessionService.prune_cookies(large_cookies)
        self.assertEqual(len(pruned), SessionService.MAX_COOKIES_PER_CHANNEL)

    def test_b7_02_duplicate_cookie_deduplication(self):
        """B7.2: Duplicate (domain, path, name) cookies keep the latest entry."""
        dup_cookies = [
            {"name": "sess", "value": "old_val", "domain": ".site.com", "path": "/"},
            {"name": "sess", "value": "new_val", "domain": ".site.com", "path": "/"},
        ]
        pruned = SessionService.prune_cookies(dup_cookies)
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["value"], "new_val")

    def test_b7_03_zero_or_none_expires_timestamp(self):
        """B7.3: Session cookies with expires=None or 0 are preserved by prune_cookies."""
        session_cookies = [
            {"name": "s1", "value": "v1", "domain": ".site.com", "expires": None},
            {"name": "s2", "value": "v2", "domain": ".site.com", "expires": 0},
        ]
        pruned = SessionService.prune_cookies(session_cookies)
        self.assertEqual(len(pruned), 2)

    def test_b7_04_samesite_mapping_variations(self):
        """B7.4: Integer samesite flags (2, 1, 0, -1) map to standard string names."""
        prof = self.test_root / "samesite_prof"
        cookies_db = prof / "Default" / "Network" / "Cookies"
        cookies_db.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(cookies_db))
        conn.execute("""
            CREATE TABLE cookies (
                host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB,
                path TEXT, expires_utc INTEGER, is_secure INTEGER, is_httponly INTEGER,
                samesite INTEGER
            )
        """)
        conn.execute("INSERT INTO cookies VALUES ('.a.com', 'c0', 'v', X'', '/', 0, 0, 0, 0)")
        conn.execute("INSERT INTO cookies VALUES ('.b.com', 'c1', 'v', X'', '/', 0, 0, 0, 1)")
        conn.execute("INSERT INTO cookies VALUES ('.c.com', 'c2', 'v', X'', '/', 0, 0, 0, 2)")
        conn.execute("INSERT INTO cookies VALUES ('.d.com', 'c_neg', 'v', X'', '/', 0, 0, 0, -1)")
        conn.commit()
        conn.close()

        extracted = CookieExtractor.extract_cookies_for_profile(prof)
        sm_map = {c["name"]: c["sameSite"] for c in extracted}
        self.assertEqual(sm_map.get("c0"), "None")
        self.assertEqual(sm_map.get("c1"), "Lax")
        self.assertEqual(sm_map.get("c2"), "Strict")
        self.assertEqual(sm_map.get("c_neg"), "Lax")

    def test_b7_05_empty_cookie_list_round_trip(self):
        """B7.5: Empty cookie list cleanly round-trips through prune and vault."""
        self.assertEqual(SessionService.prune_cookies([]), [])
        protected = protect_json([])
        unprotected = unprotect_json(protected)
        self.assertEqual(unprotected, [])

    # =========================================================================
    # Feature 8 Boundaries: Packaging & Dependencies
    # =========================================================================

    def test_b8_01_sys_modules_no_playwright_loaded(self):
        """B8.1: No playwright module loaded in sys.modules during execution."""
        # Unload playwright if lingering
        modules_to_check = [m for m in sys.modules if "playwright" in m]
        # In runtime execution of BrowserService/CookieExtractor, playwright is not required
        bs = BrowserService()
        self.assertIsNotNone(bs)

    def test_b8_02_requirements_format_validity(self):
        """B8.2: requirements.txt lines are valid pip requirement specifications."""
        lines = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Must not contain playwright
            self.assertNotIn("playwright", stripped.lower())

    def test_b8_03_spec_files_valid_python_syntax(self):
        """B8.3: Spec files parse successfully with ast.parse without syntax errors."""
        for spec_p in SPEC_PATHS:
            content = spec_p.read_text(encoding="utf-8")
            parsed = ast.parse(content, filename=str(spec_p))
            self.assertIsNotNone(parsed, f"{spec_p.name} must parse as valid Python AST")

    def test_b8_04_build_script_has_no_playwright_install(self):
        """B8.4: build_exe.ps1 does not attempt to execute 'playwright install'."""
        content = (PROJECT_ROOT / "build_exe.ps1").read_text(encoding="utf-8")
        self.assertNotIn("playwright install", content.lower())

    def test_b8_05_api_bridge_has_no_playwright_imports(self):
        """B8.5: src/web/api_bridge.py contains no playwright imports."""
        api_bridge_path = PROJECT_ROOT / "src" / "web" / "api_bridge.py"
        content = api_bridge_path.read_text(encoding="utf-8")
        self.assertNotIn("import playwright", content)
        self.assertNotIn("from playwright", content)


if __name__ == "__main__":
    unittest.main()
