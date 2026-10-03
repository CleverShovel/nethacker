"""Spell casting for the Wizard on an autoascend-family tree.

The jawfish base never parses the spell menu (Character.parse_spellcast_view is only called from commented-out
lines and only knows the Healer) and never casts an attack spell, so a Wizard fights with a quarterstaff while
force bolt (2d12, hits when rnd(20) < 10 + AC) sits unused. This module adds, without touching the rest of the tree:
  * learn_spells(): a one-off Inventory strategy that opens the cast menu and fills character.known_spells;
  * get_potential_spell_usages(): the fight's 'cast' actions, on fight_heur's priority scale;
  * note_cast(): a stderr counter line (the stats logger's data never leaves the sandbox).
make_wizard.py wires the three hooks into a copy of the tree."""
import os
import sys

from . import utils
from .glyph import G
from .strategy import Strategy
from . import wizard_magic_config as cfg

SPELL = 'force bolt'


def _log(agent, what):
    print(f'WIZMAGIC pid={os.getpid()} {what} depth={agent.blstats.depth} turn={agent.blstats.time}',
          file=sys.stderr, flush=True)


class _Beam:
    """Stands in for a wand in fight_heur's path model: a beam that does not bounce."""

    @staticmethod
    def is_ray_wand():
        return False


_BEAM = _Beam()


def _first_target(agent, monsters, dy, dx):
    """(distance, monster) of the first monster on the line within CAST_RANGE, None when a pet, a peaceful or an
    unknown figure stands first, or the line runs into a wall."""
    y, x = agent.blstats.y, agent.blstats.x
    walkable = agent.current_level().walkable
    for dist in range(1, cfg.CAST_RANGE + 1):
        y += dy
        x += dx
        if not (0 <= y < agent.glyphs.shape[0] and 0 <= x < agent.glyphs.shape[1]):
            return None
        glyph = agent.glyphs[y, x]
        if glyph in G.PETS:
            return None
        if glyph in G.MONS:
            found = [m for m in monsters if m[1] == y and m[2] == x]
            return (dist, found[0]) if found else None
        if not walkable[y, x]:
            return None
    return None


def get_potential_spell_usages(agent, monsters, dy, dx):
    """[(priority, ('cast', dy, dx, spell, targets))] for the direction (dy, dx), like get_potential_wand_usages."""
    if not cfg.CAST_FORCE_BOLT:
        return []
    ch = agent.character
    known = getattr(ch, 'known_spells', None) or {}
    if known.get(SPELL) is None:
        return []
    if agent.blstats.energy < cfg.CAST_MIN_PW + cfg.CAST_RESERVE_PW:
        return []
    from .glyph import Hunger
    if agent.blstats.hunger_state >= Hunger.WEAK:   # spell.c: 'You are too hungry to cast that spell' (uhunger <= 10)
        return []
    if getattr(ch, 'spell_fail_chance', {}).get(SPELL, 1.0) > cfg.CAST_MAX_FAIL:
        return []
    if agent._last_turn - agent.last_cast_fail_turn[SPELL] < 2:
        return []
    if agent.character.prop.confusion or agent.character.prop.stun or agent.character.prop.hallu:
        return []
    from .combat import fight_heur as fh
    if fh.missiles_risk_the_watch(agent):
        return []
    target = _first_target(agent, monsters, dy, dx)
    if target is None:
        return []
    dist, monster = target
    mon = monster[3]
    hp_ratio = agent.blstats.hitpoints / agent.blstats.max_hitpoints
    if mon.mname in fh.WEAK_MONSTERS and hp_ratio > cfg.CAST_WEAK_HP_RATIO:
        return []
    dangerous = fh.is_dangerous_monster(monster)
    if cfg.CAST_MODE == 'threat' and not (dangerous or hp_ratio < cfg.CAST_THREAT_HP_RATIO):
        return []
    priority = cfg.CAST_BASE + (cfg.CAST_DANGEROUS_BONUS if dangerous else 0) + cfg.CAST_LOWHP_BONUS * (1 - hp_ratio)
    priority -= cfg.CAST_DISTANCE_PENALTY * (dist - 1)
    priority += fh.elbereth_attack_penalty(agent, monsters, monster)
    # force bolt flies on past its target like a wand of striking (bhit: range 6-13, -3 per monster hit): a pet,
    # a peaceful or ourselves further down the line get 2d12 too -- the same path model the wands use
    for _y, _x, hit, p in fh.simulate_wand_path(agent, _BEAM, monsters, dy, dx):
        if hit == 'pet':
            priority -= cfg.CAST_PET_PENALTY * p
        elif hit == 'peaceful':
            priority -= cfg.CAST_PEACEFUL_PENALTY * p
        elif hit == 'self':
            priority -= 30 * p
    return [(priority, ('cast', dy, dx, SPELL, {(monster[1], monster[2], monster)}))]


def cast_directed(agent, spell, dy, dx):
    """Cast `spell` in the direction (dy, dx); True when the game asked for the direction (i.e. the cast was not
    failed outright). Agent.cast types the compass STRING that calc_direction returns ('e', 'w', 'ne' ...) as raw
    keys: e/s/w are no direction keys and 'n' is south-east in vi-keys, so the game answered 'What a strange
    direction!' and released the spell along the previous direction -- or at the caster when there was none.
    zap() maps the string to a CompassDirection action first; so does this."""
    from nle.nethack import actions as A
    y, x = agent.blstats.y, agent.blstats.x
    compass = agent.calc_direction(y, x, y + dy, x + dx)
    action = _COMPASS[compass]
    asked = [False]
    letter = agent.character.known_spells[spell]

    def keys():
        if 'You are too impaired' in agent.message:
            return
        yield letter
        for _ in range(3):
            if 'In what direction?' in agent.message:
                break
            yield ' '
        if 'In what direction?' in agent.message:
            asked[0] = True
            yield action

    with agent.atom_operation():
        agent.step(A.Command.CAST, keys())
    if asked[0]:
        agent.stats_logger.log_event(f'cast_{spell}')
    else:
        agent.last_cast_fail_turn[spell] = agent._last_turn
        agent.stats_logger.log_event(f'cast_fail_{spell}')
    return asked[0]


def _compass_table():
    from nle.nethack import actions as A
    return {'n': A.CompassDirection.N, 's': A.CompassDirection.S, 'e': A.CompassDirection.E,
            'w': A.CompassDirection.W, 'ne': A.CompassDirection.NE, 'se': A.CompassDirection.SE,
            'nw': A.CompassDirection.NW, 'sw': A.CompassDirection.SW}


_COMPASS = _compass_table()


def note_cast(agent, spell, pw_before, failed, targets=None):
    name = ''
    if targets:
        t = next(iter(targets))
        name = f' target={t[2][3].mname!r}@{t[0]},{t[1]}'
    if failed:
        # the failure rate changed under us (a metal helm/shield/body armor worn since the menu was read: spell.c
        # percent_success adds spelarmr/spelshld/uarmhbon): trust nothing until the menu is read again
        agent.character.spell_fail_chance[spell] = 1.0
        agent.inventory._spells_dirty = True
    extra = ''
    if failed or agent.blstats.energy >= pw_before:  # no Pw spent: what did the game say?
        extra = f' pw_after={agent.blstats.energy} msgs={" | ".join(agent._message_history[-6:])[-320:]!r}'
    _log(agent, f'cast spell={spell!r} pw_before={pw_before} failed={failed} hp={agent.blstats.hitpoints}'
                f'/{agent.blstats.max_hitpoints} at=({agent.blstats.y},{agent.blstats.x}){name}{extra}')


@utils.debug_log('inventory.learn_spells')
@Strategy.wrap
def learn_spells(self):
    """Open the cast menu once (it takes no game time) so character.known_spells / spell_fail_chance are filled."""
    agent = self.agent
    ch = agent.character
    if not cfg.CAST_FORCE_BOLT or ch.role != ch.WIZARD:
        yield False
    now = agent.blstats.time
    stale = self._spells_parsed_turn is None or self._spells_dirty or \
        now - self._spells_parsed_turn >= cfg.REPARSE_TURNS
    if not stale or agent.get_visible_monsters():
        yield False
    yield True
    self._spells_parsed_turn = now
    self._spells_dirty = False
    if cfg.PARSE_ENABLED:
        ch.parse_spellcast_view()
    _log(agent, f'spells={sorted(ch.known_spells)} fail={ch.spell_fail_chance} pw={agent.blstats.energy}'
                f'/{agent.blstats.max_energy}')


def install(inventory_cls):
    assert not hasattr(inventory_cls, 'learn_spells')
    inventory_cls.learn_spells = learn_spells
    orig_init = inventory_cls.__init__

    def __init__(self, *a, **k):
        orig_init(self, *a, **k)
        self._spells_parsed_turn = None
        self._spells_dirty = False

    inventory_cls.__init__ = __init__
