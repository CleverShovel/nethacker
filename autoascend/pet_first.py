"""pet_first.py -- let the starting pet do the early fighting (spell_port/make_petfirst.py hooks it into Agent.fight2).

Wizards start with a kitten that is stronger than they are (pt1: a pet is within 3 squares in 67-79% of the Wizard samples during the first 3000 turns,
31-42% later). Two behaviours, both only for Wizards:

  pit wait (always on in this module): the message 'The kitten falls into a pit!' / '... is caught in ...' starts a wait of up to PIT_WAIT_MAX turns (search)
      while no hostile is in view and the pet glyph is still on that square. A trapped monster pulls free with chance 1/40 per move (trap.c mintrap), so the
      wait averages ~40 turns; swapping places with it instead would make it go wild with chance 1/mtame (10%) (hack.c). The wait also keeps the pet from
      being left behind. A pet that is killed by the fall ('is killed') does not start a wait.
  far wait (mode 'both'): while every visible hostile is NOT adjacent to us and each of them is adjacent to a pet (the pet is already fighting it), at XL <= FAR_XL
      and HP >= FAR_HP of max, we wait (search) instead of walking up to it, at most FAR_WAIT_MAX turns in a row. When a hostile reaches us, the normal
      fight (force bolt first, melee otherwise) takes over.
"""
import re

from . import jf_config  # noqa: F401  (kept for the tree's import layout)
from .glyph import G

PIT_WAIT_MAX = 80
FAR_XL = 4
FAR_HP = 0.6
FAR_WAIT_MAX = 12
MODE = 'both'      # 'pit' or 'both' (set by make_petfirst.py)

_TRAP_MSG = re.compile(r'(?:kitten|housecat|large cat|little dog|\bdog\b|large dog|pony|horse)[^.!]*?(?:falls into a pit|is caught in|is stuck|is trapped)', re.I)
_DEAD = re.compile(r'killed|dies|destroyed', re.I)


def _st(agent):
    st = agent.__dict__.get('_petfirst')
    if st is None:
        st = agent._petfirst = {'trap_until': -1, 'trap_pos': None, 'far': 0}
    return st


def _is_wizard(agent):
    try:
        return agent.character.role == agent.character.WIZARD
    except Exception:
        return False


def _pet_positions(agent):
    from . import utils
    ys, xs = utils.isin(agent.glyphs, G.PETS).nonzero()
    return [(int(y), int(x)) for y, x in zip(ys, xs)]


def wait_reason(agent, monsters):
    """None, or 'pit' / 'far': the reason to spend this turn waiting."""
    try:
        if not _is_wizard(agent):
            return None
        bl = agent.blstats
        st = _st(agent)
        if bl.hunger_state >= 3 or agent.character.prop.blind:
            return None
        msg = ' '.join(str(agent.single_message or '').split())
        pets = _pet_positions(agent)
        if msg and _TRAP_MSG.search(msg) and not _DEAD.search(msg) and pets:
            # the pet that fell: the one nearest to us (it just moved there)
            st['trap_pos'] = min(pets, key=lambda p: max(abs(p[0] - bl.y), abs(p[1] - bl.x)))
            st['trap_until'] = bl.time + PIT_WAIT_MAX
        if st['trap_until'] > bl.time:
            near_hostile = any(max(abs(m[1] - bl.y), abs(m[2] - bl.x)) <= 7 for m in monsters)
            if near_hostile or st['trap_pos'] not in pets:
                st['trap_until'] = -1
            else:
                agent.log('PETWAIT pit')
                return 'pit'
        if MODE != 'both':
            return None
        if not monsters or not pets or bl.experience_level > FAR_XL or bl.hitpoints < FAR_HP * bl.max_hitpoints:
            st['far'] = 0
            return None
        for m in monsters:
            my, mx = m[1], m[2]
            if max(abs(my - bl.y), abs(mx - bl.x)) <= 1:
                st['far'] = 0
                return None            # it is on us: fight
            if not any(max(abs(my - py), abs(mx - px)) <= 1 for py, px in pets):
                st['far'] = 0
                return None            # a monster the pet is not fighting
        st['far'] += 1
        if st['far'] > FAR_WAIT_MAX:
            return None
        agent.log('PETWAIT far')
        return 'far'
    except Exception:
        return None
