import unittest

from bzd import commands as C

SNAP = {
    "overview": "Nessun gruppo sopra la norma.",
    "briefing": [{"text": "Momentum sul giornaliero: in calo su BTC."}],
    "classes": {"crypto": {"name": "Cripto", "heat": 31.2, "band": "↘ sotto la norma", "change_7d": 7.4}},
    "markets": [{"market": "BTC", "label": "BTC", "price": 59694.2, "heat": 23.6, "band": "↘ sotto la norma", "returns": {"1g": -2.5, "7g": -8.0, "30g": -28.0},
                 "position": {"label": "molto economico", "from_high": -38.4, "from_low": 1.9}, "zones": {"1d": {"tag": "GIU"}}},
                {"market": "GC=F", "label": "Oro", "price": 3651.4, "returns": {}}],
    "technical": [{"market": "BTC", "trend": {"1d": "ribasso", "1w": "ribasso", "1M": "laterale"}, "rsi": {"1d": 24.9}}],
    "alerts": {"setups": [{"market": "BTC", "setup": "PANICO", "trigger": "2026-11-05T08:00:00+00:00"}],
               "moves": [{"at": "2026-11-24T15:35:00+00:00", "label": "Rame", "pct": -5.6, "window": "24h"}], "resets": []},
    "tests": [{"outcome": "supportata", "setup_name": "PANICO", "class_name": "cripto", "reading": ["Ha retto."]},
              {"outcome": "non supportata", "setup_name": "SQUEEZE", "class_name": "cripto", "reading": ["No."]}],
    "verdicts": {"O2": {"outcome": "supportata", "line": "Economiche meglio."}, "O1": {"outcome": "non supportata", "line": "No."}},
}
BOTS = {"bots": [{"name": "Strangle BTC coperto", "venue": "Deribit", "state": "acceso", "status": {"net": "test", "equity": 99901.6, "options": [], "paused": True},
                  "events": [{"t": "2026-11-24T13:44:58+00:00", "event": "conto"}]}]}


def get(path, timeout=None):
    return BOTS if path == "/api/bots" else SNAP


class TestCommands(unittest.TestCase):
    def test_ticker_finds_by_code_label_and_common_name(self):
        self.assertIn("<b>BTC</b>", C.answer("/ticker", ["btc"], get))
        self.assertIn("<b>Oro</b>", C.answer("/ticker", ["oro"], get))
        self.assertIn("<b>Oro</b>", C.answer("/ticker", ["gold"], get))
        self.assertIn("Non trovo", C.answer("/ticker", ["pippo"], get))
        self.assertIn("Scrivi il mercato", C.answer("/ticker", [], get))

    def test_ticker_says_momentum_trend_and_rsi(self):
        text = C.answer("/ticker", ["BTC"], get)
        for bit in ("scende forte", "giornaliero ribasso", "ipervenduto", "PANICO del 05/11", "-8,0%"):
            self.assertIn(bit, text)

    def test_tests_lists_only_what_held(self):
        text = C.answer("/test", [], get)
        self.assertIn("PANICO", text)
        self.assertIn("O2", text)
        self.assertNotIn("SQUEEZE", text)
        self.assertNotIn("O1", text)

    def test_alert_newest_first(self):
        text = C.answer("/alert", [], get)
        self.assertLess(text.index("Rame"), text.index("PANICO"))

    def test_bot_shows_state_and_never_offers_controls_here(self):
        text = C.answer("/bot", [], get)
        self.assertIn("testnet", text)
        self.assertIn("in pausa", text)
        self.assertIn("dall'app", text)

    def test_oggi_and_help(self):
        self.assertIn("Cripto: 31", C.answer("/oggi", [], get))
        self.assertIn("/ticker", C.answer("/aiuto", [], get))
        self.assertIsNone(C.answer("/compra", [], get))

    def test_app_down_gives_a_short_message(self):
        def down(path, timeout=None):
            raise OSError("refused")
        self.assertEqual(C.answer("/oggi", [], down), C.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
