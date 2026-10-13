"""Ghi nguyen tu: reader dong thoi khong bao gio doc phai JSON do."""
import json
import threading
import unittest
from pathlib import Path
import tempfile

from src.repositories.local_repo import LocalJsonRepository
from src.services.settings_service import SettingsService


class TestAtomicSave(unittest.TestCase):
    def test_concurrent_read_write_never_torn(self):
        tmp = Path(tempfile.mkdtemp())
        repo = LocalJsonRepository(file_path=tmp / "db.json")
        errors = []
        stop = threading.Event()

        def writer():
            i = 0
            while not stop.is_set():
                i += 1
                try:
                    repo._save_raw_data({"accounts": [], "channels": [],
                                         "sessions": {}, "n": i,
                                         "pad": "x" * 5000})
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

        def reader():
            while not stop.is_set():
                try:
                    # Di duong production (co retry) thay vi open tho:
                    # app khong bao gio duoc thay file do hay PermissionError.
                    data = repo._read_raw_data()
                    assert isinstance(data, dict) and "sessions" in data
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

        ws = [threading.Thread(target=writer, daemon=True) for _ in range(2)]
        rs = [threading.Thread(target=reader, daemon=True) for _ in range(4)]
        for t in ws + rs:
            t.start()
        stop.wait(1.0)
        stop.set()
        for t in ws + rs:
            t.join(timeout=5)
        self.assertEqual(errors, [])
        leftovers = list(tmp.glob("db.json.*.tmp"))
        self.assertEqual(leftovers, [])
        # roundtrip van doc duoc qua repo
        data = repo._read_raw_data()
        self.assertIn("n", data)

    def test_settings_atomic_roundtrip(self):
        tmp = Path(tempfile.mkdtemp())
        svc = SettingsService(file_path=tmp / "settings.json")
        svc.settings["general"]["default_user"] = "Tester"
        self.assertTrue(svc.save_settings())
        self.assertEqual(list(tmp.glob("settings.json.*.tmp")), [])
        svc2 = SettingsService(file_path=tmp / "settings.json")
        self.assertEqual(svc2.settings["general"]["default_user"], "Tester")


if __name__ == "__main__":
    unittest.main()
