import sys
from pathlib import Path

# Add project root and bundle root to sys.path so 'src' can be imported anywhere
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", str(PROJECT_ROOT)))
    if str(BUNDLE_ROOT) not in sys.path:
        sys.path.insert(0, str(BUNDLE_ROOT))
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.core.config import Config
from src.core.logger import logger
from src.repositories.local_repo import LocalJsonRepository
from src.services.settings_service import SettingsService

from src.services.session_service import SessionService
from src.services.browser_service import BrowserService
from src.services.account_service import AccountService
from src.services.sync_service import SyncService


def resolve_web_entry() -> tuple[str, str]:
    """Trả về (url, http_root) để pywebview serve local offline.

    Ưu tiên http_server để relative assets ./assets/* ./vendor/* chạy đúng
    cả khi chạy source lẫn exe đóng gói.
    """
    web_dir = PROJECT_ROOT / "src" / "web"
    # Khi frozen, data files nằm cạnh exe hoặc trong _MEIPASS
    candidates = [
        web_dir / "index.html",
        Path(getattr(sys, "_MEIPASS", "")) / "src" / "web" / "index.html" if getattr(sys, "_MEIPASS", "") else None,
        PROJECT_ROOT / "web" / "index.html",
    ]
    for c in candidates:
        if c and Path(c).exists():
            abs_file = str(Path(c).resolve())
            root = str(Path(c).parent.resolve())
            return abs_file, root
    # fallback: đường dẫn tuyệt đối
    fallback = web_dir / "index.html"
    return str(fallback.resolve()), str(web_dir.resolve())


def run_web_gui(account_service: AccountService, settings_service: SettingsService):
    """WebView2 duy nhất — Edge Chromium GPU, offline-first."""
    import webview
    from src.web.api_bridge import WebBridge

    # Thiết lập AppUserModelID để Windows Taskbar nhận diện icon riêng biệt thay vì icon Python mặc định
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("vblogin.manager.1.0")
    except Exception:
        pass

    logger.info("Khởi chạy VBLogin WebView2 (Edge Chromium, GPU, offline-first)...")

    api = WebBridge(account_service=account_service, settings_service=settings_service)
    # Dau sync online lien may (presence + khoa + inbox xin mo qua Firebase RTDB).
    # Tat ca network chay thread nen; that bai -> local-only, khong block UI.
    try:
        sync = getattr(account_service, "sync_service", None)
        if sync is not None:
            api.attach_sync(sync)
            logger.info("Sync online lien may: da kich hoat (Firebase RTDB).")
    except Exception as e:
        logger.warning(f"Khong kich hoat duoc sync online (chay local-only): {e}")
    url, http_root = resolve_web_entry()
    debug = "--debug" in sys.argv or settings_service.get("general", "debug", False) is True

    window = webview.create_window(
        title="VBLogin • Multi-Channel Dashboard",
        url=url,
        js_api=api,
        width=1320,
        height=880,
        min_size=(1060, 720),
        background_color="#0b0f19",

        text_select=False,
    )
    api.set_window(window)

    icon_candidates = [
        PROJECT_ROOT / "src" / "web" / "assets" / "app.ico",
        Path(getattr(sys, "_MEIPASS", "")) / "src" / "web" / "assets" / "app.ico" if getattr(sys, "_MEIPASS", "") else None,
    ]
    icon_path = next((str(c.resolve()) for c in icon_candidates if c and c.exists()), None)

    import threading
    import atexit
    import signal

    _cleaned_up = False
    _cleanup_lock = threading.Lock()

    def do_cleanup(*args, **kwargs):
        nonlocal _cleaned_up
        with _cleanup_lock:
            if _cleaned_up:
                return
            _cleaned_up = True
            logger.info("Đang giải phóng toàn bộ phiên làm việc trước khi tắt app...")
            try:
                if api is not None:
                    api.shutdown()
                else:
                    account_service.cleanup_on_shutdown()
            except Exception as ex:
                logger.error(f"Lỗi khi giải phóng phiên khi tắt app: {ex}")

    # Bắt tín hiệu hệ điều hành Windows Shutdown / Logoff / Close
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

            def _console_ctrl_handler(ctrl_type):
                logger.info(f"Nhận tín hiệu Windows Shutdown/Control Event: {ctrl_type}")
                do_cleanup()
                return False

            global _win_shutdown_handler
            _win_shutdown_handler = PHANDLER_ROUTINE(_console_ctrl_handler)
            ctypes.windll.kernel32.SetConsoleCtrlHandler(_win_shutdown_handler, True)
            logger.info("Đã đăng ký Windows Shutdown/Logoff Control Handler thành công.")
        except Exception as e:
            logger.debug(f"Đăng ký SetConsoleCtrlHandler bỏ qua: {e}")

    # Gắn sự kiện pywebview window closing & closed
    try:
        window.events.closing += do_cleanup
        window.events.closed += do_cleanup
    except Exception as e:
        logger.debug(f"Gắn sự kiện window close bỏ qua: {e}")

    # Đăng ký atexit dự phòng khi python thoát
    atexit.register(do_cleanup)

    def _sig_handler(sig, frame):
        do_cleanup()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    except Exception:
        pass

    # Kết nối watchdog để cập nhật giao diện ngay khi phiên chết được tự động xả
    def _on_auto_released(ch_id):
        try:
            api.notify_frontend("channel_status_changed", {
                "channel_id": ch_id,
                "status": "READY",
                "locked_by": None
            })
            api._push_channel_status(ch_id)
        except Exception:
            pass
    account_service.on_session_auto_released = _on_auto_released

    try:
        # http_server giúp load ./assets + ./vendor/tailwind.js đúng MIME, offline 100%
        webview.start(
            debug=debug,
            http_server=True,
            http_port=None,
            gui="edgechromium",
            icon=icon_path
        )
    except Exception as e:
        msg = str(e).lower()
        logger.error(f"Không thể khởi chạy WebView2: {e}")
        if "edge" in msg or "webview2" in msg or "runtime" in msg:
            logger.error(
                "Máy này thiếu Microsoft Edge WebView2 Runtime. "
                "Tải tại: https://developer.microsoft.com/microsoft-edge/webview2/"
            )
        raise
    finally:
        do_cleanup()


def build_services():
    Config.ensure_directories()
    settings_service = SettingsService()

    logger.info("Chế độ lưu trữ: LOCAL JSON (data/local_db.json)")
    repo = LocalJsonRepository()

    session_service = SessionService(repository=repo)

    browser_service = BrowserService()
    sync_service = SyncService(settings_service=settings_service)
    account_service = AccountService(
        repository=repo,
        session_service=session_service,
        browser_service=browser_service,
        sync_service=sync_service,
    )
    # Tự động giải phóng các khóa mồ côi từ phiên trước nếu app bị tắt đột ngột
    try:
        recovered = account_service.recover_orphaned_locks()
        if recovered:
            logger.info(f"Khởi động: Đã giải phóng {len(recovered)} khóa mồ côi từ phiên trước: {recovered}")
    except Exception as e:
        logger.warning(f"Khôi phục khóa mồ côi bỏ qua: {e}")

    # Khởi chạy session watchdog nền (quét xả phiên chết định kỳ mỗi 5s)
    try:
        account_service.start_watchdog(interval_sec=5.0)
    except Exception as e:
        logger.warning(f"Khởi động watchdog bỏ qua: {e}")

    # Tự mã hóa cookies plaintext cũ (one-time, có backup) — không chặn khởi động
    try:
        result = repo.migrate_plaintext_cookies()
        if result.get("migrated"):
            logger.info(f"Vault: đã mã hóa {result['migrated']} phiên cookies cũ.")
    except Exception as e:
        logger.warning(f"Vault auto-migrate bỏ qua: {e}")
    return account_service, settings_service


def ensure_desktop_shortcut():
    """Tự động tạo shortcut VBLogin trên Desktop của người dùng nếu chưa có (khi chạy EXE)."""
    if not getattr(sys, "frozen", False):
        return
    try:
        import os
        import subprocess
        import tempfile

        exe_path = Path(sys.executable).resolve()
        desktop_candidates = [
            Path(os.environ.get("USERPROFILE", "")) / "Desktop",
            Path(os.environ.get("ONEDRIVE", "")) / "Desktop" if os.environ.get("ONEDRIVE") else None,
            Path.home() / "Desktop"
        ]
        desktop = next((d for d in desktop_candidates if d and d.exists()), None)
        if not desktop:
            return

        shortcut_file = desktop / "VBLogin.lnk"
        if shortcut_file.exists():
            return

        vbs = (
            f'Set oWS = WScript.CreateObject("WScript.Shell")\r\n'
            f'sLinkFile = "{shortcut_file}"\r\n'
            f'Set oLink = oWS.CreateShortcut(sLinkFile)\r\n'
            f'oLink.TargetPath = "{exe_path}"\r\n'
            f'oLink.WorkingDirectory = "{exe_path.parent}"\r\n'
            f'oLink.Description = "VBLogin Manager"\r\n'
            f'oLink.IconLocation = "{exe_path},0"\r\n'
            f'oLink.Save\r\n'
        )
        tmp_vbs = Path(tempfile.gettempdir()) / "create_vblogin_shortcut.vbs"
        tmp_vbs.write_text(vbs, encoding="utf-8")
        subprocess.run(["cscript", "//nologo", str(tmp_vbs)], shell=True, capture_output=True, timeout=5)
        try:
            tmp_vbs.unlink(missing_ok=True)
        except Exception:
            pass
        logger.info(f"Đã tự động tạo Desktop Shortcut tại: {shortcut_file}")
    except Exception as e:
        logger.debug(f"Bỏ qua tự động tạo shortcut: {e}")


def main():
    logger.info("=" * 60)
    logger.info("VB-STUDIO Multi-Channel (WebView2 UI) khởi động...")
    logger.info(f"Thư mục gốc: {Config.BASE_DIR}")
    logger.info("=" * 60)

    ensure_desktop_shortcut()

    account_service, settings_service = build_services()
    run_web_gui(account_service, settings_service)


if __name__ == "__main__":
    main()

