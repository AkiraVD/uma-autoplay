# TODO

Ordered by value-per-effort. Everything here came out of the completed
Agnes Tachyon career run (see `screen-map.md`).

## 1. DONE - Fix `SKILL_PTS_REGION` on Finale race days

`check_skill_pts()` returns -1 on the URA Finale race-day lobby because the
stats row sits ~50px lower there (the extra `Race Day` banner). `auto_buy_skill()`
then bails at `-1 < SKILL_PTS_CHECK` and never buys. **The completed run finished
with 1927 unspent skill points.**

Do not just move the region - it differs per screen. Read it relative to the
stat row, or try the normal region and fall back to a shifted one when the first
read fails the range check.

Careful: fixing this re-opens the Skills-screen path that caused the wedges in
item 2, so land that first.

## 2. PARTLY DONE - Event-outcome scoring

Today `event_choice()` fuzzy-matches an OCR'd event name against a 49-entry
config; 7 events missed and silently took the top choice (see
`../scratchpad/missing_events.md`).

Better approach, borrowed in concept from UMAT: **score the outcomes, not the
event.** Read each choice's effects off screen (the event screen has an
`Effects` button) and rank by keyword:

    good: "Speed +", "Stamina +", "Power +", "Guts +", "Wisdom +", "Energy +",
          "Mood +", "bond +", "hint +", "Skill points +", "Practice Perfect",
          "Charming", "Fast Learner"
    bad:  "Practice Poor", "Slacker", "Slow Metabolism", "Mood -", "Gatekept",
          "Event Chain Ended"

This removes the need to recognise the event at all, and works unchanged for any
future scenario. Keep the existing config as an override for events where the
best choice is not the one with the best immediate effects.

## 3. PARTLY DONE - Use `master.mdb` as a data source  — no new risk surface

Skill names now come from it; see "Skill names come from master.mdb" at the
end of this file. Event and race names still do not.

`C:\Users\<user>\AppData\LocalLow\Cygames\Umamusume\master\master.mdb`
is plain SQLite, ~16.7MB, 416 tables, and the game repatches it on update.
Reading it is a local file read - no network, no injection.

- `text_data` category **181** = 12,758 event names -> canonicalise OCR'd event
  names before matching (fixes "Diligent Effort A" -> "A Diligent Effort")
- `text_data` categories 28/29/32 = race names, 47/48 = skill names/descriptions
- `skill_data`, `support_card_data`, `single_mode_free_shop_item` (MANT shop)

Could replace the hand-maintained `data/races.json` and `data/skills.json` so
they stop going stale on patches. Copy the file before opening it; never open the
game's copy directly.

**Verified limit:** the choice->effect mapping is NOT in master.mdb. Category 267
(choice text) has only 18 rows. Event outcomes live in the Unity story-timeline
asset bundles. So master.mdb gives correct names, not correct answers - which is
why item 2 is the actual fix.

## 4. NOT A BUG - energy reader

`check_energy_level()` reported 104.24%. `hundred_energy_pixel_constant = 236`
does not hold once the max energy bar extends. Only used against thresholds, so
it is not currently causing bad decisions, but `max_energy` is wrong.

## 5. Add the missing event entries

`../scratchpad/missing_events.md`. Only worth doing if item 2 is not done.

## Investigated and parked: API / packet mode

UMAT's "API Mode" chain is:

    UMAT -> HTTP localhost:8123 -> KUC / uma_viewer -> captured packets -> CarrotJuicer

CarrotJuicer "hooks the decryption function in libnative.dll" - DLL injection
into the running game, not passive sniffing.

Blockers for this setup:
- **KUC / uma_viewer is not publicly available.** Not in UMAT's repo or
  requirements; `config.example.json` ships `"api": {"enabled": false}`.
- Capture tooling targets Android (Riru-CarrotJuicer, needs root) or the DMM
  client (EXNOA-CarrotJuicer). We are on Steam Global. Hachimi has a Steam
  installer so a path plausibly exists, but it would have to be assembled.
- Injecting into the game process is materially more detectable than reading
  pixels and moving the mouse.

Worth stealing regardless: UMAT's API client is fallback-safe - every getter
returns `None` on failure so callers drop back to OCR transparently, and it is
off by default. That is the right shape if a packet source is ever added.

Real argument for packets: Trackblazer's shop inventory, coin balance and grade
points are genuinely hard to read off screen. Not a reason to switch for URA.

## Not started: Trackblazer scenario

Confirmed feasible by OCR - UMAT has a full `core/Trackblazer/` OCR
implementation, so it does not require packets. But it is not a liftable module:
they forked the whole bot per scenario (`core/Base`, `core/Ura`, `core/Grandlive`,
`core/Trackblazer`, `core/Unity` each carry near-identical copies). The genuinely
new parts are `items.py` (~54KB shop database), `item_purchase_execution.py`,
`item_use_execution.py`.

Scenario adds: coin shop refreshing every 6 turns, Grade Points replacing career
goals, epithets/race routes, rival VS races, Twinkle Star Climax finale,
~30-40 races. Start with a screen-mapping pass like `screen-map.md`.


---

# Status after the TODO pass

## 1. `SKILL_PTS_REGION` - done

`(755, 720, 85, 42)` -> `(750, 715, 95, 105)`. The number sits 34px under the
"Skill Pts" label on every screen, but the whole box drops ~54px on Finale race
days (742 -> 796), so the region now spans both. `extract_number` only merges
digits sharing a line, so the label and the neighbouring "Full Stats" button
cannot bleed into the value.

Verified: normal lobby 166, training screen 203, **Finale lobby 1519** (was -1
all career). Returns -1 on the Skills and Complete Career screens, which is
correct - the value lives elsewhere there and `check_skill_pts()` is only called
from the lobby.

## 2. Event-outcome scoring - working, with a known gap

New `core/event_outcomes.py`, wired into `core/events.py::event_choice()`:

    config override  ->  outcome scoring  ->  top choice

The config stays authoritative deliberately. Against the 49 hand-tuned entries
the scorer agrees on 21 and disagrees on 7 - and the disagreements are mostly
**chain events** (`Raising the Uma Lord's Castle`, `Assembling the Uma Lord's
Minions`, `Just a Little Closer`) where you pick to continue the chain, not for
the best immediate stats. That is precisely why config wins.

Outcome tables live in `data/events/` (2475 events). Scoring weights stat gains
by the user's `priority_stat` order, treats hints/mood as high value, penalises
named bad conditions, and halves anything marked `(random)`.

Two traps found while building it, both fixed:
- Each option is a **separate record sharing the EventName**. First-one-wins
  dropped every alternative and made everything look single-option.
- ~1195 entries carry a **blank label**, which is a descriptive summary of a
  conditional result, not a selectable option. Scoring it produced nonsense
  (Dance Lesson scored 316).

Of the 7 events that missed during the real career, 4 now resolve:
`Reminiscent Clover` -> 2, `A Diligent Effort` -> 1, `A Bakushin Greeting!` -> 1,
`Suspicious, But Safe?!` -> 1 (single outcome).

**Still unresolved:** `Happy Meek's Challenge!`, `After the URA Finale Semifinal`,
`Twinkle Monthly Special Issue`. These are scenario events and are not in the
tables (`ura_finale.json` is only 872 B). They fall back to top choice.

### DONE - next step for item 2: read the Effects panel

See "The Choices panel is read off the screen" at the end of this file. The
paragraph below is kept because its conclusion about the button was wrong in an
instructive way: the panel usually opens with no click at all.


The `Effects` button **does** show the outcomes on screen - the button position
varies, which is why a single fixed-coordinate click missed it and I initially
concluded otherwise. Reading it would cover the scenario events above, plus any
event added by a future patch, with no table to maintain. Needs a live career
with events on screen to map: find the button (template, not fixed coords),
click, and read the per-option effect text.

## 3. `master.mdb` - deferred, largely superseded for events

The event-name canonicalisation this was wanted for is now handled by fuzzy
matching against the 2475 outcome-table names (`Diligent Effort A` ->
`A Diligent Effort` at 100%). Still worth doing for `data/races.json` and
`data/skills.json` staleness. Details in the original item above.

## 4. Energy reader - not a bug

`hundred_energy_pixel_constant = 236` is the pixel width of *100* energy, and
`energy_level` and `max_energy` are both in those units. A 246px bar means max
energy is 104, so the "104.24" reading was a correct read of a full extended bar
(max energy rises above 100 through events). My original note misread this.

## 5. Missing event entries - superseded by item 2 for 4 of 7


---

# Run 2 result (validation run, same uma / deck / config)

Full career unattended, URA Finale won, one manual intervention.

| | Run 1 | Run 2 |
|---|---|---|
| Speed | 931 (SS) | **1204 (UG)** |
| Fans | 356,953 | **428,038** |
| Skills bought | 0 | **7** |
| Skill points left unspent | 1927 | 887 |
| Manual restarts | 4 | 1 |
| Runtime | ~90 min over 4 restarts | 58.6 min |
| Errors / next-button warnings | several | 0 / 0 |

Validated live: `SKILL_PTS_REGION` (7 buys, including on Finale race days),
event scorer (10 decisions, 2- and 3-option, top and non-top picks, correct
rows), `ura_finale_race_btn` (all 3 Finale races started), lobby recovery
(5 escapes), skill-scan logging (no false stall).

Event handling over the career: 20 config hits, 10 scorer decisions,
8 blind top-choices. The 8 are scenario events absent from the outcome tables -
the case the Effects-panel reader would close.

## Still open after run 2

1. **Taskbar-occlusion detection is untested.** Written into the supervisor
   after the incident, but the run had already started, so it never ran. See the
   section in `screen-map.md`.
2. DONE - **Read the Effects panel** (item 2's next step). Covers the 8 blind
   choices and anything a patch adds; see the section at the end of this file.
3. **`master.mdb`** for `races.json` / `skills.json` staleness.
4. `check_training()`'s closing Back click is the wedge trigger when the bottom
   strip is covered; it has no retry of its own and relies on the lobby recovery.


---

# Unity Cup - status after the port

Ran a full Maruzensky Unity Cup career unattended: five team races (team rank
F -> A -> S, +50 all-attributes bonus), the S+ Team Zenith Finals, and the three
URA Finals races. Final: spd 1242 / sta 733 / pwr 997 / guts 389 / wit 564,
263,708 fans. Every screen and reader fix is documented in `screen-map.md`.

## Open

1. **DONE - Spirit Burst is wired into all three scorers.** It had reached
   `rainbow_training` only; `focus_max_friendships` and `training_score` (the
   `most_support_card` path) both ignored it, which meant Junior Year - the year
   uma.guide says burst-popping matters most, because it drives facility levels
   and team recruitment - never saw a burst at all.

   Weights come from uma.guide's turn-scoring tables, which value a Spirit Burst
   at 2 points, the same as one rainbow support on this repo's scale, and from
   UMAT's `assets/unity/training_score_unity.example.json`, which puts a
   charging gauge at half a burst. Defaults are now gauge 1.0, burst 2.0,
   extreme burst 3.0 (was 0.5 / 1.0 / absent).

   Timing follows the guide's "pop early, save later": in Junior and Classic a
   burst scores flat, so the bot will take an otherwise empty facility to pop
   one. From Senior Year the burst is scaled by the facility's own score
   (`STRONG_TRAINING_SCORE = 2.0`), so it amplifies a strong training but cannot
   drag the bot onto an empty one. The Finale pops again - last chance to spend
   - while gauges score 0 there, since a gauge only pays off through a later
   burst and there are no turns left.

   An Extreme burst now also bypasses the `MAX_FAILURE` filter in all four
   candidate filters, because it forces the training's failure chance to 0%.

   `assets/icons/unity_burst_extreme.png` has since been cut from a live
   Extreme burst and verified - see the icons section below.
2. **Choose the team-race opponent.** The bot confirms whatever the game
   preselects. Everything needed is on screen: `Rank 23/28/40`, grades `E/F/G`,
   and a per-discipline circle/triangle/cross row in the confirmation modal.
   Beating a harder team raises team rank (which drives facility levels), but
   losing lowers it.
3. Three Unity careers have now been run end to end. Configs are parked as
   `config.tachyon.bak.json` and `config.maruzensky.bak.json`; `config.json` is
   currently tuned for [Flare] Aston Machan (Sprint A / Mile B, Front).

## Restart hygiene (learned the hard way)

Waiting for a run to exit by polling `status.json` fails if that file was just
deleted - the poll times out and a *second* bot starts alongside the first. Two
bots fighting over one screen looks exactly like a game bug: clicks get undone,
modals flicker open and shut, and the logs interleave. Confirm no `run_career`
process is alive before starting one.

## Unity run 3 (2026-09-09) — career completed, SS rank

Result: SS / 18,057, spd 1331, sta 863, pwr 1095, guts 536, wit 830.
Team Sunny Runners S+ 1st place, 348,088 fans. No stalls between the
lobby and the Finals; the only wedge was the final screen.

### Fixed
- `unity_begin_showdown` had no settle delay while the other three Unity
  transition buttons did. The loop re-polled inside its own transition,
  which is the modal <-> VS oscillation seen on the Zenith screen.
  All four now settle. **Untested against a live Zenith screen** — this
  run re-entered the scenario past that point.
- `career_complete` screen is now recognised and handled
  (`assets/buttons/complete_career_btn.png`, 1.000 on that screen).
  Previously the bot tapped at it forever: it has no Tazuna hint and no
  Back or Close button (0.45-0.57), so lobby recovery had nothing to
  click. **Untested** — written after the career had already finished.

### Open
- Post-completion screens are still unhandled: Spark Selection
  ("Select which Sparks to keep") and the REWARDS sequence both follow
  Complete Career and neither is in the templates dict. A run that
  completes will wedge one screen later than it used to.
- `auto_buy_skill` can leave an uncommitted cart. At career end the
  Complete Career button read 1593 skill points while the skill screen
  read 661, i.e. ~932 points were selected but never confirmed. At least
  one buy_skill pass selects and then loses the confirm/learn chain.
  Worth finding which one — points in a cart are indistinguishable from
  points unspent until the screen is opened.
- `check_skill_pts` reads `SKILL_PTS_REGION`, which the career-complete
  layout does not use (its counter is inside the Skills button at
  ~(355, 905)). Hence the positional constants added for that screen.
- Failure-label OCR: `read_failure_from()` falls back to the only box with an
  explicit `%` when label matching fails. Recorded here as "papering over the
  label match" on the strength of it firing 26 times in one run - **that was
  overstated**. Measured across a full Unity career: 8 fallbacks in 110 failure
  reads, 7%, with no other soft OCR failure logged anywhere in the run (turn
  counter, banner, gains, energy and caps all read clean). It also degrades
  safely: an unreadable failure is treated as unsafe, so the cost is a skipped
  training, never a risky one. Leave it unless the rate climbs.

## Unity icons: what the rail actually shows (2026-09-09, verified live)

Four distinct states, and the earlier detector caught none of them correctly.

- **charging** - grey/blue flame, LEFT of the portrait (x~836), hue ~208deg.
  Fills from the bottom as it charges, so one template cannot cover every fill
  level. `unity_spirit_gauge.png`, 20x20 core, confidence 0.60.
- **ready** - green flame with a glow halo, LEFT (x~836), hue ~160deg. This is
  the one that will actually fire; a merely full gauge does not.
  `unity_burst_ready.png`, 24x24 core, confidence 0.80.
- **extreme, live** - large magenta chevron badge, RIGHT of the portrait
  (x~924), with a magenta halo round the card and a gold full bar.
  `unity_burst_extreme.png`, 24x24, confidence 0.80.
- **extreme, spent** - small magenta flame, also RIGHT. Kept as
  `unity_burst_extreme_spent.png`. The live template scores 0.291 on it, so a
  spent burst is not miscounted as live.

Three bugs this uncovered:

1. `unity_burst_ready.png` was a picture of the orange "stat up" chevron badge,
   not a burst. It matched at (924, 266) and on the facility icons, so Burst was
   0 on every scan of every run to date.
2. Templates cut on one facility did not transfer, because the glow halo is
   semi-transparent and blends with the facility background - a 52px crop
   scored 1.000 on the classroom and 0.622 at the pool. Cropping to the flame
   core (24px, no halo) fixed it: 0.967 cross-facility, 0.409 on blue flames.
3. Every scan region covered only the LEFT column, so a live Extreme burst
   could never have been detected regardless of template quality. Added
   `UNITY_RAIL_BBOX = (800, 145, 950, 715)` spanning both columns.

Verified counts: live-extreme screen {spirit 1, burst 1, burst_ex 1}; spent
extreme {burst_ex 0}; two non-extreme screens {burst_ex 0}.

### Open
- One charging flame goes undetected on the spent-extreme screen (3 visible, 2
  found) - most likely a fill level the single template does not cover.
- DONE - the scorers read the printed stat gains; see the stat gains section
  below. The orange number turned out to be an addition to the bubble, and the
  digits needed a template bank rather than OCR.

## Stat gains are now read and scored (2026-09-09)

The training screen prints the gains per stat and nothing read them; every
scorer worked from support counts and rainbow colours as proxies for a number
the game was already displaying.

**Semantics, confirmed against the game.** Each column shows a bubble and an
orange number below it, and the training awards **bubble + orange**. A facility
with no bonus shows only the orange number. Verified on a Power training that
displayed Stamina +17/+5 and Power +37/+16: Stamina moved 22 and Power 53 once
the concurrent "Growing as a Team" (+7 all stats) and a story event (+10 Power)
were accounted for. Three stats reconciled exactly.

**Reader.** `core/gains.py`. easyocr is unusable on this strip - it reads the
leading "+" as a digit ("+37" -> "437") and drops narrow ones ("+16" -> "6"),
managing 2/16 columns. The UI font is fixed, so digits are matched against a
template bank in `assets/digits/`, harvested from five labelled screens. That
reads **5/5 screens, 16/16 columns**. Three filters do the work:

- glyph height 19-28px (the "+" is 15-18)
- width/height < 0.90 (the "+" is ~1.05, the widest digit 0.82)
- within 45px of the column centre (excludes the neighbouring column and the
  stat header row below)

Glyphs are padded into a fixed box, never stretched - stretching a narrow "1"
to a square makes it read as "7".

**Scoring.** `logic.gain_score()` weights each stat by the user's priority order
and adds `STAT_GAIN_POINTS = 0.04` per weighted point, so a strong training
lands near 2.0, one rainbow support on this scale. It feeds all three scorers.
An unreadable screen returns 0.0, leaving the previous behaviour untouched.

Bursts multiply the gains rather than adding a flat bonus, so a burst on a big
training outranks a burst on a small one: `BURST_GAIN_MULTIPLIER = 1.5`,
`BURST_EX_GAIN_MULTIPLIER = 2.0`. Measured: the same Power gains score 4.62
plain, 6.93 with a ready burst, 9.24 with an extreme - against 1.63 for a
typical Speed training.

### Open
- DONE - digit **9** harvested from a recorder frame the user spotted
  (`EXTREME_f_021948_0.33_full.png`, Skill Pts orange row `+9`). The bank is
  complete 0-9, 39 samples, and reads 6/6 screens including that frame
  (spd 11, wit 48, skill 31). Worth noting where the sample came from: the
  recorder's kept frames are mostly skill lists and race results, because the
  pink test fires on any purple UI, so they are a poor place to hunt for
  training-screen digits. The ring buffer holds the training screens, but as
  lossy JPEG panel crops with x shifted by -150.
- DONE - `gain_score` is now cap-aware; see the section below.
- The gain constants are module-level in `logic.py`, not config keys, so they
  are deliberately not in the web UI - adding them would need a `web/dist`
  rebuild.
- Emulator layout unchecked: `GAIN_COLUMN_X` is a dict of plain x centres, so
  `adjust_constants_x_coords()` cannot shift it by suffix.

## Friend-card outings (Recreation) - implemented 2026-09-09

Friend-type supports (Tazuna, Riko, Thorn, Light Halo - any card with the friend
type) do not hand out stats on the training facilities. Their bond and their
event chain come from **outings**, and the outing also restores energy and
clears negative conditions. None of that was handled:

- `check_support_card()` detected the friend icon but `logic.py` sums friendship
  only over the five stat keys, so friend bond never reached any score.
- `do_recreation()` was called from exactly one place - low mood - and clicked
  Recreation blind.

**Signal.** The Recreation button carries a pink badge when an outing is
available: the same smiley-figure glyph as `support_card_type_friend.png`,
recoloured. Being the generic friend-type glyph rather than a portrait, it works
for any friend card. Cut to `assets/icons/recreation_badge.png`; separation is
0.998 worst-positive against 0.275 best-negative (absent on turn 1 of a career,
present later, so it is a real signal).

**Policy** (`logic.should_recreate`), weighing the outing against resting as
well as training:

| situation | action |
|---|---|
| condition showing, training worth < 4.0 | outing (clears it, and returns mood/bond) |
| condition showing, training worth >= 4.0 | keep training - the condition can wait |
| about to rest, energy >= 30, spill <= 12 | outing instead of rest |
| about to rest, energy < 30 | rest - it returns more energy |
| training worth < 2.0, spill <= 12 | outing |
| training worth < 2.0, spill > 12, mood low | outing |
| training worth >= 2.0 | train |
| gains unreadable | train - unknown is not worthless |

"Spill" is recovery lost to the energy cap: 70/100 with a ~20 recovery wastes 0,
95/100 wastes 15. Numbers come from the game's outcome tables - karaoke +2 mood,
stroll +1 mood +10 energy, shrine +1 mood +10..30 energy - and a rest returns
more raw energy than any of them.

### Open
- DONE - the flat `RECREATION_ENERGY_ESTIMATE = 20` is gone; see the outing
  chain section below. The real figure is 24-70, median 30.
- Only one friend card has been observed. If another renders a different badge,
  `umatool sep` will show it and a second template can be added.
- The chain is not planned ahead as a whole - each turn is judged on its own.
  Knowing which chain event comes next would let it hold a turn for a big one.

## Dispatch order in `career_lobby()` - fixed 2026-09-09

Three loops this scenario came from the same shape, not from three bugs: a
generic handler placed above a screen-specific branch. `cancel_btn.png` scores
1.000 on the Team Zenith confirmation modal and on the Complete Career
confirmation, both of which pair Cancel with the accept button the bot actually
wants. The generic cancel ran first, dismissed the modal, the screen behind
re-opened it, and the loop had no way out.

The earlier patch gated cancel on `accept_on_screen = unity_begin_showdown or
career_finish`, which fixed the two known modals and nothing else - the next
confirmation screen would have hit it again.

`career_lobby()` now runs in two sections:

1. **Screen-specific branches** - `select_event`, `career_finish`, the five
   Unity branches, claw, `career_complete`.
2. **Generic handlers** - `inspiration`, `next`, `next2`, `cancel`, `retry`.
3. Then the Tazuna lobby check and the not-in-lobby recovery, unchanged.

The `accept_on_screen` gate is gone: with the accept branches above cancel it
could only ever be true on a frame the bot was already stopping on.

New screens go in section 1. A branch added below the generic handlers gets
whatever `next` or `cancel` leaves behind, which on a confirmation modal is
nothing.

### Open
- Untested against the game. The reorder only changes which branch wins when
  two templates match the same frame, so the risk is a screen that showed both
  a specific button and `next`/`cancel` and relied on the generic one winning.
  Worth watching the first race-day and post-race sequence of the next run.
- The claw branch still falls through without `continue` when `check_credit()`
  reads nothing, so an unreadable claw screen now reaches the generic handlers
  before the not-in-lobby recovery instead of going straight to it.

## `gain_score` now discounts capped stats - 2026-09-09

`filter_by_stat_caps` only ever looked at a training's **own** stat, but every
training also prints side stats, and those were scored at full value even when
the stat had no room left. On this run's config (sta capped at 500) a SPD
training printing spd +30 / sta +20 scored 2.76 when the truth was 1.80 - a 35%
over-valuation, and enough to pick the wrong facility.

Three changes in `core/logic.py`:

- `stat_cap(stat, game_caps)` extracted from the closure inside
  `filter_by_stat_caps`, so the cap rule (lower of configured and on-screen,
  `DEFAULT_STAT_CAP = 1200` when neither reads) now has one definition and both
  callers share it.
- `set_stat_headroom(current_stats, game_caps)` records `cap - current` per
  stat into a module-level `_stat_headroom`, published by `do_something()`
  before any scorer runs. A stat whose current value read as -1 is left out of
  the dict entirely, and gains into it keep scoring at full value - guessing
  low would silently write off a training that is still worth taking.
- `gain_score` clips each gain to `min(amount, headroom)`. Skill points have no
  cap and are exempt. Burst multipliers apply after clipping, so a burst
  multiplies what actually lands rather than what is printed.

Unit-tested against a stubbed `core.state` (the real one builds an easyocr
Reader at import): capped secondary worth nothing, partial headroom clipped,
skill points exempt, unreadable stat unaffected, screen cap beating config cap,
burst multiplying only the landed gains, fully-capped board scoring 0.0.

### Open
- Not run against the game. The change can only lower scores, so the failure
  mode is under-valuing a training, not chasing a bad one.
- Late in a career this lowers `training_value()` across the board, which feeds
  `should_recreate`. Expect more outings in the last third of a run. That is
  arguably correct - capped training really is low value - but it is a
  behaviour shift nobody asked for, so it wants watching. (The thresholds it
  used to feed are gone; it now feeds the value comparison instead.)
- `_stat_headroom` is module-level state set once per turn, in the same style
  as `state.CURRENT_YEAR`. It goes stale if a scorer is ever called outside a
  `do_something()` turn; `training_value()` in `execute.py` is called right
  after and is fine.

## Outing chains are read ahead - 2026-09-09

`should_recreate` used to price every outing the same, so step 1 of a friend
card chain and step 5 scored identically. They are not close:

| step | energy | mood | skill | hints | clears a condition |
|---|---|---|---|---|---|
| 1 | 29 | +1.0 | 7 | - | no |
| 2 | 28 | +0.6 | - | - | **yes** |
| 3 | 33 | +1.0 | 7 | 0.2 | no |
| 4 | 27 | +1.0 | 14 | - | **yes** |
| 5 | 22 | +1.1 | 9 | **1.6** | no |

(averaged over the five friend characters, from the data file)

**The framing in the old TODO was wrong.** It said the chain should be "planned
ahead as a whole". A chain advances only when an outing is taken - it does not
tick with the calendar - so there is no scheduling problem and nothing to hold
a turn for. The next step is the same next step whenever you take it. What was
actually missing was knowing *which* step is next.

### Where the data came from

`data/events/support_card.json` already had it. Chain events carry one chevron
per step in their name, so "Memories of Cinema" with three chevrons is step 3.
154 cards have chevron chains but most are training-card chains that fire on a
training, not an outing.

There is **no numeric signature** separating the two - Manhattan Cafe (a
training card) hands out as much Energy per step as Sasami does - so
`core/outings.py` carries the five friend characters by name in
`FRIEND_CARDS`. Add to it if a sixth ships; until then an unrecognised one
falls back to the averaged prediction, which is the old behaviour.

### How the position is tracked

Two mechanisms, because neither is sufficient alone:

- **Counting.** `do_recreation()` calls `outings.advance()`. Recreation and a
  friend outing are the same button, so every trip through it moves the chain.
- **Naming.** Only branching steps put choices on screen, so most steps go past
  without a readable name. When one *is* readable, `outings.note_event()`
  matches it back to a character and a depth and overrides the counter. That is
  also how a restart mid-career resyncs.

Until a step names itself the card is unknown, so the prediction is the average
across the five chains at that depth. The depth is what drives the decision, so
that is good enough - and it sharpens the moment a name lands.

### Pricing

`should_recreate` is now one comparison instead of a ladder of thresholds:
the outing against whatever the bot was about to do. `RECREATION_ENERGY_ESTIMATE`,
`RECREATION_MAX_WASTE`, `REST_BEATS_OUTING_ENERGY`, `LOW_VALUE_TRAINING_SCORE`
and `STRONG_ENOUGH_TO_KEEP` are all gone.

Energy is state-dependent, and **the obvious anchor is wrong**. Pricing energy
at "25 energy buys a 2.0 training, so 0.08 a point" double counts, because the
training spends a turn as well as the energy and turns are the scarcer
resource. The right anchor is the rest it avoids: a rest returns ~50 energy and
costs one turn, a turn is worth ~2.5, so 0.05 a point at the bottom of the tank
tapering to 0.01 on a full one. Energy that would spill past the cap is worth
nothing, the same clipping the stat caps got.

A training is compared *after* its own energy cost (`TRAINING_ENERGY_COST = 25`),
because an outing pays energy out and a training pays it in.

Verified by `tests/test_outings.py` (49 checks, real data file, stubbed
`core.state`): parsing of random/slash/all-stats/heal outcomes, chain
progression and exhaustion, name resync overriding the counter, energy scarcity
and spill, and ten decision cases.

### Open
- Not run against the game.
- `MOOD_POINTS`, `HINT_POINTS`, `CONDITION_CLEAR_POINTS`, `BOND_POINTS` and
  `TRAINING_ENERGY_COST` are reasoned estimates, not measured. The energy
  anchor is the only one with a derivation behind it.
- DONE - the badge does disappear once a chain is spent (confirmed in game), so
  it is a gate rather than a hint. `should_recreate` returns before pricing
  anything without it, which made the plain-recreation profile unreachable; it
  is gone. The useful consequence is that **a depth past the end of the chain
  now means the tracked position is wrong, not that the chain is finished** -
  a mis-read panel, or a counted outing that was abandoned. It clamps to the
  last known step and warns. Pricing it as a karaoke session instead, which is
  what the old fallback did, would have quietly stopped the bot taking outings
  the badge was telling it were on offer.
- The counter is lost if the bot restarts mid-career, but it resyncs the next
  time the Recreation panel is opened, which is every outing.
- A career that ends with steps left has spent outings on a chain it never
  cashed. Nothing prices that in: `outings.steps_remaining()` exists but no
  caller uses it, and turns-left-in-career is not derived anywhere.

## The Recreation panel was cancelling every outing - 2026-09-09

**Clicking Recreation with a friend support in the deck does not go out. It
opens a chooser**, and that chooser was never handled:

```
  Recreation                       <- assets/ui/recreation_panel.png, 1.000
    Riko Kashimoto   [gauge]
    Event Progress   > > > . .     <- assets/ui/event_progress.png, 1.000
    Aston Machan     Trainee       <- plain recreation
    Cancel                         <- cancel_btn.png, 0.982
```

`cancel_btn.png` matches that Cancel button at **0.982**, so the generic cancel
handler dismissed the panel on the next poll. Every outing the bot ever decided
to take was cancelled a moment later, and so was every mood-driven recreation,
for as long as a friend card has been in the deck. `do_recreation()` clicked
Recreation and returned; nothing clicked a row.

This is the same failure as the Zenith finals and the Complete Career
confirmation - a generic handler above a screen with no branch of its own.
Reordering the dispatch did not fix it, because there was still no branch to
reorder above.

### What the panel gives us

It states outright both things the chain tracker was inferring:

- **Which friend card is in the deck** - the row is named, and the name OCRs
  cleanly ("Riko Kashimoto").
- **How far the chain has run** - one chevron per step, filled blue as it
  advances. Filled chevrons are steps already done, so three filled means step
  four is next. That mapping comes from watching the bar go from zero filled to
  one filled across a single outing.

`core/state.py::check_recreation_panel()` reads both. The chevrons are counted
by hue (a flat cyan-blue, 180-220 degrees) rather than by template, so it does
not need to know whether the chain has three steps or five, and it survives the
fill animation. `outings.set_position()` takes the result and overrides the
counter, which cannot tell an outing that was taken from one that was opened
and abandoned - exactly what was happening.

Measured on a 1920x1080 Steam window: five chevrons 33x36 at x centres 627,
669, 712, 754, 797, all on y 399; card name text at x382-516, y342-356; Cancel
at (552, 774).

### The friend row is always the right row

It gives everything plain recreation does and advances the chain as well, so
the bot takes it whenever `event_progress` matches, clicking 30px above that
pill - a gap clear of the name, the Friendship Gauge and the chevrons. The
trainee row is the fallback when no friend row is on offer.

### Verified

`tests/test_recreation_panel.py`, 14 checks against two captured frames
(`tests/fixtures/recreation/`): the name and chevron count read correctly, the
empty chevrons are not counted, nothing matches on a frame without the panel,
the panel branch sits above the generic cancel handler in `career_lobby`, and
the click lands inside the row.

The game's own Log independently confirms the chain data. An outing logged
"Energy recovered by 30 / Stamina went up by 12 / Guts went up by 12 / Gained 3
hint level(s) for Rushing Gale! / Friendship with Riko Kashimoto is maxed out",
which is Riko step 5 ("A Peek at Her Heart") word for word out of
`support_card.json`, down to the good variant of its random roll.

That Log entry did **not** line up with the panel captured minutes earlier,
which showed three chevrons rather than four. The explanation was mundane - the
run was being played by hand between the two captures - and the mapping is
confirmed as it stands:

| chevrons filled | position | the next outing takes |
|---|---|---|
| none | step 0/5 | step 1 |
| three | step 3/5 | step 4 |

Filled chevrons are steps already done, so `set_position(card, filled)` records
`filled` as the depth and `next_outing()` predicts `filled + 1`.

### Open
- The panel geometry is fixed to the Steam layout. `RECREATION_ROW_X` and
  `RECREATION_TRAINEE_ROW_MOUSE_POS` carry the right suffixes to be shifted for
  emulators; `RECREATION_CHEVRON_BBOX` and `RECREATION_NAME_REGION` do too.
- Only one friend card has been seen in a deck. With two, the panel lists both
  and the reader takes the first row.
- The game has a Require Confirmation option per action, and **Recreation's is
  On**, which adds the "Go on a fun outing?" modal on top of the chooser. That
  is handled (see the live-run section below), but it is a user setting: with it
  Off the modal never appears and the chooser goes straight out. The branch
  copes with either, so it does not matter which way it is set.

## Outing readback from the game's Log - 2026-09-09

The original form of this item was "`RECREATION_ENERGY_ESTIMATE = 20` is an
average, not read back". That constant is gone, but the underlying gap stayed:
every number the outing scorer used came from a data file and nothing ever
checked it against the game.

The game checks it for us. The right-hand **Log** panel states what an action
actually did:

```
Energy recovered by 30.
Mood remains Great.
Stamina went up by 12.
Guts went up by 12.
Gained 3 hint level(s) for Rushing Gale!.
Friendship with Riko Kashimoto is maxed out.
```

- `state.read_log_lines()` OCRs `LOG_PANEL_REGION` (the lower part of the panel,
  where the newest entry sits - OCR over the full column is slow and the older
  entries are not wanted).
- `outings.parse_log_effects()` turns that into the same effects shape a
  prediction uses. It reads the phrasing the Log uses ("recovered by",
  "went up by", "Gained N hint level(s)") rather than the data file's ("+35"),
  and only keeps the **newest block** - the Log is a scrollback, so summing
  every effect line on screen would add several turns together.
- `outings.expect_readback()` records the prediction when the outing is taken;
  `confirm_outing()` compares once the lobby comes back.

### It found a bug on its first sample

The check reported `energy should have been 24, log says 30`. That was correct
and the prediction was wrong: **the same character ships at several rarities
with the same chain but different numbers**, and `load_chains` was merging their
option dicts with `.update()`, so whichever card the data file listed last won
and the other was silently discarded. Riko's step 5 gives Energy +24 on one card
and +30 on the other.

Chains are now built per card and averaged per character, because the Recreation
panel names the character but not which card it is. That gives a mean to score
against and a spread to judge a readback by.

### Judged on the spread, not the mean

Many steps carry a random roll ("Randomly either ... or ..."), and the two card
versions differ, so an outcome that disagrees with the mean is usually normal.
`average()` now records the range it averaged over, and `confirm_outing` only
warns when the actual falls outside it. Riko step 5 predicts energy 27 with a
range of 24-30 and hints 2 with a range of 1-3; the real outing gave 30 and 3,
which is consistent, and a fabricated "Energy recovered by 3" is still caught.

Mood is deliberately left out of the comparison. It caps at GREAT and a run sits
there most of the time, so "predicted +1, log says it stayed put" is the normal
case rather than a fault.

Verified by `tests/test_outings.py::test_readback`, against the OCR output of a
real outing kept verbatim, mangling included ("level(s)" reads as "levells)",
"Gale!" as "Galel").

### Open
- Only one phrasing sample. `LOG_PATTERNS` covers energy, stats, mood, hints,
  skill points, bond and condition clears, but only the energy/stat/mood/hint
  wordings have been seen in a real Log; the rest are extrapolated from it and
  will need a sample each. A line matching none of them is ignored rather than
  parsed loosely, so the failure mode is a missed effect, not a wrong one.
- `LOG_PANEL_REGION` assumes the Log tab is the one selected in the right-hand
  panel. If the user leaves it on Sparks or Agenda there is nothing to read, and
  the readback quietly finds nothing.
- The readback only reports. Nothing feeds the measured values back into the
  scoring constants, which is what would turn `MOOD_POINTS` and friends from
  estimates into something derived.

## Live run 2026-09-09 (Unity, Riko deck) - what it found

First run with the outing work in it. Reached Classic before being stopped
deliberately. Confirmed working live: the gains reader (5/5 facilities every
turn), spirit gauge and burst detection, cap headroom, and - for the first time
ever - a friend outing actually executing.

The stat headroom also validated the gains reader against the game's own
arithmetic: SPD printed `{spd 14, pwr 7}` and the headroom moved by exactly 14
and 7 with the other three stats untouched.

### Fixed: the outing confirmation wedged the bot

Picking a row in the Recreation chooser raises a second dialog - "Go on a fun
outing? This will take up the entire turn." - with Cancel and OK. It reuses the
chooser's green header, so:

```
recreation_panel.png   0.995   <- still matches, header is shared
event_progress.png     0.638   <- covered by the dialog
cancel_btn.png         0.997   <- the trap again
ok_btn.png             1.000   <- what we want
```

With `event_progress` covered, the panel branch took its "no friend row" arm and
clicked the trainee row co-ordinates into dead space, forever. The OK button is
the only reliable tell between the chooser and the confirmation, so the branch
now checks it first.

Note this is the *third* screen in this scenario where a generic handler matched
a confirmation modal. The dispatch ordering fix was necessary but it only helps
screens that have a branch; this one had none.

### Fixed: a garbled panel read walked the chain backwards

The confirmation dialog covers the card name and the chevrons, so
`check_recreation_panel` read `'Re'` and zero chevrons. `set_position` accepted
the zero because it only ignored unmatched names when no card was tracked yet -
so a good read of Riko at step 1 was immediately overwritten with step 0. A name
that will not match now means the whole read is untrusted and is discarded.

### Changed: the gauge bonus is capped below one burst

The run trained a facility with four charging gauges instead of one carrying a
ready burst:

```
guts  friendship 2.02 + unity 4.00 + gains 1.47 = 7.49   <- 4 charging gauges
wit   friendship 1.00 + unity 2.00 + gains 2.73 = 5.73   <- 1 READY burst
```

Checked against the guides before touching it. uma.guide scores a Spirit Burst
at **2 points in all three** of its turn-scoring tables and gives a charging
gauge **no score at all** - the 1.0 gauge weight here comes from UMAT's scenario
config, not the guide. Both game8 and uma.guide say to pop bursts immediately in
the early game, because bursts are the biggest contributor to levelling
facilities, and to start saving them only from Senior.

So `MAX_GAUGE_FRACTION = 0.75` caps the whole gauge contribution at 0.75 of a
burst: one gauge still scores 1.00, but four now score 1.50 rather than 4.00.
The turn above rescores to guts 4.99 / wit 5.73, i.e. the burst wins. "Half a
burst" was written with one gauge in mind; a facility can carry four.

Sources: uma.guide Unity Cup Career Guide; game8 Unity Cup Update Guide.

### Open
- `MAX_GAUGE_FRACTION` is a judgement call, not a measured number. The guide
  gives gauges no weight at all, so anything from 0 to just-under-one-burst is
  defensible; 0.75 keeps gauges meaningful as a tiebreak without letting them
  outrank a burst.
- Not yet re-run. The outing confirmation fix and the gauge cap are both
  untested against the game.
- The failure-label OCR fallback ("using the only percentage in the bubble")
  fired repeatedly from turn 9 onward.

### Readback, corrected by the live run

The first two live readbacks both reported a mismatch and **both were wrong**.

    Outing readback for riko-kashimoto step 2/5: energy should have been 24, log says 0

The prediction was right each time. Energy went 50.00 -> 74.58 (+24.6 against a
predicted 24) and later 76.69 -> 100.00. Three separate faults, all in the
comparison rather than the data:

1. **Absence read as zero.** The Log prints an "Energy recovered by" line only
   when energy moves, and one of these outings fired a random support event
   whose dialogue was the newest block. `parse_log_effects` now records which
   fields the Log actually mentioned, and a field it never spoke about is not
   compared at all.
2. **The wrong instrument.** The bot already measures the energy bar every turn
   by counting pixels, which is far more dependable than locating the right
   block of a scrolling Log. Energy is now judged on the bar (slack 3.0 for
   estimate noise); the Log is left to cover hints, stats and conditions.
3. **Spill counted as a shortfall.** Energy that would go past the cap never
   shows on the bar, so an outing at 77 granting 24 measures +23, and one at 90
   granting 30 measures +10. The expected range is now clipped to the headroom
   the bar had at the time.

Case 3 is why this needed fixing rather than loosening: without it, every outing
taken near a full tank would have reported a fault.

### Also: UMA_LOG_DIR

`utils/log.py` wrote to `<cwd>/logs` with no override, so running the test suites
during a live career appended to the log the supervisor watches for stalls and
that the run is diagnosed from. `log_dir` now honours `UMA_LOG_DIR`; default
behaviour is unchanged.

## Wit rainbow guard, and the wit energy band - 2026-09-09

### The guard was throwing away good turns

`rainbow_training` checked wit's rainbow count **after** `max()` and returned
`None` on failure, so a wit facility that won on points and then failed the
check took every other rainbow candidate down with it and dropped the bot into
the weaker `most_support_card`. There were also two different thresholds for the
same thing - `< 1` in the filter, `< 2.5` in the post-check - and the message
said "doesn't have any rainbow friends" when the count could be 1 or 2.

Now one named `WIT_MIN_RAINBOWS = 3`, applied in the filter, so a disqualified
wit simply leaves the runner-up standing. Selections are otherwise unchanged.

**A correction**: this was first written up as "the guard rejected the best turn
of the career", on the strength of a log line reading `Levels:{'yellow': 2}`.
That line prints `total_friendship_levels`, the aggregate over **all** card
types on the tile. `total_rainbow_friends` counts only the facility's **own**
type - which is what a rainbow actually is - so those two yellows were probably
not wit cards at all, and the guard may well have been right. Only the aggregate
is logged, so it cannot be told apart after the fact.

### The wit energy band

Wit is the only training that hands energy back rather than spending it, so in
the middle of the tank it is really buying the next turn: it keeps enough energy
to take a good training at 0% failure when one appears. The honest comparison
there is **wit or rest**, not wit or a real training.

    WIT_ENERGY_BAND = (30, 70)
    WIT_BAND_POINTS_PER_RAINBOW = 0.9
    WIT_BAND_MIN_RAINBOWS = 1

Below 30 there is too little left for wit to climb back to a safe level and
resting is the right answer. Above 70 the energy wit returns would spill and it
is a weak training again. Inside, the bonus **scales with wit's own rainbows**,
because a wit tile with none is weak whatever the energy is.

`WIT_BAND_MIN_RAINBOWS` is the judgement call: without it the band could never
fire, since `WIT_MIN_RAINBOWS` keeps wit out of the running below 3 rainbows and
3 is rare. Inside the band the bar drops to 1, on the grounds that the turn is
being weighed against resting.

The bonus is added in **both** `rainbow_training` and `training_score`, because
`most_support_card` is the path that actually ends in a rest - a bonus only in
the rainbow scorer could never win a turn back from resting.

Energy is read once in `do_something` and published through
`set_energy_level()`, the same shape as the stat headroom, rather than each
scorer taking its own reading.

Verified by `tests/test_rainbow.py` (15 checks): the runner-up survives a
disqualified wit, wit still wins with enough of its own rainbows, other card
types at max bond do not count as wit rainbows, the bar drops only inside the
band, the bonus scales with rainbows and applies to nothing else, and a
genuinely good training still beats a banded wit.

### Open
- The band edges and 0.9/rainbow are reasoned, not measured. The thing to watch
  is whether the bot starts taking thin wit turns when a rest would have served
  it better - the log says `Energy N is inside the wit band` on the turns where
  this is in play.
- Not run against the game.

## The readback is energy-only now - 2026-09-09

Two live faults on the first outing of career 4, from one log line:

    Outing readback for riko-kashimoto step 1/5:
      energy should have been 0, saw 66; skill should have been 0, saw 30

Neither number meant anything.

**The energy bar is covered by the Recreation panel.** `check_energy_level()`
logged `Couldn't find energy bar, returning -1` at exactly the moment
`expect_readback` took its reading, so `energy_before = -1` made the delta
`65.25 - (-1) = 66`, and `headroom = max(0, -1 - -1) = 0` collapsed the expected
range to zero. A -1 is a refusal, not a measurement, and it must never reach
arithmetic. `expect_readback` is now passed nothing when the read fails, and
`confirm_outing` returns None rather than guessing.

**Picking "the newest block" of the Log does not work.** That readback's block
was `"And so, we decide on the Fillies' Revue for her next goal!"` with
`Skill Pts went up by 30` - a goal-selection event, not the outing. An earlier
one caught the tail of a dialogue. The Log is a scrollback with no timestamps
and no boundary the parser can trust, and by the time the lobby returns the
outing's own entry may be several events back.

So the comparison is now **energy alone**, measured off the bar, which is
counted in pixels rather than read as text and has been right every time it
could read at all. Energy is also what separates one chain step from another, so
it is the field worth checking. `parse_log_effects` still runs and its result is
written to the log for the record - it is just no longer judged against.

### Open
- The Log parser is now dead weight for verification. It is kept because the
  wording table is the only record of how the game phrases outcomes, and a
  future check that can locate the right block would want it.
- Nothing verifies hints, skill points or condition clears any more. Only energy
  is checked.

## The Choices panel is read off the screen - 2026-09-09

Item 2's outstanding next step, and it closes the 8 blind top-choice picks a
career was making. `core/event_effects.py` plus `state.read_choice_effects()`.

**The premise in the old entry was wrong twice over.** It said the Effects
button had to be found by template and clicked, and that the button's position
varies. What is actually true:

- **Options > Career > "Always display choice effects"** opens the panel by
  itself on every choice event. That setting was already On. The normal path
  costs **no clicks at all**, which is the whole safety argument: a modal the
  dispatch has no branch for is the failure that cost 21 minutes on the sparks
  screen and cancelled every outing for a month.
- The Effects button does exist, at a fixed (779, 838) on the two-option
  events seen. It is kept only as the fallback for the setting being Off, and
  that path closes the panel again afterwards.

Proven rather than assumed: the frame captured *before* the only Effects click
of the session already had the panel open, and a second event confirmed it with
nothing clicked.

There is also a separate "display the effects of choices as a dialog box in the
Log tab" reading of that option, which is what the wording suggests. It is not
what happens. The Log shows dialogue and past `Selection` entries while an event
is pending - no effects - so the Log is useless for *deciding*. The panel
replaces the Log column instead.

### What the panel gives

```
Choices
  [Cheerleader in Noble White] King Halo
  Speed 198/1316  Stamina 153/1348  ...  Skill Pts 167

  Let's focus on healing up.                  <- green header, option 1
    Branch 1
      Energy +10 / Mood -3
      Previously trained attribute -10
      Random 2 attribute(s) -10
    Branch 2
      ... and Become Practice Poor
  Injuries are inevitable! You'll get used to it!   <- green header, option 2
    Branch 1
      Mood -3 / Previously trained attribute -10
      Random 2 attribute(s) -10 / Become Practice Poor
  [Close]
```

Options are located by their **green header bars**, counted by hue the way the
Recreation chevrons are, so the option *text* never has to be read - which is
lucky, because it OCRs badly: "We're doing some light training today." comes
back as `['doing', 'light training today:', "We're", 'some']`. The effects
underneath read cleanly. Order comes from header position, and an option's
effects are simply everything between its header and the next one, which works
for a one-line result and an eleven-line one alike.

Measured on 1920x1080 Steam: `CHOICES_PANEL_BBOX = (1060, 100, 1660, 950)`,
Close at (1357, 995). The top starts below the panel title so the title bar's
own green is not counted as an option.

### Green bars alone are not enough - the title gates the read

Counting green bars was the first version and it was wrong. **Every other panel
that uses that column has green section headings**, and they parse cleanly into
confident nonsense. Swept over 33 captured frames:

| frame | bars found | what it really was |
|---|---|---|
| quick-mode dialog | 4 | Career Profile behind it - Trainee, Legacy Umamusume, Support Cards, Event Bonus |
| tutorial info menu | 3 | the Log tab's Unity Cup scenario sections |
| five real events | 2 | genuine Choices panels |

Those produced option lists reading `legacy 1 legacy 2`,
`event bonus total ep 103%` and `tazuna hayakawa`. `best_choice` does **not**
reject that on its own: the lines are non-empty so every option scores 0, the
sort is stable, and it returns option 1 - silently outranking both the config
and the outcome tables on a reading of the Career Profile. Live, not
hypothetical: the tutorial info menu is a choice screen whose right column
carries those green Unity Cup headings.

So `read_choice_effects` is gated on `choices_panel.png`, the panel's own title,
which separates 1.000 against 0.453. Both false-positive frames are kept as
fixtures and each asserts three things - not taken for a panel, yields no
options, **and still has the green bars that would have parsed** - so removing
the gate fails the suite rather than quietly restoring the bug.

Template separation, worst positive against best negative:

| template | positive | negative |
|---|---|---|
| `assets/ui/choices_panel.png` | 1.000 | 0.453 |
| `assets/buttons/effects_btn.png` | 1.000 | 0.588 |

### Branches are averaged, not summed

`Branch 1` / `Branch 2` are alternative results the game picks between. Summing
every line - which is what `score_outcome` does - counts an outcome that only
sometimes happens as certain. On the injury event that meant charging option 1
with a guaranteed `Become Practice Poor` when it only carries it half the time,
which is the difference between the two options. Branches are split on the
marker and averaged.

Three phrasings appear only on screen and are handled in `event_effects`:
`Previously trained attribute ±N` (one stat), `Random K attribute(s) ±N` (K
stats) and `All attributes ±N` (five), each priced at the mean of the user's
stat weights. Everything else is delegated to `score_outcome`, so the condition
tables and stat weighting have one definition.

Two more the same sweep caught, both of which had been **scoring low rather
than failing**, which is why only a vocabulary census would have found them:

- **Hints.** The panel writes `Medium Corners Hint Lvl +1` - the skill name in
  front means the subject ends in `lvl`, not `hint`, so `score_outcome` priced a
  hint at **1 point a level instead of 12**. `Unyielding Spirit Hint Lvl +2` was
  worth 2 where it should be 24. Matched explicitly now, including the `Ivl`
  misread easyocr produces about half the time. `Hint Lvl 0` still scores 0,
  which is correct - it is a real line meaning no hint.
- **Cures.** `Randomly cures 1 bad condition(s)` carries no number at all, so
  the generic `subject ± amount` parser could not see it and it scored 0.
  Worth `CURE_POINTS = 25` per condition.

Vocabulary confirmed against live frames: `Energy ±N`, `Skill Pts +N`,
`Speed/Stamina/Power/Wit ±N`, `Friendship with <name> +5`, `Previously trained
attribute ±N`, `Random N attribute(s) ±N`, `Become <Condition>`, hint levels,
cures, and `Branch 1`/`Branch 2`.

### The contrast pass is not optional here

Raw OCR of this panel drops the minus off `Mood -3` and mangles `attribute(s)`
into `attributels)`. A dropped sign turns a penalty into nothing, which is the
one error that is not safe - it biases the bot toward the option it should be
avoiding. `enhance_for_reading` first reads all 11 lines of the branched event
correctly where the raw pass got 9. The mangling is repaired in `clean()`
regardless, and both are pinned by tests.

### Precedence

    config override  ->  Choices panel  ->  outcome tables  ->  top choice

The panel runs **ahead of the name match**, because it needs no name at all.
That is the case this was built for: live, `Don't Overdo It!` OCR'd as
`Don't Overdo Itl`, missed its config entry at 78.79% against a 0.8 threshold,
and the panel scored it anyway (`#1=-98, #2=-148`, picked 1).

Config still wins where it exists, unchanged: a chain event is picked to
continue the chain, and the panel only ever shows the immediate effects.

### Verified

`tests/test_choices_panel.py`, 35 checks against five captured frames in
`tests/fixtures/choices/`: both panels read line for line, a frame showing the
Log reads as *no panel* rather than as options that do nothing, two identical
branches score the same as one, a penalty in one branch of two costs half, the
unnamed-attribute phrasings scale with the number of stats, both OCR
manglings still parse, and the injury event prefers healing up.

Live: read correctly on every event of a Junior year, and the full chain
(read -> score -> click) confirmed in the log.

### Open

- **Dialogue-only events still reach `select_event`.** `event_choice_1.png`
  matches a scenario event with no choices at all ("Holiday Season"), so the
  bot OCRs a name, misses in the config and the tables, finds no panel and no
  Effects button, and clicks "top choice" - which on that screen is just a tap
  that advances the dialogue. Harmless, but it spends an OCR pass and two fuzzy
  matches per dialogue event, and it is the one case where "no effects to read"
  is normal rather than a fault. `note_unread_event` logs it at debug level for
  that reason. Briefly had a retry loop here on the theory that the panel was
  merely late; it was not, and that has been backed out.
- **Only two-option events have been seen**, across 9 real panels in a Junior
  year. Nothing assumes a count, but the header spacing has not been checked
  against a real three-option event, and `LAST_EVENT_CHOICE_ICON_TOP` suggests
  up to five are possible. Note the 3- and 4-bar frames in the sweep above were
  all false positives, not evidence that more options work.
- The vocabulary is only as complete as what has appeared. A line matching no
  rule scores 0 and is logged as `no rule for ...`, so gaps are visible rather
  than silent, but they under-count rather than fail. Bond, hint and skill-point
  phrasings on this panel have not been seen yet.
- `CHOICES_PANEL_BBOX` carries the right suffix to be shifted for emulators, but
  the right-hand column does not exist in the portrait layout at all, so the
  reader simply finds no headers there and the tables take over.
- The panel overlaps `LOG_PANEL_REGION`. Nothing reads the Log during an event,
  so they do not collide today, but the two regions are now aliases for the same
  column in different modes.
- Not checked: whether the Effects-button fallback works, since the setting has
  been On throughout. The button is found and the close position is measured,
  but that path has never run.

## The repeat guard answered its own confirmation with "No" - 2026-09-09

`select_event`'s escape hatch took the **last** option every time. That is right
for leaving a menu that reopens - the terminal option is last ("That's all,
thank you.") - and wrong for the confirmation that leaving raises, because a
confirmation's affirmative is the **first** option.

So the Unity Cup tutorial ran: last option leaves the menu, "Are you sure?",
last option answers "No", back to the menu. It reached `REPEAT_GIVE_UP`, reset,
and started the identical cycle over. It would never have escaped:

    12:07:30 Tutorial has come back 3 times, taking the last option to break out.
    12:07:36 Tutorial has come back 4 times, taking the last option to break out.
    12:07:51 Tutorial has come back 6 times and the last option did not help

The guard now alternates - odd attempt takes the last option, even takes the
first - which covers both screens without having to tell them apart.

Same family as the four generic-handler bugs above: a rule that is correct for
one screen, applied to a screen it does not fit.


## Skill matching, and skill names from master.mdb - 2026-09-09

`buy_skill` compared the OCR'd row straight against the 14-entry configured
list with a 0.8 Levenshtein threshold. The names on that screen do not survive
OCR anywhere near well enough for that:

| OCR read | actually |
|---|---|
| `rtotessoi 0i Cunvatule` | Professor of Curvature |
| `Nesttam rtont nunnels` | Hesitant Front Runners |
| `Fiustelea race Clasels` | Flustered Pace Chasers |

**One row in fifteen cleared 0.8.** Traced through a whole career: the
configured list bought *nothing*, `No matching skills found` ten times, and
every purchase came from the end-of-career `match_any` pass that takes whatever
is affordable. The list was inert and nobody could tell, because the fallback
buys things and looks like it is working.

### Canonicalise first, then compare

Matching a mangled string against 14 entries is the wrong shape. Matching it
against *every real skill name* and taking the closest gives a canonical name,
which is then compared to the list exactly. Same idea as canonicalising an
event name before looking it up. All 17 logged reads resolve.

Three details, each measured rather than assumed:

- **`fuzz.ratio`, not `WRatio`.** WRatio's partial matching sent
  `oprng Runner U` to *Front Runner Straightaways* instead of *Spring Runner*.
  `token_sort_ratio` is far worse again (9/17 against 13/17).
- **Strip the rank glyph, anchored on whitespace.** easyocr renders ○ and ◎
  identically as `@`, `U` or `o` - and often drops them entirely - so the two
  ranks cannot be told apart and a config entry written with either should match
  both. Requiring whitespace before the glyph rewrites **0 of 383** real names;
  a naive trailing strip breaks `Up-Tempo`, `Passing Pro`, `Trick (Front)` and
  `I Can See Right Through You`.
- **The direct comparison still runs first**, so a clean read behaves exactly as
  before and this can only add matches, never remove one.

`CANONICAL_MIN_SCORE = 60` because the lowest correct score observed was 63.6.

**A correction, because the first version of this section reasoned from the
wrong premise.** It justified the floor as protection against "a skill missing
from the name list", and measured that by holding out each of the 888 distinct
names and asking what its nearest neighbour scored - median 62.7, so 61% of
missing skills would slip through a floor of 60.

That scenario does not exist. `master.mdb` is the game's own database, so every
skill the buy screen can show is in it by construction. A low score therefore
never means "unknown skill"; it means **the OCR is wrong**, because the correct
answer was definitely available. The refusal path now says exactly that in the
log, which makes it the cheapest signal there is that a read needs looking at.

The earlier "highest junk was 66.7" figure was worth even less: it was
`"Skill Pts"` matching *Killer Tunes*, one of seven strings invented for the
purpose. They are UI text that cannot appear in a crop anchored to a buy button,
and a follow-up check showed the margin does not stop them anyway.

`CANONICAL_MIN_MARGIN = 5` survives that correction on its own merits, but for a
different reason than it was introduced with. The game ships near-identical
pairs - `risk-taker`/`risk-maker` at 90.0, `ignition`/`reignition` at 88.9 - and
a read nearly as much like one as the other is not evidence for either. Buying
the wrong skill spends points that cannot be recovered, so an ambiguous read is
refused rather than guessed. It costs nothing measurable: across the 17 rows
logged from a career and the 14 read live off the Skills panel, every correct
match won by at least 6.5 points, median 22.

### The names come from master.mdb

`data/skills.json` has 383 names. `master.mdb` `text_data` category 47 has
**980**, and is repatched with the game. Measured on both samples:

| sample | skills.json | master.mdb |
|---|---|---|
| logged buy_skill reads (17) | 17 correct, 0 wrong | 17 correct, 0 wrong |
| live Skills panel reads (14) | 13 correct, 1 refused | **14 correct, 0 wrong** |

The worry was that 597 extra candidates would cost precision, since a mangled
read has more wrong neighbours to land on. It did not - zero wrong matches
across 31 cases - and it fixed the one refusal, a scenario skill
("Louder! Tracen Cheer!") the JSON does not contain at all.

`core/masterdb.py` is deliberately boring: it **copies the database before
opening it**, because opening the live one can leave -wal/-shm beside it and
take locks on a file the game is using. The copy is keyed on mtime and size, so
a patch is picked up and an unchanged database is not copied twice. Read-only,
local, nothing written back. `UMA_MASTER_MDB` overrides the path.

It **falls back to `data/skills.json`** when the database is not there, which is
what happens on an emulator or a non-default install, and to raw matching if
neither loads. Both paths are tested.

### What the OCR itself can and cannot be blamed for

Read live off the Umamusume Details > Skills panel, the *same* pipeline that
produces `rtotessoi 0i Cunvatule` on the buy screen reads
`Professor of Curvature` perfectly - mean similarity 0.928 over 14 rows, with
only three systematic errors: `!` read as `l`, `=` read as `-`, and ○ dropped
entirely (easyocr never emits it).

So the buy screen's mangling is **not** the preprocessing. Its crop is
`(x - 420, y - 40, w + 275, h + 5)`, which spans y-40 to y-10 and therefore ends
**10px above the buy icon's top edge**. Clipping text along its bottom is
exactly what turns `rn` into `m` and `h` into `n`. Worth fixing at source, and
it needs a live buy screen to measure.

### Preprocessing was investigated and left alone

12 variants scored against 11 ground-truth crops (event names, Choices panel
lines and headers, career goal, year). `3x` + Otsu binarisation wins on text -
mean 0.909 -> 0.990, and white-on-green headers 0.53 -> 0.97.

**It must not be adopted.** Run through each field's real code path, Otsu reads
**0 of 5** stat caps where the current pipeline reads 5/5. That failure would
have been silent: -1 is the designed refusal for an unreadable cap, so the bot
would fall back to `DEFAULT_STAT_CAP` on every stat and quietly train worse.

The trade-off is monotonic across every variant tried - more text accuracy, more
cap failures:

| variant | text | headers | stats | caps |
|---|---|---|---|---|
| current (2x, bicubic, c1.5) | 0.909 | 0.669 | 6/6 | **5/5** |
| 3x, bicubic, c1.5 | 0.947 | 0.863 | 6/6 | 4/5 |
| 3x, autocontrast + c1.5 | 0.959 | 0.882 | 6/6 | 2/5 |
| 3x, otsu | 0.990 | ~0.98 | 6/6 | **0/5** |

And the gains land on white-on-green option headers, which nothing reads - the
Choices panel reader uses header *positions*, not their text. The current
pipeline is already the one matched to the fields the bot depends on.

### Verified

`tests/test_skill_match.py`, 21 checks, no easyocr and no screenshots: the OCR
strings are copied verbatim from a career log, so it pins real damage rather
than invented damage. Covers the mdb path (skipped, not failed, where the game
is not installed), the JSON fallback, the rank-glyph strip against all real
names, and that an unlisted skill is still not bought.

### Open

- The floor and margin currently reject nothing in either sample, so they are
  backstops rather than filters doing daily work.
- **DECIDED - Steam only, and that is fine.** The JSON fallback is gone, so a
  machine without master.mdb identifies no skills and buys none. That is the
  emulator case, where the game runs inside BlueStacks/LDPlayer and writes no
  LocalLow copy on the host. Not worth solving: this setup is Steam. If it ever
  matters, the fix is to commit a copy of master.mdb to the repo - no licensing
  problem here since nothing is published - but a committed copy goes stale on
  every game patch, which is the exact property reading the live file was chosen
  for. It would be a worse source everywhere except that one host.
- Because OCR never emits the glyph, `Standard Distance` canonicalises to the
  ◎ entry when the screen shows ○. Matching is unaffected - it is
  rank-insensitive by design - but the canonical name reported can name the
  wrong rank.
- **DONE (scoring) / open (wiring) - the purchases can now be ranked.** See
  "Which skills to buy, scored for Team Trials" at the end of this file.
  `buy_skill` itself is still greedy in scroll order; `core/skill_score.py`
  decides what *should* be bought but nothing calls it yet.
- master.mdb is now read for skill names only. Category 181 (12,758 event names)
  would canonicalise event-name OCR the same way, and 28/29/32 (race names)
  would stop `data/races.json` going stale. Both are small changes now that
  `core/masterdb.py` exists.


## Which skills to buy, scored for Team Trials - 2026-09-09

`core/skill_score.py`. Ports the condition scorer from the public optimizer at
https://daftuyda.moe/optimizer onto master.mdb.

### The objective, which took a correction to get right

The first reading of that optimizer was that it did not transfer, because it
scores skills purely on **activation** - a gold activation pays 12 SV and a
white one 5, whatever the skill actually does - while a career bot presumably
wants skills that win races.

That was backwards. **A career exists to produce an Uma for Team Trials**, and
career races are winnable without skills at all. So Team Trials scoring *is* the
objective, and what a skill does really is irrelevant. Everything below follows
from that.

    consistency = timing*0.45 + breadth*0.30 + scenario*0.25 - strictness
    composite   = 0.6*consistency + 0.4*costEfficiency   (ranking and display)
    objective   = consistency * SV                       (what the planner maximises)

- **timing** - `always==1` 0.98; `is_lastspurt`/`is_finalcorner` 0.88, or 0.76
  with `_random`; `phase_random`/`corner_random` 0.62.
- **breadth** - range coverage parsed off `order`, `order_rate`,
  `distance_rate`. `order==1` (must be leading) caps at 0.18.
- **scenario** - penalties for what nobody controls: `blocked_*` -0.22,
  `is_surrounded`/`temptation` -0.20, `is_overtake` -0.18.
- Condition blocks combine as `1 - prod(1 - 0.9*score)`, an OR: a skill with two
  triggers fires if either is met.

Two inputs are better than the source's, because the database has them rather
than having to be guessed from a web page: gold/white is `skill_data.rarity`
(1 white, 2 gold) instead of "cost >= 170", and costs are the real
`single_mode_skill_need_point.need_skill_point`.

Selection is an exact DP knapsack over the budget, with skills grouped so only
one rank of a skill can be taken.

### Four bugs in THIS port, each found by running it rather than reading it

To be clear about whose bugs these were: all four were introduced here, writing
`skill_score.py`. None is a fault in the source optimizer, and none existed in
this repo before - there was no planner at all. Two of them (2 and 4) are things
the source gets right that the first port simply left out, which is the usual
way a port goes wrong: the parts that look like detail are the parts carrying
the hard-won knowledge.

Every one spent an entire budget on something worthless, and none would have
shown up in a unit test written from my own design - they needed real data.

1. **It bought debuffs.** The first run put all 400 points into ten
   `Fukushima Racecourse ×` - *"moderately decrease performance"*, 40 SP each.
   They are the cheapest skills in the game with trivially satisfiable
   conditions, so consistency-over-cost rates them top. Excluded on
   `grade_value < 0`, which catches **48** where the `×` glyph catches 33:
   `Gatekept`, `Defeatist`, `Packphobia` and `Paddock Fright` are debuffs with
   ordinary names.
2. **It bought racecourse greens.** Eleven venue-locked passives
   (`track_id==10004`, `time==4`) that pay out only if the draw sends you there,
   which nothing controls. This is the source's `GREEN_PASSIVE_PENALTY`, which
   the first port skipped. Identified by `float_ability_time == -1` plus a
   volatile condition, and excluded by default.
3. **The objective counted cost twice.** The planner maximised the *composite*,
   which already divides value by cost, while the knapsack also constrains cost
   through the budget. That degenerates into "buy whatever is cheapest" - a
   400-point plan of five 70-point passives ahead of any gold skill. The
   objective is expected SV; the composite is for display only.
4. **The aptitude filter was too strict.** Filtering on a single distance threw
   away Mile skills for an Uma with Sprint A *and* Mile A, which runs both.
   Aptitudes are sets.

Result for a Front / Sprint+Mile / Turf Uma at 400 SP: Concentration (140),
Taking the Lead (120), Nothing Ventured (120) - 26.7 expected SV, all gold.

### It found a live mistake in the config

`Speed Star` is on the configured skill list and its condition is
`running_style==2` - Pace only. On a Front runner it is 180 skill points that
can never fire. `Keen Eye` is `distance_type==2`, so it is dead in a Sprint race
too, though fine for an Uma that also runs Mile.

### Verified

`tests/test_skill_score.py`, 30 checks, no easyocr and no screenshots - pure
logic over master.mdb, so it runs in about a second. The first three tests pin
bugs 1, 2 and 3 above against the real database rather than against invented
data.

### Open

- DONE - `buy_skill` now calls it at career end. See "Buying skills, revamped"
  at the end of this file.
- Costs on screen are not read at all; the planner takes them from the database,
  which assumes the OCR'd name resolved to the right skill. That is the same
  dependency the matching work has, and the clipped crop still undermines it.
- `disable_singlemode` is carried through but not used as a filter. 354 of 577
  purchasable skills have it set, including every `◎` rank, which suggests it
  means "not directly buyable in a career" - but that reading is unverified, and
  filtering on a guess would silently hide skills that are really on offer.
- The weights are the source optimizer's, not measured here. They are a
  reasonable prior rather than something this repo has evidence for.


## Buying skills, revamped - 2026-09-09

Three changes, and they split the job in two because the right answer differs
between the middle of a career and the end of one.

### Config: what this Uma will actually run

`skill.skill_distance` (a list) and `skill.skill_run_style`. A skill gated on a
running style or distance the trainee does not have can never fire, so these
decide what is worth any points at all. Distance is a list because an Uma with
Sprint A **and** Mile A enters both, and filtering on one throws away half a
usable list.

All three edits the repo requires: `config.template.json`,
`state.reload_config()`, and `web/src` - a new `SkillAptitude.tsx` with toggle
buttons, the zod schema, and `web/dist` rebuilt. `node_modules` was not
installed, so that needed `npm install` first; the build then caught an unused
import in the new component.

### Mid-career: usable, and only at max hint

The discount on a skill comes from its hint level, so **the hint level is the
signal** - at max hint the price is as low as it will ever go. Levels 1-3 take
10% off each and 4-5 take 5% each, so max hint is 40% off; Fast Learner takes
another 10% off everything.

Hints keep arriving all career. A skill bought at hint 2 costs a fifth more than
the same skill bought later, and a point spent early cannot be spent again, so
anything not at max hint is left for the end-of-career pass.

`at_max_discount(record, cost, hint)` checks the hint level first and falls back
to comparing the printed price against the database's undiscounted cost when the
badge will not read - the same conclusion by arithmetic instead of by reading a
number the game already worked out. The fallback is deliberately generous
(`<=`, plus slack) because Fast Learner discounts further still.

### Career end: spend it all, by plan

`buy_planned()` scans once to see what is offered *and what it actually costs*,
runs the knapsack from `skill_score` against the readable skill points, then
scans again to buy the plan. Two passes because scrolling invalidates every box,
so the second matches by name rather than by remembered position.

Using the on-screen price rather than the database one matters: the database
price is undiscounted, so planning on it would under-spend and leave points to
be destroyed - the one thing this pass exists to prevent.

### DONE - the offsets are measured, and the name crop was the OCR bug

Measured on a live buy screen (Grass Wonder, Junior Pre-Debut, 1920x1080).
Buttons sat at x=784 with a row pitch of 156.

    SKILL_NAME_OFFSET = (-420, -52, 305, 30)
    SKILL_COST_OFFSET = (-75, -8, 70, 40)
    SKILL_HINT_OFFSET = (-102, -56, 118, 44)

**The name crop was the whole OCR problem.** The old one covered y-40..y-10
while the name sits at y-45..y-29, so it sliced the ascenders off and padded the
bottom with empty row. Same image, same OCR, only the crop moved:

| crop | reads |
|---|---|
| dy=-40 (old) | `benoia nine Emperor $ DiviIne mignt` |
| dy=-52 (new) | `Behold Thine Emperor's Divine Might` |

Six of six rows now read 100% correct. Everything written earlier about
canonicalising damaged names still holds, but the damage was self-inflicted -
not a limit of easyocr, and not something preprocessing could have fixed. The
preprocessing investigation that concluded "leave it alone" was looking at the
wrong thing.

The guessed offsets were badly wrong: cost was put at dx=-118 (really -75) and
hint at dx=-250 (really -102, and *above* the price rather than beside it). The
fail-closed design is what made that harmless - nothing was bought, rather than
the wrong thing being bought.

**The hint badge is two lines**, "Hint Lvl 2" over "20% OFF!", which made
extract_number useless: it sees both 2 and 20 with no way to tell which is the
level. `read_hint` reads it as text and separates them by context, returning
both. Either half is enough, because level 5 and 40% off are the same fact.

    Hint badge 'Hint Lvl 2 20% OFFI' -> {'level': 2, 'discount': 20}

A row with no hint shows no badge and reads as an empty string, which returns
None rather than a level of 0.

### Verified live, end to end

Through the real `scan_rows` against the screen:

| name read | cost | hint | usable | max discount |
|---|---|---|---|---|
| Behold Thine Emperor's Divine Might | 160 | level 2, 20% | yes | no - deferred |
| Homestretch Haste | 170 | none | yes | no - deferred |
| Slick Surge | 180 | none | no - Late Surger only | - |
| Flustered Pace Chasers | 130 | none | no - debuff | - |

`Flustered Pace Chasers` is a real, purchasable debuff sitting in the list
("slightly increase fatigue for pace chasers"), so excluding negative
grade_value is not a hypothetical safeguard.

### The remaining failure modes still fail closed

Named without the `_REGION` suffix on purpose: `adjust_constants_x_coords`
shifts every `_REGION` constant by the emulator offset, and shifting a *relative*
offset would move the crop clean off the row.

Every unreadable value means **do not buy**:

- mid-career, nothing readable -> skip, and the end-of-career pass gets it.
  That is arguably the better strategy anyway, so a wrong offset costs nothing.
- career end, no plan -> falls back to the old "buy anything affordable",
  because points there are destroyed outright and buying something beats
  buying nothing.

`tests/test_buy_skill.py` has a `test_reading_failures_are_safe` group pinning
exactly that. Worst case the behaviour degrades to what it was before.

### Open

- **DONE - offsets measured and verified live.** Mid-career buying now works;
  on the screen tested it correctly deferred everything, because nothing was at
  max hint yet.
- Not yet seen: a row actually **at** max hint (level 5). Every hint on the test
  screen was level 2, so the buying branch has been watched refusing but never
  accepting. The refusal is the safe half.
- **`skill.skill_list` is no longer used for buying.** The rule is now "general
  or matches this Uma's aptitudes, at max hint", which is what was asked for,
  but it means the configured list only survives as documentation. Worth
  deciding whether it should still gate purchases.
- **DONE - `core/skill_tiers.py` is the drive.** `MIN_BUY_TIER = "A"`, enforced
  in `usable_here`, so B tier and unranked skills are not bought. B tier stays
  in the file deliberately; the floor is a buying decision, not a claim the
  information is worthless.

  **Unranked skills fail the floor too, and that is deliberate.** The tier list
  is not exhaustive, so this skips some genuinely good skills - spending points
  on a skill nobody rated is the worse mistake. Confirmed as wanted, so it is a
  decision rather than an open question.
- DONE - `skill.skill_list` is gone from the config, `state.py`, the zod schema
  and the UI, and `update_config` drops it from an existing config.json.
  `is_skill_match` went with it - the list was its only caller. `canonical_skill`
  stays, because the scan still has to turn a mangled row into a real name
  before anything can look up its tier or its aptitudes.
