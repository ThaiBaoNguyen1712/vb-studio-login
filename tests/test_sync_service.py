"""Unit tests cho SyncService — 100% mock transport, khong cham mang that."""
import time
import unittest
from unittest.mock import MagicMock, patch

from src.services.sync_service import SyncService, _safe_key, _unsafekey, _is_fresh, STALE_AFTER_S


def _svc(store=None):
    settings = MagicMock()
    settings.get.side_effect = lambda sec, key, default=None: {
        ("firebase", "url"): "https://example.firebasedatabase.app/",
        ("firebase", "enabled"): True,
    }.get((sec, key), default)
    settings.get_auth_user.return_value = {"email": "a@x.com", "idToken": "tok"}
    s = SyncService(settings_service=settings)
    s.set_providers(
        identity=lambda: {"user": "Tester", "email": "a@x.com", "aliases": []},
        holders=lambda: {},
    )
    if store is not None:
        # Gia lap Firebase: nested dict, PUT sau tao cay, GET tra ve subtree.
        state = {"db": {}}

        def _put(tree, parts, data):
            for p in parts[:-1]:
                tree = tree.setdefault(p, {})
                if not isinstance(tree, dict):
                    return
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
                return _get(state["db"], parts)
            if method in ("PUT", "PATCH"):
                _put(state["db"], parts, data)
                return data
            if method == "DELETE":
                _delete(state["db"], parts)
                return None
            raise AssertionError(method)

        s._req = fake_req
        s._mark_ok()
    return s


class TestSyncKeys(unittest.TestCase):
    def test_safe_key_roundtrip_vietnamese(self):
        for name in ["Bảo Nguyễn", "a@x.com", "Admin", "Tên có/ký.tự $đặc#biệt[x]"]:
            k = _safe_key(name)
            self.assertNotRegex(k, r"[.\$#\[\]/]")
            self.assertEqual(_unsafekey(k), name.strip())

    def test_is_fresh(self):
        now_ms = int(time.time() * 1000)
        self.assertTrue(_is_fresh(now_ms))
        self.assertFalse(_is_fresh(now_ms - int((STALE_AFTER_S + 5) * 1000)))
        self.assertFalse(_is_fresh(None))
        self.assertFalse(_is_fresh("junk"))


class TestSyncLocks(unittest.TestCase):
    def test_claim_free_channel(self):
        s = _svc({})
        self.assertTrue(s.claim_lock("ch1", "Tester", "pc-1"))
        rl = s.remote_lock_of("ch1")
        self.assertIsNotNone(rl)
        self.assertEqual(rl["holder"], "Tester")

    def test_claim_denied_when_fresh_other(self):
        s = _svc({})
        self.assertTrue(s.claim_lock("ch1", "Bob", "pc-B"))
        s2 = _svc({})
        # share the same fake backend
        s2._req = s._req
        self.assertFalse(s2.claim_lock("ch1", "Alice", "pc-A"))
        rl = s2.remote_lock_of("ch1")
        self.assertEqual(rl["holder"], "Bob")

    def test_claim_takeover_stale(self):
        s = _svc({})
        stale_ts = int(time.time() * 1000) - int((STALE_AFTER_S + 10) * 1000)
        s._req("PUT", "locks/ch9", {"holder": "Ghost", "machine": "pc-X", "ts": stale_ts})
        self.assertIsNone(s.remote_lock_of("ch9"))
        self.assertTrue(s.claim_lock("ch9", "Tester", "pc-1"))
        self.assertEqual(s.remote_lock_of("ch9")["holder"], "Tester")

    def test_release_own_lock(self):
        s = _svc({})
        s.claim_lock("ch1", "Tester", s.machine_id)
        s.release_lock("ch1")
        self.assertIsNone(s.remote_lock_of("ch1"))

    def test_release_keeps_fresh_other(self):
        s = _svc({})
        s._req("PUT", "locks/ch1", {"holder": "Bob", "machine": "pc-B", "ts": int(time.time() * 1000)})
        s.release_lock("ch1", force=False)
        self.assertIsNotNone(s.remote_lock_of("ch1"))
        s.release_lock("ch1", force=True)
        self.assertIsNone(s.remote_lock_of("ch1"))


class TestSyncInbox(unittest.TestCase):
    def test_send_and_resolve(self):
        s = _svc({})
        rid = s.send_request("Bob", {"channel_id": "ch1", "requester": "Alice", "message": "gap"})
        self.assertTrue(rid and rid.startswith("q_"))
        got = []
        holder_svc = _svc({})
        holder_svc._req = s._req
        holder_svc.set_providers(
            identity=lambda: {"user": "Bob", "email": "", "aliases": []},
            holders=lambda: {},
        )
        holder_svc.tick()
        got = holder_svc.inbox_snapshot()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["requester"], "Alice")
        self.assertTrue(holder_svc.resolve_request(rid, "approve", "Bob"))
        # requester thay ket qua qua outbox tracking
        s.tick()
        self.assertEqual(s.outbox_snapshot(), [])


class TestSyncTickOffline(unittest.TestCase):
    def test_tick_without_config_stays_offline(self):
        settings = MagicMock()
        settings.get.return_value = ""
        settings.get_auth_user.return_value = None
        s = SyncService(settings_service=settings)
        s.tick()
        self.assertFalse(s.is_online())


if __name__ == "__main__":
    unittest.main()
