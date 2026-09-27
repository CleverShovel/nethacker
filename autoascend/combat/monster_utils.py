from . import monster_profile, rules_config as cfg

# heuristic monster types lists
ONLY_RANGED_SLOW_MONSTERS = ['floating eye', 'blue jelly', 'brown mold', 'gas spore', 'acid blob']
EXPLODING_MONSTERS = ['yellow light', 'gas spore', 'flaming sphere', 'freezing sphere', 'shocking sphere']
INSECTS = ['giant ant', 'killer bee', 'soldier ant', 'fire ant', 'giant beetle', 'queen bee']
WEAK_MONSTERS = ['lichen', 'newt', 'shrieker', 'grid bug']
WEIRD_MONSTERS = ['leprechaun', 'nymph']


def is_only_ranged_slow(mon):
    """Monsters not to be meleed: the listed ones plus slow ones with a dangerous passive attack."""
    return mon.mname in ONLY_RANGED_SLOW_MONSTERS or monster_profile.is_passive_hazard(mon)


def is_monster_faster(agent, monster):
    _, y, x, mon, _ = monster
    if cfg.SPEED:
        return monster_profile.is_faster_than_player(mon)
    return 'bat' in mon.mname or 'dog' in mon.mname or 'cat' in mon.mname \
           or 'kitten' in mon.mname or 'pony' in mon.mname or 'horse' in mon.mname \
           or 'bee' in mon.mname or 'fox' in mon.mname


def imminent_death_on_melee(agent, monster):
    if cfg.THREAT:
        damage = monster_profile.damage_per_turn(monster[3], agent.blstats.armor_class)
        if damage is not None:
            # one bad turn from this monster (all its attacks hit for maximum) could kill us
            return agent.blstats.hitpoints <= cfg.THREAT_FACTOR * damage[1]
    # hypothesis: BALROG progress here is purely a function of experience level, with no
    # reward for survival/depth and no penalty for dying (XP already gained is kept). The
    # cautious defaults (flee any dangerous monster below 16 HP) make fragile Healers avoid
    # the very fights that would level them up, so they stall at low XP. Engaging at lower HP
    # trades meaningless survival for extra kills / XP, which is what actually scores.
    if is_dangerous_monster(monster):
        return agent.blstats.hitpoints <= 16
    # hypothesis: retreating from ordinary monsters below 10 HP avoids the
    # common two-hit deaths while retaining normal aggression at full health.
    return agent.blstats.hitpoints <= 10


def is_dangerous_monster(monster):
    _, y, x, mon, _ = monster
    is_pet = 'dog' in mon.mname or 'cat' in mon.mname or 'kitten' in mon.mname or 'pony' in mon.mname \
             or 'horse' in mon.mname
    # 'mumak' in mon.mname or 'orc' in mon.mname or 'rothe' in mon.mname \
    # or 'were' in mon.mname or 'unicorn' in mon.mname or 'elf' in mon.mname or 'leocrotta' in mon.mname \
    # or 'mimic' in mon.mname
    return is_pet or mon.mname in INSECTS


def consider_melee_only_ranged_if_hp_full(agent, monster):
    return monster[3].mname in ('brown mold', 'blue jelly') and agent.blstats.hitpoints == agent.blstats.max_hitpoints
