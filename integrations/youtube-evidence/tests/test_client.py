"""Offline validation; no Google credentials needed."""
import io
import unittest
from unittest.mock import patch
from youtube_client import parse_id, watch_link, search, details, evidence_checklist, google_get

class Tests(unittest.TestCase):
    def test_ids(self):
        vid="dQw4w9WgXcQ"
        self.assertEqual(parse_id("https://youtu.be/"+vid),vid)
        self.assertEqual(parse_id("https://www.youtube.com/watch?v="+vid),vid)
        self.assertIn("&t=12s",watch_link(vid,12))
    def test_parse_id_rejects_ambiguous_urls_and_input_types(self):
        vid = "dQw4w9WgXcQ"
        invalid = (
            None, 123, [], "x" * 2049,
            f"https://youtube.com:0/watch?v={vid}",
            f"https://youtube.com:/watch?v={vid}",
            f"https://youtube.com/watch?v={vid}&v=aaaaaaaaaaa",
            f"https://youtube.com/watch?v={vid}&v=",
            f"https://[youtube.com/watch?v={vid}",
        )
        for value in invalid:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    parse_id(value)

    def test_parse_id_rejects_embedded_controls_stripped_by_urlparse(self):
        vid = "dQw4w9WgXcQ"
        malformed = (
            f"https://www.youtube.com/\twatch?v={vid}",
            f"https://www.youtube.com/wa\ntch?v={vid}",
            f"https://youtu.be/{vid[:4]}\r{vid[4:]}",
        )
        for value in malformed:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    parse_id(value)
        # Ordinary whitespace around a pasted link remains supported.
        self.assertEqual(vid, parse_id(f" \nhttps://youtu.be/{vid}\n "))

    def test_parse_id_keeps_supported_https_forms(self):
        vid = "dQw4w9WgXcQ"
        valid = (
            vid, f"https://youtu.be/{vid}",
            f"https://WWW.YOUTUBE.COM/watch?v={vid}",
            f"https://youtube.com/shorts/{vid}",
            f"https://youtube.com/embed/{vid}",
            f"https://youtube.com/live/{vid}",
        )
        for value in valid:
            with self.subTest(value=value):
                self.assertEqual(vid, parse_id(value))

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
    def test_google_get_rejects_duplicate_json_keys_at_any_depth(self):
        payloads = (
            b'{"items":[{"id":"A"}],"items":[]}',
            b'{"items":[{"id":{"videoId":"A","videoId":"B"}}]}',
            b'{"error":{"code":403},"error":null,"items":[]}',
        )
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "fixture-only-key"}):
            for payload in payloads:
                with self.subTest(payload=payload):
                    def opener(url, timeout):
                        self.assertEqual(timeout, 15)
                        return io.BytesIO(payload)
                    with self.assertRaisesRegex(RuntimeError, "YouTube API request failed: ValueError"):
                        google_get("search", {"q": "fixture"}, opener=opener)

    def test_google_get_retains_valid_nested_json(self):
        payload = b'{"items":[{"id":{"videoId":"dQw4w9WgXcQ"}}]}'
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "fixture-only-key"}):
            result = google_get("search", {"q": "fixture"},
                                opener=lambda url, timeout: io.BytesIO(payload))
        self.assertEqual(result["items"][0]["id"]["videoId"], "dQw4w9WgXcQ")

    def test_search(self):
        def mock(endpoint,params): return {"items":[{"id":{"videoId":"dQw4w9WgXcQ"},"snippet":{"title":"Sample"}}]}
        self.assertEqual(search("subwoofer",get=mock)[0]["title"],"Sample")
    def test_search_rejects_bad_input_before_network(self):
        def no_network(*args):
            self.fail("invalid search input must not reach the API")
        for query, limit in ((None, 1), ([], 1), ("   ", 1),
                             ("ok", True), ("ok", 1.5), ("ok", "2"),
                             ("ok", 0), ("ok", 26)):
            with self.subTest(query=repr(query), limit=repr(limit)):
                with self.assertRaises(ValueError):
                    search(query, limit, get=no_network)

    def test_search_malformed_response_fails_closed(self):
        for response in (None, [], {}, {"error": {"message": "synthetic"}},
                         {"items": None}, {"items": {}}, {"items": "oops"}):
            with self.subTest(response=repr(response)):
                with self.assertRaisesRegex(RuntimeError, "Unexpected YouTube search response"):
                    search("fixture", get=lambda *args: response)

    def test_search_rejects_error_envelope_even_with_items(self):
        for payload in ({"error": {"code": 403}, "items": []},
                        {"error": None, "items": []}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(RuntimeError, "Unexpected YouTube search response"):
                    search("fixture", get=lambda *args: payload)

    def test_search_skips_malformed_entries_without_crashing(self):
        vid = "dQw4w9WgXcQ"
        entries = [None, "bad", {"id": None}, {"id": {"videoId": None}},
                   {"id": {"videoId": vid}, "snippet": None},
                   {"id": {"videoId": vid}, "snippet": {"description": None}},
                   {"id": {"videoId": vid}, "snippet": {"title": "valid"}}]
        result = search("fixture", get=lambda *args: {"items": entries})
        self.assertEqual(1, len(result))
        self.assertEqual("valid", result[0]["title"])
        self.assertEqual(vid, result[0]["video_id"])

    def test_search_retains_bounded_valid_description(self):
        vid = "dQw4w9WgXcQ"
        result = search("fixture", get=lambda *args: {"items": [
            {"id": {"videoId": vid}, "snippet": {"description": "x" * 600}}]})
        self.assertEqual(500, len(result[0]["description_excerpt"]))

    def test_details(self):
        def mock(endpoint,params): return {"items":[{"id":"dQw4w9WgXcQ","snippet":{"title":"Sample"}}]}
        self.assertIn("metadata only",details("dQw4w9WgXcQ",get=mock)["inspection_status"])
    def test_details_empty_items_is_not_found(self):
        result = details("dQw4w9WgXcQ", get=lambda *args: {"items": []})
        self.assertEqual({"found": False, "video_id": "dQw4w9WgXcQ", "watch_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}, result)
    def test_details_malformed_top_level_fails_closed(self):
        for response in (None, [], {}, {"error": {"message": "synthetic"}},
                         {"items": None}, {"items": {}}, {"items": "oops"}):
            with self.subTest(response=repr(response)):
                with self.assertRaisesRegex(RuntimeError, "Unexpected YouTube details response"):
                    details("dQw4w9WgXcQ", get=lambda *args: response)
    def test_details_rejects_error_envelope_even_with_items(self):
        for payload in ({"error": {"code": 403}, "items": []},
                        {"error": None, "items": []}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(RuntimeError, "Unexpected YouTube details response"):
                    details("dQw4w9WgXcQ", get=lambda *args: payload)

    def test_details_rejects_ambiguous_multiple_items(self):
        vid = "dQw4w9WgXcQ"
        for items in (
            [{"id": vid}, {"id": vid}],
            [{"id": vid}, {"id": "AAAAAAAAAAA"}],
            [{"id": "AAAAAAAAAAA"}, {"id": vid}],
        ):
            with self.subTest(items=items):
                with self.assertRaisesRegex(RuntimeError, "Unexpected YouTube details response"):
                    details(vid, get=lambda *args: {"items": items})

    def test_details_malformed_item_or_mismatched_id_fails_closed(self):
        for item in (None, "bad", {}, {"id": None}, {"id": "x" * 11},
                     {"id": "dQw4w9WgXcQ", "snippet": None},
                     {"id": "dQw4w9WgXcQ", "contentDetails": []},
                     {"id": "dQw4w9WgXcQ", "statistics": "bad"}):
            with self.subTest(item=repr(item)):
                with self.assertRaisesRegex(RuntimeError, "Unexpected YouTube details response"):
                    details("dQw4w9WgXcQ", get=lambda *args: {"items": [item]})
    def test_details_malformed_field_types_fails_closed(self):
        for item in ({"snippet": {"title": None}}, {"snippet": {"description": []}},
                     {"contentDetails": {"duration": 123}}, {"statistics": {"viewCount": 123}}):
            with self.subTest(item=repr(item)):
                with self.assertRaisesRegex(RuntimeError, "Unexpected YouTube details response"):
                    details("dQw4w9WgXcQ", get=lambda *args: {"items": [{"id": "dQw4w9WgXcQ", **item}]})
    def test_details_retains_bounded_valid_metadata(self):
        result = details("dQw4w9WgXcQ", get=lambda *args: {"items": [{"id": "dQw4w9WgXcQ", "snippet": {"description": "x" * 3500}, "contentDetails": {"duration": "PT1M"}, "statistics": {"viewCount": "123"}}]})
        self.assertEqual(3000, len(result["description"]))
        self.assertEqual("123", result["view_count"])
        self.assertEqual("PT1M", result["duration"])
    def test_checklist(self):
        self.assertEqual(evidence_checklist("dQw4w9WgXcQ")["status"],"unverified")

if __name__=="__main__": unittest.main()
