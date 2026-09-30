## Purpose

Standalone symbolic NetHack ArenaBot derived from Jawfish's prayer-model and Archeologist-digging seed. This child tests observation-driven Healer casting alongside the primary parent's bounded natural recovery. The objective is mean official NetHackers progression; this child's fitness is unknown until outer evaluation. Licenses and provenance remain intact.

## Repository Map

- `bot.py`: public factory and ArenaBot reset/act/close facade.
- `arena_adapter.py`: observation/action queues, policy worker, restart and game-state transfer.
- `autoascend/agent.py`: terminal observation parsing, atomic commands, combat, emergency ordering and search receipts.
- `autoascend/spell_healing.py`: observed spell parsing, bounded cast transactions, retry state and diagnostics.
- `autoascend/recovery.py`: quiet-state eligibility, HP-loss tracking and bounded natural recovery.
- `autoascend/global_logic.py`, `strategy.py`: progression objectives and nested survival preemption.
- `autoascend/dive_logic.py`, `castle_logic.py`, `castle_power.py`, `valley.py`: descent, digging, shelter and specialized travel.
- `autoascend/nhmodel/`: prayer model, recent unseen-attack evidence and static monster knowledge.
- `autoascend/character.py`, `item/`, `monster_tracker/`, `glyph/`, `objects/`, `level.py`: symbolic observation state and game knowledge.
- `autoascend/exploration_logic.py`, `combat/`, `soko_solver/`: exploration, combat ranking and Sokoban.
- `tests/test_spell_healing.py`, `test_spell_observations.py`, `test_unseen_prayer.py`, `test_recovery.py`: menu transactions, real parser/atomic-method fixtures, emergency ordering, recovery and restart checks.
- `.gigaevo/EXPERIMENT.json`: implementation report. `LICENSE`, `SEED_PROVENANCE.json`, `nethackers.solution.json`: provenance and arena metadata.

## Architecture and Data Flow

Arena observations enter `Bot.act`; the adapter resumes the blocking policy worker and returns one legal action index. Agent.step/update decodes terminal messages and popups and feeds command-specific input generators before updating symbolic state. Runtime decisions use supplied observations and static knowledge only.

Eligible injured Healers open the current spell menu after higher-priority emergencies. Parsing accepts exact retention, validated intervals such as `71%-80%`, and forgotten spells. The interval's lower endpoint determines whether memory remains. Selection uses current letters, displayed failure, spell level, available energy and missing HP. Unknown or invalid rows are unusable. If the first page has no eligible spell, traversal follows explicit observed pagination, up to eight pages; repeated pages cancel.

The cast iterator stays inside one atomic operation through observed `--More--`/misc message pages before the menu, after selection and after self-direction. This handles hunger and fading-recall messages that previously caused cancellation before the direction prompt. Self-direction is sent only for a current direction prompt. Eight message acknowledgements bound the whole transaction. Cancellation rechecks observations, clears newly exposed prompts with at most three escapes, and raises AgentPanic for inherited resynchronization if a chain cannot finish. Failure retains a 20-turn retry deadline. Completion and an advanced turn allow the existing immediate retry; unchanged-turn completion retains backoff.

Diagnostics distinguish `directed` (self-target input sent), `completed` (the exchange ended without an observed pending prompt), energy expenditure and net HP change. Neither completion nor net HP change proves useful replenishment. The first 64 `HEAL_MENU` records per game reach stderr and the latest 64 remain in a ring. They contain observed rows, rejection reasons, input sequence, message count, HP/energy, elapsed turns and retry deadline. Recording occurs before atomic-exit callbacks. Restart copies guards and diagnostics into a fresh controller; no pending generator transfers. A new game resets them.

Natural recovery remains below survival, food, combat, spells and descent escape. It starts below 70% HP and aims for 90% in observed quiet. HP loss blocks rest for five turns. Each search permits outer preemption; no healing for 30 turns, 200 elapsed turns, 200 searches, four consecutive same-turn responses or a failed command receipt stops recovery with backoff. Tool-assisted dives and unfinished own pits remain with their specialized descent controller. Spell observations update this existing recovery state, and emergency/recovery callbacks resume only after the cast transaction closes.

## Entrypoints and Interfaces

`bot.make_agent()` returns the unchanged ArenaBot interface: `reset(initial_observation)`, `act(observation) -> int`, `close()`.

`parse_healing_spells(lines)` and `choose_healing_spell(spells, energy, missing_hp)` are pure functions. `SpellHealing.ready(...)` checks injury/resources/retry; `cast(agent, command)` returns transaction completion; `adopt(previous)` copies game-owned guards and diagnostic state. No new runtime dependencies or external services are used.

`Recovery.observe(blstats)`, `rest()` and `adopt(previous)` retain the primary-parent interfaces. `Agent.search(return_result=True)` returns a SearchResult for one search; legacy search callers retain their prior interface.

## How to Run and Validate

From the candidate root:

```sh
python -m unittest discover -s tests -q
/home/projects/atlas_cyber/gigaevo-summer-school/.venv/bin/python /home/projects/nethack/gigaevo-summer-school/problems/nethack/repo_benchmark.py --candidate-repo . --mode syntax
git diff --check
```

All 86 focused tests pass. Syntax validation compiled 55 Python files; inherited regex escape warnings remain. Tests use synthetic observations through production parser, step/update and atomic methods without host NLE. They cover interval retention, current letters, pagination, missing capability, real failure, intervening message pages, unfinished direction prompts, bounded stalls, outcome accounting, receiver recovery observations, emergency priority and restart continuity.

The single permitted smoke was consumed using:

```sh
/home/projects/atlas_cyber/gigaevo-summer-school/.venv/bin/python /home/projects/nethack/gigaevo-summer-school/problems/nethack/repo_benchmark.py --candidate-repo . --mode smoke --workers 1
```

Both games completed 512 actions without reported bot errors, at 358 and 239 turns, in 8.880215 seconds total. Inspected artifacts: `/home/projects/nethack/gigaevo-summer-school/outputs/nethack_smoke/68a3ff681f3d4a0ba6deb8efb47caca5/arena.log` and `episodes.json`. The smoke covers Valkyrie and Archeologist, not Healer casting. Its partial-suite invalid-fitness sentinel is not a child score. No further gameplay is authorized in this mutation; full evaluation belongs to GigaEvo.

## Current Strategy

Keep inherited progression, preparation, exploration, digging, combat and prayer. Attempt spell healing only for Healers with at least six missing HP, at most 65% HP and at least five energy. Confusion, stun, hallucination, polymorph, Weak-or-worse hunger and Stressed-or-worse burden block attempts. Healing failure must be at most 20%; extra healing at most 15%, with at least 25 missing HP. Deadly-status cures, critical potions, prayer and inherited unseen-danger downstairs escape retain priority. Casting complements the existing natural recovery rather than introducing new global scheduling or exposure ranking.

## Known Limitations

- Casting consumes energy/nutrition and can fail or expose the hero to another attack. This experiment does not change threat ranking, equipment or spell learning.
- Marked message pages are acknowledged; unmarked unexpected messages cause conservative cancellation. Unknown layouts and exceeded bounds resynchronize rather than assume success.
- Menus use the first eligible page, not a global optimum across pages. Forgotten or unreliable spells remain unavailable.
- Natural recovery still consumes nutrition and cannot guarantee absence of hidden danger. Descent-specific rests retain inherited behavior.
- Diagnostics are bounded and lack arena episode identifiers. Energy expenditure, command completion and HP gain are distinct observations; none establishes improved progression.
- Synthetic tests and non-Healer smoke cannot establish live Healer success or additive benefit on the natural-recovery parent.

## Mutation Notes

Implemented selector-led attempt `attempt_9ab7bed91dce443c93aa67f4e4cf9e1e`, `material_change=false`. Primary parent `ca8940a5` at `3301676a81b41f226d6667c2172d69595f490e5d` has current fitness 0.28943425074190154. Donor `f4565b6f` at `4d7cdbbaaf0787da0b7c4b80e1b4eb990c95fbdf` has current fitness 0.2692213788899086 and supplies capability evidence, not the comparison baseline.

Read the task, immutable plan, memory index and attempt summaries, relevant original assessments, both parent dossiers and relevant full sources, benchmark feedback and captured arena/episode files. Early healing attempt `attempt_f0653f02c6dc4f3d857ad92fefd38a21` lacked live replenishment evidence. Donor attempt `attempt_bde49873a47d4d9f957af4d3d0ebb79c` captured 196 directed transactions and 194 net HP gains among 268 records, but its aggregate gain over its own base was only 0.000152249. Records such as arena.log:122 show a hunger message followed by ESC, energy loss, unchanged HP and a remaining direction prompt. Primary-parent recovery attempt `attempt_c0205ba8348344e4971bfcc563281e79` established useful natural recovery on this receiver. Combining these mechanisms is a new interaction test, not an assumption that donor gains transfer.

Transferred the donor menu parser, bounded pagination, diagnostics and restart adoption. Refined the cast transaction to acknowledge current message pages, verify direction completion, and bound cancellation; added raw-observation regression and integration tests. These refinements address a risk explicitly named in the plan, so the central hypothesis is unchanged. No exposure-policy transplant, broad scheduler rewrite, score-only guard, benchmark/evaluator/sandbox change, dependency change or experiment-memory write was made. The implemented phenotype is left for outer comparison regardless of eventual fitness.
