# Ablation switches for ring/amulet handling (see ring_amulet_logic.py). With all three strategies
# switched off the bot plays exactly like the tree this module is installed into.

# put on an unidentified amulet when safe, to find out what it is. do_wear.c: strangulation gives an
# immediate "It constricts your throat!" that we react to by removing the amulet at once
# (Amulet_off() cancels the countdown). A cursed one cannot be #removed ("You can't.  It is cursed."),
# so a prayer must be available up front and is the fallback (pray.c: strangulation is major trouble).
# OFF: measured on five leaders it was never better (-1.5% .. -19%): the trial rarely identifies the
# amulet and always takes it off again, so it costs a prayer's timeout and turns for nothing
AMULET_IDENTIFY_BY_WEAR = False
AMULET_WEAR_MIN_HP_FRAC = 0.6
AMULET_WEAR_SAFE_RADIUS = 4

# wear increase accuracy/damage, protection rings and the reflection amulet (do_wear.c: they only
# change combat resolution) only while a hostile is within ENGAGE_RADIUS, take them off afterwards
COMBAT_ONLY_WEAR = True
ENGAGE_RADIUS = 6
DISENGAGE_COOLDOWN = 10

# take off non-essential rings/amulets once Hungry or worse (eat.c gethungry(): 1 nutrition per 20
# turns per worn ring/amulet), put them back once fed
NUTRITION_REMOVE = True

# wear the rings the character STARTS with and keep them on. u_init.c ini_inv(): only the Wizard has
# any (two random rings); every starting item is created uncursed with its BUC known, so they can
# always be #removed, and levitation / hunger / aggravate monster are never generated for them.
# What is left that hurts is polymorph (allmain.c: 1 in 100 per turn) -- a polymorph status takes
# every starting ring off again for good -- and teleportation (1 in 85 per turn, within the level).
# OFF by default: measured on four wizard leaders, mean -0.024 (one better, three worse)
STARTING_RINGS_WEAR = False

# --- identifying rings/amulets by reading scrolls (scroll_identify.py) ---
SCROLL_IDENTIFY = True
# safe moment: HP at least this and at least this fraction of max (earth: up to d20; a blessed fire on
# ourselves: 15-25), nobody in sight, a prayer available, no shop in view
SCROLL_MIN_HP = 26
SCROLL_MIN_HP_FRAC = 0.9
SCROLL_READ_COOLDOWN = 25
# never read a scroll that is less likely than this to be identify (price-narrowed candidates)
SCROLL_MIN_P_IDENTIFY = 0.10
# read only when P(identify) >= SCROLL_SEVERE_COST x P(severe outcome), severe = punishment, a cursed
# create monster / genocide, amnesia weighted by what it costs this character (scroll_identify.py)
SCROLL_SEVERE_COST = 3.0
AMNESIA_WEIGHT_PLAIN = 0.1     # the level map and some discoveries
AMNESIA_WEIGHT_CASTER = 0.3    # + rn2(n + 1) of the n known spells (Priest, Healer, Monk)
AMNESIA_WEIGHT_WIZARD = 0.6    # a Wizard's only attack is the force bolt spell he starts with
# wear identified rings/amulets that help whenever they are worn (the combat-only ones have their own rule)
WEAR_IDENTIFIED = True
ALWAYS_WEAR_RINGS = ('slow digestion', 'free action', 'poison resistance', 'gain constitution', 'gain strength')
ALWAYS_WEAR_AMULETS = ('amulet of life saving', 'amulet versus poison')

# no ring/amulet logic from this depth on: the castle (depth 25-29) and Gehennom belong to the tree's
# own levitation / magical breathing / teleport-control machinery, which wears and removes rings and
# amulets on purpose -- removing a levitation ring over the moat would drown the character
MAX_DEPTH = 24
