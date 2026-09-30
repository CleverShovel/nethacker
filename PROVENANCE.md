# Astra human Healer

Derived from the v272 AutoAscend policy by vlomshakov, with upstream lineage retained in nethackers.solution.json. AutoAscend and upstream contributions retain their licenses.

Uses the observation-driven survival and movement principles of kenforthewin/nethack_astra; no LLM, remote terminal or model API is used at runtime.

v1 enables the existing Mines tool-acquisition route for human Healers. All existing healing, recovery, branch, combat and return checks remain. Target identity is hea-hum-neu-fem; results must be measured separately from the gnome policy.

v5 independently tests v1 with the tool expedition at experience level 4 instead of 3. This compares shorter food exposure against better preparation for the hostile human Mines. All other behavior is unchanged.

v6 fixes the observed missing O import in food-making armor handling and refreshes casting odds after removing a piece of armor, avoiding unnecessary further stripping. Adapted from previously tested gnome development fixes v201/v203, now evaluated independently on humans.

v9 enables the inherited floating-eye combat filter. It preserves the existing fed, nearly-full-health, lone-eye stall escape and ranged/blindfold options.

v14 extends the existing close-threat sleep-wand rule to visible wererats, werejackals and werewolves before health drops below60%. Human diagnostic losses repeatedly engage wererats until potions run out. Keeps the existing charge, resistance, cooldown, alignment and ray-safety checks.

v23 independently applies bounded pet separation only when still XL1 after1200 turns. The global early separation in v12 was rejected. This tests the repeated XP1 stalled-leveling failure while preserving the pet for ordinarily progressing games. Existing health, visible-enemy, known-stair and300-turn budget guards remain.

v29 repairs a bypass in the existing combat-stall tracker: when all actions are filtered out, report a non-contact blocked action before searching. Diagnostics show two adjacent floating eyes holding fight2 stationary for8000turns. The existing passive-monster release timeout, hunger/emergency and floating-eye safety guards remain; no forced unsafe melee was added.
