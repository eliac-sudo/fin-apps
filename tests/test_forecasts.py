import io, unittest

import pandas as pd

from bzd import forecasts as F, jobs as J, recorder as R


def obs(start, end, date, value):
    return {"realtime_start": start, "realtime_end": end, "date": date, "value": value}


class Forecasts(unittest.TestCase):
    def test_unchanged_target_year_stays_in_the_new_edition(self):
        raw = {"FEDTARMD": [obs("2026-06-17", "2026-09-15", "2027-01-01", "3.4"), obs("2026-09-16", "9999-12-31", "2027-01-01", "3.9"),
                            obs("2026-06-17", "9999-12-31", "2028-01-01", "3.1")]}
        d = F.parse_sep("FEDTARMD", raw["FEDTARMD"], F.sep_editions(raw))
        last = d[d.made == "2026-09-16"].set_index("target").value
        self.assertEqual(last.to_dict(), {"2027": 3.9, "2028": 3.1})
        self.assertEqual(d[d.made == "2026-06-17"].set_index("target").value.to_dict(), {"2027": 3.4, "2028": 3.1})

    def test_past_years_and_missing_values_are_dropped(self):
        raw = [obs("2026-09-16", "9999-12-31", "2025-01-01", "4.0"), obs("2026-09-16", "9999-12-31", "2026-01-01", ".")]
        self.assertTrue(F.parse_sep("FEDTARMD", raw, ["2026-09-16"]).empty)

    def test_longer_run_is_dated_by_its_edition(self):
        raw = [obs("2026-06-17", "2026-09-15", "2026-06-17", "3.0"), obs("2026-09-16", "9999-12-31", "2026-06-17", "3.1"),
               obs("2026-09-16", "9999-12-31", "2026-09-16", "3.2")]
        d = F.parse_sep("FEDTARMDLR", raw, [])
        self.assertEqual(d.set_index("made").value.to_dict(), {"2026-06-17": 3.1, "2026-09-16": 3.2})

    def test_philly_horizons_map_to_target_periods(self):
        b = io.BytesIO()
        with pd.ExcelWriter(b) as w:
            pd.DataFrame({"YEAR": [2026], "QUARTER": [4], "CPI1": [1.7], "CPI2": [4.0], "CPI6": [2.4], "CPIA": [3.8], "CPIC": [2.3]}).to_excel(w, sheet_name="CPI", index=False)
            for s in F.SPF_SHEETS[1:]:
                pd.DataFrame({"YEAR": [2026], "QUARTER": [4]}).to_excel(w, sheet_name=s, index=False)
        d = F.parse_philly(b.getvalue()).set_index("target").value
        self.assertEqual(d.to_dict(), {"2026": 3.8, "2026Q3": 1.7, "2026Q4": 4.0, "2027Q4": 2.4, "2028": 2.3})

    def test_ecb_rolling_horizons_are_left_out(self):
        csv = "KEY,FCT_TOPIC,FCT_HORIZON,TIME_PERIOD,OBS_VALUE\nk,HICP,2027,2026-Q4,2.6\nk,HICP,LT,2026-Q4,2.0\nk,RGDP,P21M,2028-Q2,1.3\n"
        d = F.parse_ecb_spf(csv)
        self.assertEqual(list(d.target), ["2027", "LT"])
        self.assertEqual(set(d.made), {"2026Q4"})

    def test_xlsx_validation(self):
        self.assertIsNone(R.validate("xlsx", b"PK\x03\x04rest"))
        self.assertEqual(R.validate("xlsx", b"<!DOCTYPE html>"), "not xlsx")

    def test_every_forecast_source_is_recorded(self):
        names = {j.name for j in J.all_jobs()}
        self.assertTrue({"fc_oecd_outlook", "fc_ecb_spf", "fc_philly_spf", "fc_kalshi_kxfed", "fc_polymarket_fed"} <= names)
        self.assertTrue({f"macro_fred_{s.lower()}" for s in J.FRED_ALL} <= names)

    def test_ladders_read_from_the_highest_level_down(self):
        opts = [{"name": n} for n in ("Above -75,000", "Above 75,000", "Above 200,000")]
        self.assertEqual([o["name"] for o in F.by_strike(opts)], ["Above 200,000", "Above 75,000", "Above -75,000"])
        named = [{"name": "Hike 25bps"}, {"name": "Fed maintains rate"}]
        self.assertEqual(F.by_strike(named), named)

    def test_fed_view_compares_with_the_previous_edition(self):
        d = pd.DataFrame({"made": ["2026-06-17", "2026-09-16", "2026-09-16", "2026-06-17"], "series": ["fed_funds_median"] * 3 + ["unemployment"],
                          "target": ["2027", "2027", "2026", "2027"], "value": [3.6, 4.1, 4.1, 4.3]})
        v = F.fed_view(d)
        med = v["rows"][0]
        self.assertEqual((v["made"], v["prev_made"]), ("2026-09-16", "2026-06-17"))
        self.assertEqual((med["values"]["2027"], med["prev"]["2027"]), (4.1, 3.6))
        self.assertEqual(v["chart"]["dates"], ["2026-06-17", "2026-09-16"])
        self.assertEqual(v["chart"]["fed_funds_median"], [3.6, 4.1])

    def test_view_survives_missing_files(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as t:
            old = os.environ.get("BZD_DATA")
            os.environ["BZD_DATA"] = t
            try:
                v = F.view()
            finally:
                os.environ.pop("BZD_DATA") if old is None else os.environ.__setitem__("BZD_DATA", old)
        self.assertEqual(v["errors"], [])
        self.assertIsNone(v["fed"])
        self.assertEqual(v["markets"], [])

    def test_names_with_a_comma_before_any_digit_are_not_strikes(self):
        self.assertIsNone(F._strike("Hold, no change"))
        self.assertEqual(F._strike("Jan, 2027"), 2027.0)
        self.assertEqual(F._strike("Above -75,000"), -75000.0)

    def test_ten_cent_spread_uses_the_midpoint(self):
        self.assertEqual(F._prob({"yes_bid_dollars": "0.4500", "yes_ask_dollars": "0.5500", "last_price_dollars": "0.0000"}), 0.5)
        self.assertEqual(F._prob({"yes_bid_dollars": "0.3000", "yes_ask_dollars": "0.5500", "last_price_dollars": "0.2000"}), 0.2)
        self.assertIsNone(F._prob({"yes_bid_dollars": "0", "yes_ask_dollars": "0.9", "last_price_dollars": "0"}))

    def test_event_period_from_ticker(self):
        self.assertEqual(F.event_period("KXFED-27JAN"), "gen 2027")
        self.assertEqual(F.event_period("KXINXY-26DEC31"), "dic 2026")
        self.assertEqual(F.event_period("KXRECSSNBER-27"), "2027")
        self.assertIsNone(F.event_period("KXFED-ABC"))

    def _with_raw(self, files, fn):
        import gzip, json, os, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            for job, body in files.items():
                p = Path(t) / "raw" / job / "2026-11-24" / "120000Z.json.gz"
                p.parent.mkdir(parents=True)
                p.write_bytes(gzip.compress(body if isinstance(body, bytes) else json.dumps(body).encode()))
            old = os.environ.get("BZD_DATA")
            os.environ["BZD_DATA"] = t
            try:
                return fn()
            finally:
                os.environ.pop("BZD_DATA") if old is None else os.environ.__setitem__("BZD_DATA", old)

    def test_kalshi_skips_settled_events_keeps_likely_rungs_and_one_broken_source_hides_nothing(self):
        def m(ev, close, name, p, vol):
            return {"event_ticker": ev, "close_time": close, "title": "t", "yes_sub_title": name, "yes_bid_dollars": str(p - .01),
                    "yes_ask_dollars": str(p + .01), "last_price_dollars": "0", "volume_fp": str(vol)}
        settled = [m("KXFED-26DEC", "2026-12-09", "Above 4.00%", .99, 9)]
        ladder = [m("KXFED-27JAN", "2027-01-27", f"Above {k}", p, v) for k, p, v in
                  [(5, .04, 1), (4.75, .05, 1), (4.5, .2, 50), (4.25, .6, 90), (4, .9, 80)]]
        nxt = [m("KXFED-27MAR", "2027-03-18", "Above 4.25%", .5, 5)]
        later = [m("KXFED-27APR", "2027-04-28", "Above 4.25%", .5, 5)]
        files = {"fc_kalshi_kxfed": {"markets": settled + ladder + nxt + later}, "fc_kalshi_kxcpi": b"not json",
                 "fc_polymarket_fed": [{"id": "1", "title": "Fed in Jan?", "endDate": "2027-01-28", "volume24hr": 5,
                                        "markets": [{"groupItemTitle": "Hold", "outcomePrices": "[\"0.4\", \"0.6\"]"}]}]}
        old = F.MAX_OPTIONS
        F.MAX_OPTIONS = 3
        try:
            v = self._with_raw(files, F.view)
        finally:
            F.MAX_OPTIONS = old
        kx = [x for x in v["markets"] if x["source"] == "Kalshi"]
        self.assertEqual([x["label"] for x in kx], ["Tasso Fed (limite alto) dopo la riunione · gen 2027", "Tasso Fed (limite alto) dopo la riunione · mar 2027"])
        self.assertEqual([o["name"] for o in kx[0]["options"]], ["Above 4.5", "Above 4.25", "Above 4"])
        self.assertTrue(any(x["source"] == "Polymarket" for x in v["markets"]))
        self.assertEqual(v["errors"], ["Kalshi KXCPI: JSONDecodeError"])

    def test_polymarket_overlap_does_not_shrink_the_second_feed(self):
        ev = lambda i, vol: {"id": str(i), "title": f"E{i}", "volume24hr": vol, "markets": [{"groupItemTitle": "x", "outcomePrices": "[\"0.5\", \"0.5\"]"}]}
        eco = [ev(i, 100 - i) for i in range(10)]  # read first
        fed = [ev(i, 100 - i) for i in range(5)] + [ev(i, 50 - i) for i in range(20, 35)]
        v = self._with_raw({"fc_polymarket_fed": fed, "fc_polymarket_economy": eco}, F.polymarket_view)
        self.assertEqual(len(v), 20)

    def test_longer_run_date_is_not_an_edition(self):
        d = pd.DataFrame({"made": ["2026-09-16", "2026-09-17"], "series": ["fed_funds_median", "fed_funds_longer_run"],
                          "target": ["2027", "longer_run"], "value": [4.1, 3.2]})
        v = F.fed_view(d)
        self.assertEqual((v["made"], v["targets"], v["longer_run"]), ("2026-09-16", ["2027"], 3.2))


if __name__ == "__main__":
    unittest.main()
