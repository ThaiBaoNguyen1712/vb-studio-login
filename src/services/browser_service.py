import os
import sys
import shutil
import subprocess
import threading
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path

from src.core.config import Config
from src.core.logger import logger
from src.services.cookie_extractor import CookieExtractor


class BrowserService:
    """
    Manages Native Chromium browser execution (Google Chrome & Microsoft Edge)
    using independent user data directories per profile.
    Completely eliminates external automation drivers and automation flags
    to avoid bot detection and ensure natural browser fingerprints.
    """

    AUTOSAVE_INTERVAL_SEC: int = 300

    def __init__(self):
        self._active_processes: Dict[str, subprocess.Popen] = {}
        self._worker_threads: Dict[str, threading.Thread] = {}
        self._lock: threading.RLock = threading.RLock()
        self._channel_locks: Dict[str, threading.Lock] = {}

    def _get_channel_lock(self, channel_id: str) -> threading.Lock:
        """Retrieves or creates a dedicated mutex lock for channel operations."""
        with self._lock:
            if channel_id not in self._channel_locks:
                self._channel_locks[channel_id] = threading.Lock()
            return self._channel_locks[channel_id]

    @property
    def _active_contexts(self) -> Dict[str, Any]:
        """
        Backward compatibility alias for AccountService.release_user_channels
        which accesses self.browser_service._active_contexts.keys().
        """
        self._clean_dead_processes()
        return self._active_processes

    @_active_contexts.setter
    def _active_contexts(self, val: Dict[str, Any]):
        self._active_processes = val

    def _clean_dead_processes(self) -> None:
        """Removes terminated processes from tracking dictionary."""
        with self._lock:
            for ch_id in list(self._active_processes.keys()):
                p = self._active_processes.get(ch_id)
                if p is not None and p.poll() is not None:
                    if self._active_processes.get(ch_id) is p:
                        self._active_processes.pop(ch_id, None)

    def _find_chrome(self) -> Optional[Path]:
        """Detects Google Chrome executable on Windows and PATH."""
        if sys.platform == "win32":
            try:
                import winreg
                for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    for subkey in (
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
                    ):
                        try:
                            with winreg.OpenKey(root, subkey) as k:
                                val, _ = winreg.QueryValueEx(k, "")
                                if val and Path(val).is_file():
                                    return Path(val)
                        except Exception:
                            pass
            except Exception:
                pass

            env_vars = ["PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"]
            for env_var in env_vars:
                base = os.environ.get(env_var)
                if base:
                    cand = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
                    if cand.is_file():
                        return cand

            for hardcoded in (
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ):
                cand = Path(hardcoded)
                if cand.is_file():
                    return cand

        for bin_name in ("chrome", "chrome.exe", "google-chrome"):
            w = shutil.which(bin_name)
            if w:
                cand = Path(w)
                if cand.is_file():
                    return cand

        return None

    def _find_edge(self) -> Optional[Path]:
        """Detects Microsoft Edge executable on Windows and PATH."""
        if sys.platform == "win32":
            try:
                import winreg
                for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    for subkey in (
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
                        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
                    ):
                        try:
                            with winreg.OpenKey(root, subkey) as k:
                                val, _ = winreg.QueryValueEx(k, "")
                                if val and Path(val).is_file():
                                    return Path(val)
                        except Exception:
                            pass
            except Exception:
                pass

            env_vars = ["PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"]
            for env_var in env_vars:
                base = os.environ.get(env_var)
                if base:
                    cand = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
                    if cand.is_file():
                        return cand

            for hardcoded in (
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ):
                cand = Path(hardcoded)
                if cand.is_file():
                    return cand

        for bin_name in ("msedge", "msedge.exe", "microsoft-edge"):
            w = shutil.which(bin_name)
            if w:
                cand = Path(w)
                if cand.is_file():
                    return cand

        return None

    def detect_browser_executable(self=None) -> Optional[Path]:
        """
        Detects installed Chromium-based browser on Windows.
        Priority:
        1. Google Chrome (preferred)
        2. Microsoft Edge (fallback, pre-installed on Windows 10/11)
        3. Generic PATH executables
        """
        svc = self if isinstance(self, BrowserService) else BrowserService()

        chrome = svc._find_chrome()
        if chrome:
            return chrome

        edge = svc._find_edge()
        if edge:
            return edge

        for name in ("google-chrome", "chrome", "chromium", "microsoft-edge", "msedge"):
            w = shutil.which(name)
            if w:
                cand = Path(w)
                if cand.is_file():
                    return cand

        return None

    def is_channel_open(self, channel_id: str) -> bool:
        """Returns True if the browser process for channel_id is currently running."""
        with self._lock:
            proc = self._active_processes.get(channel_id)
            if proc is not None:
                if proc.poll() is None:
                    return True
                if self._active_processes.get(channel_id) is proc:
                    self._active_processes.pop(channel_id, None)
            return False

    def close_channel_browser(self, channel_id: str, wait_timeout: float = 2.0) -> bool:
        """
        Forcefully terminates the browser process tree for channel_id using taskkill on Windows.
        Never holds internal locks while waiting on the OS: snapshot the proc handle
        under lock, kill + wait WITHOUT locks, then untrack. This keeps
        release_user_channels responsive (old code held locks during a 5s wait
        per channel, freezing the pywebview bridge N*5s).
        Returns True if a running process was terminated, False otherwise.
        """
        ch_lock = self._get_channel_lock(channel_id)
        with ch_lock:
            with self._lock:
                proc = self._active_processes.get(channel_id)
                if proc is None:
                    return False

                if proc.poll() is not None:
                    if self._active_processes.get(channel_id) is proc:
                        self._active_processes.pop(channel_id, None)
                    return False

        pid = proc.pid
        logger.info(f"Yêu cầu đóng trình duyệt kênh '{channel_id}' (PID: {pid})...")

        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=3
                )
            except Exception as te:
                logger.warning(f"taskkill thất bại cho PID {pid}: {te}, thử dùng proc.kill()")
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.terminate()
            except Exception:
                pass
        else:
            try:
                proc.terminate()
            except Exception:
                pass

        try:
            proc.wait(timeout=wait_timeout)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=1)
            except Exception:
                pass

        with ch_lock:
            with self._lock:
                if self._active_processes.get(channel_id) is proc:
                    self._active_processes.pop(channel_id, None)
                worker_t = self._worker_threads.get(channel_id)

        if worker_t and worker_t.is_alive() and threading.current_thread() != worker_t:
            try:
                worker_t.join(timeout=wait_timeout)
            except Exception:
                pass
            with self._lock:
                self._worker_threads.pop(channel_id, None)
        return True

    def close_all_browsers(self) -> int:
        """Closes all active channel browser processes and returns count of closed browsers."""
        with self._lock:
            channel_ids = list(self._active_processes.keys())
        count = 0
        for ch_id in channel_ids:
            if self.close_channel_browser(ch_id):
                count += 1
        return count

    def get_active_channel_ids(self) -> List[str]:
        """Returns list of all channel IDs that currently have an active browser process."""
        with self._lock:
            channel_ids = list(self._active_processes.keys())
        return [ch_id for ch_id in channel_ids if self.is_channel_open(ch_id)]

    def get_active_pid(self, channel_id: str) -> Optional[int]:
        """Returns the PID of the browser process for channel_id, or None if not running."""
        with self._lock:
            proc = self._active_processes.get(channel_id)
            if proc and proc.poll() is None:
                return proc.pid
            return None

    def launch_channel_browser(
        self,
        channel_id: str,
        target_url: str = "https://accounts.google.com",
        cookies: Optional[List[Dict[str, Any]]] = None,
        on_started: Optional[Callable[[], None]] = None,
        on_closed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_autosave: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_heartbeat: Optional[Callable[[], None]] = None
    ) -> None:
        """
        Launches a native browser process in a separate monitor thread.
        - Isolates profile by --user-data-dir="<profile_dir>"
        - Completely natural flags without any automation flags (CDP, webdriver)
        - Monitors process lifecycle and periodically autosaves cookies
        - Extracts cookies upon browser exit and invokes on_closed callback
        """
        def _worker():
            proc: Optional[subprocess.Popen] = None
            profile_dir: Optional[Path] = None
            ch_lock = self._get_channel_lock(channel_id)
            try:
                with ch_lock:
                    if self.is_channel_open(channel_id):
                        logger.warning(f"Trình duyệt cho kênh '{channel_id}' đã đang chạy.")
                        if on_started:
                            try:
                                on_started()
                            except Exception as se:
                                logger.warning(f"Lỗi callback on_started: {se}")
                        return

                    browser_exe = self.detect_browser_executable()
                    if not browser_exe:
                        raise RuntimeError("Không tìm thấy trình duyệt Google Chrome hoặc Microsoft Edge trên máy tính.")

                    profile_dir = Config.get_profile_path(channel_id)
                    profile_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Khởi động Native Browser ({browser_exe.name}) cho kênh '{channel_id}' tại: {profile_dir}")

                    cmd = [
                        str(browser_exe),
                        f"--user-data-dir={profile_dir.resolve()}",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--start-maximized",
                        "--hide-crash-restore-bubble",
                        target_url
                    ]

                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    with self._lock:
                        self._active_processes[channel_id] = proc
                    logger.info(f"Tiến trình trình duyệt kênh '{channel_id}' đã khởi động thành công (PID: {proc.pid})")

                    if on_started:
                        try:
                            on_started()
                        except Exception as se:
                            logger.warning(f"Lỗi callback on_started: {se}")

                # Monitor process until user closes window or taskkill terminates
                import time as _pytime
                last_autosave = _pytime.time()
                while proc.poll() is None:
                    try:
                        proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        if on_heartbeat:
                            try:
                                on_heartbeat()
                            except Exception:
                                pass
                        now_t = _pytime.time()
                        if on_autosave and profile_dir and (now_t - last_autosave >= self.AUTOSAVE_INTERVAL_SEC):
                            last_autosave = now_t
                            try:
                                snapshot = CookieExtractor.extract_cookies_for_profile(profile_dir)
                                if snapshot:
                                    logger.info(f"Tự lưu {len(snapshot)} cookies cho kênh đang mở '{channel_id}'.")
                                    on_autosave(snapshot)
                            except Exception as ae:
                                logger.debug(f"Lỗi autosave snapshot kênh '{channel_id}': {ae}")

            except Exception as e:
                logger.error(f"Lỗi khởi chạy trình duyệt kênh '{channel_id}': {e}")
                if proc is not None:
                    with self._lock:
                        if self._active_processes.get(channel_id) is proc:
                            self._active_processes.pop(channel_id, None)
                if on_error:
                    try:
                        on_error(e)
                    except Exception:
                        pass
                return

            # Process exited normally or was terminated
            extracted_cookies: List[Dict[str, Any]] = []
            if profile_dir:
                try:
                    extracted_cookies = CookieExtractor.extract_cookies_for_profile(profile_dir)
                    logger.info(f"Đã trích xuất {len(extracted_cookies)} cookies từ profile kênh '{channel_id}'.")
                except Exception as ce:
                    logger.warning(f"Lỗi trích xuất cookies khi đóng kênh '{channel_id}': {ce}")

            with self._lock:
                if self._active_processes.get(channel_id) is proc:
                    self._active_processes.pop(channel_id, None)

            if on_closed:
                try:
                    on_closed(extracted_cookies)
                except Exception as oe:
                    logger.warning(f"Lỗi callback on_closed kênh '{channel_id}': {oe}")

            with self._lock:
                self._worker_threads.pop(channel_id, None)

        thread = threading.Thread(
            target=_worker,
            name=f"BrowserThread-{channel_id}",
            daemon=True
        )
        with self._lock:
            self._worker_threads[channel_id] = thread
        thread.start()

    def _sanitize_cookies(self, cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sanitizes cookies structure for internal consistency and backwards compatibility.
        """
        sanitized = []
        for c in cookies:
            if not isinstance(c, dict):
                continue
            clean = {
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": c.get("domain"),
                "path": c.get("path", "/"),
            }
            if "expires" in c and c["expires"] is not None and c["expires"] > 0:
                clean["expires"] = float(c["expires"])
            if "httpOnly" in c:
                clean["httpOnly"] = bool(c["httpOnly"])
            if "secure" in c:
                clean["secure"] = bool(c["secure"])
            if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
                clean["sameSite"] = c["sameSite"]

            if clean["name"] is not None and clean["value"] is not None and clean["domain"] is not None:
                sanitized.append(clean)
        return sanitized
