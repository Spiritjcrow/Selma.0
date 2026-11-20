"""Offline smoke tests for Webflow connector."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import webflow_university_connector as w
class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        w.DB_PATH=str(Path(self.tmp.name)/"catalog.db")
    def tearDown(self): self.tmp.cleanup()
    def test_url_restriction(self):
        for url in ["https://university.webflow.com.evil.test/courses/x","http://university.webflow.com/courses/x","https://evil.test/courses/x"]:
            with self.assertRaises(ValueError): w.canonical_url(url,course=True)
    def test_parse_and_search(self):
        html='<a href="/courses/cms"><h2>CMS Basics</h2>Beginner 46m</a>'
        with patch.object(w,"fetch_html",return_value=html):
            self.assertEqual(w.sync_catalog_from_web()["courses_indexed"],1)
        self.assertEqual(len(w.query_courses("CMS Basics")),1)
        self.assertEqual(len(w.query_courses("CMS",level="Advanced")),0)
    def test_empty_sync_preserves_cache(self):
        with patch.object(w,"fetch_html",return_value='<a href="/courses/cms"><h2>CMS Basics</h2></a>'):
            w.sync_catalog_from_web()
        with patch.object(w,"fetch_html",return_value="<html></html>"):
            with self.assertRaises(ValueError): w.sync_catalog_from_web()
        self.assertEqual(len(w.query_courses("CMS")),1)
    def test_auth(self):
        from fastapi.testclient import TestClient
        client=TestClient(w.app)
        self.assertEqual(client.post("/v1/search",json={}).status_code,401)
        with patch.dict(os.environ,{"CONNECTOR_BEARER_TOKEN":"test-only-secret"}):
            self.assertEqual(client.post("/v1/search",headers={"Authorization":"Bearer test-only-secret"},json={}).status_code,200)
if __name__=="__main__": unittest.main()
