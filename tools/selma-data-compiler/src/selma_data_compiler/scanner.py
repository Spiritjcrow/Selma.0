from __future__ import annotations
import ast, hashlib, re
from pathlib import Path
from typing import Iterable
from .model import Artifact
from .rules import DOMAIN_RULES, PATH_PRIORITY, IGNORE_DIRS, TEXT_SUFFIXES

REF_RE = re.compile(r"(?:from|import|require\(|include|dependsOn|implementation|api|project\()[\s\"'(:=]+([A-Za-z0-9_./:@-]+)")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _read_text(path: Path, max_bytes: int = 2_000_000) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Makefile"}:
        return ""
    try:
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""

def _symbols(path: Path, text: str) -> list[str]:
    if path.suffix.lower() == ".py" and text:
        try:
            tree = ast.parse(text)
            out = [n.name for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
            return sorted(set(out))[:200]
        except SyntaxError:
            pass
    pat = re.compile(r"\b(?:class|fun|function|interface|object|def)\s+([A-Za-z_][A-Za-z0-9_]*)")
    return sorted(set(pat.findall(text)))[:200]

def _references(text: str) -> list[str]:
    return sorted(set(m.group(1) for m in REF_RE.finditer(text or "")))[:300]

def _kind(path: Path) -> str:
    name, suffix = path.name.lower(), path.suffix.lower()
    if name == "androidmanifest.xml": return "manifest"
    if suffix in {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".properties"}: return "config"
    if suffix in {".md", ".txt"}: return "document"
    if suffix in {".py", ".kt", ".kts", ".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".js", ".jsx", ".ts", ".tsx", ".sh", ".ps1", ".sql"}: return "source"
    if suffix in {".html", ".css", ".xml"}: return "ui-or-resource"
    if suffix in {".db", ".sqlite", ".sqlite3"}: return "database"
    if suffix in {".glb", ".gltf", ".png", ".jpg", ".jpeg", ".webp", ".svg"}: return "asset"
    return "binary-or-other"

def _state(path: Path, text: str, kind: str) -> str:
    low, n = (text or "").lower(), path.name.lower()
    if "generated" in low[:400] or n.endswith(".generated"): return "generated"
    if any(t in low for t in ("todo", "placeholder", "not implemented", "stub")): return "placeholder-or-partial"
    if kind == "document" and any(t in low for t in ("planned", "proposal", "roadmap", "future work")): return "planned"
    return "source-present"

def _authority(kind: str, state: str, path: Path, text: str) -> int:
    low = (text or "").lower()
    if "selma:canonical" in low: return 100
    if kind == "config": return 80
    if "runtime" in path.as_posix().lower() or kind == "database": return 75
    if kind == "source": return 70
    if kind == "manifest": return 68
    if kind == "ui-or-resource": return 60
    if kind == "document": return 40 if state != "planned" else 25
    if state == "generated": return 20
    return 30

def _domain(path: Path, text: str) -> tuple[str, float, str]:
    p = path.as_posix().lower()
    for domain, needles in PATH_PRIORITY:
        if any(n in p for n in needles):
            return domain, 0.99, f"path:{domain}"
    config_suffixes = {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".properties"}
    if path.suffix.lower() in config_suffixes and any(token in path.name.lower() for token in ("config", "settings", "preferences")):
        return "config", 0.99, "file-role:config"
    sample = (p + "\n" + (text or "")[:120_000]).lower()
    scores, matches = {}, {}
    for domain, needles in DOMAIN_RULES:
        hit = [n for n in needles if n in sample]
        if hit:
            scores[domain], matches[domain] = len(hit), hit
    if not scores: return "unknown", 0.30, "no-rule-match"
    domain = max(scores, key=lambda d: (scores[d], d != "docs", d != "config"))
    return domain, min(0.95, 0.55 + 0.08 * scores[domain]), "heuristic:" + ",".join(matches[domain][:5])

def scan_roots(roots: Iterable[Path]) -> list[Artifact]:
    artifacts = []
    for root in roots:
        root = root.expanduser().resolve()
        if not root.exists(): continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            try:
                if not path.is_file(): continue
                rel_parts = path.relative_to(root).parts if root.is_dir() else (path.name,)
                if any(part in IGNORE_DIRS for part in rel_parts): continue
                st, text, sha = path.stat(), _read_text(path), sha256_file(path)
                domain, confidence, reason = _domain(path, text)
                kind = _kind(path); state = _state(path, text, kind)
                rel = str(path.relative_to(root)) if root.is_dir() else path.name
                artifact_id = hashlib.sha256(f"{root}\0{rel}\0{sha}".encode()).hexdigest()[:24]
                artifacts.append(Artifact(artifact_id, str(path), str(root), rel, path.name, path.suffix.lower(), st.st_size, sha, st.st_mtime_ns, domain, kind, state, _authority(kind, state, path, text), confidence, reason, _symbols(path, text), _references(text), [], {}))
            except (OSError, ValueError):
                continue
    return artifacts
