# TODO

Open work only. Everything resolved has been cut - the write-ups are in git
history (`git log -p docs/TODO.md`) and the measured screen layouts are in
`screen-map.md`.

## Scenarios

- **Unity: choose the team-race opponent.** The bot confirms whatever the game
  preselects. Everything needed is on screen - `Rank 23/28/40`, grades `E/F/G`,
  and a per-discipline circle/triangle/cross row in the confirmation modal.
  Beating a harder team raises team rank, which drives facility levels; losing
  it lowers them.
- **Trackblazer: plays, but cannot finish a Climax race.** See the Trackblazer
  section below for what exists and what is left. Feasible by OCR - UMAT has a
  full OCR implementation - but not a liftable module: they fork the whole bot
  per scenario, and the genuinely new parts are the shop database (now
  generated from master.mdb), item purchase and item use.

## master.mdb

`core/masterdb.py` backs trainee data, training costs, skill names, costs and
rarity, and the server's pickers. Two uses are still open:

- `data/races.json` and `data/skills.json` still go stale on patches.
  `text_data` categories 28/29/32 are race names, 47/48 skill names.
- Category 181 (12,758 event names) would canonicalise event-name OCR the way
  skill names are canonicalised now.

## Untested paths, each waiting on a screen that has not appeared

- **`set_skip_x2()`'s press path.** The button was already x2 when the handler
  first ran, so it read the state and returned without pressing. Zero
  occurrences of "Story Skip reads" in any log, so it still has never pressed.
- **A skill row at max hint (level 5).** Still only ever watched refusing: all
  871 of the logged lines are `is not at max hint ... leaving it for the end of
  the career`, and not one is an acceptance.
- **`unity_begin_showdown`'s settle delay** against a live Team Zenith screen.

Cleared on 2026-09-17, kept briefly as a record of what the evidence was:

- ~~`login_bonus` has never fired live~~ - fired at 22:39:51 during a daily
  reset, and the reload resumed the career correctly through Continue Career.
- ~~A three-option event~~ - six seen, including `Lovely Training Weather` and
  `New Year's Shrine Visit`, all with the first icon at `top=513`, which is
  exactly what `option_count()` predicts for three.
- ~~The Effects-button fallback~~ - fired 22 times
  (`Choices panel is not open; using the Effects button`), so "Always display
  choice effects" was evidently off for part of a run.

## Numbers that are reasoned rather than measured

Worth deriving properly if the behaviour ever looks wrong:

- Outings: `MOOD_POINTS`, `HINT_POINTS`, `CONDITION_CLEAR_POINTS`,
  `BOND_POINTS`, `TRAINING_ENERGY_COST`. Only the energy anchor has a
  derivation behind it, and the readback checks energy alone.
- The wit band's `(30, 70)` edges and its 0.9 per rainbow.
- `MAX_GAUGE_FRACTION = 0.75`. uma.guide gives a charging gauge no weight at
  all, so anything from 0 to just under one burst is defensible.
- `core/skill_score.py`'s weights are the source optimizer's, not measured here.

## Smaller open items

- **A career that ends with chain steps left** has spent outings on a chain it
  never cashed. `outings.steps_remaining()` exists but nothing calls it.
  `logic.career_ending()` now names the last five turns off the year string,
  which is the signal such a check would hang from; an exact turns-left count
  is still not derived anywhere, and the turn counter cannot supply one - it
  counts down to the next race day rather than the end of the career, and reads
  -1 (unreadable) throughout Trackblazer's climax.
- **Only one friend card has ever been seen in a deck.** With two the panel
  lists both and the reader takes the first row.
- **`LOG_PANEL_REGION` assumes the Log tab is selected** in the right-hand
  panel. Left on Sparks or Agenda, the readback quietly finds nothing.
- **The readback checks energy only.** Hints, skill points and condition clears
  are parsed and logged but never judged - locating the right block of a
  scrolling Log proved unreliable.
- **The end-of-career stop message does not say which template matched.** The
  branch is `team_rank or game_nav` and both match on the home screen, so the
  log cannot say which caught it. Naming it would make the next such run
  self-evidencing.
- **Dialogue-only events still reach `select_event`.** `event_choice_1.png`
  matches a scenario event with no choices at all, costing an OCR pass and two
  fuzzy matches per dialogue event. Harmless, and logged at debug.
- **The failure-label OCR fallback** fires on about 7% of reads - 8 of 110 in a
  full career - and degrades safely, since an unreadable failure is treated as
  unsafe. Leave it unless the rate climbs.
- **`disable_singlemode`** is carried through `skill_score` but not used as a
  filter. 354 of 577 purchasable skills set it, which suggests "not buyable in a
  career", but that reading is unverified and filtering on a guess would hide
  skills that really are on offer.
- **Skill costs on screen are not read by the planner.** It takes them from the
  database, which assumes the OCR'd name resolved to the right skill.

## Trackblazer

A full career was played on 2026-09-17, so most of this section's screens are
now measured; `screen-map.md` has the geometry. What exists:

- `core/scenarios.py` holds per-mode values and `race_day()` reads them, so a
  Climax race day clicks the right button instead of URA's position.
- `data/trackblazer_shop.json` is generated from master.mdb: 53 real items with
  costs and decoded effects, replacing 25 guessed ones.
- `core/trackblazer.py`'s tables are checked against the game - `CLIMAX_VP` at
  six placements, `POINTS_BY_GRADE` at G3, `TARGETS` at Junior turf.

Still to do:

- **A Climax race cannot be finished.** `race_day()` starts one, but the
  full-width lineup **Race!** (960,999) and the rewards **Next** (552,1000)
  have no template - the best existing matches score 0.475 and 0.528, so both
  need cutting - and `race_prep()`/`after_race()` cannot drive those screens.
  The six-screen sequence is written up in `screen-map.md`.
- **Auto-detect.** `saw_scenario("trackblazer", ...)` still has no caller. The
  lobby's Result Pts badge or the Shop facility button are the obvious tells.
- **Result Pts HUD.** The in-career badge reads `<Year> Result Pts` and a bare
  count - no `/target`, unlike the How to Play mock-up. Expect a digit-template
  bank rather than easyocr, as `core/gains.py` needed.
- **Race selection by points.** `decide_race_for_goal()` needs a Trackblazer
  arm, and `data/races.json` carries no grade where master.mdb does.
- **Reading the shop, and buying.** The flow is fully mapped but no code reads
  it. Note a purchase is four screens deep and three different green buttons
  share (686,997), so a reader must match on the title bar.
- **Epithets.** The stat awards are documented from seriru's guide (+30/+20/+10
  tiers) but nothing models them; they are the scenario's real stat engine.
- **Nine mode gates** still branch inline on `GRAND_CONCERT_SEEN`/`UNITY_SEEN`
  rather than going through `core/scenarios.py`. Moving `state.py:608` needs
  the `scenarios` -> `state` import inverted first.
- **Best Umamusume Award** at the end of each Late December turn, which raises
  the trainee's Unique Skill level. Not in any guide consulted; found by reading
  the in-game How to Play.

## Parked: API / packet mode

UMAT's chain is UMAT -> HTTP localhost -> KUC / uma_viewer -> captured packets
-> CarrotJuicer, and CarrotJuicer hooks the decryption function in
libnative.dll - DLL injection, not passive sniffing. KUC is not publicly
available, the capture tooling targets Android or the DMM client rather than
Steam Global, and injecting into the game process is materially more detectable
than reading pixels and moving the mouse.

Worth revisiting only if Trackblazer's shop inventory, coin balance and grade
points turn out to be genuinely unreadable on screen.
