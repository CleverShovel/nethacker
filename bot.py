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

import importlib  # noqa: E402
import re  # noqa: E402

# identity -> variant package, chosen on held-out games (see build_ident.py)
CHOICE = {
    "arc-dwa-law-fem": "pf_base",
    "arc-dwa-law-mal": "pf_base",
    "arc-gno-neu-fem": "pf_base",
    "arc-gno-neu-mal": "pf_base",
    "arc-hum-law-fem": "pf_base",
    "arc-hum-law-mal": "pf_base",
    "arc-hum-neu-fem": "pf_base",
    "arc-hum-neu-mal": "pf_base",
    "bar-hum-cha-fem": "pf_base",
    "bar-hum-cha-mal": "pf_base",
    "bar-hum-neu-fem": "pf_base",
    "bar-hum-neu-mal": "pf_base",
    "bar-orc-cha-fem": "pf_base",
    "bar-orc-cha-mal": "pf_base",
    "cav-dwa-law-fem": "pf_base",
    "cav-dwa-law-mal": "pf_base",
    "cav-gno-neu-fem": "pf_base",
    "cav-gno-neu-mal": "pf_base",
    "cav-hum-law-fem": "pf_base",
    "cav-hum-law-mal": "pf_base",
    "cav-hum-neu-fem": "pf_base",
    "cav-hum-neu-mal": "pf_base",
    "hea-gno-neu-fem": "pf_hg",
    "hea-gno-neu-mal": "pf_hg",
    "hea-hum-neu-fem": "pf_hh",
    "hea-hum-neu-mal": "pf_hh",
    "kni-hum-law-fem": "pf_base",
    "kni-hum-law-mal": "pf_base",
    "mon-hum-cha-fem": "pf_base",
    "mon-hum-cha-mal": "pf_base",
    "mon-hum-law-fem": "pf_base",
    "mon-hum-law-mal": "pf_base",
    "mon-hum-neu-fem": "pf_base",
    "mon-hum-neu-mal": "pf_base",
    "pri-elf-cha-fem": "pf_base",
    "pri-elf-cha-mal": "pf_base",
    "pri-hum-cha-fem": "pf_pa",
    "pri-hum-cha-mal": "pf_pa",
    "pri-hum-law-fem": "pf_pa",
    "pri-hum-law-mal": "pf_pa",
    "pri-hum-neu-fem": "pf_pa",
    "pri-hum-neu-mal": "pf_pa",
    "ran-elf-cha-fem": "pf_base",
    "ran-elf-cha-mal": "pf_base",
    "ran-gno-neu-fem": "pf_base",
    "ran-gno-neu-mal": "pf_base",
    "ran-hum-cha-fem": "pf_base",
    "ran-hum-cha-mal": "pf_base",
    "ran-hum-neu-fem": "pf_base",
    "ran-hum-neu-mal": "pf_base",
    "ran-orc-cha-fem": "pf_base",
    "ran-orc-cha-mal": "pf_base",
    "rog-hum-cha-fem": "pf_base",
    "rog-hum-cha-mal": "pf_base",
    "rog-orc-cha-fem": "pf_base",
    "rog-orc-cha-mal": "pf_base",
    "sam-hum-law-fem": "pf_v35",
    "sam-hum-law-mal": "pf_v35",
    "tou-hum-neu-fem": "pf_base",
    "tou-hum-neu-mal": "pf_base",
    "val-dwa-law-fem": "pf_base",
    "val-hum-law-fem": "pf_base",
    "val-hum-neu-fem": "pf_base",
    "wiz-elf-cha-fem": "pf_base",
    "wiz-elf-cha-mal": "pf_base",
    "wiz-gno-neu-fem": "pf_base",
    "wiz-gno-neu-mal": "pf_base",
    "wiz-hum-cha-fem": "pf_base",
    "wiz-hum-cha-mal": "pf_base",
    "wiz-hum-neu-fem": "pf_base",
    "wiz-hum-neu-mal": "pf_base",
    "wiz-orc-cha-fem": "pf_base",
    "wiz-orc-cha-mal": "pf_base"
}
DEFAULT = "pf_base"
_ROLES = {"Archeologist": "arc", "Barbarian": "bar", "Caveman": "cav", "Cavewoman": "cav", "Healer": "hea",
          "Knight": "kni", "Monk": "mon", "Priest": "pri", "Priestess": "pri", "Ranger": "ran", "Rogue": "rog",
          "Samurai": "sam", "Tourist": "tou", "Valkyrie": "val", "Wizard": "wiz"}
_RACES = {"human": "hum", "elven": "elf", "dwarven": "dwa", "gnomish": "gno", "orcish": "orc"}
_ALIGNS = {"lawful": "law", "neutral": "neu", "chaotic": "cha"}
_RE = re.compile(r"You are an? (lawful|neutral|chaotic) (?:(male|female) )?(human|elven|dwarven|gnomish|orcish) "
                 r"(" + "|".join(_ROLES) + r")\b")
_FEMALE_ROLES = {"Cavewoman", "Priestess", "Valkyrie"}
_RE_CUT = re.compile(r"You are an? (lawful|neutral|chaotic) (?:(male|female) )?(human|elven|dwarven|gnomish|orcish)")
_RE_TITLE = re.compile(r"Agent the (\w+)")
# Xp 1 rank titles (role.c)
_TITLES = {"Digger": "Archeologist", "Plunderer": "Barbarian", "Plunderess": "Barbarian",
           "Troglodyte": "Caveman", "Rhizotomist": "Healer", "Gallant": "Knight", "Candidate": "Monk",
           "Aspirant": "Priest", "Tenderfoot": "Ranger", "Footpad": "Rogue", "Hatamoto": "Samurai",
           "Rambler": "Tourist", "Stripling": "Valkyrie", "Evoker": "Wizard"}


def _identity(observation):
    texts = []
    for key in ("message", "tty_chars"):
        try:
            texts.append(bytes(observation[key]).decode("latin-1", "replace"))
        except Exception:  # noqa: BLE001
            pass
    text = " ".join(texts)
    m = _RE.search(text)
    if m is not None:
        align, gender, race, role = m.groups()
    else:
        # an 80-column welcome line cuts the role off ("... neutral female gnomish"): take alignment, gender
        # and race from it and the role from the status line's Xp 1 rank title ("Agent the Digger")
        m = _RE_CUT.search(text)
        t = _RE_TITLE.search(text)
        if m is None or t is None or t.group(1) not in _TITLES:
            return None
        align, gender, race = m.groups()
        role = _TITLES[t.group(1)]
    gender = "fem" if gender == "female" or role in _FEMALE_ROLES else "mal"
    return f"{_ROLES[role]}-{_RACES[race]}-{_ALIGNS[align]}-{gender}"

# role -> package when the race cannot be read (see build_ident.py)
FALLBACK = {"hea": "pf_hg", "pri": "pf_base"}
_RE_ALIGN = re.compile(r"\b(Lawful|Neutral|Chaotic)\b")


def _by_status(observation):
    try:
        text = bytes(observation["tty_chars"]).decode("latin-1", "replace")
    except Exception:  # noqa: BLE001
        return None
    t = _RE_TITLE.search(text)
    a = _RE_ALIGN.search(text)
    if t is None or t.group(1) not in _TITLES:
        return None
    role = _ROLES[_TITLES[t.group(1)]]
    align = _ALIGNS[a.group(1).lower()] if a else None
    pkgs = {p for k, p in CHOICE.items() if k.startswith(role + "-") and (align is None or k.split("-")[2] == align)}
    if len(pkgs) == 1:
        return pkgs.pop()
    return FALLBACK.get(role)


class Bot:
    def __init__(self) -> None:
        self._drivers = {}
        self._driver = None

    def reset(self, initial_observation):
        ident = _identity(initial_observation)
        pkg = CHOICE.get(ident)
        if pkg is None and ident is not None:
            pkg = CHOICE.get(ident[:-3] + ("mal" if ident.endswith("fem") else "fem"))
        if pkg is None:
            pkg = _by_status(initial_observation)
        pkg = pkg or DEFAULT
        if pkg not in self._drivers:
            self._drivers[pkg] = importlib.import_module("adapter_" + pkg).AutoAscendDriver()
        self._driver = self._drivers[pkg]
        self._driver.reset(initial_observation)

    def act(self, observation):
        return self._driver.act(observation)

    def close(self):
        for driver in self._drivers.values():
            driver.close()


def make_agent():
    return Bot()
