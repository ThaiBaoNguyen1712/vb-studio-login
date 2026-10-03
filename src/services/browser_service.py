import os
import sys
import threading
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path
from playwright.sync_api import sync_playwright

from src.core.config import Config
from src.core.logger import logger

# Đảm bảo đường dẫn driver Playwright trong môi trường đóng gói PyInstaller
if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        driver_path = Path(meipass) / "playwright" / "driver"
        if driver_path.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "0")

class BrowserService:
    """
    Manages Playwright browser automation, persistent profiles,
    cookie injection and extraction upon browser close.
    """

    def __init__(self):
        self._active_contexts: Dict[str, Any] = {}

    def is_channel_open(self, channel_id: str) -> bool:
        return channel_id in self._active_contexts

    def close_channel_browser(self, channel_id: str) -> bool:
        """Đóng context Chromium của một kênh nếu đang mở."""
        context = self._active_contexts.get(channel_id)
        if context:
            try:
                logger.info(f"Yêu cầu đóng trình duyệt kênh '{channel_id}'...")
                context.close()
                return True
            except Exception as e:
                logger.warning(f"Lỗi khi đóng context Chromium kênh '{channel_id}': {e}")
        return False

    def close_all_browsers(self) -> int:
        """Đóng toàn bộ context Chromium đang mở trên máy này."""
        count = 0
        for ch_id, context in list(self._active_contexts.items()):
            try:
                logger.info(f"Đóng trình duyệt kênh '{ch_id}'...")
                context.close()
                count += 1
            except Exception as e:
                logger.warning(f"Lỗi khi đóng context Chromium kênh '{ch_id}': {e}")
        return count

    # Tự lưu cookies mỗi 5 phút khi browser còn mở (không chờ đóng mới lưu)
    AUTOSAVE_INTERVAL_SEC = 300

    def _launch_persistent_context(self, playwright, profile_dir: Path, custom_args: List[str]):
        """
        Khởi chạy trình duyệt bền vững (Persistent Context).
        Tự động nhận diện và fallback lần lượt:
        1. Google Chrome (nếu máy có Chrome)
        2. Microsoft Edge (có sẵn 100% trên Windows 10/11)
        3. Playwright Chromium mặc định
        """
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--no-first-run",
            "--no-default-browser-check"
        ] + custom_args

        last_error = None
        # Thử lần lượt các trình duyệt Chromium phổ biến trên máy người dùng
        for channel in ["chrome", "msedge", None]:
            try:
                kwargs = {
                    "user_data_dir": str(profile_dir),
                    "headless": False,
                    "no_viewport": True,
                    "args": launch_args,
                    "ignore_default_args": ["--enable-automation"],
                }
                if channel:
                    kwargs["channel"] = channel
                context = playwright.chromium.launch_persistent_context(**kwargs)
                logger.info(f"Đã mở trình duyệt thành công (channel: {channel or 'default chromium'})")
                return context
            except Exception as e:
                last_error = e
                logger.warning(f"Không thể mở với channel='{channel}': {e}")

        raise RuntimeError(f"Không thể khởi chạy trình duyệt: {last_error}")

    def launch_channel_browser(
        self,
        channel_id: str,
        target_url: str,
        cookies: Optional[List[Dict[str, Any]]] = None,
        on_started: Optional[Callable[[], None]] = None,
        on_closed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_autosave: Optional[Callable[[List[Dict[str, Any]]], None]] = None
    ):
        """
        Launches a Chromium persistent context in a separate thread.
        """
        def _worker():
            playwright = None
            context = None
            try:
                profile_dir = Config.get_profile_path(channel_id)
                logger.info(f"Khởi động Chromium cho kênh '{channel_id}' tại profile: {profile_dir}")

                playwright = sync_playwright().start()

                # Launch persistent context with smart channel fallback (Chrome -> Edge -> Chromium)
                context = self._launch_persistent_context(playwright, profile_dir, [])

                self._active_contexts[channel_id] = context

                # Inject existing cookies if provided
                if cookies and len(cookies) > 0:
                    try:
                        clean_cookies = self._sanitize_cookies(cookies)
                        context.add_cookies(clean_cookies)
                        logger.info(f"Đã inject {len(clean_cookies)} cookies vào context.")
                    except Exception as ce:
                        logger.warning(f"Lỗi khi nạp cookies (sẽ tiếp tục mở trang): {ce}")

                # Open or reuse main page
                pages = context.pages
                page = pages[0] if pages else context.new_page()

                # Notify UI that browser successfully opened
                if on_started:
                    on_started()

                # Navigate to the target Studio or Login URL
                logger.info(f"Điều hướng tới URL: {target_url}")
                page.goto(target_url, wait_until="commit", timeout=60000)

                # Event loop waiting for user to close browser window.
                from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
                browser_closed = False
                while not browser_closed:
                    try:
                        page.wait_for_event("close", timeout=self.AUTOSAVE_INTERVAL_SEC * 1000)
                        browser_closed = True
                    except PlaywrightTimeoutError:
                        # Còn mở -> tự lưu snapshot cookies hiện tại
                        if on_autosave and context:
                            try:
                                snapshot = context.cookies()
                                logger.info(f"Tự lưu {len(snapshot)} cookies cho kênh đang mở '{channel_id}'.")
                                on_autosave(snapshot)
                            except Exception as se:
                                logger.warning(f"Tự lưu cookies '{channel_id}' lỗi (bỏ qua): {se}")
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "target closed" in error_msg or "context closed" in error_msg:
                            logger.info(f"Trình duyệt kênh '{channel_id}' đã được người dùng đóng.")
                            browser_closed = True
                        else:
                            raise

            except Exception as e:
                error_msg = str(e).lower()
                if "target closed" in error_msg or "context closed" in error_msg:
                    logger.info(f"Trình duyệt kênh '{channel_id}' đã được người dùng đóng.")
                else:
                    logger.error(f"Lỗi trong quá trình chạy trình duyệt kênh '{channel_id}': {e}")
                    if on_error:
                        on_error(e)
            finally:
                # Extract all cookies before completely shutting down context
                extracted_cookies = []
                if context:
                    try:
                        extracted_cookies = context.cookies()
                        logger.info(f"Đã trích xuất thành công {len(extracted_cookies)} cookies từ phiên.")
                    except Exception as e:
                        logger.warning(f"Không thể trích xuất cookies khi đóng: {e}")

                    try:
                        context.close()
                    except Exception:
                        pass

                if playwright:
                    try:
                        playwright.stop()
                    except Exception:
                        pass

                self._active_contexts.pop(channel_id, None)

                # Callback with extracted cookies
                if on_closed:
                    on_closed(extracted_cookies)

        thread = threading.Thread(target=_worker, name=f"BrowserThread-{channel_id}", daemon=True)
        thread.start()

    def _sanitize_cookies(self, cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Playwright requires specific cookie fields. Filters out incompatible fields like sameSite='None' with insecure scheme.
        """
        sanitized = []
        for c in cookies:
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

            # Only add if valid name and value
            if clean["name"] is not None and clean["value"] is not None and clean["domain"] is not None:
                sanitized.append(clean)
        return sanitized
