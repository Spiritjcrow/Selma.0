"""HTTP authentication regression for Selma Universal Files."""
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class FileServerAuthenticationTests(unittest.TestCase):
    def test_directory_listing_requires_session_token(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        with tempfile.TemporaryDirectory() as root:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(PROJECT / "tools" / "selma_files_server.py"),
                    "--root",
                    root,
                    "--port",
                    str(port),
                ],
                cwd=PROJECT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            def stop_server():
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
                if process.stderr is not None:
                    process.stderr.close()

            self.addCleanup(stop_server)
            session_url = f"http://127.0.0.1:{port}/api/session"
            for _ in range(50):
                try:
                    with urllib.request.urlopen(session_url, timeout=0.2) as response:
                        token = json.load(response)["token"]
                    break
                except (OSError, urllib.error.URLError):
                    if process.poll() is not None:
                        self.fail(process.stderr.read().decode("utf-8", "replace"))
                    time.sleep(0.02)
            else:
                self.fail("file server did not start")

            list_url = f"http://127.0.0.1:{port}/api/list"
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(list_url, timeout=1)
            self.assertEqual(403, denied.exception.code)

            request = urllib.request.Request(
                list_url,
                headers={"X-Selma-Token": token},
            )
            with urllib.request.urlopen(request, timeout=1) as response:
                self.assertEqual(200, response.status)


if __name__ == "__main__":
    unittest.main()
