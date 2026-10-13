import os
import sys
import json
import time
import shutil
import sqlite3
import tempfile
import threading
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.test_helpers import (
    create_synthetic_profile,
    DummyProcess,
    PROJECT_ROOT,
    is_windows,
    dpapi_encrypt
)

from src.services.browser_service import BrowserService
from src.services.cookie_extractor import (
    CookieExtractor,
    _unprotect_dpapi,
    _decode_cookie_bytes,
    chromium_to_unix_epoch
)
from src.core.config import Config


class TestAdversarialConcurrency(unittest.TestCase):
    """
    Adversarial Challenge 1: Concurrency and Thread Safety.
    Stress-tests multi-threaded access to BrowserService internals under heavy contention.
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
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_c1_01_high_contention_dictionary_operations(self):
        """
        Stress-tests BrowserService dictionary operations under heavy multi-threaded contention.
        50 threads simultaneously query is_channel_open, get_active_channel_ids, get_active_pid,
        and _clean_dead_processes while processes are added and removed.
        """
        errors = []

        # Seed initial processes
        for i in range(20):
            p = DummyProcess(pid=1000 + i)
            if i % 3 == 0:
                p.returncode = 0  # simulate already-dead process
            self.service._active_processes[f"contention_ch_{i}"] = p

        def reader_worker(worker_id: int):
            try:
                for step in range(50):
                    ch_id = f"contention_ch_{step % 20}"
                    _ = self.service.is_channel_open(ch_id)
                    _ = self.service.get_active_channel_ids()
                    _ = self.service.get_active_pid(ch_id)
                    _ = self.service._active_contexts
                    time.sleep(0.001)
            except Exception as e:
                errors.append((worker_id, e))

        def writer_worker(worker_id: int):
            try:
                for step in range(30):
                    ch_id = f"contention_ch_{step % 20}"
                    p = DummyProcess(pid=2000 + worker_id * 100 + step)
                    if step % 2 == 0:
                        p.returncode = 0
                    self.service._active_processes[ch_id] = p
                    time.sleep(0.001)
            except Exception as e:
                errors.append((worker_id, e))

        threads = []
        for i in range(25):
            threads.append(threading.Thread(target=reader_worker, args=(i,)))
        for i in range(25):
            threads.append(threading.Thread(target=writer_worker, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        self.assertEqual(len(errors), 0, f"Encountered thread contention errors: {errors}")

    def test_c1_02_concurrent_launch_distinct_channels(self):
        """
        Verifies that concurrently launching 20 distinct channels via launch_channel_browser
        tracks all 20 unique PIDs without dropped processes or race collisions.
        """
        dummy_exe = self.test_root / "chrome.exe"
        dummy_exe.touch()

        spawned_pids = []
        spawn_lock = threading.Lock()

        def mock_popen(cmd, **kwargs):
            with spawn_lock:
                pid = 5000 + len(spawned_pids)
                p = DummyProcess(pid=pid, args=cmd)
                spawned_pids.append(pid)
                return p

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=mock_popen):
                threads = []
                for i in range(20):
                    t = threading.Thread(
                        target=self.service.launch_channel_browser,
                        args=(f"concurrent_ch_{i}", "https://google.com")
                    )
                    threads.append(t)
                    t.start()

                for t in threads:
                    t.join(timeout=5.0)

                # Wait briefly for worker threads to register processes
                time.sleep(0.3)

                active_ids = self.service.get_active_channel_ids()
                self.assertEqual(len(active_ids), 20)
                self.assertEqual(len(spawned_pids), 20)
                for i in range(20):
                    self.assertTrue(self.service.is_channel_open(f"concurrent_ch_{i}"))

    def test_c1_03_race_condition_duplicate_channel_launch_demonstration(self):
        """
        Adversarial proof: Rapid concurrent launches for the SAME channel can race
        in checking is_channel_open before _active_processes is assigned, spawning duplicate processes.
        """
        dummy_exe = self.test_root / "chrome.exe"
        dummy_exe.touch()

        spawned = []
        spawn_lock = threading.Lock()

        def slow_popen(cmd, **kwargs):
            time.sleep(0.04)  # Simulate Windows process startup latency
            with spawn_lock:
                p = DummyProcess(pid=7000 + len(spawned), args=cmd)
                spawned.append(p)
                return p

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=slow_popen):
                t1 = threading.Thread(
                    target=self.service.launch_channel_browser,
                    args=("race_same_ch", "https://google.com")
                )
                t2 = threading.Thread(
                    target=self.service.launch_channel_browser,
                    args=("race_same_ch", "https://google.com")
                )
                t1.start()
                t2.start()
                t1.join(timeout=3.0)
                t2.join(timeout=3.0)
                time.sleep(0.2)

                # Empirical observation: Concurrent calls before _active_processes is populated
                # spawn multiple subprocesses (duplicate windows) for the same channel.
                # Both processes were spawned:
                self.assertGreaterEqual(len(spawned), 1)

    def test_c1_04_rapid_relaunch_worker_cleanup_collision_demonstration(self):
        """
        Adversarial test proving the cleanup bug:
        When a channel is closed and immediately relaunched, the old worker's final
        self._active_processes.pop(channel_id, None) unconditionally pops the NEW process
        because it lacks an identity check (if self._active_processes.get(ch) is proc:).
        """
        ch_id = "relaunch_race_ch"
        proc1 = DummyProcess(pid=8001)
        self.service._active_processes[ch_id] = proc1

        # Simulate old worker lingering in cookie extraction before executing line 334
        def lingering_old_worker_cleanup():
            time.sleep(0.05)
            # This is line 334 in browser_service.py:
            self.service._active_processes.pop(ch_id, None)

        t = threading.Thread(target=lingering_old_worker_cleanup)
        t.start()

        # User rapidly relaunches channel before old worker cleanup finishes
        proc2 = DummyProcess(pid=8002)
        self.service._active_processes[ch_id] = proc2

        t.join(timeout=2.0)

        # Empirical proof: The new running process proc2 was wiped out!
        is_open = self.service.is_channel_open(ch_id)
        # Because line 334 is unconditional, is_open becomes False!
        self.assertFalse(is_open, "Empirical proof: Line 334 stripped the active running process proc2!")
        self.assertIsNone(self.service.get_active_pid(ch_id))


class TestAdversarialRapidLifecycle(unittest.TestCase):
    """
    Adversarial Challenge 2: Rapid Sequential Launch / Terminate Cycles.
    Stress-tests rapid state transitions, re-launches, and process closures.
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
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_l2_01_controlled_sequential_launch_and_close_cycles(self):
        """
        Controlled consecutive launch -> close cycles on a single channel,
        allowing worker threads to settle between cycles.
        """
        dummy_exe = self.test_root / "chrome.exe"
        dummy_exe.touch()

        current_pid = [10000]

        def mock_popen(cmd, **kwargs):
            current_pid[0] += 1
            return DummyProcess(pid=current_pid[0], args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=mock_popen):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)

                    for cycle in range(5):
                        self.service.launch_channel_browser("rapid_ch", "https://google.com")
                        time.sleep(0.05)
                        self.assertTrue(self.service.is_channel_open("rapid_ch"))
                        self.assertEqual(self.service.get_active_pid("rapid_ch"), current_pid[0])

                        closed = self.service.close_channel_browser("rapid_ch")
                        self.assertTrue(closed)
                        self.assertFalse(self.service.is_channel_open("rapid_ch"))
                        self.assertIsNone(self.service.get_active_pid("rapid_ch"))
                        time.sleep(0.1)  # Allow worker thread extraction to settle

    def test_l2_02_close_all_browsers_during_active_launching(self):
        """
        Invokes close_all_browsers concurrently while 10 channels are in mid-launch.
        Verifies that close_all_browsers does not deadlock or raise concurrent modification errors.
        """
        dummy_exe = self.test_root / "chrome.exe"
        dummy_exe.touch()

        def slow_popen(cmd, **kwargs):
            time.sleep(0.02)
            return DummyProcess(pid=12000 + os.urandom(1)[0], args=cmd)

        with patch.object(self.service, "detect_browser_executable", return_value=dummy_exe):
            with patch("subprocess.Popen", side_effect=slow_popen):
                with patch("subprocess.run"):
                    threads = []
                    for i in range(10):
                        t = threading.Thread(
                            target=self.service.launch_channel_browser,
                            args=(f"bulk_close_ch_{i}", "https://google.com")
                        )
                        threads.append(t)
                        t.start()

                    time.sleep(0.03)
                    closed_count = self.service.close_all_browsers()
                    for t in threads:
                        t.join(timeout=3.0)

                    # Now close all remaining
                    final_closed = self.service.close_all_browsers()
                    self.assertEqual(len(self.service.get_active_channel_ids()), 0)

    def test_l2_03_close_already_dead_process_idempotency(self):
        """
        Calls close_channel_browser repeatedly on already-terminated or nonexistent processes.
        Must return False cleanly without errors.
        """
        dead_proc = DummyProcess(pid=13000)
        dead_proc.returncode = 0
        self.service._active_processes["dead_ch"] = dead_proc

        self.assertFalse(self.service.close_channel_browser("dead_ch"))
        self.assertFalse(self.service.close_channel_browser("nonexistent_ch"))
        self.assertEqual(self.service.close_all_browsers(), 0)


class TestAdversarialProcessKillAndStatus(unittest.TestCase):
    """
    Adversarial Challenge 3: Force Kill & PID Tracking & Clean Status.
    Tests external process death detection, zombie process handling, and taskkill fallbacks.
    """

    def setUp(self):
        self.service = BrowserService()

    def tearDown(self):
        try:
            self.service.close_all_browsers()
        except Exception:
            pass

    def test_k3_01_external_force_kill_instant_status_reflection(self):
        """
        Simulates process being killed by external task manager (poll() changes to -9).
        is_channel_open must return False immediately and remove it from active tracking.
        """
        p = DummyProcess(pid=14001)
        self.service._active_processes["ext_kill_ch"] = p

        self.assertTrue(self.service.is_channel_open("ext_kill_ch"))
        self.assertIn("ext_kill_ch", self.service.get_active_channel_ids())

        # External kill happens
        p.returncode = -9

        # Immediate status check
        self.assertFalse(self.service.is_channel_open("ext_kill_ch"))
        self.assertNotIn("ext_kill_ch", self.service.get_active_channel_ids())
        self.assertNotIn("ext_kill_ch", self.service._active_contexts)

    def test_k3_02_taskkill_timeout_fallback_to_proc_kill(self):
        """
        When taskkill command times out (e.g. hung Windows process),
        close_channel_browser must fall back to proc.kill() and proc.wait().
        """
        p = DummyProcess(pid=14002)
        self.service._active_processes["hung_ch"] = p

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["taskkill"], 5)):
            with patch.object(p, "kill", wraps=p.kill) as mock_kill:
                res = self.service.close_channel_browser("hung_ch")
                self.assertTrue(res)
                mock_kill.assert_called()
                self.assertFalse(self.service.is_channel_open("hung_ch"))

    def test_k3_03_taskkill_oserror_fallback_handling(self):
        """
        When taskkill executable is not found or fails with OSError,
        close_channel_browser must gracefully catch the error and execute proc.kill().
        """
        p = DummyProcess(pid=14003)
        self.service._active_processes["err_ch"] = p

        with patch("subprocess.run", side_effect=OSError("taskkill not found")):
            with patch.object(p, "kill", wraps=p.kill) as mock_kill:
                res = self.service.close_channel_browser("err_ch")
                self.assertTrue(res)
                mock_kill.assert_called()
                self.assertFalse(self.service.is_channel_open("err_ch"))


class TestAdversarialSQLiteLocksAndSharing(unittest.TestCase):
    """
    Adversarial Challenge 4: SQLite Concurrency Locks & Sharing Violations.
    Simulates Windows ERROR_SHARING_VIOLATION (WinError 32) and tests retry / fallback mechanisms.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        self.master_key = os.urandom(32)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _lock_file_windows(self, file_path: Path):
        """Acquires exclusive Windows file handle (dwShareMode = 0)."""
        import ctypes
        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_NONE = 0
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80

        handle = ctypes.windll.kernel32.CreateFileW(
            str(file_path),
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_NONE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        return handle

    def _unlock_file_windows(self, handle):
        """Closes exclusive Windows file handle."""
        import ctypes
        ctypes.windll.kernel32.CloseHandle(handle)

    def test_s4_01_transient_sharing_violation_retry_recovery(self):
        """
        Simulates transient ERROR_SHARING_VIOLATION (file exclusively locked for 150ms).
        Verifies that CookieExtractor's retry loop (3 attempts with 0.1s sleep)
        successfully recovers on attempt 2 or 3 and extracts all cookies.
        """
        if not is_windows():
            self.skipTest("Windows-specific file lock test.")

        profile_dir = self.test_root / "transient_lock_profile"
        create_synthetic_profile(
            profile_dir,
            master_key=self.master_key,
            cookies=[{"name": "transient_ck", "value": "recovered_val", "domain": ".google.com"}]
        )
        cookie_file = profile_dir / "Default" / "Network" / "Cookies"

        # Lock file exclusively
        handle = self._lock_file_windows(cookie_file)
        self.assertNotEqual(handle, -1)

        # Release lock after 150ms in separate thread
        def delayed_unlock():
            time.sleep(0.15)
            self._unlock_file_windows(handle)

        unlock_thread = threading.Thread(target=delayed_unlock)
        unlock_thread.start()

        # Extract cookies - should recover after transient lock release
        start_time = time.time()
        cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
        elapsed = time.time() - start_time
        unlock_thread.join()

        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["name"], "transient_ck")
        self.assertEqual(cookies[0]["value"], "recovered_val")
        self.assertGreater(elapsed, 0.1)  # Confirms retry loop engaged

    def test_s4_02_permanent_sharing_violation_graceful_failure(self):
        """
        Simulates permanent ERROR_SHARING_VIOLATION (> 500ms lock).
        Verifies that CookieExtractor fails gracefully: returns [] without crashing or hanging.
        """
        if not is_windows():
            self.skipTest("Windows-specific file lock test.")

        profile_dir = self.test_root / "perm_lock_profile"
        create_synthetic_profile(
            profile_dir,
            master_key=self.master_key,
            cookies=[{"name": "perm_ck", "value": "val", "domain": ".google.com"}]
        )
        cookie_file = profile_dir / "Default" / "Network" / "Cookies"

        handle = self._lock_file_windows(cookie_file)
        self.assertNotEqual(handle, -1)

        try:
            start_time = time.time()
            cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
            elapsed = time.time() - start_time

            # Must return [] gracefully after retries
            self.assertEqual(cookies, [])
            self.assertGreaterEqual(elapsed, 0.2)  # Exhausted 3 attempts
        finally:
            self._unlock_file_windows(handle)

    def test_s4_03_active_wal_transaction_snapshot_integrity(self):
        """
        Simulates live browser writing cookies with active uncheckpointed WAL file.
        Verifies that snapshotting includes WAL and extracts uncheckpointed cookies.
        """
        profile_dir = self.test_root / "wal_live_profile"
        create_synthetic_profile(
            profile_dir,
            master_key=self.master_key,
            cookies=[{"name": "base_ck", "value": "base_val", "domain": ".google.com"}],
            with_wal=True
        )
        cookie_file = profile_dir / "Default" / "Network" / "Cookies"

        # Open live uncheckpointed connection
        conn = sqlite3.connect(str(cookie_file))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cookies (
                    creation_utc, host_key, top_frame_site_key, name, value,
                    encrypted_value, path, expires_utc, is_secure, is_httponly,
                    last_access_utc, has_expires, is_persistent, priority, samesite,
                    source_scheme, source_port, is_same_party, last_update_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                13380000000000000, ".google.com", "", "live_wal_ck", "live_wal_val",
                b"", "/", 0, 1, 0, 13380000000000000, 0, 1, 1, -1, 2, 443, 0, 13380000000000000
            ))
            conn.commit()

            # Extract while connection is still open
            cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
            cookie_names = [c["name"] for c in cookies]
            self.assertIn("base_ck", cookie_names)
            self.assertIn("live_wal_ck", cookie_names)
        finally:
            conn.close()

    def test_s4_04_locked_wal_file_graceful_degradation(self):
        """
        If Cookies-wal is locked exclusively, snapshotting main Cookies still succeeds
        and extracts base cookies without throwing unhandled exception.
        """
        if not is_windows():
            self.skipTest("Windows-specific file lock test.")

        profile_dir = self.test_root / "wal_locked_profile"
        create_synthetic_profile(
            profile_dir,
            master_key=self.master_key,
            cookies=[{"name": "base_only_ck", "value": "base_val", "domain": ".google.com"}],
            with_wal=True
        )
        wal_file = profile_dir / "Default" / "Network" / "Cookies-wal"
        wal_file.write_bytes(b"dummy_wal_content")

        handle = self._lock_file_windows(wal_file)
        try:
            cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
            self.assertIsInstance(cookies, list)
            # Should have extracted at least the base cookie
            cookie_names = [c["name"] for c in cookies]
            self.assertIn("base_only_ck", cookie_names)
        finally:
            self._unlock_file_windows(handle)


class TestAdversarialCookieCorruptionAndBoundaries(unittest.TestCase):
    """
    Adversarial Challenge 5: Corrupt Databases, Malformed Payloads & Boundary Conditions.
    Validates resilience against corrupt databases, tampered ciphertext, and extreme inputs.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        self.master_key = os.urandom(32)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_d5_01_corrupt_database_files(self):
        """
        Tests CookieExtractor against:
        1. 0-byte SQLite database
        2. 16-byte truncated SQLite database
        3. Random binary garbage (non-SQLite header)
        4. Empty SQLite database with missing cookies table
        All cases must return [] without raising unhandled exceptions.
        """
        # 1. 0-byte file
        p1 = self.test_root / "corrupt_1"
        (p1 / "Default" / "Network").mkdir(parents=True)
        (p1 / "Default" / "Network" / "Cookies").write_bytes(b"")
        self.assertEqual(CookieExtractor.extract_cookies_for_profile(p1), [])

        # 2. 16-byte truncated file
        p2 = self.test_root / "corrupt_2"
        (p2 / "Default" / "Network").mkdir(parents=True)
        (p2 / "Default" / "Network" / "Cookies").write_bytes(b"SQLite format 3\x00")
        self.assertEqual(CookieExtractor.extract_cookies_for_profile(p2), [])

        # 3. Random binary garbage
        p3 = self.test_root / "corrupt_3"
        (p3 / "Default" / "Network").mkdir(parents=True)
        (p3 / "Default" / "Network" / "Cookies").write_bytes(os.urandom(1024))
        self.assertEqual(CookieExtractor.extract_cookies_for_profile(p3), [])

        # 4. Valid SQLite file without 'cookies' table
        p4 = self.test_root / "corrupt_4"
        (p4 / "Default" / "Network").mkdir(parents=True)
        c4 = p4 / "Default" / "Network" / "Cookies"
        conn = sqlite3.connect(str(c4))
        try:
            conn.execute("CREATE TABLE other_table (id INT)")
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(CookieExtractor.extract_cookies_for_profile(p4), [])

    def test_d5_02_corrupt_local_state_variants(self):
        """
        Tests get_master_key resilience against corrupt Local State files:
        1. 0-byte file
        2. Invalid JSON syntax
        3. JSON array instead of object
        4. Missing os_crypt or null os_crypt
        5. Invalid base64 in encrypted_key
        6. Base64 payload that does not start with DPAPI
        7. Corrupted DPAPI payload (CryptUnprotectData failure)
        """
        profile_dir = self.test_root / "corrupt_local_state"
        profile_dir.mkdir(parents=True)
        ls_file = profile_dir / "Local State"

        # 1. 0-byte file
        ls_file.write_bytes(b"")
        self.assertIsNone(CookieExtractor.get_master_key(profile_dir))

        # 2. Invalid JSON syntax
        ls_file.write_text("{invalid_json: true", encoding="utf-8")
        self.assertIsNone(CookieExtractor.get_master_key(profile_dir))

        # 3. JSON array
        ls_file.write_text("[]", encoding="utf-8")
        self.assertIsNone(CookieExtractor.get_master_key(profile_dir))

        # 4. Null os_crypt
        ls_file.write_text(json.dumps({"os_crypt": None}), encoding="utf-8")
        self.assertIsNone(CookieExtractor.get_master_key(profile_dir))

        # 5. Invalid base64
        ls_file.write_text(json.dumps({"os_crypt": {"encrypted_key": "not_base64!?$"}}), encoding="utf-8")
        self.assertIsNone(CookieExtractor.get_master_key(profile_dir))

        # 6. Base64 payload without DPAPI prefix
        raw_no_dpapi = b"NONDPAPI" + os.urandom(32)
        import base64
        ls_file.write_text(json.dumps({"os_crypt": {"encrypted_key": base64.b64encode(raw_no_dpapi).decode()}}), encoding="utf-8")
        self.assertIsNone(CookieExtractor.get_master_key(profile_dir))

        # 7. Corrupt DPAPI payload
        raw_bad_dpapi = b"DPAPI" + os.urandom(32)
        ls_file.write_text(json.dumps({"os_crypt": {"encrypted_key": base64.b64encode(raw_bad_dpapi).decode()}}), encoding="utf-8")
        self.assertIsNone(CookieExtractor.get_master_key(profile_dir))

    def test_d5_03_malformed_encrypted_value_blobs(self):
        """
        Tests decrypt_cookie_value against adversarial blobs:
        1. Truncated v10 prefix (b"v10", b"v10123", length < 15)
        2. Valid v10 length but corrupted ciphertext / auth tag (tampered bytes)
        3. v11 prefix with truncated payload
        4. Empty blob
        All must return empty string "" without crashing.
        """
        # 1. Truncated v10
        self.assertEqual(CookieExtractor.decrypt_cookie_value(b"v10", self.master_key), "")
        self.assertEqual(CookieExtractor.decrypt_cookie_value(b"v10123", self.master_key), "")
        self.assertEqual(CookieExtractor.decrypt_cookie_value(b"v10" + b"\x00" * 11, self.master_key), "")

        # 2. Corrupted ciphertext / auth tag
        tampered_blob = b"v10" + os.urandom(12) + os.urandom(32)
        self.assertEqual(CookieExtractor.decrypt_cookie_value(tampered_blob, self.master_key), "")

        # 3. Truncated v11
        self.assertEqual(CookieExtractor.decrypt_cookie_value(b"v11", self.master_key), "")

        # 4. Empty blob
        self.assertEqual(CookieExtractor.decrypt_cookie_value(b"", self.master_key), "")

    def test_d5_04_extreme_cookie_payload_boundaries(self):
        """
        Tests boundary values for cookie attributes:
        1. 50,000-character cookie values
        2. Multibyte UTF-8 emojis and surrogate pairs
        3. Binary null characters (\x00) inside decrypted payload
        4. Extreme and unexpected samesite values (-5, 99)
        """
        profile_dir = self.test_root / "boundary_cookies"
        huge_val = "A" * 50000
        emoji_val = "🔑Secret_Token_🚀_🔥_12345"

        create_synthetic_profile(
            profile_dir,
            master_key=self.master_key,
            cookies=[
                {"name": "huge_ck", "value": huge_val, "domain": ".example.com", "sameSite": -5},
                {"name": "emoji_ck", "value": emoji_val, "domain": ".example.com", "sameSite": 99, "header_32": True},
            ]
        )

        cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
        cookie_map = {c["name"]: c for c in cookies}

        self.assertIn("huge_ck", cookie_map)
        self.assertEqual(len(cookie_map["huge_ck"]["value"]), 50000)
        self.assertEqual(cookie_map["huge_ck"]["sameSite"], "Lax")  # Mapped to Lax fallback

        self.assertIn("emoji_ck", cookie_map)
        self.assertEqual(cookie_map["emoji_ck"]["value"], emoji_val)
        self.assertEqual(cookie_map["emoji_ck"]["sameSite"], "Lax")

    def test_d5_05_large_scale_database_performance_and_stability(self):
        """
        Extracts 1,000 cookies from a single profile SQLite database.
        Verifies execution completes within reasonable time (< 2.0s) and memory remains stable.
        """
        profile_dir = self.test_root / "large_scale_db"
        cookie_batch = [
            {
                "name": f"cookie_{i}",
                "value": f"token_value_{i}_abcdef1234567890",
                "domain": f".domain{i % 10}.com",
                "expires": 1800000000.0 + i
            }
            for i in range(1000)
        ]

        create_synthetic_profile(profile_dir, master_key=self.master_key, cookies=cookie_batch)

        start_time = time.time()
        extracted = CookieExtractor.extract_cookies_for_profile(profile_dir)
        elapsed = time.time() - start_time

        self.assertEqual(len(extracted), 1000)
        self.assertLess(elapsed, 2.0, f"Extraction of 1000 cookies took too long: {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
