# Ablation switches for the data-driven monster rules (see monster_profile.py). Each rule can be
# turned off on its own; with all of them off the bot plays exactly like its parent.
ELBERETH = True        # who ignores Elbereth follows NetHack 3.6.6 onscary(); no Elbereth next to those
ELBERETH_RANGED = True # ... and Elbereth doesn't stop a breath/spit/gaze attack even from a scared monster
PASSIVE = True         # slow monsters with a dangerous passive attack (monst.c AT_NONE) are ranged-only
PASSIVE_SESSILE_ANY = True  # ... including a sessile one (mmove 0) whose passive damage looks small alone
SPEED = True           # "faster than us" is mmove > 12 from the game data, not a list of name fragments
THREAT = True          # "about to die in melee" compares HP with the monster's worst-case damage per turn
THREAT_FACTOR = 1.0    # hp <= THREAT_FACTOR * worst-case damage of one monster turn
