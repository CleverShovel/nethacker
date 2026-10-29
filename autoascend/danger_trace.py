"""Death-scene trace: a purely observational ring buffer of the last game turns, printed to stderr when the episode ends.

Nothing here changes what the bot does (it only reads blstats / glyphs / messages, takes no game action and uses no
random numbers), so a run with the trace must reproduce the run without it episode for episode. One DTRACE line per
game turn is kept per process; when the game ends (Agent.step sees `done`) the last RING turns are printed together with
the final message:
  DTRACE_END pid=<pid> depth=.. xl=.. hp=h/m turns=.. last_msg=..
  DTRACE pid=<pid> t=<turn> d=<depth> xl=.. hp=h/m pw=.. ac=.. hun=.. act=<last action> mons=<name@dy,dx ...> msg=<msg>
act is the key the bot sent when the observation of this turn was produced (a move into a monster is a melee attack,
Command.CAST a spell, Command.SEARCH a wait ...)."""
import collections
import os
import sys

from .glyph import G, MON

RING = 60
RADIUS = 3


def _state(agent):
    st = agent.__dict__.get('_dtrace')
    if st is None:
        st = agent._dtrace = {'t': None, 'buf': collections.deque(maxlen=RING), 'act': ''}
    return st


def note_action(agent, action):
    try:
        _state(agent)['act'] = getattr(action, 'name', str(action))
    except Exception:
        pass


def _nearby(agent):
    bl = agent.blstats
    y0, x0 = bl.y, bl.x
    h, w = agent.glyphs.shape
    out = []
    for dy in range(-RADIUS, RADIUS + 1):
        for dx in range(-RADIUS, RADIUS + 1):
            if not dy and not dx:
                continue
            y, x = y0 + dy, x0 + dx
            if 0 <= y < h and 0 <= x < w:
                g = agent.glyphs[y, x]
                if g in G.MONS:
                    try:
                        name = MON.permonst(g).mname
                    except Exception:
                        name = '?'
                    out.append(f"{'*' if g in G.PETS else ''}{name}@{dy},{dx}")
    return out


def _food(agent):
    try:
        return agent.carried_food_nutrition()
    except Exception:
        return '?'


def _inv(agent, only_food=False):
    try:
        out = []
        for it in agent.inventory.items:
            if only_food and it.category != 6:     # FOOD_CLASS
                continue
            out.append(str(it.text)[:44])
        return out[:40]
    except Exception:
        return '?'


CRISIS_ON = 1 / 3      # HP at or below this fraction (or <= 6 HP) starts a crisis: the ring is printed, then every turn
CRISIS_OFF = 0.6       # the crisis ends when HP is back above this fraction


def on_update(agent):
    try:
        st = _state(agent)
        bl = agent.blstats
        if bl.time == st['t']:
            return
        st['t'] = bl.time
        msg = ' '.join(str(agent.single_message).split())[:110]
        line = (f't={bl.time} d={bl.depth} xl={bl.experience_level} hp={bl.hitpoints}/{bl.max_hitpoints} '
                f'pw={bl.energy} ac={bl.armor_class} hun={bl.hunger_state} act={st["act"]} '
                f'mons={",".join(_nearby(agent)) or "-"} msg={msg!r}')
        st['buf'].append(line)
        pid = os.getpid()
        frac = bl.hitpoints / max(bl.max_hitpoints, 1)
        if bl.hunger_state >= 2 and bl.time - st.get('last_hun', -999) >= 50:
            st['last_hun'] = bl.time
            print(f'DTRACE_HUN pid={pid} turn={bl.time} depth={bl.depth} xl={bl.experience_level} hun={bl.hunger_state} '
                  f'food={_food(agent)} prayer_failed={agent.prayer_failed} pw={bl.energy} items={_inv(agent, only_food=True)}',
                  file=sys.stderr, flush=True)
        if not st.get('crisis'):
            if frac <= CRISIS_ON or bl.hitpoints <= 6:
                st['crisis'] = True
                print(f'DTRACE_CRISIS pid={pid} turn={bl.time} depth={bl.depth} xl={bl.experience_level} '
                      f'hp={bl.hitpoints}/{bl.max_hitpoints}', file=sys.stderr, flush=True)
                for old in st['buf']:
                    print(f'DTRACE pid={pid} {old}', file=sys.stderr, flush=True)
                print(f'DTRACE_INV pid={pid} turn={bl.time} food={_food(agent)} prayer_failed={agent.prayer_failed} '
                      f'items={_inv(agent)}', file=sys.stderr, flush=True)
        else:
            print(f'DTRACE pid={pid} {line}', file=sys.stderr, flush=True)
            if frac > CRISIS_OFF and bl.hitpoints > 6:
                st['crisis'] = False
                print(f'DTRACE_CRISIS_END pid={pid} turn={bl.time}', file=sys.stderr, flush=True)
    except Exception:
        pass


def on_done(agent, observation):
    try:
        st = _state(agent)
        pid = os.getpid()
        bl = getattr(agent, 'blstats', None)
        raw = bytes(observation['tty_chars'].reshape(-1)).decode(errors='replace')
        rows = [raw[i:i + 80].strip() for i in range(0, len(raw), 80)]
        last = ' | '.join(r for r in rows[:3] if r)[:200]
        hp = f'{bl.hitpoints}/{bl.max_hitpoints}' if bl else '?'
        print(f'DTRACE_END pid={pid} depth={bl.depth if bl else "?"} xl={bl.experience_level if bl else "?"} hp={hp} '
              f'turns={bl.time if bl else "?"} top_lines={last!r}', file=sys.stderr, flush=True)
        for line in st['buf']:
            print(f'DTRACE pid={pid} {line}', file=sys.stderr, flush=True)
        print(f'DTRACE_INV_END pid={pid} food={_food(agent)} prayer_failed={agent.prayer_failed} items={_inv(agent)}', file=sys.stderr, flush=True)
    except Exception:
        pass
