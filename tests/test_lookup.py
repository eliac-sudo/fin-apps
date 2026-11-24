import unittest
from unittest import mock

import pandas as pd

from bzd import lookup as LK

UNIVERSE = {"BTC": {"name": "BTC", "dex": "principale", "price": 100.0, "volume_24h": 9e9, "open_interest": 1e9, "funding_hourly": 1e-5, "change_24h": 0, "max_leverage": 40},
            "xyz:NVDA": {"name": "xyz:NVDA", "dex": "xyz", "price": 190.0, "volume_24h": 3e8, "open_interest": 1e8, "funding_hourly": 0, "change_24h": 0, "max_leverage": 20},
            "io:NVDA": {"name": "io:NVDA", "dex": "io", "price": 190.0, "volume_24h": 5e6, "open_interest": 1e6, "funding_hourly": 0, "change_24h": 0, "max_leverage": 10}}


class TestSearch(unittest.TestCase):
    def setUp(self):
        LK._cache.clear()

    def test_a_company_name_finds_its_perps_busiest_first(self):
        with mock.patch.object(LK, "universe", return_value=UNIVERSE), mock.patch.object(LK, "yahoo_search", return_value=[{"symbol": "NVDA", "name": "NVIDIA", "type": "EQUITY", "exchange": "NMS"}]):
            ids = [r["id"] for r in LK.search("nvidia")]
        self.assertEqual(ids, ["hl:xyz:NVDA", "hl:io:NVDA", "yf:NVDA"])

    def test_a_broken_source_is_skipped(self):
        with mock.patch.object(LK, "universe", return_value=UNIVERSE), mock.patch.object(LK, "yahoo_search", side_effect=OSError):
            self.assertEqual([r["id"] for r in LK.search("btc")], ["hl:BTC"])
        self.assertEqual(LK.search("  "), [])

    def test_only_safe_ids_are_fetched(self):
        with mock.patch.object(LK, "universe", return_value=UNIVERSE):
            self.assertTrue(LK.valid("hl:xyz:NVDA"))
            self.assertFalse(LK.valid("hl:NOPE"))
            self.assertTrue(LK.valid("yf:GC=F"))
            for bad in ("yf:../../x", "yf:a b", "yf:http://x", "file:/etc/passwd", "yf:"):
                self.assertFalse(LK.valid(bad), bad)

    def test_view_has_the_technical_shape_and_market_facts(self):
        idx = pd.date_range("2024-01-01", periods=500, freq="D", tz="UTC")
        c = pd.Series(range(100, 600), idx, dtype=float)
        d = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * .99, "close": c})
        with mock.patch.object(LK, "bars", return_value=(d, None, {"source": "Yahoo", "name": "Test"})):
            v = LK.technical("yf:TEST")
        self.assertTrue(v["searched"])
        self.assertIn("1d", v["frames"])
        self.assertEqual(v["position"]["label"], "molto caro")


class TestApp(unittest.TestCase):
    def test_unknown_ids_never_reach_the_network(self):
        with mock.patch.object(LK, "universe", return_value=UNIVERSE), mock.patch.object(LK, "http") as http:
            self.assertFalse(LK.valid("hl:FAKE"))
        http.assert_not_called()
