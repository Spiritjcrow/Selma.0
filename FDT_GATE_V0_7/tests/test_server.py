import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from fdt_gate.cli import init_workspace, load_gate
from fdt_gate.server import serve


class ServerBoundaryTests(unittest.TestCase):
    def test_bearer_principal_binding(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            info = init_workspace(root)
            (root / "workspace/hello.txt").write_text("hello\n", "utf-8")
            gate, token_map, _, _ = load_gate(root)
            s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
            t = threading.Thread(target=serve, args=(gate, token_map, "127.0.0.1", port), daemon=True)
            t.start()
            base = f"http://127.0.0.1:{port}"
            for _ in range(50):
                try:
                    urllib.request.urlopen(base + "/healthz", timeout=0.1)
                    break
                except Exception:
                    time.sleep(0.02)
            token = info["bearer_token"]
            action = {"actor":"local-agent","effect":"fs.read","resource":"workspace/hello.txt","method":"READ","payload":{}}
            req = urllib.request.Request(base + "/v1/authorize", data=json.dumps(action).encode(), method="POST",
                                         headers={"Content-Type":"application/json","Authorization":"Bearer " + token})
            receipt = json.load(urllib.request.urlopen(req, timeout=2))
            self.assertEqual(receipt["decision"], "ALLOW")
            action["actor"] = "forged-agent"
            req = urllib.request.Request(base + "/v1/authorize", data=json.dumps(action).encode(), method="POST",
                                         headers={"Content-Type":"application/json","Authorization":"Bearer " + token})
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=2)
            self.assertEqual(ctx.exception.code, 403)


if __name__ == "__main__": unittest.main()
