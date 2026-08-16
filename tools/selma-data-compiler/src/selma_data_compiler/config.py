from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import tomllib

DEFAULT_CONFIG_PATH = Path(__file__).with_name("default_forge_config.toml")

def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result

class ForgeConfig:
    def __init__(self, workspace: Path, data: dict, sources: list[str]):
        self.workspace = workspace.expanduser().resolve()
        self.data = data
        self.sources = sources

    @classmethod
    def load(cls, workspace: Path) -> "ForgeConfig":
        workspace = workspace.expanduser().resolve()
        with DEFAULT_CONFIG_PATH.open("rb") as handle:
            data = tomllib.load(handle)
        sources = [str(DEFAULT_CONFIG_PATH)]
        override = workspace / ".selma" / "forge_config.toml"
        if override.exists():
            with override.open("rb") as handle:
                data = _deep_merge(data, tomllib.load(handle))
            sources.append(str(override))
        return cls(workspace, data, sources)

    @property
    def minimal_questions(self) -> bool:
        return bool(self.data.get("policy", {}).get("minimal_questions", True))

    @property
    def max_questions(self) -> int:
        return max(0, int(self.data.get("policy", {}).get("max_questions_before_best_effort", 1)))

    @property
    def sandbox_timeout_seconds(self) -> int:
        return max(1, int(self.data.get("sandbox", {}).get("timeout_seconds", 45)))

    @property
    def additional_roots(self) -> list[str]:
        values = self.data.get("forge", {}).get("additional_roots", [])
        return [str(value) for value in values] if isinstance(values, list) else []

    def resolve_roots(self, roots: list[str | Path]) -> list[Path]:
        resolved = []
        seen = set()
        for item in [*roots, *self.additional_roots]:
            path = Path(item).expanduser()
            if not path.is_absolute():
                path = self.workspace / path
            path = path.resolve()
            key = str(path)
            if key not in seen:
                seen.add(key)
                resolved.append(path)
        return resolved

    def to_dict(self) -> dict:
        return {
            "workspace": str(self.workspace),
            "sources": list(self.sources),
            "resolved": deepcopy(self.data),
        }
