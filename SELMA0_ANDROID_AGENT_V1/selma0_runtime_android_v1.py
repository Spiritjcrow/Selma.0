import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from selma0_llm_router_android_v1 import Selma0LLMRouterAndroidV1
from selma0_memory_android_v1 import Selma0MemoryAndroidV1

SELMA0_HOST_V1 = os.getenv("SELMA0_HOST_V1", "127.0.0.1")
SELMA0_PORT_V1 = int(os.getenv("SELMA0_PORT_V1", "8765"))
SELMA0_SYSTEM_V1 = os.getenv(
    "SELMA0_SYSTEM_PROMPT_V1",
    "You are Selma.0, a persistent Android-first AI assistant. Be concise, useful, technically precise, and protect user control and data.",
)

MEMORY_V1 = Selma0MemoryAndroidV1()
ROUTER_V1 = Selma0LLMRouterAndroidV1()


class Selma0RuntimeAndroidV1:
    def chat(self, text):
        text = str(text).strip()
        if not text:
            return {"error": "empty message"}

        MEMORY_V1.add("user", text)
        history = MEMORY_V1.recent(20)
        messages = [{"role": "system", "content": SELMA0_SYSTEM_V1}]
        for item in history:
            if item["role"] in ("user", "assistant"):
                messages.append({"role": item["role"], "content": item["content"]})

        result = ROUTER_V1.reply(messages)
        MEMORY_V1.add("assistant", result["text"], {"route": result["route"], "error": result["error"]})
        return result

    def status(self):
        return {
            "name": "Selma.0",
            "runtime": "SELMA0_ANDROID_AGENT_V1",
            "platform": "Android 13+ / Termux and Codespaces development",
            "host": SELMA0_HOST_V1,
            "port": SELMA0_PORT_V1,
            "memory_db": MEMORY_V1.db_path,
            "local_llm": ROUTER_V1.local_base,
            "online_fallback_configured": bool(ROUTER_V1.online_base and ROUTER_V1.online_model),
        }


SELMA0_V1 = Selma0RuntimeAndroidV1()


class Selma0HTTPAndroidV1(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def send_json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/api/selma0/status/v1":
            self.send_json(200, SELMA0_V1.status())
            return
        if self.path == "/api/selma0/memory/v1":
            self.send_json(200, {"events": MEMORY_V1.recent(50)})
            return
        if self.path == "/":
            page = b"""<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>Selma.0</title><style>body{font:16px system-ui;max-width:760px;margin:24px auto;padding:0 14px;background:#111;color:#eee}textarea{width:100%;min-height:90px}button{padding:12px 18px;margin-top:8px}pre{white-space:pre-wrap;background:#1d1d1d;padding:14px;border-radius:8px}</style><h1>Selma.0 Android Agent V1</h1><textarea id='m' placeholder='Message Selma.0'></textarea><br><button onclick='go()'>Send</button><pre id='o'>Ready.</pre><script>async function go(){let m=document.getElementById('m').value;let r=await fetch('/api/selma0/chat/v1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});document.getElementById('o').textContent=JSON.stringify(await r.json(),null,2)}</script>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/selma0/chat/v1":
            self.send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            result = SELMA0_V1.chat(body.get("message", ""))
            self.send_json(200 if "error" not in result else 400, result)
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})


def main():
    server = ThreadingHTTPServer((SELMA0_HOST_V1, SELMA0_PORT_V1), Selma0HTTPAndroidV1)
    print(f"[Selma.0] Android Agent V1 active at http://{SELMA0_HOST_V1}:{SELMA0_PORT_V1}")
    print(f"[Selma.0] Memory: {MEMORY_V1.db_path}")

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    server.serve_forever()
    server.server_close()


if __name__ == "__main__":
    main()
