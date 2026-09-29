# Ablation switches for ring/amulet handling (see ring_amulet_logic.py). With all three strategies
# switched off the bot plays exactly like the tree this module is installed into.

# put on an unidentified amulet when safe, to find out what it is. do_wear.c: strangulation gives an
# immediate "It constricts your throat!" that we react to by removing the amulet at once
# (Amulet_off() cancels the countdown). A cursed one cannot be #removed ("You can't.  It is cursed."),
# so a prayer must be available up front and is the fallback (pray.c: strangulation is major trouble).
AMULET_IDENTIFY_BY_WEAR = True
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

# no ring/amulet logic from this depth on: the castle (depth 25-29) and Gehennom belong to the tree's
# own levitation / magical breathing / teleport-control machinery, which wears and removes rings and
# amulets on purpose -- removing a levitation ring over the moat would drown the character
MAX_DEPTH = 24
