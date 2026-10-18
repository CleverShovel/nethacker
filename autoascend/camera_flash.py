"""camera_flash.py -- an expensive camera in the early fights (spell_port/make_cam.py hooks it into Agent.emergency_strategy).

uhitm.c flash_hits_mon (3.6.6): a monster hit by the flash that does not resist blinding (has eyes, is not a light) is blinded; within
dist2 < 9 (two squares) it flees 3 times in 4 (monflee: rnd(100) turns, or for good 1 time in 4 of those), and adjacent (dist2 < 3) the
blindness is permanent (mblinded = 0 with mcansee = 0). Tourists start with the camera (median 67 charges); dx1: 28 of 32 fatal early
Tourist crises had one in the pack, 0 flashes.

choose(agent) -> (item, direction name, monster tuple) or None. Fires when a hostile (get_visible_monsters leaves peacefuls out) stands on a
straight line within 2 squares (nothing between) and
  * it is dangerous (monster_utils.is_dangerous_monster), or HP is below CAM_HP of max, or 2+ hostiles are within 2 squares;
  * it has eyes (not F b j P v y e), the same species has not been flashed in the last CAM_SAME_TURNS turns, and nothing was flashed in the
    last CAM_GAP turns.
Never while blind. An empty camera ('Nothing happens') is remembered by opp_items.use_camera and not used again."""
from nle import nethack as nh

from . import jf_config
from . import opp_items

CAM_HP = 0.5
CAM_MIN_DIFF = 2
CAM_STRONG_DIFF = 4
CAM_STRONG_HP = 0.85
CAM_CROWD_HP = 0.7
_NO_EYES = ('mold', 'jelly', 'fungus', 'lichen', 'shrieker', 'blob', 'pudding', 'vortex', 'spore', 'light', 'eye', 'brown', 'ooze')
CAM_GAP = 2
CAM_SAME_TURNS = 8
_EYELESS = set('FbjPvye')
_DIRS = {(-1, 0): 'n', (1, 0): 's', (0, 1): 'e', (0, -1): 'w', (-1, 1): 'ne', (-1, -1): 'nw', (1, 1): 'se', (1, -1): 'sw'}


def _state(agent):
    st = agent.__dict__.get('_camflash')
    if st is None:
        st = agent._camflash = {'last': -99, 'species': {}}
    return st


def _camera(agent):
    empty = opp_items.state(agent).empty
    for it in agent.inventory.items:
        try:
            if it.category == nh.TOOL_CLASS and 'expensive camera' in it.text and it.text not in empty:
                return it
        except Exception:
            continue
    return None


def choose(agent):
    try:
        bl = agent.blstats
        if agent.character.prop.blind:
            return None
        st = _state(agent)
        if bl.time - st['last'] < CAM_GAP:
            return None
        mons = agent.get_visible_monsters()
        if not mons:
            return None
        cam = _camera(agent)
        if cam is None:
            return None
        from .combat.monster_utils import is_dangerous_monster
        occupied = {(m[1], m[2]) for m in mons}
        near = [m for m in mons if max(abs(m[1] - bl.y), abs(m[2] - bl.x)) <= 2]
        if not near:
            return None
        hp_low = bl.hitpoints < CAM_HP * bl.max_hitpoints
        cands = []
        for m in near:
            dist, y, x, mon, glyph = m
            dy, dx = y - bl.y, x - bl.x
            n = max(abs(dy), abs(dx))
            if n == 0 or not (dy == 0 or dx == 0 or abs(dy) == abs(dx)):
                continue
            dy, dx = int(dy), int(dx)
            sy, sx = int(dy > 0) - int(dy < 0), int(dx > 0) - int(dx < 0)
            if n == 2 and (bl.y + sy, bl.x + sx) in occupied:
                continue
            name = getattr(mon, 'mname', '?')
            if name == 'unknown' or str(getattr(mon, 'mlet', '?')) in _EYELESS:
                continue
            # immobile / eyeless things (molds, jellies, lichens, shriekers, spores, lights): a flash does nothing to them
            if any(k in name for k in _NO_EYES) or getattr(mon, 'mmove', 12) < 3:
                continue
            if bl.time - st['species'].get(name, -99) < CAM_SAME_TURNS:
                continue
            diff = getattr(mon, 'difficulty', 0) or 0
            hpr = bl.hitpoints / max(bl.max_hitpoints, 1)
            # only a real threat: hurt (below CAM_HP) with a monster that is not trivial, or a strong monster (rothe, hill orc,
            # giant ant, homunculus ...) next to us while below CAM_STRONG_HP, or three hostiles at once while below CAM_CROWD_HP
            if not ((hpr < CAM_HP and diff >= CAM_MIN_DIFF) or (diff >= CAM_STRONG_DIFF and n == 1 and hpr < CAM_STRONG_HP) or
                    (len(near) >= 3 and hpr < CAM_CROWD_HP and diff >= CAM_MIN_DIFF)):
                continue
            cands.append(((-diff, n), m, _DIRS[(sy, sx)], name))
        if not cands:
            return None
        cands.sort(key=lambda c: c[0])
        _, m, direction, name = cands[0]
        return cam, direction, m, name
    except Exception as e:
        if not agent.__dict__.get('_camflash_err'):
            agent._camflash_err = True
            agent.log(f'CAMFLASH_ERR {e!r}')
        return None


def do_flash(agent, pick):
    cam, direction, m, name = pick
    st = _state(agent)
    st['last'] = agent.blstats.time
    st['species'][name] = agent.blstats.time
    agent.log(f'CAMFLASH {name} {direction} dist {max(abs(m[1] - agent.blstats.y), abs(m[2] - agent.blstats.x))} '
              f'hp {agent.blstats.hitpoints}/{agent.blstats.max_hitpoints}')
    opp_items.use_camera(agent, cam, direction)
