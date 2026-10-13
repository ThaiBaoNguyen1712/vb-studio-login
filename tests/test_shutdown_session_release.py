import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.repositories.local_repo import LocalJsonRepository
from src.services.session_service import SessionService
from src.services.browser_service import BrowserService
from src.services.account_service import AccountService
from src.services.settings_service import SettingsService
from src.web.api_bridge import WebBridge
from src.domain.models import Account, Channel
from src.core.constants import Platform, ChannelStatus


class TestShutdownSessionRelease(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_file = Path(self.temp_dir.name) / "test_db.json"
        self.repo = LocalJsonRepository(file_path=self.db_file)
        self.session_service = SessionService(repository=self.repo)
        self.browser_service = BrowserService()
        self.settings_service = MagicMock(spec=SettingsService)
        self.settings_service.get.return_value = False
        self.sync_service = MagicMock()
        self.sync_service.is_online.return_value = False

        self.account_service = AccountService(
            repository=self.repo,
            session_service=self.session_service,
            browser_service=self.browser_service,
            sync_service=self.sync_service,
        )

        # Seed sample account and channels
        acc = Account(id="acc_test", display_name="Test Account", email="test@gmail.com")
        self.account_service.create_account(acc)
        ch1 = Channel(
            id="ch_test_1",
            account_id="acc_test",
            platform=Platform.YOUTUBE_SHORTS,
            channel_name="Channel 1",
            studio_url="https://studio.youtube.com",
            login_url="https://accounts.google.com",
            status=ChannelStatus.READY
        )
        ch2 = Channel(
            id="ch_test_2",
            account_id="acc_test",
            platform=Platform.TIKTOK,
            channel_name="Channel 2",
            studio_url="https://tiktok.com",
            login_url="https://tiktok.com/login",
            status=ChannelStatus.READY
        )
        self.account_service.create_channel(ch1)
        self.account_service.create_channel(ch2)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cleanup_on_shutdown_releases_locked_channels(self):
        # Giả lập 2 kênh đang bị khóa bởi "user_alice"
        self.session_service.try_acquire_channel("ch_test_1", "user_alice")
        self.session_service.try_acquire_channel("ch_test_2", "user_alice")

        # Kiểm tra trước khi tắt app: kênh đang bị giữ
        channels = self.repo.get_channels()
        self.assertEqual(channels[0].locked_by, "user_alice")
        self.assertEqual(channels[1].locked_by, "user_alice")

        # Thực hiện tắt app
        released = self.account_service.cleanup_on_shutdown(user_name="user_alice")

        self.assertIn("ch_test_1", released)
        self.assertIn("ch_test_2", released)

        # Sau khi tắt app: mọi kênh đều phải được giải phóng
        channels_after = self.repo.get_channels()
        self.assertIsNone(channels_after[0].locked_by)
        self.assertIsNone(channels_after[1].locked_by)

    def test_cleanup_on_shutdown_closes_active_browsers(self):
        # Giả lập 1 process browser đang chạy
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        self.browser_service._active_processes["ch_test_1"] = mock_proc

        self.session_service.try_acquire_channel("ch_test_1", "user_bob")

        with patch.object(self.browser_service, "close_channel_browser", return_value=True) as mock_close:
            released = self.account_service.cleanup_on_shutdown(user_name="user_bob")
            mock_close.assert_called_with("ch_test_1")

        self.assertIn("ch_test_1", released)
        channels_after = self.repo.get_channels()
        self.assertIsNone(channels_after[0].locked_by)

    def test_cleanup_on_shutdown_stops_sync_service(self):
        self.account_service.cleanup_on_shutdown()
        self.sync_service.stop.assert_called_once()

    def test_recover_orphaned_locks_on_startup(self):
        # Giả lập trường hợp phiên trước bị crash/kill: DB vẫn lưu in_use_by nhưng không có browser nào chạy
        self.session_service.try_acquire_channel("ch_test_1", "crashed_user")
        self.session_service.try_acquire_channel("ch_test_2", "crashed_user")

        channels = self.repo.get_channels()
        self.assertEqual(channels[0].locked_by, "crashed_user")
        self.assertEqual(channels[1].locked_by, "crashed_user")

        # Khởi động app: chạy hàm recover_orphaned_locks
        recovered = self.account_service.recover_orphaned_locks()
        self.assertIn("ch_test_1", recovered)
        self.assertIn("ch_test_2", recovered)

        # Sau khi recover: mọi khóa mồ côi đã được giải phóng
        channels_after = self.repo.get_channels()
        self.assertIsNone(channels_after[0].locked_by)
        self.assertIsNone(channels_after[1].locked_by)

    def test_recover_orphaned_locks_respects_remote_locks(self):
        # Giả lập sync_service online và có máy khác đang giữ ch_test_1
        self.sync_service.is_online.return_value = True
        self.session_service.try_acquire_channel("ch_test_1", "remote_user")
        self.session_service.try_acquire_channel("ch_test_2", "local_crashed_user")

        # Mock máy khác giữ ch_test_1
        with patch.object(self.account_service, "_remote_lock_other", side_effect=lambda ch: {"holder": "other_machine"} if ch == "ch_test_1" else None):
            recovered = self.account_service.recover_orphaned_locks()

        # ch_test_1 không bị giải phóng vì máy khác đang giữ
        self.assertNotIn("ch_test_1", recovered)
        # ch_test_2 là của máy này bị crash -> được giải phóng
        self.assertIn("ch_test_2", recovered)

    def test_web_bridge_release_all_sessions_and_shutdown(self):
        api = WebBridge(account_service=self.account_service, settings_service=self.settings_service)
        self.session_service.try_acquire_channel("ch_test_1", "bridge_user")

        with patch.object(self.account_service, "cleanup_on_shutdown", wraps=self.account_service.cleanup_on_shutdown) as mock_cleanup:
            api.shutdown()
            mock_cleanup.assert_called_once()

        channels_after = self.repo.get_channels()
        self.assertIsNone(channels_after[0].locked_by)

    def test_stale_lock_auto_expiration_on_acquire(self):
        from datetime import datetime, timedelta
        # Giả lập 1 kênh bị khóa từ 5 phút trước (mất heartbeat do crash đột ngột)
        data = self.repo._read_raw_data()
        stale_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        data["sessions"]["ch_test_1"] = {
            "channel_id": "ch_test_1",
            "cookies_data": [],
            "in_use_by": "dead_process_user",
            "in_use_since": stale_time,
            "last_heartbeat": stale_time,
            "last_synced_at": None,
            "updated_by": None
        }
        self.repo._save_raw_data(data)

        # Người dùng mới mở kênh -> khóa stale tự động bị hủy và cấp cho người mới
        ok, occupant = self.session_service.try_acquire_channel("ch_test_1", "new_user")
        self.assertTrue(ok)
        self.assertIsNone(occupant)

        sess = self.repo.get_session("ch_test_1")
        self.assertEqual(sess.in_use_by, "new_user")

    def test_stale_lock_auto_cleared_in_get_channels(self):
        from datetime import datetime, timedelta
        data = self.repo._read_raw_data()
        stale_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        data["sessions"]["ch_test_1"] = {
            "channel_id": "ch_test_1",
            "cookies_data": [],
            "in_use_by": "crashed_user",
            "in_use_since": stale_time,
            "last_heartbeat": stale_time,
            "last_synced_at": None,
            "updated_by": None
        }
        self.repo._save_raw_data(data)

        # Đọc danh sách kênh -> tự động hóa giải lock stale
        channels = self.repo.get_channels()
        ch1 = next(c for c in channels if c.channel.id == "ch_test_1")
        self.assertIsNone(ch1.locked_by)
        self.assertEqual(ch1.current_status, ChannelStatus.NOT_SETUP)

    def test_session_watchdog_auto_releases_dead_browser(self):
        # Kênh được khóa nhưng browser không chạy
        self.session_service.try_acquire_channel("ch_test_1", "user_crashed")
        self.browser_service._channel_locks["ch_test_1"] = MagicMock()

        released_channels = []
        self.account_service.on_session_auto_released = lambda ch: released_channels.append(ch)

        # Chạy 1 chu kỳ watchdog
        self.account_service._watchdog_tick()

        self.assertIn("ch_test_1", released_channels)
        ch1 = self.repo.get_channel("ch_test_1")
        sess = self.repo.get_session("ch_test_1")
        self.assertIsNone(sess.in_use_by)


if __name__ == "__main__":
    unittest.main()
