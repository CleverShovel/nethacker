# Local experiment history

These are measured outcomes from earlier runs. Avoid repeating failed ideas.

| attempt | hypothesis | public score | local validation | decision |
| --- | --- | --- | --- | --- |
| 1.1 | leave level-one farming at XL4 to find food and | 0.1086 | — | rejected |
| 2.1 | recovering HP before exploring prevents attrition deaths | 0.1512 | +0.0349 | promoted |
| 3.1 | keep distance from passive acid, paralysis, fire and stun attacks | 0.1080 | — | rejected |
| 5.1 | avoiding known petrifying corpses without gloves prevents | 0.2399 | — | rejected |
| 6.1 | starting descent at XL9 avoids attrition during the extended XL9-10 | 0.2670 | — | rejected |
| 7.1 | refusing petrifying sacrifice corpses without gloves avoids | 0.2862 | +0.0000 | promoted |
| 8.1 | three-turn tactical forecasts avoid near-term lethal exchanges | 0.2893 | — | rejected |
| 9.1 | give hunger prayers a longer cooldown even when fainting; | 0.2817 | — | rejected |
| 10.1 | always avoid shooting gas spores beside pets; blast kills | 0.3082 | +0.0000 | promoted |
| 11.1 | avoid a potentially lethal passive acid splash while injured, | 0.3494 | +0.0000 | promoted |
| 12.1 | during the dive, removing an uncursed shield makes a mattock | 0.3178 | — | rejected |
| 13.1 | the pinned peer's integrated descent and survival strategy will | 0.4102 | +0.0384 | promoted |
| 14.1 | collect fresh nearby kills for food without long detours | 0.4221 | -0.2078 | rejected by local validation |
| 15.1 | preserve usable Elbereth protection against susceptible enemies | 0.4393 | +0.0000 | promoted |

## Whole-peer baselines

These exact peer commits were evaluated locally on the same 15 public games. A high Private score need not beat this bot on the public batch.

| source | public mean | compared champion | decision |
| --- | --- | --- | --- |
| `github.com/Komershan/nethacker@6073d88ea81f05d20c46c57b8fb9a38a54bfe75e` | 0.1351 | 0.1512 | not adopted: lower local public mean |
| `github.com/vkurenkov/nethacker@a5f72915d2a27db4c3835df61196dafe1ca31d7b` | 0.2692 | 0.1512 | promoted as local baseline |

## Reviewed experiment notes

Reviewed 27 September 2026. These notes summarize completed attempts through 14;
the automatically generated history table is authoritative for newer decisions.
This is experiment context, not a required new mutation or a measured gain.

## Current baseline family: accepted whole-peer replacement in attempt 13

Attempt 13 adopted the integrated `autoascend` strategy package from
github.com/vkurenkov/nethacker@ef6acf87e265f74600b914060f620d06117070a3,
preserving its MIT license/provenance and the parent's entrypoint/arena adapter.
The package matches that pinned source except a hypothesis comment. Fourteen
existing Python modules changed and four were added. This is one explicitly
tested whole-strategy hypothesis, not evidence for each component separately.
Full Public 0.3324406823 -> 0.4101632157; fresh validation
0.0593658973 -> 0.0977981021. Promotion passed both gates.
Full15 had eight gains, four losses (2/3/4/12), three score ties; include those
losses in future screening alongside stronger games. Fresh 1036/1037 improved;
1038 tied in score but depth fell from 5 to 4. Three fresh games do not establish
general improvement for every situation.

Important differences: DIVE_XL is 8 rather than the older 10. Sacrifice safety
is retained via the petrifying-body set. Gas-spore guards cover visible pets,
peaceful monsters and recent unseen pets in ranged/melee selection. The old
HP-conditioned acid-jelly penalty is replaced with an all-HP ONLY_RANGED rule
for spotted/ochre jellies; enabled LATE_FIXES forces HAZARD_FIXES on. Inspect
current code rather than assume the older narrow guard implementation remains.
Earlier notes below describe experiments on the previous family. Do not
blindly restore their exact patches or infer that a component's old isolated
failure proves it fails inside this jointly tested replacement.

Before the package replacement, four narrow digging ideas were tested and
reverted on the OLD parent: pre-dig Elbereth regressed seed 2 with a fresh
control; pit continuation's apparent gain disappeared under fresh controls;
raising retry cap 6 -> 16 gave no reliable gain; minimum-water island digging
tied 0/4/7. Their rejection and the later package-level win are distinct facts.

## Attempt 14: Public gain rejected by fresh validation

The periodic food strategy was changed from underfoot-only collection to
corpses initially at most three path steps away and at most 15 turns old,
retaining its existing hunger/edibility/scheduling/preemption checks. The
15-turn age limit is used for initial selection, not rechecked after travel.
Full Public improved
0.4069901063 -> 0.4221446135, but fresh validation regressed
0.4013412921 -> 0.1935119149. The variant was published, not promoted. The
current champion therefore remains attempt 13 despite attempt 14's higher
Public rank. This is already a failed hypothesis on the NEW baseline family.
Future food variants need distinct evidence and fresh validation, not merely
more favorable Public samples.
Full15 had eight gains, two ties and five losses (5/6/8/9/11); 6/9/11 collapsed
to depth 1. Fresh 1039/1041 regressed from depth 29/26 to 3/1 while 1040 gained
from 3 to 26. These endpoints do not establish whether food, travel, combat or
later routing caused the changes. The initial path/age filters are not an
elapsed-time or threat limit throughout the trip.
Preliminary CASTLE_PASSAGE enablement had no gain in seven sampled games and
lost on 7; unrestricted EAT_NEARBY_CORPSES looked promising on 2/3/4/8 but
regressed the combined eight-game sample after adding 0/1/5/6. Both were
reverted. Distinguish these tested failures from narrower untested mechanisms.

## Earlier baseline family (attempts 4–12): historical findings

Attempt 11 subtracts 100 from melee priority for spotted/ochre jellies when
current absolute HP <= 6 * (species base mlevel + 1). This is a heuristic
priority penalty, not a hard ban, an acid-resistance check, or an HP-fraction
gate; it may activate at full HP when maximum HP is low. It was accepted in
the earlier family; attempt 13 uses a different rule above. Full Public:
0.3096071522 -> 0.3493565494, two gains (3/7),
one loss (2), twelve score ties. Fresh seeds 1030–1032 tied at 0.0863222983;
1030 had 91 extra turns, so the validation trajectories were not all identical.
Seed 3's depth-6 -> 27 rescue reproduced against a fresh parent in development
and in full15. Changes on 2/7/11 have also occurred in same-source reruns;
do not attribute all of them to the jelly rule without traces. Direct fixtures
covered spotted jelly at 36/100 HP and a newt at 36 HP, not every boundary.

Attempt 10 additionally enabled the existing projectile guard against a gas
spore with a visible pet in its clipped 3x3 neighborhood, independently of
HAZARD_FIXES. Full Public: 0.3013431297 parent to 0.3081941584 candidate
(+0.0068510287), three gains (0/1/8), two losses (7/9), ten ties. The fresh
1027–1029 validation tied at 0.2297637148; promotion passed. This guard was
accepted alongside the earlier sacrifice fix below. The proposed benefit is
avoiding pet blast deaths/alignment loss, but saved endpoint results do not
directly measure that causal chain. The small-sample gains on 0/1 persisted;
the broader batch reduced the net benefit substantially. A rerun of the parent
on 0/1 reproduced its reference scores, turns and depths.

Do not generalize the result to remembered pets, peaceful monsters, wand
behavior, or enabling all HAZARD_FIXES. A separate projectile overshoot/bystander
guard was tested first and reverted: 0/1/6 tied in score, but seed 2 fell from
0.445181 to 0.179100. Keep that failed mechanism distinct from the accepted
gas-spore projectile guard.

Attempt 7 added only a `GlobalLogic.can_sacrify()` guard against cockatrice and
chickatrice corpse selection without gloves. Full Public: 0.2597258454 parent
to 0.2861614452 candidate, two improvements and thirteen score ties. Fresh three
games tied at 0.4086152658, so the candidate was promoted. Its safety principle
remains relevant; inspect the new family's equivalent implementation.
It prevents a deliberate sacrifice pickup route; it is not general protection
against live petrifying monsters or every floor inspection.

## Preliminary failures omitted from the short history table

These changes were tested and reverted. Revisit only with a materially different
mechanism supported by new evidence, not merely a different favorable subset.

- Unconditional early digging-tool retention showed no gain in attempts 5 and 6.
- Quiet recovery below 80% HP before diving was mixed and regressed several
  strong games (attempt 5). Broad passive-contact avoidance lost on the full
  Public batch (attempt 3).
- Blanket earlier dive thresholds were unreliable: XL9 lost on full15 in
  attempt 6 despite a good three-game sample. XL8 also regressed. Attempt 7's
  25,000-turn/XL8 exit gained on 3/7/13 but regressed 2/4/8; a 10,000-turn/XL5
  first-level exit also had a larger regression than its gain.
- Permitting injured Valkyries to melee cold-passive jellies/molds and treating
  every species of difficulty >=8 as dangerous regressed samples (attempt 7).
- Enabling existing Elbereth recovery during the tour initially helped seed 3
  but regressed strong games in the broader nine-game sample (attempt 7).
- Exact critical-HP prayer eligibility did not improve samples 0/3/6 and
  1/7/13 in attempt 7. Do not claim it is untested.
- Broad remembered-petrifying-corpse BFS exclusion lost on full15 (attempt 5).
  Skipping all floor inspection on those squares also regressed stronger games
  (attempt 7). Blind-only inspection suppression and a guard only on the
  inspection PICKUP fallback did not improve 7/2/12. These differ from the
  successful sacrifice-selector guard above.
- Attempt 11's persistent Mines inventory cap of 580, triggered by an
  alternative squeeze-route search, tied 3/13 but regressed 8 from 0.601565 to
  0.206129; reverted. This is distinct from selective equipment handling.
- Requiring XL7+, hunger better than Weak and 70% HP for the affected fountain
  dipping branch showed no reliable gain on 9/3/8; reverted (attempt 11).
- Lycanthropy-family corpse avoidance was reverted after nine seeds without
  reliable gain (attempt 11). Fresh control explained an apparent seed-8 loss;
  seed-10 loss lacked a fresh control. Keep that uncertainty explicit rather
  than claim each changed endpoint proves a regression from the mechanism.

## Tactical lookahead: implemented, no measured Public improvement

Attempt 8 completed the requested three-turn planner and published it, but
candidate and same-run parent both scored 0.2893345546. Every full15 per-game
result field matched except wall time. No fresh validation or promotion followed.
The saved 0.2861614452 champion score from another run is not the right control
for claiming this planner improved anything.

The model and adapter were unchanged from the supplied assets. The mutator fixed
two integration defects: production StatsLogger requires explicit registration
of lookahead_plan/lookahead_override/lookahead_unsupported, and the default
TACTICAL_LOOKAHEAD flag must precede JF_CFG environment overrides. The original
fake-logger fixture missed the first defect. Production logger plus real fight2
fixtures now demonstrate an override can execute on a constructed observation.

Saved arena results contain no planner counters or action traces. Actual-game
planning and override counts remain unverified. A sample depth change that did
not persist in full15 does not prove activation. Before interpreting a further
planner variant, obtain bounded direct activation/fallback/override diagnostics;
do not broaden its safety gates merely to manufacture activity. The model
estimates hidden HP/damage/energy rather than cloning exact future game states.

## Hunger prayer cooldown: sample gain did not generalize

Attempt 9 changed only the fainting hunger-prayer cooldown from 400 to 1,000
turns. Seeds 0/1/2/3/6/7/9 improved in aggregate from 0.2165201326 to
0.2863659629, but full15 regressed from 0.2981700203 to 0.2817352023
(-0.0164348180): four gains, five losses and six ties. Major losses on 7/8/11
outweighed gains on 0/5/6/9; seeds 8 and 11 were absent from the small sample.
The fully scored candidate was published, rejected locally and not validated.
Do not repeat an unconditional 1,000-turn fainting cooldown as an untested fix.
An unconditional 1,200-turn version had already regressed the seven-game
sample. Exact HP prayer eligibility and suppressing prayers after divine anger
again showed no score gain on 0/1/2/6 and were reverted. Any new prayer change
needs a distinct observed mechanism and a comparison including strong games.

## Evaluation discipline

Attempt 12's dive mattock/removable-shield change is a measured full15 failure:
0.3278805121 -> 0.3177516954, two gains (4/10), one large loss (8), twelve ties.
Seed 4's depth-23 -> 27 rescue persisted across fresh controls, repeat candidate
and full15, but the unsampled seed 8 fell from depth 27 to 4 and outweighed it.
Both versions produced both outcomes on seed 7, so its apparent sample gain
was not attributed to the change. The candidate was published, not promoted.
The mechanism did more than briefly remove a shield to dig: armor selection
continually excluded all shields during the dive while a mattock was selected.
Future variants must distinguish enabling tool access from maintaining a
shieldless armor set. This code distinction is not a proven causal explanation
of seed 8's loss; no armor/action trace established that. Direct fixtures
covered tool eligibility, not the complete armor/takeoff sequence.

Same-source reruns have varied. Inspected seed derivation uses secret,
evaluation ID and trajectory ID, not solution digest or EXPERIMENTS.md. The
cause of variation remains unproven. Compare with the same-run full Public
parent and retain fresh local validation. Small samples and death labels alone
do not establish causal improvement. Public publication and organizer Private
scores are separate from local champion promotion.

At the 16:29 UTC organizer check, attempt 6 completed all 73 Private identities
and scored 0.0989282843 in generalist, better than our other fully covered
programs at that time. Its Valkyrie-only Private was 0.1814241152, below
attempt 4's 0.2255993128. The broader aggregate does not reverse the local
Valkyrie rejection or authorize replacing this identity's champion with it.
Attempt 8's Valkyrie Private also equals 0.2255993128; its immediate parent's
Valkyrie Private row was absent, so this is not a paired planner comparison.
These are organizer aggregates, not local validation or per-seed evidence.

Provenance: completed runs participant-0005-b906e518,
participant-0006-6d314c23, participant-0007-ed40d0f8 and
participant-0008-48e7c81b, participant-0009-9fe41255 and
participant-0010-310b06c4, participant-0011-47d99143 and
participant-0012-780726ff, participant-0013-3758e1f8 and
participant-0014-e3c0ae62; detailed host-side
reviews are in the identity's reviews/20260927-baseline-review.md and
20260927-attempt{6,7,8,9,10,11,12,13,14}-review.md.



## Blind digging protection renewal (2026-09-27)

Hypothesis: when blind, renew Elbereth after fresh damage without a lifetime
retry cap, allowing a digger to recover protection against raven attacks.
Sighted limits, engraving restrictions, and the damage gate remain intact.
Inspected pinned peer 3's identical capped digging implementation and peer 1's
Mines routing. The preliminary SKIP_SOKOBAN routing experiment matched parent
seeds 0/2/3/4 exactly and was reverted. No peer code was copied.

Final candidate: all 15 val-dwa-law-fem training seeds, evaluation-id local,
run in foreground batches of 3–5. Parent mean 0.430768417; candidate 0.439336083;
delta +0.008567666. Seeds 9 and 11 improved, seed 13 regressed, and twelve tied
in score. Full candidate results: local-eval.json. This is training-set evidence,
not a held-out improvement claim.

Direct checks passed for renewal after six attempts plus fresh damage, no
repeat without new damage, retained sighted cap, and forbidden engraving.
Imports and make_agent/reset/act interface smoke check passed.
