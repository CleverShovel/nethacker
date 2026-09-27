"""Monster facts taken from NetHack 3.6.6 (NLE 1.x) instead of hand-written name lists.

Sources, in order of trust:
  * nle.nethack.permonst(): level, speed (mmove), flags, class -- read at run time;
  * monster_data.MONSTERS: attacks and alignment, generated from NLE's src/monst.c (3.6.6) and
    checked against permonst (level, speed, AC of all 380 monsters agree);
  * the C sources for behaviour: monmove.c onscary()/distfleeck(), uhitm.c passive(), mattacku.
The wiki describes newer versions than 3.6.6; nothing here comes from it unverified.
"""
import functools

from ..glyph import MON
from . import rules_config as cfg
from .monster_data import MONSTERS

PLAYER_SPEED = 12

RIDERS = ('Death', 'Famine', 'Pestilence')

# passive() in uhitm.c: only these leave a mark on a hero who just hit the monster in melee.
# acid: 1 in 2 per hit; cold/fire/shock/stun: 2 in 3 per hit while the monster survives;
# AD_PLYS (floating eye, gelatinous cube) and AD_STON (cockatrice) cost the game.
_PASSIVE_DAMAGE_CHANCE = {'AD_ACID': 1 / 2, 'AD_COLD': 2 / 3, 'AD_FIRE': 2 / 3, 'AD_ELEC': 2 / 3,
                          'AD_STUN': 2 / 3}
_PASSIVE_FATAL = ('AD_PLYS', 'AD_STON')
# a passive attack this costly (expected HP per melee hit) makes a slow monster ranged-only
PASSIVE_HAZARD_DAMAGE = 8


def _key(mon):
    name = mon.mname
    # a werecreature's human form shares its name with the animal form
    if name.startswith('were') and ord(mon.mlet) == MON.S_HUMAN:
        return name + '@'
    return name


@functools.lru_cache(maxsize=None)
def _row(key):
    return MONSTERS.get(key)


def row(mon):
    return _row(_key(mon))


def _alignment(mon):
    r = row(mon)
    return r[3] if r else 0


def respects_elbereth(mon):
    """False for who ignores a written Elbereth in 3.6.6 (monmove.c onscary): humans and elves
    (class @), minotaurs, the Riders, the Wizard, Angels and every other lawful minion
    (Aleax, couatl, ki-rin, Archon), shopkeepers/guards/priests (all @). Blind and peaceful
    monsters ignore it too, but the bot cannot see either; peaceful ones are never attacked."""
    if mon.mname in ('unknown', 'minotaur', 'Wizard of Yendor', 'Angel') or mon.mname in RIDERS:
        return False
    if ord(mon.mlet) == MON.S_HUMAN:
        return False
    if mon.mflags2 & MON.M2_MINION and _alignment(mon) > 0:
        return False
    return True


def passive_attack(mon):
    r = row(mon)
    if r is None:
        return None
    for atk in r[4]:
        if atk[0] == 'AT_NONE':
            return atk
    return None


def passive_damage(mon):
    """Expected HP lost per melee hit we land (inf when it can paralyse or petrify us)."""
    atk = passive_attack(mon)
    if atk is None:
        return 0.0
    _, adtyp, dice, sides = atk
    if adtyp in _PASSIVE_FATAL:
        return float('inf')
    chance = _PASSIVE_DAMAGE_CHANCE.get(adtyp)
    if chance is None:
        return 0.0
    dice = dice or (row(mon)[0] + 1)  # 0dN means (monster level + 1)dN in passive()
    return chance * dice * (sides + 1) / 2


def is_passive_hazard(mon):
    """Slow or sessile monsters (molds, jellies, blobs, floating eye) that hurt a lot when hit:
    fight them from a distance or not at all, and walk around them."""
    if not cfg.PASSIVE:
        return False
    return mon.mmove <= 3 and passive_damage(mon) >= PASSIVE_HAZARD_DAMAGE


def is_faster_than_player(mon):
    return mon.mmove > PLAYER_SPEED


def _turn_multiplier(mon, worst_case):
    moves = mon.mmove / PLAYER_SPEED
    return -(-mon.mmove // PLAYER_SPEED) if worst_case else moves


def _attack_damage(atk, level):
    """(average, maximum) damage of one attack that hits (mhitu.c hitmu / castmu)."""
    aatyp, _, dice, sides = atk
    if aatyp == 'AT_NONE':
        return 0.0, 0
    if aatyp == 'AT_MAGC':  # psi bolt is the common damaging spell: d(level / 2 + 1, 6)
        dice, sides = level // 2 + 1, 6
    dice = dice or (level + 1)
    average, maximum = dice * (sides + 1) / 2, dice * sides
    if aatyp == 'AT_WEAP':  # the monster's own weapon adds to the base dice
        average, maximum = average + 3, maximum + 8
    return average, maximum


def hit_chance(mon, armor_class):
    """mattacku(): the attack lands when 10 + level + AC > rnd(20); a negative AC also reduces
    the damage, which is ignored here."""
    r = row(mon)
    level = r[0] if r else mon.mlevel
    tmp = 10 + level + (armor_class if armor_class >= 0 else armor_class / 2)
    return min(1.0, max(0.0, (tmp - 1) / 20))


def damage_per_turn(mon, armor_class):
    """(expected, worst case) HP the monster takes off us in one game turn while adjacent."""
    r = row(mon)
    if r is None:
        return None
    level = r[0]
    chance = hit_chance(mon, armor_class)
    expected = worst = 0.0
    for atk in r[4]:
        average, maximum = _attack_damage(atk, level)
        expected += chance * average
        worst += maximum
    return (expected * _turn_multiplier(mon, False), worst * _turn_multiplier(mon, True))
