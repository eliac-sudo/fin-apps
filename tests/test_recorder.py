import contextlib, gzip, io, os, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from bzd import jobs as J, recorder as R

SECRET = "s3cr3t-key-value"


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if "boom" in self.path:
            self.send_response(429); self.send_header("Retry-After", "7777"); self.end_headers(); return
        body = b"<html>blocked</html>" if "html" in self.path else b'{"a":1}'
        self.send_response(200); self.end_headers(); self.wfile.write(body)

    def log_message(self, *a):
        pass


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arc = R.Archive(self.tmp.name)
        os.environ["TEST_KEY"] = SECRET

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self):
        return "".join(p.read_text() for p in (Path(self.tmp.name) / "manifest").glob("*.jsonl"))

    def test_saves_gzip_with_matching_hash(self):
        rec, _ = R.run_one(self.arc, J.Job("a", self.url + "/x", 60))
        self.assertTrue(rec["ok"])
        self.assertEqual(gzip.open(Path(self.tmp.name) / rec["path"]).read(), b'{"a":1}')

    def test_unchanged_response_is_logged_but_not_stored_twice(self):
        j = J.Job("a", self.url + "/x", 60)
        first, _ = R.run_one(self.arc, j)
        second, _ = R.run_one(self.arc, j)
        self.assertTrue(second["unchanged"])
        self.assertEqual(second["path"], first["path"])
        self.assertEqual(len(list((Path(self.tmp.name) / "raw").rglob("*.gz"))), 1)

    def test_block_page_with_status_200_is_a_failure(self):
        rec, _ = R.run_one(self.arc, J.Job("a", self.url + "/html", 60))
        self.assertFalse(rec["ok"])
        self.assertNotIn("path", rec)

    def test_secret_never_reaches_manifest_or_state(self):
        j = J.Job("a", self.url + "/x?k={TEST_KEY}", 60, needs=("TEST_KEY",))
        R.run_one(self.arc, j)
        R.run_one(self.arc, J.Job("b", self.url + "/boom?k={TEST_KEY}", 60, needs=("TEST_KEY",)))
        self.assertIn("{TEST_KEY}", self.manifest())
        self.assertNotIn(SECRET, self.manifest())
        self.assertNotIn(SECRET, (Path(self.tmp.name) / "state.json").read_text())

    def test_failures_back_off_and_honour_retry_after(self):
        j = J.Job("b", self.url + "/boom", 60)
        rec, ra = R.run_one(self.arc, j)
        self.assertEqual(rec["status"], 429)
        self.assertEqual(R.retry_delay(j, 1, ra), 7777)
        self.assertEqual(R.retry_delay(j, 2), 120)
        self.assertEqual(R.retry_delay(j, 20), 3600)

    def test_api_errors_inside_200_are_failures(self):
        self.assertIn("retCode", R.validate("json", b'{"retCode":10001,"retMsg":"bad"}'))
        self.assertIn("code", R.validate("json", b'{"code":"51000","msg":"bad"}'))
        self.assertIsNone(R.validate("json", b'{"code":"0","data":[]}'))
        self.assertIsNone(R.validate("json", b'{"retCode":0}'))
        self.assertEqual(R.validate("json", b"Please limit requests"), "not json")
        self.assertEqual(R.validate("json", b"{}"), "empty result")
        self.assertEqual(R.validate("xml", b"<!DOCTYPE html><html>"), "not xml")
        self.assertIsNone(R.validate("xml", "﻿<?xml version='1.0'?>".encode()))

    def test_candle_requests_do_not_depend_on_start_time(self):
        self.assertEqual(J.candle_jobs(), J.candle_jobs())
        req = dict(J.candle_jobs()[0].body)["req"]
        self.assertGreater(req["endTime"], 4e12)

    def test_job_names_are_unique(self):
        names = [j.name for j in J.all_jobs() + J.candle_jobs()]
        self.assertEqual(len(names), len(set(names)))

    def test_status_flags_jobs_that_never_ran(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(R.cmd_status(self.arc), 1)


if __name__ == "__main__":
    unittest.main()
