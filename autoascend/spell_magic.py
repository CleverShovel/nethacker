"""Spells for the casters of an autoascend-family tree: force bolt, self spells and learning from spellbooks.

Superset of wizard_magic_port/wizard_magic.py (the force bolt part is unchanged). The jawfish base never parses the spell
menu for anyone but the Healer and never reads a spellbook; this module adds, without touching the rest of the tree:
  * learn_spells(): Inventory strategy that opens the cast menu and fills character.known_spells / spell_fail_chance /
    spell_level (a one-off, no game time);
  * get_potential_spell_usages(): fight 'cast' actions for force bolt;
  * choose_self_spell() / cast_self(): non-directional / self-directed spells -- healing and extra healing (answered with
    '.'), protection, haste self, cure blindness -- decided at the top of Agent.emergency_strategy;
  * read_new_spellbook(): Inventory strategy that studies a found book at a safe moment.

Rules used (NetHack 3.6.6 spell.c study_book/cursed_book/percent_success/spelleffects, potion.c, u_init.c):
  * read_ability = Int + 4 + XL/2 - 2*level; a blessed book always works, a cursed one never does (and gives no prompt),
    otherwise it fails when rnd(20) > read_ability. Only a Wizard is asked 'This spellbook is [very ]difficult to
    comprehend. Continue?' -- when read_ability < 20 ('very' when < 12) and the book is not blessed/cursed. The prompt is
    therefore a level oracle: this module computes the posterior over the book's level from it and declines when the
    chance of a bad failure is too high.
  * a failed read does rn2(level): 0 teleport, 1 aggravate, 2 blindness 250-349 turns, 3 lose gold, 4 confusion,
    5 contact poison, 6 explosion (level 7 book), and leaves us helpless for the study delay.
  * casting costs 5*level Pw; healing and extra healing ask a direction; 'too hungry' at hunger Weak, no cast while
    confused."""
import os
import sys

from . import utils
from .glyph import G
from .strategy import Strategy
from . import spell_config as cfg

SPELL = 'force bolt'

# ------------------------------------------------------------------------------------------------ logging


def _log(agent, what):
    print(f'SPELLSTAT pid={os.getpid()} {what} depth={agent.blstats.depth} turn={agent.blstats.time}',
          file=sys.stderr, flush=True)


def _roles(ch, names):
    return {getattr(ch, n) for n in names}


# ------------------------------------------------------------------------------------------------ force bolt


class _Beam:
    """Stands in for a wand in fight_heur's path model: a beam that does not bounce."""

    @staticmethod
    def is_ray_wand():
        return False


_BEAM = _Beam()


def _first_target(agent, monsters, dy, dx):
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


def _retained(ch, spell):
    """False once the spell is forgotten ('(gone)' in the menu after 20000 turns): casting it then only stuns and
    confuses ('Your knowledge of this spell is twisted')."""
    return getattr(ch, 'spell_retention', {}).get(spell, 100) > 0


def get_potential_spell_usages(agent, monsters, dy, dx):
    """[(priority, ('cast', dy, dx, spell, targets))] for the direction (dy, dx), like get_potential_wand_usages."""
    if not cfg.CAST_FORCE_BOLT:
        return []
    ch = agent.character
    known = getattr(ch, 'known_spells', None) or {}
    if known.get(SPELL) is None or not _retained(ch, SPELL):
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
    for _y, _x, hit, p in fh.simulate_wand_path(agent, _BEAM, monsters, dy, dx):
        if hit == 'pet':
            priority -= cfg.CAST_PET_PENALTY * p
        elif hit == 'peaceful':
            priority -= cfg.CAST_PEACEFUL_PENALTY * p
        elif hit == 'self':
            priority -= 30 * p
    return [(priority, ('cast', dy, dx, SPELL, {(monster[1], monster[2], monster)}))]


def _compass_table():
    from nle.nethack import actions as A
    return {'n': A.CompassDirection.N, 's': A.CompassDirection.S, 'e': A.CompassDirection.E,
            'w': A.CompassDirection.W, 'ne': A.CompassDirection.NE, 'se': A.CompassDirection.SE,
            'nw': A.CompassDirection.NW, 'sw': A.CompassDirection.SW}


_COMPASS = _compass_table()


def cast_directed(agent, spell, dy, dx):
    """Cast `spell` in the direction (dy, dx); True when the game asked for the direction (the cast was not failed
    outright). The direction goes in as a CompassDirection action (Agent.cast types the compass string as raw keys)."""
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


def note_cast(agent, spell, pw_before, failed, targets=None):
    name = ''
    if targets:
        t = next(iter(targets))
        name = f' target={t[2][3].mname!r}@{t[0]},{t[1]}'
    if failed:
        agent.character.spell_fail_chance[spell] = 1.0
        agent.inventory._spells_dirty = True
    extra = ''
    if failed or agent.blstats.energy >= pw_before:
        extra = f' pw_after={agent.blstats.energy} msgs={" | ".join(agent._message_history[-6:])[-320:]!r}'
    _log(agent, f'cast spell={spell!r} pw_before={pw_before} failed={failed} hp={agent.blstats.hitpoints}'
                f'/{agent.blstats.max_hitpoints} at=({agent.blstats.y},{agent.blstats.x}){name}{extra}')


# ------------------------------------------------------------------------------------------------ self spells

# spell -> (Pw cost, config prefix) ; costs are 5 * level
_COST = {'healing': 5, 'extra healing': 15, 'protection': 5, 'haste self': 15, 'cure blindness': 10}


def _state(agent):
    st = getattr(agent, '_spell_state', None)
    if st is None:
        st = agent._spell_state = {'last': {}, 'fail_until': {}, 'count': {}}
    return st


def _can_cast_now(agent):
    from .glyph import Hunger
    prop = agent.character.prop
    if prop.confusion or prop.stun or prop.hallu or prop.polymorph:
        return False
    if agent.blstats.hunger_state >= Hunger.WEAK:
        return False
    return True


def _deadly_status(agent):
    import nle.nethack as nh
    deadly = int(agent.last_observation['blstats'][nh.NLE_BL_CONDITION]) & (
        nh.BL_MASK_STONE | nh.BL_MASK_SLIME | nh.BL_MASK_STRNGL | nh.BL_MASK_FOODPOIS | nh.BL_MASK_TERMILL)
    return bool(deadly)


def _usable(agent, spell, max_fail):
    ch = agent.character
    known = getattr(ch, 'known_spells', None) or {}
    if known.get(spell) is None or not _retained(ch, spell):
        return False
    if getattr(ch, 'spell_fail_chance', {}).get(spell, 1.0) > max_fail:
        return False
    st = _state(agent)
    now = agent.blstats.time
    if now < st['fail_until'].get(spell, -1):
        return False
    return agent.blstats.energy >= _COST[spell]


def choose_self_spell(agent):
    """Name of the self spell to cast now, or None. Cheap when nothing relevant is known."""
    if not cfg.SELF_SPELLS:
        return None
    ch = agent.character
    known = getattr(ch, 'known_spells', None)
    if not known or ch.role not in _roles(ch, cfg.PARSE_ROLES):
        return None
    wanted = ('healing', 'extra healing', 'protection', 'haste self', 'cure blindness')
    if not any(known.get(s) is not None for s in wanted):
        return None
    if not _can_cast_now(agent) or _deadly_status(agent):
        return None
    bl = agent.blstats
    st = _state(agent)
    now = bl.time
    prop = ch.prop
    cache = []

    def monsters():
        if not cache:
            cache.append(agent.get_visible_monsters())
        return cache[0]

    def near(d):
        return [m for m in monsters() if m[0] <= d]

    if cfg.CURE_BLIND_ENABLE and prop.blind and _usable(agent, 'cure blindness', cfg.BLIND_MAX_FAIL):
        return 'cure blindness'

    missing = bl.max_hitpoints - bl.hitpoints
    frac = bl.hitpoints / max(bl.max_hitpoints, 1)
    if cfg.HEAL_ENABLE and missing >= cfg.HEAL_MIN_MISSING and (
            (frac <= cfg.HEAL_HP_FRAC and near(cfg.HEAL_NEAR_DIST)) or frac <= cfg.HEAL_ALONE_FRAC):
        if missing >= cfg.EXTRA_HEAL_MISSING and _usable(agent, 'extra healing', cfg.HEAL_MAX_FAIL):
            return 'extra healing'
        if _usable(agent, 'healing', cfg.HEAL_MAX_FAIL):
            return 'healing'
        if _usable(agent, 'extra healing', cfg.HEAL_MAX_FAIL):
            return 'extra healing'

    from .combat import fight_heur as fh
    if cfg.PROTECT_ENABLE and bl.experience_level >= cfg.PROTECT_MIN_XL and \
            now - st['last'].get('protection', -10 ** 9) >= cfg.PROTECT_COOLDOWN and \
            bl.energy >= _COST['protection'] + cfg.PROTECT_RESERVE_PW and \
            _usable(agent, 'protection', cfg.PROTECT_MAX_FAIL):
        close = [m for m in near(cfg.PROTECT_DIST) if m[3].mname not in fh.WEAK_MONSTERS]
        if close and (bl.depth >= cfg.PROTECT_MIN_DEPTH or frac < cfg.PROTECT_HP_FRAC or
                      any(fh.is_dangerous_monster(m) for m in close)):
            return 'protection'
    if cfg.HASTE_ENABLE and now - st['last'].get('haste self', -10 ** 9) >= cfg.HASTE_COOLDOWN and \
            bl.energy >= _COST['haste self'] + cfg.HASTE_RESERVE_PW and \
            _usable(agent, 'haste self', cfg.HASTE_MAX_FAIL):
        close = near(cfg.HASTE_DIST)
        if close and (frac <= cfg.HEAL_HP_FRAC or any(fh.is_dangerous_monster(m) for m in close)):
            return 'haste self'
    return None


def cast_self(agent, spell):
    """Cast a self / non-directional spell. Answers a direction prompt (healing, extra healing) with '.'. Returns True
    when Pw was spent without a 'fail to cast' message."""
    from nle.nethack import actions as A
    letter = agent.character.known_spells[spell]
    pw_before = agent.blstats.energy
    st = _state(agent)
    st['last'][spell] = agent.blstats.time
    asked = [False]

    def keys():
        if 'You are too impaired' in agent.message:
            return
        yield letter
        if 'In what direction?' in agent.message:
            asked[0] = True
            yield '.'

    with agent.atom_operation():
        agent.step(A.Command.CAST, keys())
    msgs = ' | '.join(agent._message_history[-6:])
    failed = 'fail to cast' in msgs or 'too hungry' in msgs or 'too impaired' in msgs or 'cannot cast' in msgs
    spent = agent.blstats.energy < pw_before
    ok = spent and not failed
    st['count'][spell] = st['count'].get(spell, 0) + (1 if ok else 0)
    if not ok:
        st['fail_until'][spell] = agent.blstats.time + cfg.SELF_FAIL_LOCKOUT
        agent.character.spell_fail_chance[spell] = 1.0
        agent.inventory._spells_dirty = True
    agent.stats_logger.log_event(f'cast_{spell}' if ok else f'cast_fail_{spell}')
    _log(agent, f'selfcast spell={spell!r} ok={ok} asked={asked[0]} pw={pw_before}->{agent.blstats.energy} '
                f'hp={agent.blstats.hitpoints}/{agent.blstats.max_hitpoints} msgs={msgs[-200:]!r}')
    return ok


# ------------------------------------------------------------------------------------------------ menu parsing


@utils.debug_log('inventory.learn_spells')
@Strategy.wrap
def learn_spells(self):
    """Open the cast menu (no game time) so character.known_spells / spell_fail_chance / spell_level are filled."""
    agent = self.agent
    ch = agent.character
    if not cfg.PARSE_ENABLED or ch.role not in _roles(ch, cfg.PARSE_ROLES):
        yield False
    now = agent.blstats.time
    stale = self._spells_parsed_turn is None or self._spells_dirty or \
        now - self._spells_parsed_turn >= cfg.REPARSE_TURNS
    if not stale or agent.get_visible_monsters():
        yield False
    yield True
    self._spells_parsed_turn = now
    self._spells_dirty = False
    ch.parse_spellcast_view()
    keep = getattr(ch, 'spell_retention', {})
    sig = (tuple(sorted(ch.known_spells)), tuple(sorted(keep.items())), round(sum(ch.spell_fail_chance.values()), 2),
           agent.blstats.max_energy // 10)
    if sig != getattr(self, '_spells_logged', None):
        self._spells_logged = sig
        import nle.nethack as nh
        books = [(i.text, i.status) for i in self.items if i.category == nh.SPBOOK_CLASS]
        _log(agent, f'spells={sorted(ch.known_spells)} level={getattr(ch, "spell_level", {})} '
                    f'fail={ch.spell_fail_chance} keep={keep} pw={agent.blstats.energy}/{agent.blstats.max_energy} '
                    f'xl={agent.blstats.experience_level} int={agent.blstats.intelligence} '
                    f'wis={agent.blstats.wisdom} armor={armor_summary(self)} books={books}')


# ------------------------------------------------------------------------------------------------ reading books

# probability of each level among all spellbooks (objects.c, per mille; blank paper and level 0 left out)
_RISK = {   # failed read (level L): rn2(L) -> effect index; which indices are 'severe' for a low-level character
    1: [], 2: [], 3: [2], 4: [2], 5: [2, 4], 6: [2, 4, 5], 7: [2, 4, 5, 6]}
P_BLESSED = 0.029   # mkobj.c blessorcurse(otmp, 17): 1 in 17 is blessed or cursed, half each
P_CURSED = 0.029


def read_outcome(levels, int_, xl, band):
    """(P(success), P(severe failure)) for a book drawn from `levels` ({level: weight}) given the prompt band:
    'easy' (no prompt), 'difficult' (read_ability 12..19) or 'very' (< 12). Blessed books never prompt and always
    succeed; cursed books never prompt and always fail; uncursed ones prompt when read_ability < 20."""
    succ = sev = tot = 0.0
    for level, w in levels.items():
        ra = int_ + 4 + xl // 2 - 2 * level
        pf = max(0.0, min(1.0, (20 - ra) / 20.0))
        severe_given_fail = len(_RISK.get(level, [2, 4, 5, 6])) / level if level else 0
        unc_band = 'very' if ra < 12 else 'difficult' if ra < 20 else 'easy'
        # joint weights of (blessed / cursed / uncursed) and the band that was observed
        for p_b, p_succ, p_sev, bands in (
                (P_BLESSED, 1.0, 0.0, ('easy',)),
                (P_CURSED, 0.0, severe_given_fail, ('easy',)),
                (1 - P_BLESSED - P_CURSED, 1 - pf, pf * severe_given_fail, (unc_band,))):
            if band in bands:
                tot += w * p_b
                succ += w * p_b * p_succ
                sev += w * p_b * p_sev
    if tot <= 0:
        return 0.0, 1.0
    return succ / tot, sev / tot


def book_levels(item, known_names=()):
    """{level: weight} over the spellbook kinds the item may still be (weights = generation probability)."""
    out = {}
    for o in item.objs:
        if getattr(o, 'level', None) is None or o.name in known_names:
            continue
        out[o.level] = out.get(o.level, 0.0) + o.prob
    return out


def _book_key(item, xl):
    return (item.text if hasattr(item, 'text') else str(item.objs[0].name), xl)


def _safe_to_read(inv):
    from .level import Level
    agent = inv.agent
    bl = agent.blstats
    if bl.hitpoints < cfg.LEARN_MIN_HP_FRAC * bl.max_hitpoints:
        return False
    prop = agent.character.prop
    if prop.blind or prop.confusion or prop.stun or prop.hallu or prop.polymorph:
        return False
    if agent.get_visible_monsters():
        return False
    from .glyph import Hunger
    if bl.hunger_state >= Hunger.HUNGRY or bl.depth <= 0:
        return False
    if agent.current_level().dungeon_number == Level.SOKOBAN:
        return False
    if utils.isin(agent.glyphs, G.SHOPKEEPER).any():
        return False
    return bl.time - inv._last_book_turn >= cfg.LEARN_COOLDOWN


@utils.debug_log('inventory.read_new_spellbook')
@Strategy.wrap
def read_new_spellbook(self):
    import nle.nethack as nh
    from nle.nethack import actions as A
    from .item.item import Item
    if not cfg.LEARN_ENABLE:
        yield False
    agent = self.agent
    ch = agent.character
    if ch.role not in _roles(ch, cfg.LEARN_ROLES):
        yield False
    xl = agent.blstats.experience_level
    int_ = agent.blstats.intelligence
    known = set(getattr(ch, 'known_spells', {}) or {})
    candidates = []
    for item in self.items:
        if item.category != nh.SPBOOK_CLASS or item.status == Item.CURSED:
            continue
        tries = self._book_tries.get(_book_key(item, xl), 0)
        if tries >= cfg.LEARN_MAX_TRIES:
            continue
        refresh = False
        if item.is_unambiguous() and item.object.name in known:
            # a book of a spell we know: study it again only when the memory is nearly gone (spell.c: 'You know
            # it quite well already' while more than 10% of the 20000 turns are left)
            keep = getattr(ch, 'spell_retention', {}).get(item.object.name, 100)
            if not cfg.REFRESH_ENABLE or keep > cfg.REFRESH_AT_PCT:
                continue
            refresh = True
            levels = {item.object.level: 1.0}
        else:
            levels = book_levels(item, known)
            if not levels:
                continue
        if item.status == Item.BLESSED:
            candidates.append((1.0, item, levels))
            continue
        succ_easy, _ = read_outcome(levels, int_, xl, 'easy')
        succ_dif, _ = read_outcome(levels, int_, xl, 'difficult')
        candidates.append((max(succ_easy, succ_dif) + (1.0 if refresh else 0.0), item, levels))
    if not candidates or not _safe_to_read(self):
        yield False
    candidates.sort(key=lambda c: -c[0])
    _, book, levels = candidates[0]
    letter = self.items.get_letter(book)
    key = _book_key(book, xl)
    trace = {'band': 'easy', 'decision': ''}

    def gen():
        if 'What do you want to read?' not in agent.single_message:
            trace['decision'] = 'no read prompt'
            return
        yield letter
        text = '\n'.join(list(agent.popup) + list(agent.single_popup)) + '\n' + agent.single_message
        if 'difficult to comprehend' in text:
            band = 'very' if 'very difficult' in text else 'difficult'
            trace['band'] = band
            succ, sev = read_outcome(levels, int_, xl, band)
            if sev > cfg.LEARN_MAX_SEVERE or succ < cfg.LEARN_MIN_SUCCESS:
                trace['decision'] = f'decline succ={succ:.2f} sev={sev:.3f}'
                self._book_tries[key] = cfg.LEARN_MAX_TRIES
                yield 'n'
                return
            trace['decision'] = f'accept succ={succ:.2f} sev={sev:.3f}'
            yield 'y'
        else:
            trace['decision'] = 'no prompt'
        for _ in range(6):
            if b'--More--' in bytes(agent._observation['tty_chars'].reshape(-1)):
                yield A.TextCharacters.SPACE
            else:
                break

    yield True
    self._book_tries[key] = self._book_tries.get(key, 0) + 1
    self._last_book_turn = agent.blstats.time
    pre = set(known)
    with agent.atom_operation():
        agent.step(A.Command.READ, gen())
    self.items.update(force=True)
    self._spells_dirty = True
    tail = ' | '.join(agent._message_history[-8:])[-300:]
    _log(agent, f'book_read book={book.text!r} int={int_} xl={xl} band={trace["band"]} {trace["decision"]} '
                f'tries={self._book_tries[key]} known_before={sorted(pre)} msgs={tail!r}')


# ------------------------------------------------------------------------------------------------ armor budget

# role -> spelbase, spelshld, spelarmr (role.c) and the stat percent_success uses
_ROLE_PAR = {'WIZARD': (1, 3, 10, 'intelligence'), 'PRIEST': (3, 2, 10, 'wisdom'), 'MONK': (8, 2, 20, 'wisdom')}


def _role_par(agent):
    ch = agent.character
    for name, par in _ROLE_PAR.items():
        if ch.role == getattr(ch, name):
            return par
    return None


def item_penalty(par, item):
    """What wearing `item` adds to the spell failure's splcaster (spell.c percent_success): metallic body armor adds
    spelarmr, any shield spelshld (a shield bigger than the small one also divides the chance by 4: banned), a metallic
    helmet 4 (not the helm of brilliance), metallic gloves 6, metallic boots 2."""
    from . import objects as O
    o = item.object
    metallic = 11 <= o.metal <= 17     # objects/data.py IRON .. MITHRIL
    sub = o.sub
    if sub == O.ARM_SUIT:
        return par[2] if metallic else 0
    if sub == O.ARM_SHIELD:
        return par[1] + (1000 if o.name != 'small shield' else 0)
    if sub == O.ARM_HELM:
        return 4 if metallic and o.name != 'helm of brilliance' else 0
    if sub == O.ARM_GLOVES:
        return 6 if metallic else 0
    if sub == O.ARM_BOOTS:
        return 2 if metallic else 0
    return 0


def penalty_budget(agent, par):
    """Largest total armor penalty that keeps a level 1 spell (skill Basic: +20 'special') at <= ARMOR_MAX_FAIL failure:
    chance = min(120, 11*stat/2 + 20); success = chance*(20 - s)/15 - s with s = spelbase + penalties."""
    stat = getattr(agent.blstats, par[3])
    chance = min(120, 11 * stat // 2 + 20)
    target = 100.0 * (1.0 - cfg.ARMOR_MAX_FAIL)
    s_max = (chance * 20 / 15.0 - target) / (chance / 15.0 + 1.0)
    return int(s_max) - par[0]


def limit_spell_penalty(inv, best_items, best_ac, cands):
    """Called by Inventory.get_best_armorset: drop the armor whose spell penalty buys the least AC until the set fits
    the budget. `cands[slot]` is [(ac, item)] of every wearable candidate (a lower ac is better)."""
    if not cfg.ARMOR_BUDGET:
        return best_items, best_ac
    agent = inv.agent
    ch = agent.character
    if ch.role not in _roles(ch, cfg.ARMOR_ROLES):
        return best_items, best_ac
    par = _role_par(agent)
    if par is None:
        return best_items, best_ac
    budget = penalty_budget(agent, par)
    if budget < 0:        # the base alone is too much: nothing to save
        return best_items, best_ac
    best_items, best_ac = list(best_items), list(best_ac)
    for _ in range(len(best_items) + 1):
        pens = {s: item_penalty(par, it) for s, it in enumerate(best_items) if it is not None}
        total = sum(pens.values())
        if total <= budget:
            break
        options = []
        for slot, pen in pens.items():
            if pen <= 0:
                continue
            alt = [(ac, it) for ac, it in cands.get(slot, []) if item_penalty(par, it) == 0]
            alt_ac, alt_it = min(alt, key=lambda c: c[0], default=(10, None))
            options.append(((alt_ac - best_ac[slot]) / pen, slot, alt_ac, alt_it))
        if not options:
            break
        _, slot, alt_ac, alt_it = min(options, key=lambda o: o[0])
        best_items[slot], best_ac[slot] = alt_it, (alt_ac if alt_it is not None else None)
    return best_items, best_ac


def armor_summary(inv):
    """Worn armor with the penalty it adds, for the SPELLSTAT line."""
    par = _role_par(inv.agent)
    out = []
    try:
        for name in ('suit', 'shirt', 'helm', 'gloves', 'boots', 'off_hand', 'cloak'):
            it = getattr(inv.items, name)
            if it is None:
                continue
            if it.is_unambiguous():
                out.append(f'{it.object.name}:{item_penalty(par, it) if par else "?"}')
            else:
                out.append(f'{name}?{it.text!r}')
    except Exception as e:   # diagnostics must never break the game
        out.append(f'err:{e!r}')
    return out


# ------------------------------------------------------------------------------------------------ install


def install(inventory_cls):
    assert not hasattr(inventory_cls, 'learn_spells')
    inventory_cls.learn_spells = learn_spells
    inventory_cls.read_new_spellbook = read_new_spellbook
    orig_init = inventory_cls.__init__

    def __init__(self, *a, **k):
        orig_init(self, *a, **k)
        self._spells_parsed_turn = None
        self._spells_dirty = False
        self._book_tries = {}
        self._last_book_turn = -10 ** 9

    inventory_cls.__init__ = __init__
