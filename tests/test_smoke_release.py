import json
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import Config
from src.core.constants import APP_NAME, APP_VERSION
from src.core.secure_store import protect_json, unprotect_json, is_protected
from src.main import build_services
from src.services.browser_service import BrowserService
from src.services.sync_service import SyncService
from src.web.api_bridge import WebBridge


class TestSmokeRelease(unittest.TestCase):
    """Final release smoke test suite."""

    def test_constants_and_version(self):
        self.assertEqual(APP_NAME, "VBLogin")
        self.assertTrue(APP_VERSION.startswith("v"))
        html = Path("src/web/index.html").read_text(encoding="utf-8")
        self.assertIn(APP_VERSION, html)

    def test_html_assets_exist(self):
        html = Path("src/web/index.html").read_text(encoding="utf-8")
        links = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html)
        web_dir = Path("src/web")
        missing = []
        for l in links:
            if l.startswith(("http://", "https://", "#", "data:")):
                continue
            clean_l = l.split("?")[0]
            p = (web_dir / clean_l).resolve()
            if not p.exists():
                missing.append(clean_l)
        self.assertEqual(missing, [], f"Missing assets in index.html: {missing}")

    def test_api_surface_100_percent_match(self):
        acc, set_svc = build_services()
        bridge = WebBridge(acc, set_svc)
        bridge_methods = {m for m in dir(bridge) if not m.startswith("_")}

        js_dir = Path("src/web/js")
        all_calls = set()
        pattern = re.compile(r"pywebview\.api\.([a-zA-Z0-9_]+)")

        for f in js_dir.glob("*.js"):
            text = f.read_text(encoding="utf-8")
            for m in pattern.findall(text):
                all_calls.add((m, f.name))

        missing = [(m, fname) for m, fname in sorted(all_calls) if m not in bridge_methods]
        acc.stop_watchdog()
        bridge.shutdown()
        self.assertEqual(missing, [], f"Missing API methods: {missing}")

    def test_browser_detection_host(self):
        bs = BrowserService()
        detected = bs.detect_browser_executable()
        if detected:
            self.assertTrue(Path(detected).exists())

    def test_vault_security_dpapi_roundtrip(self):
        sample = {
            "channel_id": "test_ch_smoke",
            "cookies": [{"name": "SID", "value": "val123", "domain": ".google.com", "path": "/"}]
        }
        enc = protect_json(sample)
        self.assertTrue(is_protected(enc))
        dec = unprotect_json(enc)
        self.assertEqual(dec, sample)

    def test_local_database_health(self):
        db_file = Config.LOCAL_DB_FILE
        if db_file.exists():
            data = json.loads(db_file.read_text(encoding="utf-8"))
            self.assertIn("accounts", data)
            self.assertIn("channels", data)

    def test_sync_service_initialization(self):
        from src.services.settings_service import SettingsService
        ss = SettingsService()
        sync = SyncService(settings_service=ss)
        self.assertTrue(bool(sync.machine_id and len(sync.machine_id) >= 6))

    def test_packaging_specs_no_playwright(self):
        reqs = Path("requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("playwright", reqs.lower())
        for spec_name in ["VB-Login.spec", "VBLogin.spec"]:
            spec_path = Path(spec_name)
            if spec_path.exists():
                self.assertNotIn("playwright", spec_path.read_text(encoding="utf-8").lower())

    def test_no_bat_files_in_scripts(self):
        """Đảm bảo không còn file .bat nào trong thư mục scripts."""
        bat_files = list(Path("scripts").glob("*.bat"))
        self.assertEqual(bat_files, [], f"Không được chứa file .bat trong scripts: {bat_files}")
        self.assertTrue(Path("scripts/tao_shortcut_desktop.py").exists(), "tao_shortcut_desktop.py phải tồn tại")

    def test_update_service_find_python_runner(self):
        from src.services.update_service import UpdateService
        runner = UpdateService.find_python_runner()
        self.assertIsNotNone(runner, "Cần tìm được pythonw hoặc python runner trên môi trường test")
        self.assertTrue(Path(runner).exists())


if __name__ == "__main__":
    unittest.main()

