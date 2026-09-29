from __future__ import annotations

import os
import sys
import json
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from nethackers.contracts.bot import ArenaBot

_cache_root = Path(tempfile.gettempdir()) / "nethack_arena_submission_cache"
_cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_root / "xdg"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(_cache_root / "numba"))

from arena_adapter import AutoAscendDriver  # noqa: E402


class Bot:
    def __init__(self) -> None:
        self._driver = AutoAscendDriver()
        self._trace_turn = -500
        self._trace_branch = None

    def reset(self, initial_observation: Mapping[str, Any]) -> None:
        self._driver.reset(initial_observation)

    def act(self, observation: Mapping[str, Any]) -> int:
        action = self._driver.act(observation)
        # Diagnostic output only: no seed, clock, or external data enters decisions.
        bl = observation['blstats']
        branch = (int(bl[23]), int(bl[24]))
        if int(bl[20]) >= self._trace_turn + 500 or branch != self._trace_branch:
            self._trace_turn = int(bl[20])
            self._trace_branch = branch
            self._trace(observation)
        return action

    def _trace(self, observation):
        bl = observation['blstats']
        agent = self._driver._agent
        record = {'pid': os.getpid(), 'turn': int(bl[20]), 'depth': int(bl[12]),
                  'xp': int(bl[18]), 'hp': [int(bl[10]), int(bl[11])],
                  'energy': int(bl[14]), 'ac': int(bl[16]), 'hunger': int(bl[21]),
                  'branch': [int(bl[23]), int(bl[24])],
                  'message': bytes(observation['message']).split(b'\0')[0].decode(errors='replace')}
        if agent is not None:
            record['phase'] = str(agent.global_logic.milestone)
            record['panics'] = [str(e)[:180] for e in agent.all_panics[-3:]]
        print('ASTRA_TRACE ' + json.dumps(record), file=sys.stderr, flush=True)

    def close(self) -> None:
        agent = self._driver._agent
        if agent is not None:
            print('ASTRA_END ' + json.dumps({'pid': os.getpid(),
                'messages': agent._message_history[-30:],
                'panics': [str(e)[:300] for e in agent.all_panics[-5:]]}), file=sys.stderr, flush=True)
        self._driver.close()


def make_agent() -> ArenaBot:
    return Bot()
