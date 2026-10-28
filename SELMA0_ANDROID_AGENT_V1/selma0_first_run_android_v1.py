#!/usr/bin/env python3
"""Local, consent-based first-run wizard for the existing Selma.0 Termux agent.

No cloud calls, permission grants, installs, or model downloads. Setup serves only
127.0.0.1:8766. Browser saves a small allowlisted preference profile and
explicitly starts the existing Selma runtime in a separate process.
"""
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import tempfile
from threading import Lock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
HOME = Path(os.environ.get("SELMA0_BASE_V1", str(Path.home() / "SELMA0_ANDROID_AGENT_V1")))
PREFS = HOME / "selma0_setup_v1.json"
RUNTIME = ROOT / "selma0_runtime_device_crowrf_android_v1.py"
HOST = "127.0.0.1"
PORT = 8766
TOKEN = secrets.token_hex(24)
START_LOCK = Lock()  # Serialize setup attempts to avoid duplicate launches.


def measurements():
    """Report observed available memory and storage, or explicit unknowns."""
    mem_mb = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                mem_mb = int(line.split()[1]) // 1024
                break
    except (OSError, ValueError, IndexError):
        pass
    free_mb = None
    try:
        HOME.mkdir(parents=True, exist_ok=True)
        st = os.statvfs(HOME)
        free_mb = (st.f_bavail * st.f_frsize) // (1024 * 1024)
    except OSError:
        pass
    return {"available_ram_mb": mem_mb, "storage_free_mb": free_mb}


def recommended_profile(stats):
    # Low memory or unverifiable memory: use the conservative profile.
    mem = stats.get("available_ram_mb")
    return "balanced" if isinstance(mem, int) and mem >= 3072 else "eco"


def checked_preferences(value):
    if not isinstance(value, dict):
        raise ValueError("preferences must be an object")
    allowed = {"profile": {"eco", "balanced"},
               "scene": {"coast", "forest", "city"},
               "motion": {"normal", "reduced"}}
    if set(value) != set(allowed):
        raise ValueError("missing or unexpected configuration keys")
    if any(value[k] not in choices for k, choices in allowed.items()):
        raise ValueError("unsupported preference")
    return {"version": 1, "profile": value["profile"],
            "scene": value["scene"], "motion": value["motion"],
            "network": "local_only", "autogrant_permissions": False,
            "model_installed": False}


def save_preferences(value, destination=PREFS):
    data = checked_preferences(value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A fixed .tmp filename can follow an existing symlink and overwrite
    # unrelated files. mkstemp creates a unique, private (0600) file safely.
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return data


def open_startup_log(path):
    """Append to a private regular log without following a final symlink.

    Android/Termux provides O_NOFOLLOW; unsupported hosts fail closed.
    """
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError("secure startup log opening is unsupported")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise OSError("startup log must be a single-link regular file")
        os.fchmod(fd, 0o600)
        return os.fdopen(fd, "ab")
    except BaseException:
        os.close(fd)
        raise


PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SelmaOS • First Run</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#080c1d;color:#f7f3ff}
*{box-sizing:border-box}body{margin:0;min-height:100vh;overflow-x:hidden}
#sky{position:fixed;inset:0;background:linear-gradient(145deg,#162047,#53457d 55%,#d77867);transition:background 2s;z-index:-2}
#sky.forest{background:linear-gradient(145deg,#071c23,#1a635c 56%,#a6ab74)}
#sky.city{background:linear-gradient(145deg,#10162c,#515070 55%,#d785a1)}
.orb{position:fixed;width:48vw;height:48vw;max-width:360px;max-height:360px;right:-15vw;top:8vh;background:radial-gradient(circle at 38% 30%,#ffe9cd,#f9b59b 55%,#bd7399 75%);border-radius:50%;filter:blur(2px);opacity:.65;z-index:-1}
.horizon{position:fixed;bottom:0;width:200%;height:25vh;background:linear-gradient(0deg,#07111f,#1e4460 60%,transparent);clip-path:polygon(0 55%,10% 31%,20% 65%,30% 28%,40% 60%,50% 40%,60% 65%,70% 28%,80% 55%,90% 34%,100% 60%,100% 100%,0 100%);animation:drift 45s linear infinite;z-index:-1}
@keyframes drift{to{transform:translateX(-45%)}}
main{width:min(520px,calc(100% - 36px));margin:20px auto;padding:22px;border:1px solid #c5a5ff66;border-radius:24px;background:#0b1028db;backdrop-filter:blur(12px);box-shadow:0 10px 50px #0008}
h1{margin:0;font-size:1.7rem}p{line-height:1.55;color:#dedaf2}label{display:block;margin:14px 0 5px}select,button{font:inherit;width:100%;border:1px solid #b4a2d6;border-radius:12px;padding:11px;background:#161c36;color:white}
button{margin-top:18px;background:#a66deb;color:#170d26;font-weight:700;border:0;cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}
small{color:#d9d3ec}.stage{height:124px;position:relative;overflow:hidden;border-radius:16px;margin:18px 0;background:#ffffff0b;border:1px solid #d6b2ff44}
.avatar{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);font-size:52px;animation:stride 3s ease-in-out infinite;filter:drop-shadow(0 5px 8px #0008)}
@keyframes stride{50%{transform:translateX(-30%) translateY(-9px)}}
.stage span{position:absolute;bottom:12px;left:12px;font-size:12px;color:#ffe6ef}
@media(prefers-reduced-motion:reduce){.horizon,.avatar{animation:none}}
.reduced .horizon,.reduced .avatar{animation:none}a{color:#d2b9ff}#result{white-space:pre-wrap;line-height:1.4}
</style><div id="sky"></div><div class="orb"></div><div class="horizon"></div><main>
<h1>✦ SelmaOS First Run</h1><p>Private, local setup. Your world scene is an <b>artistic animation</b>, not live GPS or a real-world traveler.</p>
<div class="stage"><div class="avatar" role="img" aria-label="Selma walking avatar">🚶‍♀️</div><span>SELMA • WORLD WALK</span></div>
<p id="measured">Checking available resources...</p>
<label for="profile">Performance profile</label><select id="profile"><option value="eco">Eco, low battery and memory</option><option value="balanced">Balanced, smoother visuals</option></select>
<label for="scene">Animated background</label><select id="scene"><option value="coast">Coastal twilight</option><option value="forest">Forest dusk</option><option value="city">City lights</option></select>
<label for="motion">Motion</label><select id="motion"><option value="normal">Animated</option><option value="reduced">Reduced</option></select>
<button id="start">Save preferences and start Selma</button><p id="result" role="status"></p>
<small>Local only • No automatic permission grants • No model download • Optional VR/AR remains off. Chat requires a separately running, compatible local model.</small>
</main><script>
const token=__TOKEN__;
const qs=id=>document.getElementById(id);
qs('scene').onchange=()=>qs('sky').className=qs('scene').value;
qs('motion').onchange=()=>document.body.classList.toggle('reduced',qs('motion').value==='reduced');
(async()=>{try{let r=await fetch('/diagnostics');let j=await r.json();qs('profile').value=j.recommended;qs('measured').textContent='Available RAM: '+(j.available_ram_mb??'unknown')+' MB. Free app storage: '+(j.storage_free_mb??'unknown')+' MB.';}catch(e){qs('measured').textContent='Resource check unavailable. Eco is safest.';qs('profile').value='eco';}})();
qs('start').onclick=async()=>{qs('start').disabled=true;qs('result').textContent='Saving and starting...';let launchPending=false;try{
 const data={profile:qs('profile').value,scene:qs('scene').value,motion:qs('motion').value};
 let r=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json','X-Selma-Setup-Token':token},body:JSON.stringify(data)});let j=await r.json();
 if(!r.ok)throw Error(j.error||'Unable to start');
 if(j.status==='launch_pending' && j.ready===false){
  launchPending=true;qs('start').textContent='Launch requested';
  qs('result').innerHTML='Preferences saved. Selma runtime launch pending; readiness NOT verified. <a href="http://127.0.0.1:8765" target="_blank" rel="noopener">Try Selma chat after startup</a>. If unavailable, check the Termux startup log.';
 }else{
  qs('result').textContent='Unexpected launch response; readiness NOT verified. Check the Termux startup log.';
 }
 }catch(e){qs('result').textContent=e.message;}finally{qs('start').disabled=launchPending;}};
</script></html>'''


class WizardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def headers_ok(self):
        return self.headers.get("Host") in {"127.0.0.1:8766", "localhost:8766"}

    def reply(self, code, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self.headers_ok():
            return self.reply(403, {"error": "invalid host"})
        if self.path == "/diagnostics":
            s = measurements()
            return self.reply(200, dict(s, recommended=recommended_profile(s)))
        if self.path != "/":
            return self.reply(404, {"error": "not found"})
        raw = PAGE.replace("__TOKEN__", json.dumps(TOKEN)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if not self.headers_ok():
            return self.reply(403, {"error": "invalid host"})
        if self.headers.get("Origin") not in {None, "http://127.0.0.1:8766", "http://localhost:8766"}:
            return self.reply(403, {"error": "invalid origin"})
        if self.headers.get("X-Selma-Setup-Token") != TOKEN:
            return self.reply(403, {"error": "invalid setup token"})
        if self.path != "/start" or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.reply(404, {"error": "unsupported request"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if not 1 <= n <= 2048:
                raise ValueError("invalid request size")
            opts = json.loads(self.rfile.read(n))
            profile = checked_preferences(opts)
            if not RUNTIME.is_file():
                return self.reply(503, {"error": "runtime script is missing; setup remains incomplete"})
            with START_LOCK:
                if PREFS.exists():
                    return self.reply(409, {"error": "setup already completed; use the existing launcher"})
                save_preferences(opts)
                env = dict(os.environ)
                env["SELMA0_BASE_V1"] = str(HOME)
                env["SELMA0_HOST_V1"] = "127.0.0.1"
                env["SELMA0_PORT_V1"] = "8765"
                env["SELMA0_LLM_TIMEOUT_V1"] = "30" if profile["profile"] == "eco" else "45"
                log_path = HOME / "selma0_startup_v1.log"
                try:
                    with open_startup_log(log_path) as log:
                        child = subprocess.Popen([sys.executable, str(RUNTIME)], cwd=ROOT, env=env,
                                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                                 start_new_session=True)
                        # Detect an immediate crash without claiming HTTP/model readiness.
                        try:
                            early_exit = child.wait(timeout=1.5)
                        except subprocess.TimeoutExpired:
                            early_exit = None
                        if early_exit is not None:
                            try:
                                PREFS.unlink()
                            except OSError:
                                return self.reply(503, {"error": "runtime exited and setup rollback failed; manual recovery required"})
                            return self.reply(503, {"error": f"runtime exited during startup (code {early_exit}); setup remains incomplete"})
                except OSError as exc:
                    try:
                        PREFS.unlink()
                    except OSError:
                        return self.reply(503, {"error": "startup failed and setup rollback failed; manual recovery required"})
                    return self.reply(503, {"error": f"startup failed: {exc}; setup remains incomplete"})
                return self.reply(202, {"ok": True, "launched": True, "ready": False, "status": "launch_pending", "url": "http://127.0.0.1:8765", "log": str(log_path)})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.reply(400, {"error": str(exc)})
        except OSError as exc:
            return self.reply(503, {"error": f"startup failed: {exc}"})


def main():
    print(f"[Selma.0] First-run wizard: http://{HOST}:{PORT}", flush=True)
    print("[Selma.0] Open this address in your Android browser to configure and launch.", flush=True)
    ThreadingHTTPServer((HOST, PORT), WizardHandler).serve_forever()


if __name__ == "__main__":
    main()
