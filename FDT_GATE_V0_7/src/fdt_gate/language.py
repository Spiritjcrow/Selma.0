from __future__ import annotations

import importlib.resources
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    start: int
    end: int


def canonical_registry() -> dict:
    data = importlib.resources.files("fdt_gate").joinpath("canonical_registry.json").read_text("utf-8")
    return json.loads(data)


def tokenize_preserving_atomic_forms(text: str) -> list[Token]:
    """Greedy lexer that never decomposes canonical atomic forms.

    It intentionally assigns no execution authority or hidden semantics to those forms.
    """
    forms = sorted(canonical_registry()["atomic_forms"], key=len, reverse=True)
    out: list[Token] = []
    i = 0
    while i < len(text):
        match = next((f for f in forms if text.startswith(f, i)), None)
        if match is not None:
            out.append(Token("ATOMIC_FORM", match, i, i + len(match)))
            i += len(match)
            continue
        if text[i].isspace():
            i += 1
            continue
        j = i + 1
        while j < len(text) and not text[j].isspace() and not any(text.startswith(f, j) for f in forms):
            j += 1
        out.append(Token("TEXT", text[i:j], i, j))
        i = j
    return out
