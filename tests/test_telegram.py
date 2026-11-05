import gzip, json, tempfile, unittest
from pathlib import Path

from bzd import telegram as T


def msg(i, text="hi"):
    return (f'<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message" data-post="c/{i}">'
            f'<div class="tgme_widget_message_text js-message_text" dir="auto">{text}</div>'
            f'<time datetime="2024-01-01T00:00:{i % 60:02d}+00:00" class="time"></time></div></div>')


def page(*ids):
    return '<div class="tgme_channel_info"></div>' + "".join(msg(i) for i in ids)


class TestParse(unittest.TestCase):
    def test_parses_id_time_and_text_with_markup(self):
        m = T.parse_page(page(5)[:0] + msg(7, "<b>🔴</b> #ETH &amp; more<br/>next"))
        self.assertEqual(m[0][0], 7)
        self.assertEqual(m[0][1], "2024-01-01T00:00:07+00:00")
        self.assertEqual(m[0][2], "🔴 #ETH & more next")

    def test_real_liquidation_formats(self):
        cases = {
            "🔴 #ETH Liquidated Long: $76.9K at $2413.87": ("ETH", "long", 76900, 2413.87),
            "✳ #BTC Liquidated Short: $137K at $50767.47": ("BTC", "short", 137000, 50767.47),
            "🔴 #BTC Liquidated Long: $97.3K at $80,096 - hyper lens": ("BTC", "long", 97300, 80096),
            "🔴 #xyz :CL Liquidated Long: $93.4K at $87.13 - hyper lens": ("xyz:CL", "long", 93400, 87.13),
            "🟢 #BTC Liquidated Short: $1.2M at $58000": ("BTC", "short", 1200000, 58000),
        }
        for text, (coin, side, usd, px) in cases.items():
            r = T.parse_liquidation(text)
            self.assertEqual((r["coin"], r["side"], r["price"]), (coin, side, px))
            self.assertAlmostEqual(r["usd"], usd)

    def test_other_text_is_not_a_liquidation(self):
        self.assertIsNone(T.parse_liquidation("Channel created"))
        self.assertIsNone(T.parse_liquidation("250,000,000 $USDC minted"))


class TestBackfill(unittest.TestCase):
    def run_fake(self, pages, root, stop=lambda: False):
        calls = []

        def get(channel, before):
            calls.append(before)
            return pages[before]

        return T.backfill(root, "c", stop, get=get, gap=0, log=lambda m: None), calls

    def rows(self, root):
        return [json.loads(x) for x in gzip.open(Path(root) / "c" / "messages.jsonl.gz", "rt")]

    def test_walks_to_channel_start_without_duplicates(self):
        with tempfile.TemporaryDirectory() as r:
            p, calls = self.run_fake({None: page(5, 6), 5: page(3, 4), 3: page(1, 2)}, r)
            self.assertTrue(p["done"])
            self.assertEqual(calls, [None, 5, 3])
            self.assertEqual(sorted(x["id"] for x in self.rows(r)), [1, 2, 3, 4, 5, 6])

    def test_resumes_where_it_stopped(self):
        pages = {None: page(5, 6), 5: page(3, 4), 3: page(1, 2)}
        with tempfile.TemporaryDirectory() as r:
            n = {"i": 0}

            def stop():
                n["i"] += 1
                return n["i"] > 1

            p, _ = self.run_fake(pages, r, stop)
            self.assertFalse(p["done"])
            p, calls = self.run_fake(pages, r)
            self.assertEqual(calls, [5, 3])
            self.assertEqual(sorted(x["id"] for x in self.rows(r)), [1, 2, 3, 4, 5, 6])

    def test_steps_over_deleted_range(self):
        with tempfile.TemporaryDirectory() as r:
            p, calls = self.run_fake({None: page(40, 41), 40: page(), 20: page(2, 3), 2: page(1)}, r)
            self.assertEqual(calls, [None, 40, 20, 2])
            self.assertTrue(p["done"])

    def test_block_page_does_not_advance_or_finish(self):
        seq = iter(["<html>blocked</html>", page(1, 2)])
        with tempfile.TemporaryDirectory() as r:
            p = T.backfill(r, "c", lambda: False, get=lambda c, b: next(seq), gap=0, log=lambda m: None)
            self.assertEqual(p["count"], 2)


if __name__ == "__main__":
    unittest.main()
