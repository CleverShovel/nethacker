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

# uhitm.c attack types that hit from a distance instead of on contact: breath (dragons, hell
# hounds, nagas, Ixoth, Nazgul), spit (cobras, black naga, Juiblex) and gaze (Medusa's stoning,
# Archon's blinding, the umber hulk's confusion, the pyrolisk's fire). None of these need the
# monster to be, or stay, adjacent, so a monster that onscary() scares off can still use one --
# an Elbereth doesn't stop it, only melee. (github.com/vkurenkov/nethacker@ef6acf87e265f74600b
#914060f620d06117070a3 found this the hard way: a dive rested on Elbereth at Dlvl 25 next to a
# yellow dragon and died to its acid breath; this table is our own read of monst.c's attack
# types, not their code, but their trace is what sent us looking for it.)
_RANGED_ATTACK_TYPES = ('AT_BREA', 'AT_SPIT', 'AT_GAZE')


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


def has_ranged_attack(mon):
    r = row(mon)
    return r is not None and any(a[0] in _RANGED_ATTACK_TYPES for a in r[4])


def respects_elbereth(mon):
    """False for who won't be scared off, or who can still hurt us even scared, by an Elbereth
    engraved in 3.6.6 (monmove.c onscary(), plus has_ranged_attack() above): humans and elves
    (class @), minotaurs, the Riders, the Wizard, Angels and every other lawful minion (Aleax,
    couatl, ki-rin, Archon -- though Archon's gaze bypasses this anyway), shopkeepers/guards/
    priests (all @), and anything that breathes, spits or gazes. Blind and peaceful monsters
    ignore it too, but the bot cannot see either; peaceful ones are never attacked."""
    if mon.mname in ('unknown', 'minotaur', 'Wizard of Yendor', 'Angel') or mon.mname in RIDERS:
        return False
    if ord(mon.mlet) == MON.S_HUMAN:
        return False
    if mon.mflags2 & MON.M2_MINION and _alignment(mon) > 0:
        return False
    if cfg.ELBERETH_RANGED and has_ranged_attack(mon):
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
    """Slow or sessile monsters that hurt when hit: fight them from a distance or not at all, and
    walk around them. A monster with mmove 0 (molds, most jellies) never gets to us on its own, so
    any passive attack it has is a reason to leave it alone, however small the damage looks from
    one hit -- green/red/yellow mold's ~5 expected HP missed our own damage cutoff below, but
    github.com/vkurenkov/nethacker@ef6acf87e265f74600b914060f620d06117070a3 found them worth
    avoiding too, from real deaths early at Dlvl 1 (its jf_config.py's LATE_FIXES); mmove == 0
    catches them (and the rest of monst.c's sessile fungi/jellies) without needing a name list or
    a damage number. A slow-but-mobile monster (mmove 1-3: floating eye, spotted/ochre jelly, the
    Oracle) still needs the damage cutoff, since most of monst.c's mmove-1-3 monsters have no
    passive worth avoiding at all."""
    if not cfg.PASSIVE:
        return False
    if mon.mmove == 0 and cfg.PASSIVE_SESSILE_ANY:
        return passive_attack(mon) is not None
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
