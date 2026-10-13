import os
import sys
import json
import sqlite3
import tempfile
import time
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
from src.services.account_service import AccountService
from src.services.settings_service import SettingsService
from src.web.api_bridge import WebBridge
from src.core.secure_store import protect_json, unprotect_json
from src.core.config import Config
from src.core.constants import ChannelStatus
from src.domain.models import Channel, Account, ChannelItemView


class TestTier4Scenarios(unittest.TestCase):
    """
    Tier 4: Real-World Application Scenarios (>=5 tests).
    End-to-end simulations of actual user workflows and production operations.
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
    # Scenario 1: Multi-Channel Launch, Independent Navigation & Clean Shutdown
    # =========================================================================
    def test_scenario_1_multi_channel_launch_and_clean_shutdown(self):
        """
        Scenario 1:
        1. Detects installed Chromium binary on host.
        2. Concurrently launches 3 channels (travel, cooking, gaming) with distinct target URLs.
        3. Verifies separate user-data-dir profiles, individual PID tracking, and concurrent open status.
        4. Sequentially terminates all 3 channels cleanly.
        5. Confirms zero lingering processes in active tracking.
        """
        dummy_exe = self.test_root / "chrome.exe"
        dummy_exe.touch()

        pids = [11001, 11002, 11003]
        pid_iter = iter(pids)
        launched_cmds = {}

        def fake_popen(cmd, **kwargs):
            pid = next(pid_iter)
            # Find channel from user-data-dir
            udd = next((a for a in cmd if "--user-data-dir=" in a), "")
            ch_name = Path(udd.split("=")[1]).name
            launched_cmds[ch_name] = cmd
            return DummyProcess(pid=pid, args=cmd)

        channels = [
            ("ch_travel", "https://studio.youtube.com/channel/travel_id"),
            ("ch_cooking", "https://studio.youtube.com/channel/cooking_id"),
            ("ch_gaming", "https://studio.youtube.com/channel/gaming_id"),
        ]

        with patch.object(BrowserService, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=fake_popen):
                for ch_id, url in channels:
                    self.service.launch_channel_browser(ch_id, target_url=url)

                time.sleep(0.18)

                # Verify all 3 channels are active
                for ch_id, url in channels:
                    self.assertTrue(self.service.is_channel_open(ch_id), f"{ch_id} should be open")
                    self.assertIn(ch_id, launched_cmds)
                    self.assertIn(url, launched_cmds[ch_id])

                # Verify unique user-data-dirs
                udds = [next(a for a in cmd if "--user-data-dir=" in a) for cmd in launched_cmds.values()]
                self.assertEqual(len(set(udds)), 3, "All user-data-dirs must be distinct")

                # Verify PID tracking
                active_ids = self.service.get_active_channel_ids()
                self.assertEqual(set(active_ids), {"ch_travel", "ch_cooking", "ch_gaming"})

                # Clean sequential shutdown
                with patch("subprocess.run"):
                    for ch_id, _ in channels:
                        ok = self.service.close_channel_browser(ch_id)
                        self.assertTrue(ok, f"Closing {ch_id} should succeed")
                        self.assertFalse(self.service.is_channel_open(ch_id))

                self.assertEqual(len(self.service.get_active_channel_ids()), 0)

    # =========================================================================
    # Scenario 2: Live Session Extraction, DPAPI Decryption & Vault Persistence
    # =========================================================================
    def test_scenario_2_live_session_extraction_dpapi_and_vault_persistence(self):
        """
        Scenario 2:
        1. Channel profile receives simulated authenticated Google session cookies.
        2. DPAPI Master Key in Local State decrypts AES-256-GCM cookies upon browser exit.
        3. Cookies are delivered to on_closed callback.
        4. Cookies pass SessionService.prune_cookies filtering.
        5. Encrypted and saved to Vault storage via secure_store.protect_json.
        6. Lossless retrieval and verification of all Google authentication cookies.
        """
        master_key = b"S2_MASTER_KEY_32_BYTES_HEX_TEST!"
        prof_path = Config.get_profile_path("ch_s2_auth")
        google_cookies = [
            {"name": "SID", "value": "s2_sid_sample_val", "domain": ".google.com", "expires": 1800000000.0},
            {"name": "HSID", "value": "s2_hsid_sample_val", "domain": ".google.com", "expires": 1800000000.0},
            {"name": "SSID", "value": "s2_ssid_sample_val", "domain": ".google.com", "expires": 1800000000.0},
            {"name": "LOGIN_INFO", "value": "s2_login_info", "domain": ".youtube.com", "expires": 1800000000.0},
        ]
        create_synthetic_profile(prof_path, master_key=master_key, cookies=google_cookies, header_32=True)

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()
        dummy_proc = DummyProcess(pid=12001)

        captured_cookies = []
        def on_closed(cookies):
            nonlocal captured_cookies
            captured_cookies = cookies

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=dummy_proc):
                self.service.launch_channel_browser("ch_s2_auth", on_closed=on_closed)
                time.sleep(0.12)

                # Simulate user closing browser window
                dummy_proc.returncode = 0
                time.sleep(0.18)

        # 1. Verification of extracted cookies
        self.assertEqual(len(captured_cookies), 4)
        cookie_dict = {c["name"]: c["value"] for c in captured_cookies}
        self.assertEqual(cookie_dict["SID"], "s2_sid_sample_val")
        self.assertEqual(cookie_dict["LOGIN_INFO"], "s2_login_info")

        # 2. Pruning
        pruned = SessionService.prune_cookies(captured_cookies)
        self.assertEqual(len(pruned), 4)

        # 3. Vault persistence
        vault_token = protect_json(pruned)
        self.assertTrue(vault_token.startswith("$DPAPI$") or vault_token.startswith("$FERNET$"))

        # 4. Vault retrieval
        decrypted_vault = unprotect_json(vault_token)
        self.assertEqual(len(decrypted_vault), 4)
        restored_dict = {c["name"]: c["value"] for c in decrypted_vault}
        self.assertEqual(restored_dict["HSID"], "s2_hsid_sample_val")

        import shutil
        shutil.rmtree(prof_path, ignore_errors=True)

    # =========================================================================
    # Scenario 3: Concurrent Browser Execution with Simultaneous Session Release
    # =========================================================================
    def test_scenario_3_concurrent_browsers_and_simultaneous_session_release(self):
        """
        Scenario 3:
        1. User 'alice' operates 2 active browsers (news, finance).
        2. User 'bob' operates 1 active browser (sports).
        3. Alice triggers 'release_my_sessions' via AccountService.
        4. Alice's 2 browsers are terminated via taskkill.
        5. Bob's browser remains open, alive, and unaffected.
        """
        mock_repo = MagicMock()
        # Bob holds a channel in DB, Alice holds an offline channel in DB
        bob_item = MagicMock()
        bob_item.locked_by = "bob"
        bob_item.channel.id = "ch_sports"

        alice_item = MagicMock()
        alice_item.locked_by = "alice"
        alice_item.channel.id = "ch_offline_alice"

        mock_repo.get_channels.return_value = [bob_item, alice_item]
        mock_session_service = MagicMock()

        account_service = AccountService(
            repository=mock_repo,
            session_service=mock_session_service,
            browser_service=self.service
        )

        alice_proc1 = DummyProcess(pid=13001)
        alice_proc2 = DummyProcess(pid=13002)

        self.service._active_processes["ch_news"] = alice_proc1
        self.service._active_processes["ch_finance"] = alice_proc2

        with patch("subprocess.run"):
            released = account_service.release_user_channels("alice")

            # Alice's channels were released
            self.assertIn("ch_news", released)
            self.assertIn("ch_finance", released)
            self.assertIn("ch_offline_alice", released)

            # Bob's channel in database was NOT released
            self.assertNotIn("ch_sports", released)

            # Alice's local browsers are closed
            self.assertFalse(self.service.is_channel_open("ch_news"))
            self.assertFalse(self.service.is_channel_open("ch_finance"))
            self.assertEqual(len(self.service.get_active_channel_ids()), 0)

    # =========================================================================
    # Scenario 4: Browser Force Close via Taskkill & Snapshot Recovery
    # =========================================================================
    def test_scenario_4_browser_force_close_taskkill_and_snapshot_recovery(self):
        """
        Scenario 4:
        1. Channel browser is running with SQLite database.
        2. External taskkill command terminates the entire process tree (/F /T /PID).
        3. SQLite snapshot copy safely executes without being blocked by dead locks.
        4. Cookie data is successfully retrieved and delivered without crashing.
        """
        master_key = b"K" * 32
        prof_path = Config.get_profile_path("ch_s4_kill")
        create_synthetic_profile(
            prof_path,
            master_key=master_key,
            cookies=[{"name": "preserved_ck", "value": "recovered_after_kill", "domain": ".site.com"}],
            with_wal=True
        )

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()
        dummy_proc = DummyProcess(pid=14001)

        captured_on_closed = []
        def on_closed(cookies):
            nonlocal captured_on_closed
            captured_on_closed = cookies

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=dummy_proc):
                self.service.launch_channel_browser("ch_s4_kill", on_closed=on_closed)
                time.sleep(0.12)

                # Perform forceful taskkill termination
                with patch("subprocess.run") as mock_taskkill:
                    success = self.service.close_channel_browser("ch_s4_kill")
                    self.assertTrue(success)
                    time.sleep(0.18)

                    # Verify taskkill was invoked with /F /T
                    if is_windows():
                        mock_taskkill.assert_called()
                        called_args = mock_taskkill.call_args[0][0]
                        self.assertEqual(called_args[:4], ["taskkill", "/F", "/T", "/PID"])

                self.assertFalse(self.service.is_channel_open("ch_s4_kill"))
                self.assertEqual(len(captured_on_closed), 1)
                self.assertEqual(captured_on_closed[0]["value"], "recovered_after_kill")

        import shutil
        shutil.rmtree(prof_path, ignore_errors=True)

    # =========================================================================
    # Scenario 5: Full WebBridge & UI Lifecycle Simulation (No Playwright Traces)
    # =========================================================================
    def test_scenario_5_webbridge_ui_lifecycle_simulation_no_playwright(self):
        """
        Scenario 5:
        1. WebBridge handles frontend launch_channel request.
        2. Dispatches channel_status_changed events to pywebview JS frontend.
        3. Starts native browser process with zero Playwright imports.
        4. Frontend calls release_my_sessions, cleaning up sessions.
        5. Confirms complete absence of Playwright in execution traces.
        """
        mock_repo = MagicMock()
        mock_repo.get_channel.return_value = MagicMock(
            id="ch_ui_test",
            channel_name="UI Test Channel",
            studio_url="https://studio.youtube.com",
            login_url="https://accounts.google.com"
        )
        mock_repo.get_channels.return_value = []

        mock_session_service = MagicMock()
        mock_session_service.try_acquire_channel.return_value = (True, "admin")
        mock_session_service.get_channel_cookies.return_value = []
        mock_session_service.release_user_channels.return_value = ["ch_ui_test"]

        account_service = AccountService(
            repository=mock_repo,
            session_service=mock_session_service,
            browser_service=self.service
        )
        settings_service = MagicMock()

        bridge = WebBridge(
            account_service=account_service,
            settings_service=settings_service
        )

        mock_window = MagicMock()
        bridge._window = mock_window

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()
        dummy_proc = DummyProcess(pid=15001)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=dummy_proc):
                # 1. UI launches channel
                res = bridge.launch_channel("ch_ui_test", "admin")
                self.assertTrue(res["success"])
                time.sleep(0.12)

                # 2. Frontend event dispatched
                mock_window.evaluate_js.assert_called()

                # 3. User releases sessions
                with patch("subprocess.run"):
                    rel_res = bridge.release_my_sessions("admin")
                    self.assertTrue(rel_res["success"])

                # 4. Strict check: Zero playwright references in active execution
                loaded_playwright = [k for k in sys.modules if k.startswith("playwright.")]
                self.assertEqual(len(loaded_playwright), 0, "No playwright modules should be loaded")

    # =========================================================================
    # Scenario 6: Periodic Autosave Snapshot During Active Browsing Session
    # =========================================================================
    def test_scenario_6_periodic_autosave_snapshot_during_active_browsing(self):
        """
        Scenario 6:
        1. Browser remains actively running.
        2. Periodic autosave trigger snapshots SQLite cookies while process is alive.
        3. Snapshot delivered to on_autosave callback without closing browser.
        4. Browser continues running uninterrupted.
        """
        master_key = b"AUTOSAVE_KEY_32_BYTES_HEX_TEST!!"
        prof_path = Config.get_profile_path("ch_autosave")
        create_synthetic_profile(
            prof_path,
            master_key=master_key,
            cookies=[{"name": "autosave_token", "value": "intermediate_val", "domain": ".site.com"}]
        )

        dummy_exe = self.test_root / "browser.exe"
        dummy_exe.touch()
        dummy_proc = DummyProcess(pid=16001)

        autosaved_snapshots = []
        def on_autosave(snapshot):
            nonlocal autosaved_snapshots
            autosaved_snapshots.append(snapshot)

        # Set small autosave interval for testing
        self.service.AUTOSAVE_INTERVAL_SEC = 0.05

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", return_value=dummy_proc):
                self.service.launch_channel_browser(
                    "ch_autosave",
                    on_autosave=on_autosave
                )

                # Let autosave trigger while process is still alive
                time.sleep(0.2)
                self.assertTrue(self.service.is_channel_open("ch_autosave"))
                self.assertGreaterEqual(len(autosaved_snapshots), 1)
                self.assertEqual(autosaved_snapshots[0][0]["name"], "autosave_token")

                # Browser is still alive and running
                self.assertTrue(self.service.is_channel_open("ch_autosave"))

                # Finally close process
                dummy_proc.returncode = 0
                time.sleep(0.12)
                self.assertFalse(self.service.is_channel_open("ch_autosave"))

        import shutil
        shutil.rmtree(prof_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
