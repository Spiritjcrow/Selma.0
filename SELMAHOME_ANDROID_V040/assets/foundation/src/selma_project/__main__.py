import argparse
import hashlib
import json
from pathlib import Path


def inventory(root: Path) -> dict[str, str]:
    """Hash regular files under root in deterministic path order."""
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {".git", "__pycache__", ".venv"} for part in relative.parts):
            continue
        if path.is_file() and not path.is_symlink():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(65536), b""):
                    digest.update(block)
            result[relative.as_posix()] = digest.hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a project integrity inventory")
    parser.add_argument("folder", type=Path)
    print(json.dumps(inventory(parser.parse_args().folder), indent=2))
