from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from nethackers.contracts.bot import ArenaBot

_cache_root = Path(tempfile.gettempdir()) / "nethack_arena_submission_cache"
_cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_root / "xdg"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(_cache_root / "numba"))

import re  # noqa: E402

# Roles played by the aa_dd line (github.com/daglar-dragomirov/nethacker); every other role, and any
# game whose role cannot be read, is played by jawfish (github.com/vkurenkov/nethacker@ef6acf8). The
# split was chosen on held-out games of our own seeds, per role, not on the public or private seeds.
DD_ROLES = ['Archeologist']
_ROLES = ("Archeologist", "Barbarian", "Caveman", "Cavewoman", "Healer", "Knight", "Monk", "Priest",
          "Priestess", "Ranger", "Rogue", "Samurai", "Tourist", "Valkyrie", "Wizard")
_ROLE_RE = re.compile(r"\b(" + "|".join(_ROLES) + r")\b")


def _role(observation: Mapping[str, Any]) -> str | None:
    texts = []
    for key in ("message", "tty_chars"):
        value = observation.get(key)
        if value is not None:
            try:
                texts.append(bytes(value).decode("latin-1", "replace"))
            except Exception:  # noqa: BLE001 - unexpected observation layout
                pass
    m = _ROLE_RE.search(" ".join(texts))
    if m is None:
        return None
    return {"Cavewoman": "Caveman", "Priestess": "Priest"}.get(m.group(1), m.group(1))


class Bot:
    def __init__(self) -> None:
        self._drivers = {}
        self._driver = None

    def _get(self, line: str):
        if line not in self._drivers:
            if line == "dd":
                from arena_adapter_dd import AutoAscendDriver as Driver
            else:
                from arena_adapter import AutoAscendDriver as Driver
            self._drivers[line] = Driver()
        return self._drivers[line]

    def reset(self, initial_observation: Mapping[str, Any]) -> None:
        line = "dd" if _role(initial_observation) in DD_ROLES else "jf"
        self._driver = self._get(line)
        self._driver.reset(initial_observation)

    def act(self, observation: Mapping[str, Any]) -> int:
        return self._driver.act(observation)

    def close(self) -> None:
        for driver in self._drivers.values():
            driver.close()


def make_agent() -> ArenaBot:
    return Bot()
