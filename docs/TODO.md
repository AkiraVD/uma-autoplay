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
- **Trackblazer: plays, and finishes Climax races.** All three rounds ran end
  to end unattended on 2026-09-18, holding `RANK 1`. See the Trackblazer
  section below for what is still left. Feasible by OCR - UMAT has a
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

- **`unity_begin_showdown`'s settle delay** against a live Team Zenith screen.

Cleared, kept briefly as a record of what the evidence was:

- ~~A skill row at max hint (level 5)~~ - accepted 2026-09-18 for the first
  time in any log, after 871 recorded refusals:
  `Mid-career skill buy: 1 of 1 full-discount skills for 102 of 1234 points:
  Corner Recovery o (102)` then `Buy Corner Recovery o at 102 (base 170), a
  full hint discount.` So `at_max_discount` does return true in the wild; the
  refusals were the rule working, not a dead branch. Same career: 32 refusals,
  1 mid-career acceptance, 8 end-of-career buys.
- ~~The TP bottle rule has never fired~~ - fired 2026-09-18 at 01:51:53 on a
  spark reroll with 9 TP in hand against a 30 TP cost:
  `Restoring TP so the reroll can go ahead.` / `Spending 1 of 157 TP bottles to
  afford the reroll.` / `Confirming the bottle.` The reroll then improved the
  set (blue 1* 5 white -> blue 2* 4 white) and the comparison kept the rerolled
  one, which is the documented "blue stars first, then white count" order
  deciding a case where the two metrics disagreed.
- ~~`set_skip_x2()`'s press path~~ - fired 2026-09-18 at 00:02:34 on a fresh
  Trackblazer career, the first time in any log: `Story Skip reads off;
  pressing for x2.` then `Story Skip reads x1; pressing for x2.` Two presses,
  Off -> x1 -> x2, with the state re-read between them rather than counted from
  an assumed start. The lobby followed at 00:02:43. It had never pressed before
  only because the button happened to already be x2 every previous time.

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
- **`11` reads as `1` in every year, and the Classic counter misreads badly.**
  Full unsampled sequence, 2026-09-18, Trackblazer/Maruzensky.

  The counter counts down to the **end of the current year**. Junior and Senior
  read that correctly - Senior ran `24, 23, 22 ... 3, 2` across Jan to Dec.

  The reproducible one: **Late Jul reads `1` in all three years**, where the
  truth is `11`. Junior, Classic and Senior each show `12, 1, 10, 9` across
  Early Jul to Late Aug. The leading digit is being dropped - the same failure
  `core/gains.py`'s glyph bank was built for, and worth fixing first because it
  is 3-for-3 rather than mysterious.

  Classic on top of that is simply wrong:

      Early Jan .. Late Jun   5 5 5 5 5 5 5 5 5 5 5   (true: 24 .. 13)
      Early Jul .. Late Aug   12  1  10  9            (right, bar the 1 = 11)
      Early Sep .. Late Dec   5 5 6 5 5 5 1 1         (true: 8 .. 1)

  `5` is the recurring wrong value, and `Early Oct 6` arriving after
  `Late Sep 5` counts *up*, so this is misreading and not a counter frozen by
  game state. Two theories are dead: not "an achieved goal blanks the box" - a
  lobby frame captured at Senior Early Dec *while* the goal read
  `Goal Achievedl MAX` shows the card reading `2 turn(s) left` and `check_turn`
  read 2 - and not simply the year, since Junior and Senior read fine.

  It matters because `decide_race_for_goal` compares `turn` against integers
  and the planner takes it as `opportunities`. Evidence is in `logs/log.txt.1`
  plus `logs/log.txt`, since the run rotated mid-career.
- **`Turn: -1` recurs at Late Dec**, at Junior and Senior alike, and through
  every TS Climax turn. `-1` is `check_turn`'s unreadable return, and no
  `Turn count out of range` warning is logged with it, so both the glyph bank
  and the OCR fallback found *nothing* rather than something out of range.
  Harmless today - it degrades to `Turn count unknown, skipping the goal race
  check this turn.` - but it silently disables that check on those turns.
- **No replay harness for the recorded careers.** `tests/fixtures/careers/`
  now holds a whole career turn by turn - the board, the energy the decision
  was made on, and what was chosen - but nothing feeds it back through the
  scorers. The mechanical half is small. What stops it is that "worse" needs
  defining: a different facility at a near-identical score is not obviously a
  regression, and a harness that cries wolf on every tie is worth less than
  none. See `docs/backtest.md`.
- **A long run's early log lives in `logs/log.txt.1`, not `log.txt`.**
  `utils/log.py` uses `RotatingFileHandler(maxBytes=1_000_000, backupCount=10)`,
  so any career that logs more than ~1 MB rotates mid-run. On 2026-09-18 the
  23:57 start and the whole Junior/Classic stretch ended up in `log.txt.1`
  while `log.txt` held only 01:13 onward. **Search `logs/log.txt*`** - a
  `logs/*.txt` glob matches none of the backups, and the silence is
  indistinguishable from a clean run: it made a career with 3 warnings look
  like it had none, and its `[BOT] Starting` line look missing.
- **`auto_buy_skill()` scans the whole list on every race day and buys
  nothing.** Measured 2026-09-18 across the three Climax race days: 24
  `leaving it for the end of the career` refusals and **zero** purchases, at
  ~6m51s for round 1 (three full rewind-and-scan cycles) and ~2m09s for round
  2 (one). The refusals are the documented max-hint rule working as intended;
  the cost is that the scan runs anyway. Worth an early-out when the tier list
  and hint state cannot produce a buy.
- **The career intro plays at Skip Off**, so every story line costs a ~9 s tap.
  `set_skip_x2` runs from the lobby, and deliberately - `execute.py` notes that
  a global handler would press it on race and story screens that drive it
  themselves - but the Skip button sits at the same `(567, 1052)` on the story
  UI. Measured 2026-09-18: 23:58:26 to 00:02:43, roughly 28 taps through
  `Trainee Event: Self-Introduction`, long enough to trip the "not in the
  career lobby for 20 checks" recovery once before the lobby appeared. About
  four minutes a career, so this is a small win, not a stall - worth weighing a
  story-screen-only exception against the risk that comment names.
- **The trainee aptitude warning ignores legacy inheritance.** `core/trainee.py`
  reads base aptitudes from master.mdb, but the Legacy screen raises them before
  the career starts. A Trackblazer run on 2026-09-18 warned
  `skill_distance includes long, but her long aptitude is C` while the Legacy
  parents had already lifted Long to A on screen, so the warning was wrong. It
  is warn-only, but it fires on exactly the careers that inherit hardest.
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

- ~~**A Climax race cannot be finished.**~~ It can. All three rounds ran
  unattended on 2026-09-18 with no new templates (presses at 01:35:13,
  01:39:05, 01:42:59, `RANK 1` held throughout): `race_day()` pressed
  `assets/trackblazer/ts_climax_race_btn.png` (its second branch - the generic
  `race_day_btn.png` does not match, exactly as that function's comment says),
  and the whole race collapsed into a single `Next.` The game's own readback
  recorded it: `Run in TS Climax Race 1 (EX)` / "Competed as the number 1
  favorite and won", followed by the `After the First Climax Race` scenario
  event, and the standings screen read `RANK 1 /16` with `10 pt(s)` - matching
  `CLIMAX_VP[1]`.

  So the missing lineup **Race!** (960,999) and rewards **Next** (552,1000)
  templates are **not** blockers. The six-screen walk in `screen-map.md` was
  measured by hand without the game's `Skip >>` / `Quick` buttons, which are
  present on those screens and collapse the sequence. Cutting those two
  templates is still worth doing for a deliberate handler, but nothing is
  waiting on them.
- **Auto-detect.** `saw_scenario("trackblazer", ...)` still has no caller. The
  lobby's Result Pts badge or the Shop facility button are the obvious tells.
- **Result Pts HUD.** The in-career badge reads `<Year> Result Pts` and a bare
  count - no `/target`, unlike the How to Play mock-up. Expect a digit-template
  bank rather than easyocr, as `core/gains.py` needed.
- **Race selection by points.** `decide_race_for_goal()` needs a Trackblazer
  arm, and `data/races.json` carries no grade where master.mdb does.

  **`prioritize_g1_race` is inert in this scenario**, so it is not the lever.
  The gate at `core/logic.py:1239` needs `"Progress"` *and* `"G1"`/`"GI"` in the
  criteria text, but Trackblazer's goals are Result Pts: measured 2026-09-18
  over a full career, 38 criteria lines contained `Progress` and **none**
  contained `G1` or `GI`, across 52 turns where the check was consulted. Turning
  the setting on changes nothing here - a Trackblazer arm has to match on points
  rather than on grade wording.
- **Reading the shop, and buying.** The flow is fully mapped but no code reads
  it. Note a purchase is four screens deep and three different green buttons
  share (686,997), so a reader must match on the title bar.
  `core/shop_choice.py` decides *what* to buy from rows once something can read
  them; the reader and the clicking are what is left.
- **Is a training bonus a percentage or a flat number?** Worth one measurement,
  because the two readings differ by about seven times and every Megaphone and
  Ankle Weights price depends on it. The items are worded
  `training gain +20% for 4 turn(s)` but the game's item screen displays `+20`.
  At the measured median of 15 points a training, a Coaching Megaphone is worth
  12 points (0.30/coin) as a percentage and 80 (2.00/coin) as a flat bonus.

  **How to settle it:** buy and use one Coaching Megaphone mid-career, then
  compare the `Gains:` a facility shows before and after. `check_training` logs
  those every turn, so the evidence records itself. Natural variation between
  turns is about +/-5 points while the readings predict +3 and +20 on a
  15-point facility, so one comparison is enough even without controlling the
  board. `core/shop_choice.py` encodes the percentage reading with
  `TRAINING_BONUS_IS_PERCENT`; flip it if the run says otherwise.
- **Megaphone and Ankle Weights stack**, and nothing uses that yet. Both can be
  active on the same turn, the Ankle Weights' +50% landing on one facility on
  top of the Megaphone's global bonus. For *buying* this changes little - the
  pair is worth the sum of its parts - but a use-logic that spends them on
  separate turns throws the combination away.
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
