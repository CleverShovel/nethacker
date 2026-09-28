# Ablation switches for ring/amulet handling (see Inventory.identify_amulet_by_wear/
# wear_combat_only_rings_amulets/shed_rings_amulets_when_hungry in item/inventory.py). Each rule
# can be turned off on its own; with all of them off the bot plays exactly like its parent (no
# ring/amulet wear/remove logic at all, same as before this feature existed).

# put on an unidentified amulet when safe, to find out what it is. do_wear.c: strangulation gives
# an immediate "constricts your throat" we react to by removing it at once (Amulet_off() cancels
# the countdown); restful sleep gives no such message, so this is a weaker, structural safety net
# (remove again next tick regardless) rather than a reactive one. Rings are NOT covered by an
# equivalent flag: do_wear.c's Ring_on() has no message at all for its dangerous types (teleport/
# hunger/aggravate monster/polymorph), so "wear and see" has no safety net for rings.
AMULET_IDENTIFY_BY_WEAR = True
# minimum HP fraction and hostile-monster-free radius required before trying an amulet on
AMULET_WEAR_MIN_HP_FRAC = 0.6
AMULET_WEAR_SAFE_RADIUS = 4

# hold onto a ring/amulet that ONLY affects combat resolution (increase accuracy/damage, AC
# protection, reflection) only while a hostile monster is within ENGAGE_RADIUS; take it off
# otherwise, since -- unlike resistances or sustain abilities -- it does nothing for us between
# fights and still costs nutrition (eat.c gethungry(): 1/20 turns per ring, 1/20 per amulet).
COMBAT_ONLY_WEAR = True
ENGAGE_RADIUS = 6
# turns to wait after the last hostile leaves ENGAGE_RADIUS before taking the item back off, so a
# monster hovering at the edge of the radius doesn't cause a wear/remove flip every turn
DISENGAGE_COOLDOWN = 10

# take off non-essential rings/amulets once Hungry or worse, to stretch remaining food; re-equip
# once fed again. Never touches a worn amulet of life saving, or an item already managed by
# COMBAT_ONLY_WEAR above.
NUTRITION_REMOVE = True
