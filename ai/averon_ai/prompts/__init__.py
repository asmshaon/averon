"""Versioned translation prompts (design D6). One JSON file per direction: <source>__<target>.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DIR = Path(__file__).parent


@dataclass(frozen=True)
class Prompt:
    direction: str
    version: str
    system: str  # contains "{dialect}"
    default_dialect: str
    examples: tuple[tuple[str, str], ...]

    @property
    def id(self) -> str:
        return f"{self.direction}@{self.version}"

    def system_text(self, dialect: str | None) -> str:
        return self.system.replace("{dialect}", dialect or self.default_dialect)

    def messages(self, text: str, dialect: str | None) -> list[dict]:
        msgs: list[dict] = [{"role": "system", "content": self.system_text(dialect)}]
        for src, tgt in self.examples:
            msgs.append({"role": "user", "content": src})
            msgs.append({"role": "assistant", "content": tgt})
        msgs.append({"role": "user", "content": text})
        return msgs


def load(source: str, target: str) -> Prompt:
    direction = f"{source}__{target}"
    data = json.loads((_DIR / f"{direction}.json").read_text(encoding="utf-8"))
    return Prompt(
        direction=direction,
        version=data["version"],
        system=data["system"],
        default_dialect=data["default_dialect"],
        examples=tuple((e["source"], e["target"]) for e in data["examples"]),
    )
