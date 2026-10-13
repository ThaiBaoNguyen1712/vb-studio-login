"""Tich hop sync 2 may (chung fake RTDB) + bridge merge. Khong cham mang that."""
import unittest
from unittest.mock import MagicMock, patch

from src.services.sync_service import SyncService
from src.services.account_service import AccountService


def make_backend():
    db = {}

    def _put(tree, parts, data):
        for p in parts[:-1]:
            tree = tree.setdefault(p, {})
        tree[parts[-1]] = data

    def _get(tree, parts):
        for p in parts:
            if not isinstance(tree, dict) or p not in tree:
                return None
            tree = tree[p]
        return tree

    def _delete(tree, parts):
        for p in parts[:-1]:
            if not isinstance(tree, dict) or p not in tree:
                return
            tree = tree[p]
        if isinstance(tree, dict):
            tree.pop(parts[-1], None)

    def fake_req(method, path, data=None):
        parts = [p for p in path.split("/") if p]
        if method == "GET":
            return _get(db, parts)
        if method in ("PUT", "PATCH"):
            _put(db, parts, data)
            return data
        if method == "DELETE":
            _delete(db, parts)
            return None
        raise AssertionError(method)

    return db, fake_req


def make_sync(user, machine, fake_req, events=None):
    settings = MagicMock()
    settings.get.side_effect = lambda sec, key, default=None: {
        ("firebase", "url"): "https://example.firebasedatabase.app/",
        ("firebase", "enabled"): True,
    }.get((sec, key), default)
    settings.get_auth_user.return_value = {"email": f"{user}@x.com", "idToken": "tok"}
    s = SyncService(settings_service=settings, machine_id=machine)
    s.set_providers(
        identity=lambda: {"user": user, "email": f"{user}@x.com", "aliases": []},
        holders=lambda: {},
    )
    s._req = fake_req
    s._mark_ok()
    if events is not None:
        s.on_remote_request = lambda r: events.append(("inbox", r))
        s.on_request_update = lambda r: events.append(("outbox", r))
    return s


class TestTwoMachines(unittest.TestCase):
    def test_handover_flow(self):
        """A giu -> B bi chan -> B xin -> A duyet -> B thay approved."""
        _, fake = make_backend()
        ev_a, ev_b = [], []
        sync_a = make_sync("Holder", "pc-A", fake, ev_a)
        sync_b = make_sync("Requester", "pc-B", fake, ev_b)

        # A claim lock
        self.assertTrue(sync_a.claim_lock("ch1", "Holder", "pc-A"))
        # B thay lock fresh cua A
        rl = sync_b.remote_lock_of("ch1")
        self.assertIsNone(rl)  # cache B chua co
        self.assertFalse(sync_b.claim_lock("ch1", "Requester", "pc-B"))
        self.assertEqual(sync_b.remote_lock_of("ch1")["holder"], "Holder")

        # B gui xin mo toi Holder
        rid = sync_b.send_request("Holder", {"channel_id": "ch1", "requester": "Requester", "message": "gap"})
        self.assertTrue(rid)
        sync_a.tick()
        self.assertEqual(len(sync_a.inbox_snapshot()), 1)
        self.assertEqual(ev_a[0][0], "inbox")

        # A duyet
        self.assertTrue(sync_a.resolve_request(rid, "approve", "Holder"))
        sync_b.tick()
        self.assertEqual(sync_b.outbox_snapshot(), [])
        kinds = [k for k, _ in ev_b]
        self.assertIn("outbox", kinds)
        approved = [r for k, r in ev_b if k == "outbox"][0]
        self.assertEqual(approved["status"], "approved")

    def test_stale_takeover(self):
        import time
        from src.services.sync_service import STALE_AFTER_S
        _, fake = make_backend()
        sync_a = make_sync("Ghost", "pc-A", fake)
        stale = int(time.time() * 1000) - int((STALE_AFTER_S + 5) * 1000)
        fake("PUT", "locks/chX", {"holder": "Ghost", "machine": "pc-A", "ts": stale})
        sync_b = make_sync("Tester", "pc-B", fake)
        self.assertIsNone(sync_b.remote_lock_of("chX"))
        self.assertTrue(sync_b.claim_lock("chX", "Tester", "pc-B"))


class TestAccountServiceRemoteDeny(unittest.TestCase):
    def test_launch_denied_by_remote(self):
        mock_repo = MagicMock()
        mock_session = MagicMock()
        browser = MagicMock()
        sync = MagicMock()
        sync.is_online.return_value = True
        sync.remote_lock_of.return_value = {"holder": "Holder", "machine": "pc-A", "ts": 9999999999999}
        acc = AccountService(repository=mock_repo, session_service=mock_session,
                             browser_service=browser, sync_service=sync)
        errs = []
        acc.launch_channel("ch1", "Requester", on_error=lambda c, m: errs.append(m))
        self.assertTrue(errs)
        self.assertIn("pc-A", errs[0])
        mock_session.try_acquire_channel.assert_not_called()

    def test_launch_offline_allows_local(self):
        mock_repo = MagicMock()
        mock_repo.get_channel.return_value = MagicMock(
            studio_url="https://s", login_url="https://l", channel_name="C")
        mock_session = MagicMock()
        mock_session.try_acquire_channel.return_value = (True, None)
        mock_session.get_channel_cookies.return_value = []
        browser = MagicMock()
        sync = MagicMock()
        sync.is_online.return_value = False
        acc = AccountService(repository=mock_repo, session_service=mock_session,
                             browser_service=browser, sync_service=sync)
        acc.launch_channel("ch1", "Me")
        mock_session.try_acquire_channel.assert_called_once()
        browser.launch_channel_browser.assert_called_once()


class TestBridgeMerge(unittest.TestCase):
    def _bridge(self, sync):
        from src.web.api_bridge import WebBridge
        mock_repo = MagicMock()
        ch = MagicMock()
        ch.id = "ch1"
        ch.channel_name = "Kenh 1"
        sess = MagicMock()
        sess.in_use_by = None
        sess.cookies_data = []
        item = MagicMock()
        item.channel = ch
        item.session = sess
        item.current_status.value = "READY"
        item.locked_by = None
        mock_repo.get_channels.return_value = [item]
        mock_session = MagicMock()
        mock_session.list_access_requests.return_value = []
        acc = AccountService(repository=mock_repo, session_service=mock_session,
                             browser_service=MagicMock(), sync_service=sync)
        settings = MagicMock()
        settings.settings = {"general": {"default_user": "Me"}}
        settings.get.side_effect = lambda s, k, d=None: {"default_user": "Me"}.get(k, d) if s == "general" else d
        b = WebBridge(account_service=acc, settings_service=settings)
        b._window = None
        b._sync_service = sync
        return b

    def test_remote_lock_marks_channel(self):
        sync = MagicMock()
        sync.remote_locks_snapshot.return_value = {
            "ch1": {"holder": "Holder", "machine": "pc-A", "ts": 9999999999999}}
        sync.outbox_snapshot.return_value = []
        sync.inbox_snapshot.return_value = []
        b = self._bridge(sync)
        rows = b.get_channels()
        self.assertEqual(rows[0]["status"], "IN_USE")
        self.assertEqual(rows[0]["locked_by"], "Holder")
        self.assertTrue(rows[0]["locked_remote"])
        self.assertEqual(rows[0]["locked_machine"], "pc-A")

    def test_no_sync_keeps_local(self):
        b = self._bridge(None)
        rows = b.get_channels()
        self.assertEqual(rows[0]["status"], "READY")
        self.assertFalse(rows[0]["locked_remote"])

    def test_request_access_remote_route(self):
        sync = MagicMock()
        sync.is_online.return_value = True
        sync.send_request.return_value = "q_x_1"
        b = self._bridge(sync)
        with patch.object(AccountService, "_remote_lock_other",
                          return_value={"holder": "Holder", "machine": "pc-A"}):
            res = b.request_access("ch1", "Me", "cho minh mo")
        self.assertTrue(res["success"])
        self.assertTrue(res.get("remote"))
        sync.send_request.assert_called_once()

    def test_resolve_remote_route(self):
        sync = MagicMock()
        sync.inbox_snapshot.return_value = [
            {"id": "q_x_1", "channel_id": "ch1", "requester": "Me",
             "holder": "Holder", "message": "", "status": "pending"}]
        sync.remote_lock_of.return_value = None
        sync.resolve_request.return_value = True
        sync.machine_id = "pc-B"
        b = self._bridge(sync)
        res = b.resolve_access_request("rdb_q_x_1", "Holder", "deny")
        self.assertTrue(res["success"])
        sync.resolve_request.assert_called_once_with("q_x_1", "deny", "Holder")


if __name__ == "__main__":
    unittest.main()
