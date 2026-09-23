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
- **The `Session Error` walk-back**, against a live dialog. Handled since
  2026-09-22: the dialog is recognised by template
  (`assets/ui/session_error.png`, 9 positives at 1.000 against a best negative
  of 0.577 over 1998 frames) and the branch presses `Title Screen` (553,704),
  taps the title at (960,940) and hands the reload to `RESUMING_CAREER`, which
  is the date-changed path's own proven walk. What is unproven is only the two
  waits - 10s for the reload and 12s after the title tap - which are the
  uma-launch skill's settle figures rather than anything measured here.
  Recognition needs no further work; timing might.

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

- ~~**A frozen client is invisible to `game_panel_blank()`.**~~ **Detected
  since 2026-09-23.** Three occurrences in three days, none of which the
  stddev check could see, because it looks for a *flat* panel and these hold
  full artwork: 2026-09-21 as the Japanese Derby started (~7.5h uptime),
  2026-09-23 01:52 inside a support card event (~3h14m), and 13:41 inside the
  "Tracen Idol" story event (~6h09m). Each cost ~35 minutes of blind tapping
  before `LOBBY_LOST_LIMIT` stopped the bot, and then the night.

  `panel_digest()` compares the panel exactly, and the two states do not
  overlap at all, so there was no threshold to tune: measured on the live game
  while the bot played, consecutive grabs three seconds apart differed by
  **41,709 to 785,636 pixels and were never identical**, while a frozen client
  is byte-identical every time. `FROZEN_PANEL_LIMIT` is 10 checks (~90s), and
  the check runs on **every** pass rather than only when the lobby is lost -
  a freeze *in* the lobby keeps matching the Tazuna hint, so the not-in-lobby
  recovery where `game_panel_blank` lives would never be reached.

  **Recovered automatically since 2026-09-23**, behind `restart_on_freeze`
  (off by default - it ends the game process). `core/recover.py::restart_client`
  closes the client, launches it, waits for the window, taps the title screen
  and hands back to `career_lobby()` with `RESUMING_CAREER` set, so the career
  resumes through Continue Career rather than being read as a finished one -
  the same hand-off the daily reset and the Session Error dialog already make.
  Bounded at `FREEZE_RESTART_LIMIT` = 5 per run: a restart costs about two
  minutes, and a game that launched and froze at once would otherwise loop on
  it all night. **Not yet proven against a live freeze** - the pieces are the
  ones `tools/umatool.py` has used all along, and the hand-off is the one the
  other two reload paths use, but the whole walk has only been driven by hand.

  Uptime is not the trigger - 3h, 6h, 7.5h. All three froze during a **scene
  transition**: a race starting, a support card event, a story event.
- **A resume after a crash does not survive `career_start`** *(only when a
  person restarts the game; the bot's own restart above sets `RESUMING_CAREER`
  and is unaffected)*. With
  `career_start.enabled` on, a bot started at the plain home screen while a
  career is in progress calls the walk rather than resuming: `RESUMING_CAREER`
  is False on a fresh start, so the home-screen branch goes straight to
  `career_start.start()`. It is **not** destructive - pressing CAREER raises the
  Continue Career dialog, which blocks Scenario Select, and none of the walk's
  templates match it, so it waits out `STEP_LIMIT` and stops - but it stops
  instead of resuming, which is the opposite of what an unattended night wants.
  Measured 2026-09-23: on that dialog `continue_career` matches while
  `team_rank`, `game_nav` and `game_nav_alt` all read False, so the fix is
  cheap - give the walk the `continue_career` template and let it press Resume,
  or have the home-screen branch press CAREER and look before deciding. Note it
  buys nothing on its own while the bot still cannot relaunch the game itself.
- **The game client stops drawing after long uptime.** 2026-09-21, ~7.5h into
  one client's run, the portrait panel went flat white the instant the Japanese
  Derby started and never redrew - the side panel froze on a stale Career
  Profile frame at the same moment. Not an X fault: `Xorg.1.log` was clean, the
  display answered with backlog 0, screenshots kept updating, and the window was
  still there. Not a lost career either - the race ran server-side, and after a
  `close`/`launch` the Continue Career dialog showed the goal still in progress
  and the results screen had Maruzensky 2nd in the Derby. Only a client restart
  clears it.
  `game_panel_blank()` now stops the bot after `BLANK_PANEL_LIMIT` flat frames
  rather than blind-tapping a dead window (it did so for twelve minutes before
  anyone looked). **What is still open is the recovery**: the bot cannot restart
  the game and press Continue Career by itself, so this still ends a night's
  run. Everything it needs is measured - `uma-launch`'s title tap,
  `CAREER_BUTTON_MOUSE_POS`, and the `continue_career` branch already in the
  loop - so the missing piece is a restart path that runs *before* the loop
  gives up, not new screen work. Whether uptime is really the trigger is a
  guess from one occurrence; log the client's uptime when it next happens.

- ~~**Nothing starts a career.**~~ **Driven and proven live 2026-09-22.**
  `core/career_start.py` walked Home -> Scenario -> Trainee -> Legacy -> Support
  Formation -> Final Confirmation and started a Grand Concert career on
  Maruzensky in **57 seconds**, first try, every step first attempt
  (22:39:33-22:40:30). Behind `career_start.enabled`, off by default, because it
  spends 30 TP. This is what used to end a night: 2026-09-19 the bot finished at
  17:55 and stopped at the home screen three times within ten minutes.

  What the run settled, all of it previously guessed:
  - **The brightness guard is right, and its two states are now both measured
    live.** `Start Career!` read **0.499** with the Friends slot empty and
    **0.797** once the borrow was taken, against the 0.512/0.822 predicted from
    `screen-map.md` and a threshold of 0.65 sitting dead centre. The walk saw
    the disabled button, opened the slot, and saw it go live - which is the
    whole borrow branch working from one pixel measurement.
  - **Tapping a borrow row takes the card outright.** No confirmation dialog,
    so the `BORROW_ATTEMPTS` bound never came near firing.
  - **The settles are enough.** 2.5s between Next presses, 4s after CAREER,
    3s and 6s around the two Start Career! presses.
  - The Final Confirmation's TP line read `Spend 30 TP to begin training? T P
    100 70`, so the cost is in the log.

  **The loop closed unattended 2026-09-23 at 01:12.** The career the walk
  started ran to its end by itself - 15 skills bought for 2332 of 2345 points,
  a spark reroll that took blue 1*/1 white to blue 3*/6 white and kept the
  rerolled set - and then `career_lobby()`'s home-screen branch called
  `career_start` on its own at 01:12:07, with a second career running 48
  seconds later at 01:12:55. Career end to next career, nobody watching. The
  brightness readings were **identical** to the first run's, 0.499 empty and
  0.797 filled, on a different deck and a different day.

  **`restore_tp` fired 2026-09-23 at 11:18**, which closes the last unexercised
  branch. The spark reroll three minutes earlier had spent a bottle of its own
  (152 -> 151) and left TP under 30, so pressing Start Career! raised the
  prompt; the walk read the stock, spent one bottle against a floor of 50,
  confirmed the quantity dialog, closed Recover TP and pressed Start Career!
  again:

      11:18:25  Short of TP to start a career; opening Recover TP.
      11:18:27  Spending 1 of 151 TP bottles to start a career.
      11:18:36  Start Career! face brightness 0.797 -> enabled
      11:18:41  Final Confirmation: Spend 30 TP to begin training? T P 55 25
      11:18:50  Career started.

  **Three careers have now been started by the loop** - 01:12, 09:15 and 11:17 -
  and the run from 07:54 to 11:18 went resume -> finish -> start -> finish ->
  start with nobody watching. Every one of them read the same two brightness
  values, 0.499 and 0.797.
- **Nothing reads which card is already in the Friends slot.** If the slot is
  filled and `Start Career!` is live, the walk presses it without checking
  *which* card is there. Harmless when the slot is empty every career, which is
  the normal case, but it means a half-finished borrow from a previous attempt
  is accepted as-is.
- ~~**The nav bar goes blind on the Scout screen.**~~ Fixed 2026-09-19. It was
  the one screen the blind tap `DIALOG_ADVANCE_ALT_MOUSE_POS` (756,980) lands
  on: `game_nav` read 0.451 and `team_rank` 0.363 there, against 0.976 and
  0.944 one tap later on Home, and `team_rank` is absent outright since Scout
  draws gacha currency where the badge sits. Cause: `game_nav_scout.png` is cut
  from the Scout tile *inactive*, so it cannot see the Scout screen - and
  re-cutting a different tile only moves the blind spot, since `game_home.png`
  was captured with the Race tab open. Only one tab is ever active, so of any
  two distinct tiles at least one is always in its normal state: hence
  `game_nav_alt` (`assets/ui/game_nav_race.png`) and a branch reading
  `team_rank or game_nav or game_nav_alt`. Union scores 0.930 worst-positive
  against 0.693 best-negative (+0.237) at the 0.85 threshold; story was
  rejected as partner at 0.844 on `continue_career`, six thousandths from
  calling a live career finished. Guarded by `game_scout_active.png` as a
  positive in `tests/test_out_of_career.py`. Numbers in `screen-map.md`.
- **A career that ends with chain steps left** has spent outings on a chain it
  never cashed. `outings.steps_remaining()` exists but nothing calls it.
  `logic.career_ending()` now names the last five turns off the year string,
  which is the signal such a check would hang from; an exact turns-left count
  is still not derived anywhere, and the turn counter cannot supply one - it
  counts down to the end of the current **year**, not the end of the career.
  (This entry said "the next race day", which the measured sequence further
  down already contradicted and the 2026-09-19 career settles: Junior ran `11`
  down to `1` across Late Jul to Late Dec, then Classic Early Jan opened at
  `24`.) The claim that it also read `-1` *throughout* Trackblazer's Climax
  dated from the mis-cropped region and no longer holds: the 2026-09-19 career
  logged **one** unreadable turn across 75 numeric ones, and a Climax race day
  returns the string `"Race Day"` rather than -1.
- ~~**`11` reads as `1`, and the Classic counter misreads badly.**~~ Root-caused
  2026-09-19 and half-fixed. Both symptoms were one defect: `check_turn`'s OCR
  fallback ranked candidate numbers by **position**, taking the topmost. The
  region's top edge catches the year label, easyocr mangles "Classic" into
  things like `'(5obbic'`, and `re.findall` pulls a `5` out of it. Measured on a
  live frame:

      box y= 18.0  conf=0.03  '(5obbic'  -> digit 5   <- garbage, and topmost
      box y=321.0  conf=0.99  '7'        -> digit 7   <- the actual counter

  Every "Classic stuck at 5" turn was that. Ranking by confidence first
  (`NUMBER_MIN_CONFIDENCE`, the rule `core/ocr.py::extract_number` already uses)
  with position only as the tie-break returns 7. The `11` case is the same
  fallback: the box text really was `'11 turn(s) left'` at high confidence, so
  the digit was never dropped by OCR.

  **Closed 2026-09-19: the reader was right, its crop was not.** The glyph pass
  read `None` on 49 of 49 live captures while passing 17 of 17 fixtures, which
  is why the fallback ran every single turn and why this hid for two careers.
  Trackblazer draws the calendar box with taller digits set lower - measured
  `y 84..131` (h 47) against URA's 36-40 - while `TURN_DIGITS_REGION` ends at
  `y 106`. Every live crop held the top 22px of a glyph and nothing else.

  That 22px is what made this look like a threshold bug for two days: it was
  taken for the digits' true size, and `TURN_GLYPH_HEIGHT = (25, 50)` for too
  strict. Widening it to (20, 45) was tried and **reverted**, because finding
  the clipped tops turned silent `None`s into confident wrong numbers (`0` for
  9, `2` for 6). **Both thresholds are correct as written** - a whole
  Trackblazer glyph is h 47 and sits inside them, and a card-centred crop
  clears `TURN_MIN_WHITE` at 0.58-0.69 rather than the clipped 0.29-0.38. The
  digit bank cut from live crops that this entry used to propose could never
  have worked either: those crops do not contain whole digits.

  Fixed **per mode** (`TB_TURN_DIGITS_REGION`, read through
  `turn_digits_region` in `core/scenarios.py`), not by moving the shared
  constant - URA's `_blue` and Grand Concert's `_purple` boxes fit it, and 17
  fixtures pass on it. `11_trackblazer*.png` guard the new crop, and the three
  1920x1080 frames in `tests/fixtures/turn/candidates/` are what it was
  measured from - the only artifact that made the diagnosis possible.

  **Confirmed live 18:33-18:36 on 2026-09-19**, the first career to run on the
  fixed code: Junior Pre-Debut read `11, 10, 9, 8, 7` on consecutive turns with
  **0** `came from the OCR fallback` warnings and **0** unreadable `-1`s, where
  every turn of the two careers before it had used the fallback. The first
  reading was `11` - the exact two-digit value that used to come back as `1`,
  which is the symptom that opened this entry.

  The decisive reading came at 18:45:30: **Junior Year Late Jul read `11`**.
  That is the turn this entry was written about - it read `1` in all three
  years of both previous careers, six times over. The whole Junior year then
  ran `11` down to `1` and into Classic Early Jan at `24`: **24 numeric turns,
  0 fallback warnings, 0 unreadable `-1`s.**

  Over that whole career, Junior Pre-Debut through the Climax: **75 numeric
  turns, 0 fallback warnings, 1 unreadable `-1`** - against 49 of 49 frames
  falling through to the fallback before the fix. The lone `-1` was not traced
  to a frame, so treat it as unconfirmed; a Climax race day has no turn counter
  at all (the box carries a red "Race Day" pill instead), which is the likeliest
  source and is expected behaviour rather than a reader failure.
- **The measured turn sequences, kept as the evidence behind the entry above.**
  Full unsampled sequence, 2026-09-18, Trackblazer/Maruzensky.

  The counter counts down to the **end of the current year**. Junior and Senior
  read that correctly - Senior ran `24, 23, 22 ... 3, 2` across Jan to Dec.

  The reproducible one: **Late Jul reads `1` in all three years**, where the
  truth is `11`. Junior, Classic and Senior each show `12, 1, 10, 9` across
  Early Jul to Late Aug. This used to read "the leading digit is being dropped,
  the same failure `core/gains.py`'s glyph bank was built for" - **wrong**. The
  2026-09-19 logging caught the box text as `'11 turn(s) left'`, so easyocr read
  both digits at high confidence and it was the fallback's ranking rule that
  lost one. The measurement below stands; the cause is the entry above.

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
  branch is `team_rank or game_nav or game_nav_alt` and all match on the home screen, so the
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

## Trackblazer - PARKED 2026-09-21

**The bot no longer drives this mode.** It is gone from the Game mode dropdown,
from `state.SCENARIOS` and from `core/scenarios.py`; a config still holding
`"scenario": "trackblazer"` falls back to Auto-detect with a warning
(`state.resolve_scenario`), and if the Climax Store button turns up on screen
anyway `state.saw_scenario` says so once and plays the career as URA rather
than pretending to know the mode.

Parked for the Climax Store. It is a scrolling shelf with per-item costs, stock
counts and a coin balance that every turn of the mode has to read, sitting in
the facility row that a race day replaces - and two of the bot's worst loops
came from that corner: the agenda-race badge looping 302 times over 2h22m on
2026-09-20, and the bot shopping on its own scheduled-race turn and then
reporting "Training button is not found" because it was standing in the shop.
The mode worked - all three Climax rounds ran unattended on 2026-09-18 holding
`RANK 1` - so this is a cost decision, not a broken-feature one.

**Nothing was deleted.** `core/parked/` has the scenario table, the two
`career_lobby()` branches and the shop driver, with `README.md` giving the
five-step unparking recipe. `tests/test_parked.py` asserts the bot imports none
of it, and `tests/test_shop_choice.py` / `tests/test_shop_read.py` still run
against the parked code so it cannot rot. The measured positions never left
`utils/constants.py` and the layouts never left `screen-map.md`.

**What stayed live, deliberately:**

- `core/trackblazer.py` and `core/epithets.py` - data and arithmetic, and
  `server/race_plan.py` is built on them, so the config page's **Race Plan**
  tab still works. Its totals are still denominated in Trackblazer Result Pts;
  that is a scoring choice, not a live mode.
- The cross-mode dialog handlers the Trackblazer work produced, which guard
  traps any mode can hit: the consecutive-races warning, the scheduled-race
  notice, and the "Enter race?" confirmation. Their assets still sit under
  `assets/trackblazer/` - that path is now the only Trackblazer left in them.

Everything below this line is the state of the mode **when it was parked**,
kept for whoever unparks it.

---

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
- ~~**Auto-detect.**~~ **Done 2026-09-19**, and it was the Shop button, as this
  entry guessed. `core/execute.py` reports
  `saw_scenario("trackblazer", "Shop button in the lobby")` when `tb_shop`
  matches and the flag is not already set, mirroring how the Lessons button
  announces Grand Concert. It only ever fires under `scenario: auto`: a fixed
  config has `apply_scenario()` set `TRACKBLAZER_SEEN` before the first lobby,
  so the guard is correctly a no-op there - which is why the 2026-09-19 career,
  pinned to `trackblazer`, logged no such line. The Result Pts badge is still
  available as a second tell if one is ever wanted.
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
- **Reading the shop, and buying.** `core/parked/shop.py` now reads the shelf and
  drives the purchase, scrolling through `core/menu_scan.py`'s `SHOP_BUY`
  profile, and `tests/test_shop_read.py` checks it against three captured
  frames. A row is anchored on its per-row **"Cost" label**, deliberately not
  its checkbox: ticking a row turns the checkbox green, so a checkbox template
  goes blind on exactly the row a buying pass most needs to find again - the
  ticked fixture pins that. A row whose name is clipped by the panel header
  reads as `None` rather than as an unknown item, and the sale price (the last
  number, "Cost ~~55~~ 44") is what the plan is costed on.

  **What is left is live work, not code.** Two things:
  - `travel_ratio` in the `SHOP_BUY` profile is a conservative **0.95**, not a
    measurement. Ad-hoc drags with no hold at either end travelled 218px of a
    requested 250 (0.872), but `slow_drag` holds at both ends to kill the glide
    and will travel further, so that figure describes the wrong drag. Erring
    high under-advances into extra overlap, which costs passes but never skips
    a row; erring low skips rows. Re-measure against `slow_drag` on a live
    shelf.
  - ~~Nothing calls `shop.visit()` yet.~~ **Wired and proven live 2026-09-19.**
    At Junior Early Jul it read the shelf, priced four rows and bought Vita 20,
    Guts Notepad, Wit Notepad and a Coaching Megaphone for 95 of 100 coins,
    every tick confirmed against the coin counter, and the balance read `5` on
    the next visit. The hook sits **below** the race-day branch in
    `career_lobby()`, because a race day replaces the facility row and the
    button's position then belongs to something else; `tb_shop` is the presence
    check, and seeing it also reports `saw_scenario("trackblazer")`. The coin
    gate works too: at 5 coins it logged "under the cheapest item at 10" and
    skipped the scan rather than paying for it.
  - **Use-on-purchase only works for a one-row basket.** `Exchange Complete`
    carries one quantity stepper **per row** (y 222/337/452) and does not list
    the rows in basket order, so stepping the first one uses whatever sorted
    first rather than what was intended - a Coaching Megaphone burned at Junior
    Early Jul would spend its four turns on nothing. The item **name**
    positions on that screen are not measured, and that is the only thing
    stopping a targeted use; until they are, a mixed basket is stored. It did
    no harm on the first outing: the zero-support gains either side of the
    purchase were identical (SPD `spd 11` at turn 1 and again at turn 12, where
    +20% would read 13), so nothing was wasted - by luck rather than design.
  - **The coin counter tweens, and the tick guard believed it.** Measured over
    the 2026-09-19 career: 34 baskets planned, **21 ticks accepted, ~160
    refused**, so the shop under-bought all night after its first success. The
    first `read_coins()` of each visit was always right (100, 105, 113, 213,
    58, 158, 260 - balances that track race payouts), while every read *inside*
    the tick loop came back 8, 9, 3, 0 or 10 regardless of the real balance:
    113 and 213 both reported "8 -> 8". It was never the region - the same
    frames read 560 and 516 correctly as saved fixtures, ticked row and all.
    The difference is that in-loop reads land 0.6s after a click, on a counter
    that is still rolling. Fixed with `settled_coins()`, which waits for two
    equal readings the way `menu_scan.wait_for_list` waits for the list, and by
    making the mismatch **advisory**: a stale reading is likelier than a
    mis-aimed click, and `Confirm Exchange` still shows the basket before
    anything is spent.
- ~~**Is a training bonus a percentage or a flat number?**~~ **A percentage**,
  settled 2026-09-19 by measurement. The board was read twice on one turn
  (Classic Late Nov, turn 3) with a Motivating Megaphone (+40%, the tier the
  shop happened to stock) used in between, so supports, levels, energy costs
  and failure rates were identical either side: SPD `spd 13 -> 19`, STA
  `sta 7 -> 9`, PWR `pwr 9 -> 12`, WIT `wit 17 -> 23`. **Nothing moved by 40**,
  and every ratio clusters on x1.4, the spread being rounding noise on small
  integers. Three further things the same run settled: it multiplies the
  **final** gain, after support bonuses (PWR and WIT carried supports and
  scaled just like the zero-support facilities); it scales **skill points**
  too (WIT skill `6 -> 8`, while a `skill: 2` holding at 2 is 2 x 1.4
  truncating rather than an exception); and it leaves **energy cost and
  failure rate untouched**. So `TRAINING_BONUS_IS_PERCENT` stays `True` and the
  sevenfold valuation swing is gone. Full table in `screen-map.md`.
- **Megaphone and Ankle Weights stack**, and nothing uses that yet. Both can be
  active on the same turn, the Ankle Weights' +50% landing on one facility on
  top of the Megaphone's global bonus. For *buying* this changes little - the
  pair is worth the sum of its parts - but a use-logic that spends them on
  separate turns throws the combination away.
- **Epithets.** The game ships them, so stop working from guides alone: names
  in `master.mdb` `text_data` category 130, conditions in category 131, joined
  by index; `nickname.scenario_id = 4` selects the **40 Trackblazer-only** ones
  and `nickname.rank` holds 1/2/3. The award is **+5/+10/+15 to 2 random
  stats**, which is 10/20/30 points in total: the +30/+20/+10 this note first
  carried was never wrong, it quoted the *total across both stats*, and the two
  figures are one fact in two units. Three pay a skill hint instead - Legendary
  (Homestretch Haste), Mile a Minute (Mile Straightaways), Dirt G1 Dominator
  (Top Pick). `rank` is **not** the bonus: all six `rank 1` are +5, but `rank
  3` carries `Heroine` and `Eat My Dust` at +10 beside its +15s, and `rank 2`
  spans the whole range. The prices:
  - **+5** - Pro Racer, Hokkaido Hotshot, Tohoku Top Dog, Kanto Conqueror,
    West Japan Whiz, Kokura Constable, Dirty Work, Junior Jewel, Globe-Trotter,
    Dirt Dancer, Umatastic, Turf Tussler, Kicking Up Dust.
  - **+10** - Spring Champion, Fall Champion, Shield Bearer, Stunning,
    Standard and Non-Standard Distance Leader, Playing Dirty, Dirt G1 Star,
    Dirt G1 Achiever, Heroine, Lady, Eat My Dust, Sprint Go-Getter, Dirt
    Sprinter.
  - **+15** - Incredible, Phenomenal, Breakneck Miler, Goddess, Dirt G1
    Powerhouse, Sprint Speedster.

  The four scenario milestones - `Moneymaker`, `Leading the Charge`, `Product
  Power`, `Climax King` - are priced by no source found; read them in game.
  Never price these by scraping game8: three fetches of one page produced three
  different groupings. Cross-checked against daftuyda's Trackblazer scheduler
  (`daftuyda/umamusume_trackblazer_scheduler`, originally by SkyeNat21), whose
  `epithets.json` carries the per-epithet value master.mdb does not: `amount`
  is the total across both stats and `display_amount` the per-stat figure,
  which is what reconciles 10/20/30 with +5/+10/+15. The repo ships no LICENSE
  file, but **the author gave permission to use it** (2026-09-20, asked
  directly). It is not original data either: every row carries
  `source_url: gametora.com/umamusume/nicknames`, so that is who the credit is
  owed to. **Take the price from it, never the condition.** Its 36 rows are
  gametora's English and are degraded against the game's own text - `Kanto
  Conqueror` omits Kawasaki and Funabashi, `Tohoku Top Dog` omits Morioka, and
  `Umatastic` writes "Uma Musume Stakes" where every race name reads
  "Umamusume", so a literal match finds nothing. It also omits the four
  scenario milestones entirely, which is why their prices are still unknown.
  Conditions come from category 131, which patches keep current. Nothing models any of
  this, and they are the scenario's real stat
  engine. Several are schedulable by race *name* - `Junior Jewel` wants 3
  "Junior Stakes" wins, `Umatastic` 3 "Umamusume Stakes", `Globe-Trotter` 3
  with a country in the name, and five more want graded wins at a named group
  of racecourses - so an agenda can target them deliberately.
- **Post-race Victory events are scored blind.** `core/event_effects.py` has no
  rule for either line such an event offers - "Stat gains based on race grade"
  and "Chance to gain a random skill" - so on 2026-09-20 every branch scored 0
  and the pick fell through to energy cost alone (`#1=-40, #2=-20`, took #2).
  The cheaper branch may well be right, but it is not being chosen on the
  reward, and nothing in the log says so unless DEBUG is read. A rule has to
  match loosely: the same run OCR'd one line as "Stat Gsinc Kaced On rafo
  Grade". These fire after every race, so this is not a rare path.
- **`GRADES` drops OP and Pre-OP, and `Pro Racer` needs them.**
  `server/master_data.py:44` maps only `{100: G1, 200: G2, 300: G3}`, so the
  `grade not in GRADES` line in `_races_from_mdb()` discards 343 of the 777
  career-programme rows: **400 = OP** (118 - Manyo Stakes, Pollux Stakes,
  January Stakes), **700 = Pre-OP** (26 - Aster Sho, Rindo Sho), **800 =
  Maiden** (172), **900 = Debut** (27). Admitting 400 alone adds 164 rows -
  Junior 15 -> 30, Classic 118 -> 184, Senior 127 -> 210 - and Junior
  *doubles*, which is the year the agenda has fewest options in and where
  `Junior Jewel` lives. Maiden and Debut are correctly outside "OP level or
  higher". `race_permission = 5` (246 rows) is **correctly** dropped: it is the
  scenario finals - URA Finale Qualifier/Semifinal/Finals, Twinkle Star Climax
  Race 1 - which `race_day()` drives rather than the schedule.
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
