"""Offline validation; no Google credentials needed."""
import unittest
from youtube_client import parse_id, watch_link, search, details, evidence_checklist

class Tests(unittest.TestCase):
    def test_ids(self):
        vid="dQw4w9WgXcQ"
        self.assertEqual(parse_id("https://youtu.be/"+vid),vid)
        self.assertEqual(parse_id("https://www.youtube.com/watch?v="+vid),vid)
        self.assertIn("&t=12s",watch_link(vid,12))
    def test_timestamp_rejects_noninteger(self):
        vid="dQw4w9WgXcQ"
        for value in (True, False, 1.5, "12", None, {}, []):
            with self.subTest(timestamp=repr(value)):
                with self.assertRaises(ValueError): watch_link(vid, value)
                with self.assertRaises(ValueError): evidence_checklist(vid, value)
    def test_timestamp_integer_bounds(self):
        vid="dQw4w9WgXcQ"
        self.assertEqual(watch_link(vid, 0), "https://www.youtube.com/watch?v="+vid)
        self.assertIn("&t=864000s", watch_link(vid, 864000))
        for value in (-1, 864001):
            with self.subTest(timestamp=value), self.assertRaises(ValueError):
                watch_link(vid, value)
    def test_bad_urls(self):
        for x in ("http://youtu.be/dQw4w9WgXcQ","https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ"):
            with self.assertRaises(ValueError): parse_id(x)
    def test_search(self):
        def mock(endpoint,params): return {"items":[{"id":{"videoId":"dQw4w9WgXcQ"},"snippet":{"title":"Sample"}}]}
        self.assertEqual(search("subwoofer",get=mock)[0]["title"],"Sample")
    def test_details(self):
        def mock(endpoint,params): return {"items":[{"snippet":{"title":"Sample"}}]}
        self.assertIn("metadata only",details("dQw4w9WgXcQ",get=mock)["inspection_status"])
    def test_checklist(self):
        self.assertEqual(evidence_checklist("dQw4w9WgXcQ")["status"],"unverified")

if __name__=="__main__": unittest.main()
