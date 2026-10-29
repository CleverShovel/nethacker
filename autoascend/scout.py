"""scout.py -- foreknowledge of the monsters on a level (spell_port/make_scout.py hooks it in).

Two sources, both read from the map right after the action that shows them:
  * telepathy (intrinsic, from a floating eye corpse; the bot already has it in about half of its games after turn ~6000) works only blind: a carried
    blindfold / towel is put on for one action, the sensed monsters (and the pet) are read from the glyph map, and it is taken off again (the
    FEYE_BLIND blindfold code does the same dance);
  * the spell 'detect monsters' (known at the start by ~7% of wizards, 5 Pw) shows them for a moment.
What is done with it:
  A. flee: hurt (HP < FLEE_HP) or no prayer available (the last one < PRAYER_GAP turns ago) and a killer-class monster within FLEE_RADIUS squares
     -> the up stairs, if reachable (never from Dlvl 1);
  B. level danger: the first scan on a level (and again after REASSESS turns) adds up the monsters' weights; DANGER_HIGH or more lowers the grind
     level by one for COOL_LEVEL turns (global_logic._grind_level asks adjust_grind_level);
  C. pet: no pet in view for PET_GONE turns -> a scan; a pet found farther than PET_FAR squares is walked to (reachable squares only).
Everything is logged with the tag 'SCOUT'."""
import nle.nethack as nh
import numpy as np
from nle.nethack import actions as A

SCAN_GAP = 120            # turns between two scans
ARRIVE_WAIT = 25          # turns on a new level before its first assessment
REASSESS = 1500
FLEE_HP = 0.6
PRAYER_GAP = 1000
FLEE_RADIUS = 12
FLEE_W = 2.0              # a monster of at least this weight counts as a killer for rule A
DANGER_HIGH = 6.0
COOL_LEVEL = 1500
MAX_DEPTH = 6
PET_GONE = 250
PET_FAR = 6
PET_TRIES = 3
SPELL_MIN_PW = 15
SPELL_MAX_FAIL = 0.30

WEIGHT = {'rothe': 3.0, 'dwarf': 3.0, 'dwarf lord': 3.5, 'dwarf king': 4.0, 'hill orc': 2.0, 'Mordor orc': 2.0, 'Uruk-hai': 3.0, 'orc shaman': 1.0,
          'giant ant': 3.0, 'soldier ant': 4.0, 'fire ant': 3.5, 'killer bee': 3.0, 'giant beetle': 3.0, 'wererat': 2.5, 'werejackal': 2.5,
          'werewolf': 4.0, 'dingo': 2.0, 'jackal': 0.4, 'fox': 0.6, 'coyote': 0.6, 'giant bat': 1.5, 'bugbear': 2.0, 'homunculus': 1.0, 'imp': 1.0,
          'gnome lord': 0.6, 'gnome': 0.3, 'hobbit': 0.3, 'giant rat': 0.3, 'sewer rat': 0.3, 'rabid rat': 0.8, 'newt': 0.1, 'gecko': 0.2,
          'iguana': 0.4, 'baby crocodile': 1.0, 'giant mimic': 3.0, 'large mimic': 2.5, 'small mimic': 1.5, 'jaguar': 3.0, 'lynx': 3.0,
          'panther': 4.0, 'wolf': 3.0, 'warg': 4.0, 'gnome king': 1.5, 'ogre': 4.0, 'leprechaun': 1.0, 'nymph': 0.5, 'quasit': 2.0}
SESSILE = frozenset(('floating eye', 'lichen', 'brown mold', 'yellow mold', 'green mold', 'red mold', 'shrieker', 'violet fungus', 'blue jelly',
                     'spotted jelly', 'ochre jelly', 'acid blob', 'gas spore', 'flaming sphere', 'freezing sphere', 'shocking sphere'))


def _st(agent):
    st = agent.__dict__.get('_scout')
    if st is None:
        st = agent._scout = dict(last_scan=-10 ** 9, seen={}, first={}, override=None, pet_seen=0, pet_tries=[], flees={}, scans=0, how={},
                                 danger_log=[], dead=False, last_err=-10 ** 9, flee_n=0, over_n=0, pet_walk=0, pet_scans=[])
    return st


def adjust_grind_level(agent, level):
    """Called by global_logic._grind_level: the level the grind should use now."""
    try:
        st = _st(agent)
        ov = st['override']
        if ov is None or level is None:
            return level
        target, until, key = ov
        if agent.blstats.time >= until:
            st['override'] = None
            return level
        return min(level, target)
    except Exception:
        return level


# ------------------------------------------------------------------------------------------------ reading the map

PEACEFUL = frozenset(('shopkeeper', 'watchman', 'watch captain', 'guard', 'prisoner', 'Oracle', 'aligned priest', 'high priest', 'attendant',
                      'Woodland-elf', 'Green-elf', 'Grey-elf'))


def _weight(p):
    name = getattr(p, 'mname', '')
    if name in SESSILE or name in PEACEFUL:
        return 0.0
    if name in WEIGHT:
        return WEIGHT[name]
    return min(0.15 * max(int(getattr(p, 'mlevel', 1) or 1), 0), 1.5)


def read_glyphs(agent, glyphs):
    """-> (monsters [(name, y, x, weight)], pets [(y, x)]) from a raw glyph array; the hero's square is skipped."""
    bl = agent.blstats
    g = np.asarray(glyphs)
    mons, pets = [], []
    ranges = [(nh.GLYPH_MON_OFF, False), (nh.GLYPH_PET_OFF, True)]
    if hasattr(nh, 'GLYPH_DETECT_OFF'):
        ranges.append((nh.GLYPH_DETECT_OFF, False))
    for off, is_pet in ranges:
        for y, x in zip(*((g >= off) & (g < off + nh.NUMMONS)).nonzero()):
            y, x = int(y), int(x)
            if (y, x) == (int(bl.y), int(bl.x)):
                continue
            if is_pet:
                pets.append((y, x))
                continue
            p = nh.permonst(int(g[y, x]) - off)
            mons.append((p.mname, y, x, _weight(p)))
    return mons, pets


def danger(agent, mons):
    bl = agent.blstats
    tot = 0.0
    for name, y, x, w in mons:
        d = max(abs(y - int(bl.y)), abs(x - int(bl.x)))
        tot += w * (1.0 if d <= FLEE_RADIUS else 0.5 if d <= 25 else 0.25)
    return tot


# ------------------------------------------------------------------------------------------------ the two scans

def _tele_tool(agent):
    try:
        if not agent.character.telepathic or getattr(agent, '_feye_blindfold_stuck', False):
            return None
        return agent._feye_tool()
    except Exception:
        return None


def _spell_ok(agent):
    ch = agent.character
    bl = agent.blstats
    if 'detect monsters' not in (getattr(ch, 'known_spells', None) or {}):
        return False
    if bl.energy < SPELL_MIN_PW:
        return False
    return getattr(ch, 'spell_fail_chance', {}).get('detect monsters', 1.0) <= SPELL_MAX_FAIL


def scan_telepathy(agent, tool):
    with agent.atom_operation():
        letter = agent.inventory.items.get_letter(tool)

        def put_on():
            if 'What do you want to put on?' in agent.single_message:
                yield letter

        agent.step(A.Command.PUTON, put_on())
        if not agent.character.prop.blind:
            agent._feye_blindfold_stuck = True
            agent.log(f'SCOUT could not put on {tool.text!r}: {agent.message[:80]!r}')
            return None
        glyphs = np.array(agent.last_observation['glyphs'])
        agent.inventory.items.update(force=True)
        worn = next((i for i in agent.inventory.items if i.objs[0].name in agent._FEYE_TOOLS and i.equipped), None)
        wletter = agent.inventory.items.get_letter(worn) if worn is not None else letter

        def remove():
            if 'What do you want to remove?' in agent.single_message:
                yield wletter

        agent.step(A.Command.REMOVE, remove())
        if agent.character.prop.blind:
            agent._feye_blindfold_stuck = True
            agent.log(f'SCOUT blindfold stuck: {agent.message[:80]!r}')
        agent.inventory.items.update(force=True)
    return glyphs


def scan_spell(agent):
    """monster detection ends in a getpos session ('monster of interest', display.c browse_map): the map already shows the monsters then;
    the glyphs are copied and the session is left with ESC (otherwise the monster tracker's own popup read dies on it)."""
    letter = agent.character.known_spells['detect monsters']
    pw0 = agent.blstats.energy
    cap = {}

    def keys():
        if 'You are too impaired' in agent.message:
            return
        yield letter
        cap['g'] = np.array(agent._observation['glyphs'])      # (last_observation is only replaced after the prompt handling that runs this generator)
        cap['msg'] = ' | '.join(agent._message_history[-3:])
        yield A.Command.ESC
        yield A.Command.ESC

    with agent.atom_operation():
        agent.step(A.Command.CAST, keys())
    spent = agent.blstats.energy < pw0
    agent.log(f"SCOUT cast detect monsters spent={spent} msg={cap.get('msg', '')[-100:]!r}")
    if not spent or 'g' not in cap:
        return None
    return cap['g']


# ------------------------------------------------------------------------------------------------ the strategy

def strategy(agent):
    from .strategy import Strategy
    from .level import Level
    from .glyph import G
    from . import utils

    def f():
        st = _st(agent)
        bl = agent.blstats
        now = bl.time
        pr = agent.character.prop
        lvl = agent.current_level()
        key = lvl.key()
        # pet bookkeeping: is a pet glyph on the screen?
        try:
            g = np.asarray(agent.glyphs)
            if ((g >= nh.GLYPH_PET_OFF) & (g < nh.GLYPH_PET_OFF + nh.NUMMONS)).any():
                st['pet_seen'] = now
        except Exception:
            pass
        st['first'].setdefault(key, now)
        if st['dead'] or agent.character.role != agent.character.WIZARD:
            yield False
            return
        if lvl.dungeon_number != Level.DUNGEONS_OF_DOOM or bl.depth > MAX_DEPTH or pr.blind or pr.hallu or pr.confusion or pr.stun or \
                pr.polymorph or bl.hunger_state >= 3 or lvl.shop[bl.y, bl.x] or agent.hands_welded():
            yield False
            return
        try:
            if agent.global_logic.dive.diving:
                yield False
                return
        except Exception:
            pass
        if now - st['last_scan'] < SCAN_GAP or now < st['last_err'] + 100 or agent.get_visible_monsters() or bl.hitpoints < 0.45 * bl.max_hitpoints:
            yield False
            return
        tool = _tele_tool(agent)
        use_spell = tool is None and _spell_ok(agent)
        if tool is None and not use_spell:
            yield False
            return
        hp_low = bl.hitpoints < FLEE_HP * bl.max_hitpoints
        gap = (now - agent.last_prayer_turn) if agent.last_prayer_turn is not None else 10 ** 6
        prayer_off = gap < PRAYER_GAP
        trig = None
        if now - st['first'][key] >= ARRIVE_WAIT and now - st['seen'].get(key, -10 ** 9) >= REASSESS:
            trig = 'assess'
        elif hp_low or prayer_off:
            trig = 'hurt' if hp_low else 'noprayer'
        elif st['pet_seen'] > 0 and now - st['pet_seen'] >= PET_GONE and len([t for t in st['pet_scans'] if now - t < 1000]) < 2:
            trig = 'pet'
        if trig is None or (trig != 'assess' and now - st['last_scan'] < 300):
            yield False
            return
        yield True
        st['last_scan'] = now
        if trig == 'pet':
            st['pet_scans'].append(now)
        try:
            glyphs = scan_telepathy(agent, tool) if tool is not None else scan_spell(agent)
            if glyphs is None:
                st['last_err'] = now
                return
            st['scans'] += 1
            how = 'tele' if tool is not None else 'spell'
            st['how'][how] = st['how'].get(how, 0) + 1
            st['seen'][key] = now
            mons, pets = read_glyphs(agent, glyphs)
            dg = danger(agent, mons)
            lvl_depth = bl.depth
            near = sorted(((max(abs(y - int(bl.y)), abs(x - int(bl.x))), n, w) for n, y, x, w in mons if w >= FLEE_W))[:4]
            decision = '-'
            # B. level danger
            if dg >= DANGER_HIGH and lvl_depth >= 2:
                st['override'] = (lvl_depth - 1, now + COOL_LEVEL, key)
                st['over_n'] += 1
                decision = f'grind one level up for {COOL_LEVEL}'
            # A. flee
            fl = st['flees'].get(key, [])
            fl = [t for t in fl if now - t < 800]
            if (hp_low or prayer_off) and near and near[0][0] <= FLEE_RADIUS and lvl_depth >= 2 and len(fl) < 2:
                ups = [p for p in zip(*utils.isin(lvl.objects, G.STAIR_UP).nonzero())]
                dis = agent.bfs()
                ups = [p for p in ups if dis[p] != -1]
                if ups:
                    st['flees'][key] = fl + [now]
                    st['flee_n'] += 1
                    decision = (decision + ' | ' if decision != '-' else '') + f'flee upstairs from {near[0][1]}@{near[0][0]}'
                    agent.log(f'SCOUT scan how={how} trig={trig} t={now} depth={lvl_depth} danger={dg:.1f} near={near} pets={len(pets)} -> {decision}')
                    y, x = min(ups, key=lambda p: dis[p])
                    for _ in range(8):
                        if (agent.blstats.y, agent.blstats.x) == (y, x):
                            break
                        agent.go_to(y, x, max_steps=12)
                        if any(m[0] <= 3 for m in agent.get_visible_monsters()):
                            break
                    if (agent.blstats.y, agent.blstats.x) == (y, x):
                        agent.move('<')
                    return
            # C. pet
            if pets and now - st['pet_seen'] >= PET_GONE:
                py, px = min(pets, key=lambda p: max(abs(p[0] - int(bl.y)), abs(p[1] - int(bl.x))))
                d = max(abs(py - int(bl.y)), abs(px - int(bl.x)))
                tries = [t for t in st['pet_tries'] if now - t < 500]
                if d > PET_FAR and len(tries) < PET_TRIES:
                    dis = agent.bfs()
                    if dis[py, px] != -1:
                        st['pet_tries'] = tries + [now]
                        st['pet_walk'] += 1
                        decision = (decision + ' | ' if decision != '-' else '') + f'walk to the pet at distance {d}'
                        agent.log(f'SCOUT scan how={how} trig={trig} t={now} depth={lvl_depth} danger={dg:.1f} near={near} pets={len(pets)} -> {decision}')
                        agent.go_to(py, px, stop_one_before=True, max_steps=40)
                        return
            agent.log(f'SCOUT scan how={how} trig={trig} t={now} depth={lvl_depth} danger={dg:.1f} mons={len(mons)} near={near} pets={len(pets)} -> {decision}')
        except Exception as e:
            from .exceptions import AgentChangeStrategy, AgentFinished, AgentPanic
            if isinstance(e, (AgentChangeStrategy, AgentFinished, AgentPanic, KeyboardInterrupt, SystemExit)):
                raise
            st['last_err'] = now
            agent.log(f'SCOUT failed: {type(e).__name__}: {str(e)[:120]}')

    return Strategy(f)
