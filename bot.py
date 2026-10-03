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

# identity -> variant package, chosen by public mean (see build_portfolio.py)
CHOICE = {
    "arc-dwa-law-fem": "pf_v38",
    "arc-dwa-law-mal": "pf_v38",
    "arc-gno-neu-fem": "pf_v36",
    "arc-gno-neu-mal": "pf_v36",
    "arc-hum-law-fem": "pf_v37",
    "arc-hum-law-mal": "pf_v37",
    "arc-hum-neu-fem": "pf_v37",
    "arc-hum-neu-mal": "pf_v36",
    "bar-hum-cha-fem": "pf_v36",
    "bar-hum-cha-mal": "pf_v38",
    "bar-hum-neu-fem": "pf_v36",
    "bar-hum-neu-mal": "pf_v37",
    "bar-orc-cha-fem": "pf_v38",
    "bar-orc-cha-mal": "pf_v38",
    "cav-dwa-law-fem": "pf_vk_s23",
    "cav-dwa-law-mal": "pf_vk_s23",
    "cav-gno-neu-fem": "pf_kef_d42161f",
    "cav-gno-neu-mal": "pf_kef_d42161f",
    "cav-hum-law-fem": "pf_v38",
    "cav-hum-law-mal": "pf_v38",
    "cav-hum-neu-fem": "pf_vk_s23",
    "cav-hum-neu-mal": "pf_vk_s23",
    "hea-gno-neu-fem": "pf_vk_s23",
    "hea-gno-neu-mal": "pf_vk_s23",
    "hea-hum-neu-fem": "pf_v36",
    "hea-hum-neu-mal": "pf_v36",
    "kni-hum-law-fem": "pf_v37",
    "kni-hum-law-mal": "pf_v37",
    "mon-hum-cha-fem": "pf_v38",
    "mon-hum-cha-mal": "pf_v38",
    "mon-hum-law-fem": "pf_v35",
    "mon-hum-law-mal": "pf_v35",
    "mon-hum-neu-fem": "pf_vk_s23",
    "mon-hum-neu-mal": "pf_vk_s23",
    "pri-elf-cha-fem": "pf_kef_d42161f",
    "pri-elf-cha-mal": "pf_v37",
    "pri-hum-cha-fem": "pf_v35",
    "pri-hum-cha-mal": "pf_v35",
    "pri-hum-law-fem": "pf_v38",
    "pri-hum-law-mal": "pf_v38",
    "pri-hum-neu-fem": "pf_v37",
    "pri-hum-neu-mal": "pf_kef_d42161f",
    "ran-elf-cha-fem": "pf_v37",
    "ran-elf-cha-mal": "pf_kef_d42161f",
    "ran-gno-neu-fem": "pf_v36",
    "ran-gno-neu-mal": "pf_v36",
    "ran-hum-cha-fem": "pf_v36",
    "ran-hum-cha-mal": "pf_v36",
    "ran-hum-neu-fem": "pf_v38",
    "ran-hum-neu-mal": "pf_v38",
    "ran-orc-cha-fem": "pf_v37",
    "ran-orc-cha-mal": "pf_v37",
    "rog-hum-cha-fem": "pf_v35",
    "rog-hum-cha-mal": "pf_v35",
    "rog-orc-cha-fem": "pf_v36",
    "rog-orc-cha-mal": "pf_v36",
    "sam-hum-law-fem": "pf_v37",
    "sam-hum-law-mal": "pf_v37",
    "tou-hum-neu-fem": "pf_v38",
    "tou-hum-neu-mal": "pf_v38",
    "val-dwa-law-fem": "pf_vk_s23",
    "val-hum-law-fem": "pf_v38",
    "val-hum-neu-fem": "pf_v37",
    "wiz-elf-cha-fem": "pf_v36",
    "wiz-elf-cha-mal": "pf_v37",
    "wiz-gno-neu-fem": "pf_v36",
    "wiz-gno-neu-mal": "pf_v37",
    "wiz-hum-cha-fem": "pf_vk_s23",
    "wiz-hum-cha-mal": "pf_vk_s23",
    "wiz-hum-neu-fem": "pf_vk_s23",
    "wiz-hum-neu-mal": "pf_vk_s23",
    "wiz-orc-cha-fem": "pf_v36",
    "wiz-orc-cha-mal": "pf_v36"
}
DEFAULT = "pf_v37"
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


class Bot:
    def __init__(self) -> None:
        self._drivers = {}
        self._driver = None

    def reset(self, initial_observation):
        ident = _identity(initial_observation)
        pkg = CHOICE.get(ident)
        if pkg is None and ident is not None:
            pkg = CHOICE.get(ident[:-3] + ("mal" if ident.endswith("fem") else "fem"))
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
