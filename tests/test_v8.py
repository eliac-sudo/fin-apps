import json, os, tempfile, unittest

import pandas as pd

from bzd import v8


class V8(unittest.TestCase):
    def test_forward_results_live_in_data_not_in_config(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["BZD_DATA"] = t
            try:
                d = v8.forward_dir()
            finally:
                os.environ.pop("BZD_DATA")
        self.assertEqual(d.name, "v8")
        self.assertTrue(str(d).startswith(t))

    def test_size_ignores_direction(self):
        b = pd.DataFrame({"open": [100.0, 100, 100, 100], "close": [110.0, 90, 100, 100]})
        r = v8.returns_for(b, 1, "ampiezza")
        self.assertAlmostEqual(r[0], 0.1)
        self.assertAlmostEqual(r[1], 0.1)

    def test_config_matches_the_preregistration(self):
        self.assertIn(v8.config_hash(), v8.DOC.read_text())


if __name__ == "__main__":
    unittest.main()
