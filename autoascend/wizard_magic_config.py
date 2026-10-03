"""Flags of the Wizard spell patch (wizard_magic.py). Written from NetHack 3.6.6 zap.c (force bolt: hits when
rnd(20) < 10 + target AC, 2d12 damage, 'Boing!' for a magic-resistant target), spell.c (5 Pw per spell level,
a failed cast costs half of it and is decided before the direction prompt) and allmain.c (Pw regeneration)."""

# master switch: parse the Wizard's spell menu once and cast force bolt in fights
CAST_FORCE_BOLT = True
# diagnostics: False = the strategy runs but never opens the cast menu
PARSE_ENABLED = True
# a cast needs 5 Pw (level 1 * 5); keep CAST_RESERVE_PW more than that in the pool
CAST_MIN_PW = 5
CAST_RESERVE_PW = 0
# the parsed menu shows the failure percentage (Wizard in a robe/cloak is ~0-5%)
CAST_MAX_FAIL = 0.20
# read the spell menu again this often (turns) and right after a failed cast: the failure rate follows the armor
REPARSE_TURNS = 100
# how far along a line a target may be (the bolt reaches like a wand of striking, 7-13 squares)
CAST_RANGE = 6
# 'always': every non-weak monster in line; 'threat': only dangerous monsters or when HP is below the ratio
CAST_MODE = 'always'
CAST_THREAT_HP_RATIO = 0.7
# weak monsters (fight_heur.WEAK_MONSTERS) are left to melee unless HP is below this ratio
CAST_WEAK_HP_RATIO = 0.5
# priorities live on fight_heur's scale: a melee attack is ~16, a ranged one 11, a wand zap -5..+10
CAST_BASE = 17
CAST_DANGEROUS_BONUS = 3
CAST_LOWHP_BONUS = 0
CAST_DISTANCE_PENALTY = 1.5
# what a pet / peaceful further along the bolt's line costs (fight_heur uses 20 and 200 for wands)
CAST_PET_PENALTY = 40
CAST_PEACEFUL_PENALTY = 200
