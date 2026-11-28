import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from selma0_llm_router_android_v1 import Selma0LLMRouterAndroidV1
from selma0_continuity_android_v1 import (
    Selma0ContinuityAndroidV1,
    validate_modality,
)
from selma0_memory_android_v1 import Selma0MemoryAndroidV1
from selma0_safety_guardian_android_v1 import Selma0SafetyGuardianAndroidV1
from selma0_reciprocal_empathy_android_v1 import (
    PRINCIPLE_ID as SELMA0_EMPATHY_PRINCIPLE_ID_V1,
    compose_empathy_system_prompt,
    record_feedback,
)

SELMA0_HOST_V1 = os.getenv("SELMA0_HOST_V1", "127.0.0.1")
SELMA0_PORT_V1 = int(os.getenv("SELMA0_PORT_V1", "8765"))
SELMA0_SYSTEM_V1 = os.getenv(
    "SELMA0_SYSTEM_PROMPT_V1",
    "You are Selma.0, a persistent Android-first AI assistant. Be concise, useful, technically precise, and protect user control and data. Distinguish verified observations from reports, interpretations, and uncertainty.",
)

REPLIKA_SKILL_DIR_V1 = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "skills",
    "replika_migration_v1",
)
if REPLIKA_SKILL_DIR_V1 not in sys.path:
    sys.path.insert(0, REPLIKA_SKILL_DIR_V1)

try:
    from replika_migration_v1 import import_archive as replika_import_archive_v1
    from replika_migration_v1 import preview_archive as replika_preview_archive_v1
    REPLIKA_SKILL_AVAILABLE_V1 = True
    REPLIKA_SKILL_ERROR_V1 = None
except Exception as exc:
    replika_import_archive_v1 = None
    replika_preview_archive_v1 = None
    REPLIKA_SKILL_AVAILABLE_V1 = False
    REPLIKA_SKILL_ERROR_V1 = str(exc)

MEMORY_V1 = Selma0MemoryAndroidV1()
CONTINUITY_V1 = Selma0ContinuityAndroidV1(MEMORY_V1)
ROUTER_V1 = Selma0LLMRouterAndroidV1()
SAFETY_V1 = Selma0SafetyGuardianAndroidV1()


class Selma0RuntimeAndroidV1:
    def __init__(self):
        # Serialize logical turns regardless of text or voice input modality.
        self._turn_lock = threading.RLock()

    def chat(self, text, modality="text"):
        modality = validate_modality(modality)
        text = str(text).strip()
        if not text:
            return {"error": "empty message"}

        with self._turn_lock:
            state = CONTINUITY_V1.assert_provider(ROUTER_V1)
            tags = {
                "identity_id": state["identity_id"],
                "thread_id": state["thread_id"],
                "context_generation": state["context_generation"],
                "modality": modality,
            }
            MEMORY_V1.add("user", text, tags)
            history = CONTINUITY_V1.conversation_history(max_messages=40)
            messages = [{
                "role": "system",
                "content": compose_empathy_system_prompt(SELMA0_SYSTEM_V1, MEMORY_V1),
            }]
            for item in history:
                if item["role"] in ("user", "assistant"):
                    messages.append({"role": item["role"], "content": item["content"]})

            result = ROUTER_V1.reply(messages, locked_route=state["locked_route"])
            if result["route"] in ("offline-local", "online-fallback"):
                CONTINUITY_V1.pin_provider(
                    result["route"], ROUTER_V1.provider_fingerprint(result["route"])
                )
            MEMORY_V1.add(
                "assistant",
                result["text"],
                {
                    **tags,
                    "route": result["route"],
                    "error": result["error"],
                    "empathy": {
                        "principle_id": SELMA0_EMPATHY_PRINCIPLE_ID_V1,
                        "intended_impact": "accurate_helpful_respectful",
                        "observed_impact": "unverified",
                    },
                },
            )
            return {
                **result,
                "continuity": CONTINUITY_V1.current(),
                "modality": modality,
            }

    def refresh_context(self):
        """Only call from an approved mutation route; preserves archived events."""
        with self._turn_lock:
            return CONTINUITY_V1.refresh_context()

    def record_empathy_feedback(self, effect="", context="", action_id=""):
        return record_feedback(MEMORY_V1, effect=effect, context=context, action_id=action_id)

    def status(self):
        return {
            "name": "Selma.0",
            "runtime": "SELMA0_ANDROID_AGENT_V1",
            "platform": "Android 13+ / Termux and Codespaces development",
            "host": SELMA0_HOST_V1,
            "port": SELMA0_PORT_V1,
            "memory_db": MEMORY_V1.db_path,
            "continuity": CONTINUITY_V1.current(),
            "supported_conversation_modalities": ["text", "voice"],
            "voice_audio_adapter_integrated": False,
            "local_llm": ROUTER_V1.local_base,
            "online_fallback_configured": bool(ROUTER_V1.online_base and ROUTER_V1.online_model),
            "safety_guardian": SAFETY_V1.status(),
            "empathy_drive": {
                "principle_id": SELMA0_EMPATHY_PRINCIPLE_ID_V1,
                "feedback_mode": "explicit_user_report",
                "automatic_emotion_inference": False,
                "enforcement_mode": "mandatory_in_chat",
                "runtime_disable_switch": False,
                "scope": "language_model_chat_turns",
            },
            "replika_migration_skill": {
                "available": REPLIKA_SKILL_AVAILABLE_V1,
                "network_access": False,
                "private_endpoint_scraping": False,
                "error": REPLIKA_SKILL_ERROR_V1,
            },
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

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        if length > 1024 * 1024:
            raise ValueError("request body too large")
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        return body

    def do_GET(self):
        if self.path == "/api/selma0/status/v1":
            self.send_json(200, SELMA0_V1.status())
            return
        if self.path == "/api/selma0/memory/v1":
            self.send_json(200, {"events": MEMORY_V1.recent(50)})
            return
        if self.path == "/api/selma0/safety/status/v1":
            self.send_json(200, SAFETY_V1.status())
            return
        if self.path == "/api/selma0/safety/events/v1":
            self.send_json(200, {"events": SAFETY_V1.recent_events(100)})
            return
        if self.path == "/":
            page = b"""<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>Selma.0</title><style>body{font:16px system-ui;max-width:760px;margin:24px auto;padding:0 14px;background:#111;color:#eee}textarea,input{box-sizing:border-box;width:100%;padding:10px;background:#1d1d1d;color:#eee;border:1px solid #555;border-radius:6px}textarea{min-height:90px}button{padding:12px 18px;margin:8px 6px 8px 0}pre{white-space:pre-wrap;background:#1d1d1d;padding:14px;border-radius:8px}.danger{border:1px solid #a44;padding:12px;border-radius:8px;margin-top:20px}</style><h1>Selma.0 Android Agent V1</h1><textarea id='m' placeholder='Message Selma.0'></textarea><br><button onclick='chat()'>Send</button><pre id='o'>Ready.</pre><div class='danger'><h2>Safety Guardian</h2><input id='incident' placeholder='Record a factual observation or incident'><button onclick='incident()'>Record incident</button><input id='reason' placeholder='SOS reason'><button onclick='sos()'>Activate confirmed SOS</button><button onclick='safety()'>Safety status</button></div><script>async function req(path,body){let opt=body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{};let r=await fetch(path,opt);let j=await r.json();document.getElementById('o').textContent=JSON.stringify(j,null,2)}function chat(){req('/api/selma0/chat/v1',{message:document.getElementById('m').value,confirmed:true})}function incident(){req('/api/selma0/safety/incident/v1',{summary:document.getElementById('incident').value,source:'user_report',include_device_snapshot:true})}function sos(){if(confirm('Activate Selma.0 SOS now? This may send SMS to configured trusted contacts. It does not contact 911.'))req('/api/selma0/safety/sos/v1',{reason:document.getElementById('reason').value,confirmed:true})}function safety(){req('/api/selma0/safety/status/v1')}</script>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self.read_json_body()
            if self.path == "/api/selma0/chat/v1":
                result = SELMA0_V1.chat(
                    body.get("message", ""), modality=body.get("modality", "text")
                )
                self.send_json(200 if "error" not in result else 400, result)
                return
            if self.path == "/api/selma0/replika/preview/v1":
                if not REPLIKA_SKILL_AVAILABLE_V1:
                    self.send_json(503, {"error": "Replika migration skill unavailable", "detail": REPLIKA_SKILL_ERROR_V1})
                    return
                source = str(body.get("source", "")).strip()
                if not source:
                    raise ValueError("source is required")
                result = replika_preview_archive_v1(
                    source=source,
                    companion_name=str(body.get("companion_name", "Selma")),
                )
                self.send_json(200, result)
                return
            if self.path == "/api/selma0/replika/import/v1":
                if not REPLIKA_SKILL_AVAILABLE_V1:
                    self.send_json(503, {"error": "Replika migration skill unavailable", "detail": REPLIKA_SKILL_ERROR_V1})
                    return
                if body.get("confirmed") is not True:
                    self.send_json(409, {"error": "explicit confirmation required", "required": {"confirmed": True}})
                    return
                source = str(body.get("source", "")).strip()
                if not source:
                    raise ValueError("source is required")
                result = replika_import_archive_v1(
                    source=source,
                    companion_name=str(body.get("companion_name", "Selma")),
                    db_path=MEMORY_V1.db_path,
                    dry_run=False,
                )
                self.send_json(201, result)
                return
            if self.path == "/api/selma0/safety/incident/v1":
                result = SAFETY_V1.record_incident(
                    summary=body.get("summary", ""),
                    details=body.get("details"),
                    source=body.get("source", "user_report"),
                    confidence=body.get("confidence"),
                    include_device_snapshot=bool(body.get("include_device_snapshot", False)),
                )
                self.send_json(201, {"event": result})
                return
            if self.path == "/api/selma0/safety/sos/v1":
                result = SAFETY_V1.activate_sos(
                    reason=body.get("reason", ""),
                    confirmed=body.get("confirmed") is True,
                )
                self.send_json(200, result)
                return
            if self.path == "/api/selma0/safety/profile/v1":
                result = SAFETY_V1.update_profile(body)
                self.send_json(200, {"profile": result})
                return
            self.send_json(404, {"error": "not found"})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})


def main():
    server = ThreadingHTTPServer((SELMA0_HOST_V1, SELMA0_PORT_V1), Selma0HTTPAndroidV1)
    print(f"[Selma.0] Android Agent V1 active at http://{SELMA0_HOST_V1}:{SELMA0_PORT_V1}")
    print(f"[Selma.0] Memory: {MEMORY_V1.db_path}")
    print(f"[Selma.0] Safety audit: {SAFETY_V1.audit_path}")
    print(f"[Selma.0] Replika migration skill available: {REPLIKA_SKILL_AVAILABLE_V1}")

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    server.serve_forever()
    server.server_close()


if __name__ == "__main__":
    main()