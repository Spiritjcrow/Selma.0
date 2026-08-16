from __future__ import annotations

DOMAIN_RULES = [
    ("memory", ("memory", "rag", "fts5", "sqlite_vec", "sqlite-vec", "embedding")),
    ("voice", ("voice", "wakeword", "wake_word", "vosk", "whisper", "piper", "tts", "stt")),
    ("avatar", ("avatar", "wallpaper", "overlay", "model-viewer", ".glb")),
    ("agents", ("agent", "orchestrator", "decision", "task_agent", "command_agent")),
    ("devices", ("device", "hardware", "bluetooth", "usb", "serial", "nearby")),
    ("network", ("network", "mesh", "wifi", "rf", "selmalink")),
    ("adapters", ("adapter", "connector", "plugin", "integration")),
    ("automations", ("automation", "scheduler", "schedule", "task runner")),
    ("runtime", ("runtime", "event bus", "process", "health", "diagnostic")),
    ("experiments", ("experiment", "prototype", "lab")),
    ("local-sandbox", ("local-sandbox", "sandbox")),
    ("safety", ("safety", "permission", "consent", "audit", "reversible", "policy")),
    ("tests", ("test_", "/tests/", "\\tests\\", "pytest", "unittest")),
    ("build", ("gradle", "cmake", "androidmanifest", "pyproject", "requirements", "dockerfile", "build")),
    ("ui", ("ui", "dashboard", "frontend", "compose", "react", "html", "css")),
    ("config", ("config", "settings", ".env", "toml", "yaml", "yml")),
    ("core", ("selma_core", "/core/", "\\core\\", "router", "identity", "main.py")),
    ("docs", ("readme", "docs", ".md", ".txt")),
]

PATH_PRIORITY = [
    ("core", ("selma_core/", "/selma_core/", "core/")),
    ("agents", ("agents/", "/agents/", "agent/")),
    ("memory", ("memory/", "/memory/")),
    ("voice", ("voice/", "/voice/")),
    ("avatar", ("avatar/", "/avatar/")),
    ("devices", ("devices/", "/devices/", "hardware/")),
    ("network", ("network/", "/network/", "mesh/", "rf/")),
    ("adapters", ("adapters/", "/adapters/", "plugins/")),
    ("automations", ("automations/", "/automations/")),
    ("runtime", ("runtime/", "/runtime/")),
    ("experiments", ("experiments/", "/experiments/")),
    ("local-sandbox", ("local-sandbox/", "/local-sandbox/")),
    ("tests", ("tests/", "/tests/")),
    ("docs", ("docs/", "/docs/")),
]

DOMAIN_DEPENDENCIES = {
    "agents": ("core", "config", "safety"),
    "memory": ("core", "config"),
    "voice": ("core", "config", "safety"),
    "avatar": ("core", "ui", "config"),
    "devices": ("core", "config", "safety"),
    "network": ("core", "config", "safety"),
    "adapters": ("core", "config", "safety"),
    "automations": ("core", "config", "safety"),
    "runtime": ("core", "config"),
    "ui": ("core", "config"),
}

IGNORE_DIRS = {".git", ".gradle", ".idea", ".vscode", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist", ".venv", "venv"}
TEXT_SUFFIXES = {".py", ".kt", ".kts", ".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".html", ".css", ".xml", ".gradle", ".properties", ".sh", ".ps1", ".sql", ".ini", ".cfg"}
