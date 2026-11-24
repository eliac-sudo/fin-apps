import fcntl, io, json, tempfile, unittest
from unittest import mock

from bzd import app as App
from bzd import bots as BT
from bzd import vol_bot as VB
from tests.test_vol_bot import MON, FakeClient


class TestBots(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def bot(self, c, now):
        return VB.Bot(c, root=self.root, notify=None, now=lambda: now, log=lambda *a: None)

    def test_no_status_yet_reads_as_off(self):
        v = BT.view(self.root)["bots"][0]
        self.assertEqual(v["state"], "spento")
        self.assertIsNone(v["status"])

    def test_running_is_read_from_the_lock(self):
        d = VB.bot_dir(self.root)
        d.mkdir(parents=True)
        f = open(d / "bot.lock", "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertTrue(BT.running(self.root))
        f.close()
        self.assertFalse(BT.running(self.root))

    def test_cycle_writes_the_status_the_app_shows(self):
        c = FakeClient()
        self.bot(c, MON).cycle()
        st = json.loads((VB.bot_dir(self.root) / "status.json").read_text())
        self.assertEqual(st["equity"], 100000.0)
        self.assertEqual(len(st["book"]), 1)
        self.assertLess(abs(st["net_delta"]), .001)
        self.assertNotIn("secret", json.dumps(st).lower())

    def test_pause_and_resume_from_the_app(self):
        BT.act({"bot": "deribit", "action": "pausa"}, self.root)
        self.assertTrue(VB.read_control(self.root)["paused"])
        c = FakeClient()
        self.bot(c, MON).cycle()
        self.assertFalse([p for m, p in c.calls if m == "private/sell"])
        BT.act({"bot": "deribit", "action": "riprendi"}, self.root)
        self.assertFalse(VB.read_control(self.root)["paused"])

    def test_emergency_close_needs_the_word_and_closes_everything(self):
        c = FakeClient()
        self.bot(c, MON).cycle()
        self.bot(c, MON.replace(hour=16)).cycle()
        with self.assertRaises(ValueError):
            BT.act({"bot": "deribit", "action": "chiudi", "confirm": "si"}, self.root)
        v = BT.act({"bot": "deribit", "action": "chiudi", "confirm": "CHIUDI"}, self.root)["bots"][0]
        self.assertTrue(v["pending_close"])
        b = self.bot(c, MON.replace(hour=17))
        b.cycle()
        self.assertEqual(b.st["book"], [])
        self.assertTrue(all(abs(x) < 1e-9 for x in c.pos.values()))
        self.assertTrue(VB.read_control(self.root)["paused"])
        self.assertFalse(BT.view(self.root)["bots"][0]["pending_close"])
        n = len(c.calls)
        self.bot(c, MON.replace(hour=18)).cycle()  # done once, not again
        self.assertFalse([p for m, p in c.calls[n:] if m == "private/buy"])

    def test_size_can_only_go_down(self):
        with self.assertRaises(ValueError):
            BT.act({"bot": "deribit", "action": "dimensione", "value": 0.5}, self.root)
        BT.act({"bot": "deribit", "action": "dimensione", "value": 0.1}, self.root)
        c = FakeClient()
        self.bot(c, MON).cycle()
        self.assertTrue(all(p["amount"] == 0.16 for m, p in c.calls if m == "private/sell" and p.get("post_only")))  # 10% of 100k at 61500
        BT.act({"bot": "deribit", "action": "dimensione", "value": 0.25}, self.root)
        self.assertIsNone(VB.read_control(self.root)["notional_per_entry"])

    def test_unknown_commands_are_refused(self):
        for body in ({"bot": "x", "action": "pausa"}, {"bot": "deribit", "action": "compra"}):
            with self.assertRaises(ValueError):
                BT.act(body, self.root)

    def test_app_refuses_bot_commands_without_its_header(self):
        h = App.Handler.__new__(App.Handler)
        h.path, h.headers, h.rfile = "/api/bots", {"Content-Length": "2"}, io.BytesIO(b"{}")
        sent = []
        h.send = lambda code, body, kind=None: sent.append(code)
        with mock.patch.object(BT, "act") as act:
            h.do_POST()
        self.assertEqual(sent, [403])
        act.assert_not_called()


if __name__ == "__main__":
    unittest.main()
