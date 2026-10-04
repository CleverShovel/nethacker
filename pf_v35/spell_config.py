"""Flags of the spell patch (spell_magic.py). Written from NetHack 3.6.6 zap.c / spell.c / potion.c / u_init.c / allmain.c
(see the module docstring of spell_magic.py for the exact rules that were read)."""

# ---- force bolt (as in wizard_magic_port; CAST_BASE/DANGEROUS/LOWHP are the values of the measured merged_wm3 build)
CAST_FORCE_BOLT = True
PARSE_ENABLED = True
CAST_MIN_PW = 5
CAST_RESERVE_PW = 0
CAST_MAX_FAIL = 0.20
REPARSE_TURNS = 100
CAST_RANGE = 6
CAST_MODE = 'always'
CAST_THREAT_HP_RATIO = 0.7
CAST_WEAK_HP_RATIO = 0.5
CAST_BASE = 17
CAST_DANGEROUS_BONUS = 3
CAST_LOWHP_BONUS = 0
CAST_DISTANCE_PENALTY = 1.5
CAST_PET_PENALTY = 40
CAST_PEACEFUL_PENALTY = 200

# roles whose spell menu is read (Character role names, upper case)
PARSE_ROLES = ('WIZARD', 'PRIEST', 'MONK')

# ---- non-combat self spells (emergency_strategy hook)
SELF_SPELLS = True            # master switch of the self-cast hook
HEAL_ENABLE = True            # healing / extra healing (direction '.' = at oneself)
HEAL_HP_FRAC = 0.5            # cast when HP <= this fraction of max ...
HEAL_NEAR_DIST = 6            # ... and a hostile is within this walking distance, or HP <= HEAL_ALONE_FRAC
HEAL_ALONE_FRAC = 0.34
HEAL_MIN_MISSING = 8          # healing is d(6,4): not worth Pw for less
EXTRA_HEAL_MISSING = 22       # extra healing (d(6,8), 15 Pw) when at least this much is missing and Pw allows
HEAL_MAX_FAIL = 0.25
PROTECT_ENABLE = True         # protection: AC bonus of log2(XL)+1 on the first cast, decays 1 per 10 turns
PROTECT_MIN_XL = 3            # XL1 gives +1 only
PROTECT_DIST = 2              # a hostile this close (walking distance)
PROTECT_MIN_DEPTH = 3         # on Dlvl 1-2 only against dangerous monsters or when HP < PROTECT_HP_FRAC
PROTECT_HP_FRAC = 0.6
PROTECT_COOLDOWN = 30         # turns between casts
PROTECT_MAX_FAIL = 0.25
PROTECT_RESERVE_PW = 5        # keep a force bolt's worth of Pw
HASTE_ENABLE = True           # haste self: Very Fast for ~100 turns, 15 Pw
HASTE_DIST = 5
HASTE_COOLDOWN = 110
HASTE_MAX_FAIL = 0.25
HASTE_RESERVE_PW = 5
CURE_BLIND_ENABLE = True      # cure blindness, 10 Pw
BLIND_MAX_FAIL = 0.25
SELF_FAIL_LOCKOUT = 3         # turns after a failed attempt before the same spell is tried again

# ---- learning new spells from found spellbooks (Wizard's 'difficult to comprehend' prompt tells the level band)
LEARN_ENABLE = True
LEARN_ROLES = ('WIZARD',)
LEARN_MAX_SEVERE = 0.05       # P(failed read with blindness/confusion/poison/explosion) accepted
LEARN_MIN_SUCCESS = 0.55      # P(the read succeeds) accepted
LEARN_MAX_TRIES = 3           # reading attempts (an interrupted study is continued) per book kind and XL
LEARN_MIN_HP_FRAC = 0.7
LEARN_COOLDOWN = 20           # turns between book attempts
LEARN_DEBUG = False
# a spell is forgotten 20000 turns after it was learned ('(gone)'); study its book again when this much is left
REFRESH_ENABLE = True
REFRESH_AT_PCT = 10

# ---- armor budget: do not wear the armor whose spell penalty (metallic suit/helmet/gloves/boots, shields) pushes the
# failure of a level 1 spell above ARMOR_MAX_FAIL; the AC lost is minimal first (get_best_armorset)
ARMOR_BUDGET = True
ARMOR_ROLES = ('WIZARD',)
ARMOR_MAX_FAIL = 0.20

SPELL_DEBUG = False
