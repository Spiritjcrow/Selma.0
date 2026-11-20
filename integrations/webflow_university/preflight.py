"""Offline preflight: checks runtime dependencies, SQLite FTS5, source syntax and tests."""
import importlib.util,sqlite3,subprocess,sys,compileall
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    required=("mcp","fastapi","uvicorn","httpx","bs4","pydantic")
    missing=[x for x in required if importlib.util.find_spec(x) is None]
    if missing:
        print("BLOCKED: missing dependencies: "+", ".join(missing))
        return 2
    with sqlite3.connect(":memory:") as c:
        try: c.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content)")
        except sqlite3.OperationalError as exc:
            print("BLOCKED: SQLite FTS5 unavailable:",exc);return 2
    if not compileall.compile_dir(str(ROOT),quiet=1):
        print("FAIL: Python compilation");return 1
    print("PASS: dependencies, FTS5 and compilation")
    result=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],cwd=ROOT,check=False)
    print("PASS: offline tests" if result.returncode==0 else "FAIL: offline tests")
    return result.returncode
if __name__=="__main__":raise SystemExit(main())
