import os
import sys
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.test_helpers import (
    create_synthetic_profile,
    DummyProcess,
    PROJECT_ROOT,
    is_windows
)

from src.services.browser_service import BrowserService
from src.services.cookie_extractor import CookieExtractor
from src.services.session_service import SessionService
from src.core.secure_store import protect_json, unprotect_json
from src.core.config import Config


class TestTier3Pairwise(unittest.TestCase):
    """
    Tier 3: Cross-Feature Combinations & Pairwise Interactions (>=8 tests).
    Validates cross-module integration, state transitions, and feature pairings.
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

    def test_p1_detection_and_launch_integration(self):
        """P1: [F1 Detection + F2 Execution] Detected binary is correctly fed to Popen with proper CLI args."""
        dummy_exe = self.test_root / "chrome.exe"
        dummy_exe.touch()

        captured_args = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured_args
            captured_args = cmd
            return DummyProcess(pid=5001, args=cmd)

        with patch.object(BrowserService, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("chan_p1", target_url="https://youtube.com")
                import time
                time.sleep(0.12)

                self.assertEqual(captured_args[0], str(dummy_exe))
                self.assertTrue(any(a.startswith("--user-data-dir=") for a in captured_args))
                self.assertIn("https://youtube.com", captured_args)

    def test_p2_launch_concurrency_and_pid_tracking(self):
        """P2: [F2 Execution + F3 PID Tracking + F4 Concurrency] Multiple channels launched concurrently have unique PIDs and active state."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        pids = [6001, 6002, 6003]
        pid_iter = iter(pids)

        def fake_popen(cmd, **kwargs):
            return DummyProcess(pid=next(pid_iter), args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                self.service.launch_channel_browser("ch_p2_a")
                self.service.launch_channel_browser("ch_p2_b")
                self.service.launch_channel_browser("ch_p2_c")

                import time
                time.sleep(0.15)

                self.assertTrue(self.service.is_channel_open("ch_p2_a"))
                self.assertTrue(self.service.is_channel_open("ch_p2_b"))
                self.assertTrue(self.service.is_channel_open("ch_p2_c"))

                active_pids = {
                    self.service.get_active_pid("ch_p2_a"),
                    self.service.get_active_pid("ch_p2_b"),
                    self.service.get_active_pid("ch_p2_c")
                }
                self.assertEqual(active_pids, {6001, 6002, 6003})

    def test_p3_lifecycle_close_and_cookie_extraction(self):
        """P3: [F3 Lifecycle + F5 SQLite Snapshot + F6 Decryption] Process termination extracts and decrypts SQLite cookies to callback."""
        master_key = b"P" * 32
        prof_path = Config.get_profile_path("ch_p3")
        create_synthetic_profile(
            prof_path,
            master_key=master_key,
            cookies=[{"name": "p3_cookie", "value": "p3_secret_val", "domain": ".google.com"}]
        )

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()
        dummy_proc = DummyProcess(pid=7001)

        extracted_result = []
        def on_closed(cookies):
            nonlocal extracted_result
            extracted_result = cookies

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=dummy_proc):
                self.service.launch_channel_browser("ch_p3", on_closed=on_closed)

                import time
                time.sleep(0.12)
                self.assertTrue(self.service.is_channel_open("ch_p3"))

                # Terminate process
                dummy_proc.returncode = 0
                time.sleep(0.15)

                self.assertFalse(self.service.is_channel_open("ch_p3"))
                self.assertEqual(len(extracted_result), 1)
                self.assertEqual(extracted_result[0]["name"], "p3_cookie")
                self.assertEqual(extracted_result[0]["value"], "p3_secret_val")

        import shutil
        shutil.rmtree(prof_path, ignore_errors=True)

    def test_p4_extraction_vault_storage_roundtrip(self):
        """P4: [F5 Snapshot + F6 Decryption + F7 Vault Storage] Snapshot extracted cookies pass pruning and vault encryption."""
        master_key = b"V" * 32
        prof_path = self.test_root / "profile_p4"
        sample_cookies = [
            {"name": "SID", "value": "sid_secret", "domain": ".google.com", "expires": 1800000000.0},
            {"name": "HSID", "value": "hsid_secret", "domain": ".google.com", "expires": 1800000000.0},
        ]
        create_synthetic_profile(prof_path, master_key=master_key, cookies=sample_cookies)

        extracted = CookieExtractor.extract_cookies_for_profile(prof_path)
        self.assertEqual(len(extracted), 2)

        pruned = SessionService.prune_cookies(extracted)
        self.assertEqual(len(pruned), 2)

        vault_payload = protect_json(pruned)
        restored = unprotect_json(vault_payload)
        self.assertEqual(len(restored), 2)
        restored_names = {c["name"] for c in restored}
        self.assertEqual(restored_names, {"SID", "HSID"})

    def test_p5_multi_channel_launch_and_bulk_close(self):
        """P5: [F2 Execution + F4 Concurrency + F3 Bulk Close] Launch 3 channels, close_all terminates all 3 cleanly."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        self.service._active_processes["bulk_1"] = DummyProcess(pid=8001)
        self.service._active_processes["bulk_2"] = DummyProcess(pid=8002)
        self.service._active_processes["bulk_3"] = DummyProcess(pid=8003)

        with patch("subprocess.run"):
            closed = self.service.close_all_browsers()
            self.assertEqual(closed, 3)
            self.assertEqual(len(self.service.get_active_channel_ids()), 0)

    def test_p6_edge_fallback_launch_with_zero_playwright(self):
        """P6: [F1 Edge Fallback + F2 Launch + F8 Zero Playwright] Edge detected fallback launches native process without Playwright."""
        fake_edge = self.test_root / "msedge.exe"
        fake_edge.touch()

        captured = []
        def fake_popen(cmd, **kwargs):
            nonlocal captured
            captured = cmd
            return DummyProcess(pid=9001, args=cmd)

        with patch.object(BrowserService, "_find_chrome", return_value=None):
            with patch.object(BrowserService, "_find_edge", return_value=fake_edge):
                with patch("subprocess.Popen", side_effect=fake_popen):
                    self.service.launch_channel_browser("edge_ch")
                    import time
                    time.sleep(0.12)

                    self.assertEqual(captured[0], str(fake_edge))
                    self.assertNotIn("playwright", sys.modules)

    def test_p7_process_crash_safe_recovery(self):
        """P7: [F3 Crash Lifecycle + F5 Snapshot Recovery + F7 Vault State] Abnormal exit recovers cookies safely."""
        prof_path = Config.get_profile_path("crash_ch")
        create_synthetic_profile(
            prof_path,
            master_key=b"C" * 32,
            cookies=[{"name": "crash_token", "value": "saved_before_crash", "domain": ".site.com"}]
        )

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()
        dummy_proc = DummyProcess(pid=9501)

        callback_cookies = []
        def on_closed(cookies):
            nonlocal callback_cookies
            callback_cookies = cookies

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=dummy_proc):
                self.service.launch_channel_browser("crash_ch", on_closed=on_closed)

                import time
                time.sleep(0.12)
                # Crash process abnormally
                dummy_proc.returncode = -9
                time.sleep(0.15)

                self.assertFalse(self.service.is_channel_open("crash_ch"))
                self.assertEqual(len(callback_cookies), 1)
                self.assertEqual(callback_cookies[0]["value"], "saved_before_crash")

        import shutil
        shutil.rmtree(prof_path, ignore_errors=True)

    def test_p8_concurrent_profiles_isolated_decryption(self):
        """P8: [F4 Concurrency + F6 Decryption + F7 Vault] Different profiles with distinct keys decrypt independently."""
        key_a = b"A" * 32
        key_b = b"B" * 32

        prof_a = self.test_root / "prof_isolated_a"
        prof_b = self.test_root / "prof_isolated_b"

        create_synthetic_profile(prof_a, master_key=key_a, cookies=[{"name": "ck_a", "value": "val_a", "domain": ".a.com"}])
        create_synthetic_profile(prof_b, master_key=key_b, cookies=[{"name": "ck_b", "value": "val_b", "domain": ".b.com"}])

        extracted_a = CookieExtractor.extract_cookies_for_profile(prof_a)
        extracted_b = CookieExtractor.extract_cookies_for_profile(prof_b)

        self.assertEqual(len(extracted_a), 1)
        self.assertEqual(extracted_a[0]["value"], "val_a")
        self.assertEqual(len(extracted_b), 1)
        self.assertEqual(extracted_b[0]["value"], "val_b")

    def test_p9_taskkill_force_close_and_subsequent_relaunch(self):
        """P9: [F2 Native Launch + F3 Taskkill + F4 Profile Reuse] Close via taskkill allows immediate relaunch with new PID."""
        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()

        proc1 = DummyProcess(pid=9901)
        proc2 = DummyProcess(pid=9902)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=proc1):
                self.service.launch_channel_browser("relaunch_ch")
                import time
                time.sleep(0.12)
                self.assertTrue(self.service.is_channel_open("relaunch_ch"))

            with patch("subprocess.run"):
                self.service.close_channel_browser("relaunch_ch")
                time.sleep(0.15)
                self.assertFalse(self.service.is_channel_open("relaunch_ch"))

            with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
                with patch("subprocess.Popen", return_value=proc2):
                    self.service.launch_channel_browser("relaunch_ch")
                    time.sleep(0.15)
                    self.assertTrue(self.service.is_channel_open("relaunch_ch"))
                    self.assertEqual(self.service.get_active_pid("relaunch_ch"), 9902)

    def test_p10_account_service_session_release_integration(self):
        """P10: [F3 Lifecycle + F4 Multi-Profile + F7 Session] AccountService.release_user_channels interacts cleanly with _active_contexts."""
        from src.services.account_service import AccountService
        mock_repo = MagicMock()
        mock_repo.get_channels.return_value = []
        mock_session_service = MagicMock()

        account_service = AccountService(
            repository=mock_repo,
            session_service=mock_session_service,
            browser_service=self.service
        )

        self.service._active_processes["ch_rel_1"] = DummyProcess(pid=10001)
        self.service._active_processes["ch_rel_2"] = DummyProcess(pid=10002)

        with patch("subprocess.run"):
            released = account_service.release_user_channels("test_user")
            self.assertIn("ch_rel_1", released)
            self.assertIn("ch_rel_2", released)
            self.assertEqual(len(self.service.get_active_channel_ids()), 0)


if __name__ == "__main__":
    unittest.main()
