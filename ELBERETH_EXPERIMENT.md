# Elbereth emergency protection

One strategy change: enable `LR_ELBERETH` in `autoascend/jf_config.py`.
At critical HP, defer unknown-item last resorts when nearby monsters respect
Elbereth and the hero can use its protection. Existing exceptions retain last
resorts while blind, in Gehennom, or against enemies that ignore Elbereth.

Reviewed the matching mechanism in the MIT-licensed peer snapshot
`github.com/kefirski/nethacker@995d8f40b2d24ee09487b0e87e014ca2fcc10928`.
The implementation already existed locally; no peer code was copied.
The source is recorded in the solution manifest.

Evaluation used `python -m nethackers.arena.run`, identity `val-dwa-law-fem`,
evaluation ID `local`, with foreground batches of four seeds:
`[2,3,8,13]` and `[0,1,4,6]`. Results: `elbereth-eval.json`.

Across these eight seeds, parent mean 0.315549 -> candidate 0.370248
(+0.054699). Seed 3 improved 0.036888 -> 0.506761 (depth 1 -> 26).
Seed 4 regressed 0.050758 -> 0.018478. Six scores tied.
Fresh pristine-parent runs on seeds 3 and 4 reproduced their reference scores,
steps, turns, and death causes; see `elbereth-parent-control.json`.
This is a sample result, not a remeasurement of the full 15-seed mean.

Compilation and importing/constructing/closing the bot passed. The
`make_agent()` / `reset()` / `act()` contract and adapter are unchanged.

Discarded experiments (fully reverted): combat Elbereth immunity checking
(seeds 3,7,8,13), earlier known healing potions (2,4,8,13), and enabling
Castle passage (1,7,8,14). All matched the parent's scores and trajectories
on their samples. Only emergency protection remains enabled.
