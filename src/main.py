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


def build_services():
    Config.ensure_directories()
    settings_service = SettingsService()

    logger.info("Chế độ lưu trữ: LOCAL JSON (data/local_db.json)")
    repo = LocalJsonRepository()

    session_service = SessionService(repository=repo)

    browser_service = BrowserService()
    account_service = AccountService(
        repository=repo,
        session_service=session_service,
        browser_service=browser_service,
    )
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

