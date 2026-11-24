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


if __name__ == "__main__":
    unittest.main()
