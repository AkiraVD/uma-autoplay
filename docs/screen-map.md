# Screen map (observed by driving the game manually)

All coordinates are **screen pixels at 1920x1080, Steam client**. The game
viewport is the vertical strip `x = 150..950` (`GAME_SCREEN_REGION`). Anything
added here must use the `_REGION` / `_BBOX` / `_MOUSE_POS` suffix convention,
which says which rectangle format a constant uses. (Emulator support, and its
`+405` x-shift, was removed on 2026-09-15.)

Captured live on a Junior Year Pre-Debut run (Agnes Tachyon, URA Finale).

## 1. Every screen names itself

There is a **dark title bar in the top-left corner** that states which screen we
are on, in plain text:

| Screen | Header text | Region |
|---|---|---|
| Career lobby | `Career` | `(150, 4, 300, 32)` |
| Training | `Training` | same |
| Skill purchase | `Learn` | same |

Modal dialogs do **not** use it — they dim the header behind them and draw their
own **green title bar** centred at `y ~= 54` (e.g. Full Stats = `Umamusume Details`).

So screen identification is a single small OCR read, not a pile of template
matches. Nothing in the bot currently uses this.

## 2. Career lobby (header `Career`)

Six buttons, fixed positions, two rows (label centres):

| Button | Position | Notes |
|---|---|---|
| Rest | `(351, 858)` | |
| Training | `(554, 854)` | |
| Skills | `(757, 858)` | opens the `Learn` screen |
| Infirmary | `(390, 974)` | greyed out when there is no condition |
| Recreation | `(552, 975)` | |
| Races | `(714, 977)` | padlock icon while Pre-Debut |

Row 2 is inset and drawn behind row 1 (a fan layout), so the two rows have
different x spacing (203.5 vs 163).

Other lobby elements: turn box `(255..440, 40..155)`, goal bar, energy bar,
mood badge (`MOOD_REGION`), race-status pill (`Debut`) at `(255..415, 168..208)`,
Tazuna HINT bubble top-right, `Full Stats` button at `(793, 650)`,
stat row at `y 700..765`, `Skip`/`Quick` at the bottom.

**The `Duel!` event badge also appears on the lobby Training button**, not just
on a facility - it is an "there is an event in training" marker.

## 3. Training screen (header `Training`)

### 3.1 The five buttons are on a fixed grid

Measured by colour-segmenting the button row across many frames:

```
x =  337   445   552   660   767      (spacing 107.5)
     spd   sta   pwr   guts  wit      (always this order)

y = 910  when resting   (disc 91x95, spans y 863..957)
y = 865  when selected  (raised 45px, spans y 820..910)
```

The two states overlap on `y = 863..910`, so **`y = 886` lands inside the disc
whether or not the button is selected** (23px of margin either way).

### 3.2 A banner says which facility is selected

Green banner at **`(150, 168, 390, 68)`** reads `"<Facility> Lvl <N>"` plus a
flavour line:

```
Speed Lvl 1 / Turf        Stamina Lvl 1 / Breaststroke
Power Lvl 1 / Dirt        Guts Lvl 1 / Incline
Wit Lvl 1 / Studying
```

This is the authoritative read of the current selection **and** it exposes the
facility level, which the bot never reads today (facility level is a `+1` to
base stat gain per level).

### 3.3 Click semantics (the important part)

Exactly one facility is selected at a time (raised, yellow chevrons beneath,
failure bubble above it, its support cards listed on the right rail).

- Clicking a **different** facility -> **selects** it. Free, no turn consumed.
- Clicking the **already-selected** facility -> **executes** the training.

This is what makes naive scanning dangerous, and it is why the existing code
uses press-and-hold previews. It also means the entry selection matters: on
entering the screen some facility is already selected, and **which one is not
deterministic** (observed `Stamina` once, `Speed` another time), so it must be
read, never assumed.

### 3.4 Everything else on the screen

- Failure bubble: floats **above the selected column**, so it moves with the
  selection. Blue at low %, orange/red at high %. `FAILURE_REGION` is a wide
  band that covers all five positions; its right edge (`x = 810`) only just
  clears the Wit bubble.
- Stat gains: `+N` numerals sit directly above their stat box, `y ~= 650..700`.
  They visually overlap the stat boxes, which makes them OCR-hostile.
- Support cards: right rail `(840..950, 150..700)` = `SUPPORT_CARD_ICON_BBOX`,
  **only for the currently selected facility**.
- `Back` at `(218, 1039)`.

## 4. Event choices

Choice rows are **bottom-anchored**: the last choice is always at
`y ~= 753`, and earlier choices stack upward in steps of **111 px**.

```
2 choices -> y = 642, 753
3 choices -> y = 531, 642, 753
```

So with `n` choices, choice `i` (1-based) is at
`y = 753 - (n - i) * 111`, `x = 553` (icon at `x = 291`).

The current code instead template-matches the first choice icon and steps
**down** by `choice_vertical_gap = 112`. That works, but it depends on the
`event_choice_1.png` template matching, and the true step is 111.

Choice icons are colour-coded by index (1 green, 2 yellow, 3 pink), which is why
a template of the green icon happens to anchor on choice 1.

Event name banner: `EVENT_NAME_REGION` reads correctly (`Paying It Forward`,
`Happy Meek's Challenge!`). Banner types seen: `Support Card Event`,
`Main Scenario Event` (with a gold URA Finale badge), `Trainee Event`.

Scenario events can carry a **`Predictions` column** (`◎` / `○` / `△`) that
literally rates the options - free signal the bot ignores.

## 5. Full Stats modal (`Umamusume Details`)

Opened from `(793, 650)`, closed at `(553, 997)`. Contains, in this order:
character name + `Potential Lvl`, stat row with caps, `Track` / `Distance` /
`Style` aptitudes, **`Growth Rate`** row, then a `Conditions` / `Skills` tab pair.

Two things here the bot does not use:
- **Growth Rate** (this run: Speed +20%, Guts +10%) - a direct multiplier on
  training gain.
- **Style aptitudes** (Front/Pace/Late/End) - only track and distance are used
  when filtering races.

## 6. Skills screen (header `Learn`)

Skill points shown at `(744, 355)` (different position from the lobby's
`SKILL_PTS_REGION`). Scrollable skill cards, each either an `Obtained` pill or a
price with `-`/`+` steppers and an optional `Hint Lvl N  10% OFF!` badge.
`Confirm` `(553, 912)`, `Reset` `(772, 912)`, `Back` `(218, 1039)`.

## 7. Stat caps move during a run

Observed the Speed cap change `1400 -> 1404` mid-run from an event, alongside
per-stat caps of `1464` / `1432` from inherited sparks. Caps must be read from
screen every time; they cannot be hardcoded or cached across turns.

---

# Deduced: how the bot should click training

## The problem with what it does now

`check_training()` locates each facility by template-matching
`assets/icons/train_<key>.png`. That is fragile for reasons that have nothing to
do with the crop quality:

- A random **`Duel!` badge** overlaps a facility icon and kills the match. The
  badge also **bounces** (~29px vertically), so no single crop is safe.
- A missed match silently drops that facility from consideration for the turn.
- It costs five template matches per turn for information that is **constant**.

The icons never move. Matching them is solving a problem the game does not have.

## The rule set

1. The five facilities are always `spd, sta, pwr, guts, wit`, left to right.
2. Their x positions are fixed: `337, 445, 552, 660, 767`.
3. `y = 886` hits the disc in both the resting and the selected state.
4. Clicking a **non-selected** facility selects it (free).
   Clicking the **selected** facility trains it (consumes the turn).
5. The green banner at `(150, 168, 390, 68)` always names the selected facility.

Rules 4 and 5 together give a scan that is safe by construction: never click
blind, and never click the same facility twice without re-reading the banner.

## Scan (reads all five, cannot train by accident)

```
enter Training                       # lobby (554, 854)
selected = read_banner()             # e.g. "spd" -- must be read, not assumed
record(selected)                     # its data is already on screen

for key in [spd, sta, pwr, guts, wit]:
    if key == selected: continue     # never click the selected one
    click(x[key], 886)
    assert read_banner() == key      # cheap guard; the game confirms the click
    record(key)
```

Four clicks, five readings, zero template matches, zero risk of committing a
turn. The banner check also turns a mis-click into a caught error instead of a
silently dropped facility.

## Execute

```
def train(key):
    if read_banner() != key:
        click(x[key], 886)           # select
        assert read_banner() == key  # refuse to double-click on a bad read
    click(x[key], 886)               # second click on the selected one -> trains
```

Verified live: selecting Speed then clicking it again ran the training and
returned to the lobby (`header: Training -> Career`).

## What this changes in the code

- `utils/constants.py`: add `SPD/STA/PWR/GUTS/WIT_TRAIN_MOUSE_POS = (x, 886)`.
  Read them as `constants.FOO` at call time, not into a module-level dict at
  import.
- `core/execute.py::check_training()`: drop `locateCenterOnScreen` on the icon
  templates; iterate the fixed positions and verify via the banner.
- `core/execute.py::do_train()`: same, using the two-click execute above.
- `assets/icons/train_*.png` become unused for positioning. They are currently
  the untouched originals - the experimental label crops were reverted.

Bonus, free once the banner is being read: `"<Facility> Lvl <N>"` also yields the
**facility level**, which feeds the stat-gain formula
(`uma.guide/guides/career-mechanics`) and is not read anywhere today.

---

# Implemented

- `utils/constants.py` - `SPD/STA/PWR/GUTS/WIT_TRAIN_MOUSE_POS` and `TRAINING_BANNER_REGION`.
- `core/state.py` - `check_selected_training() -> (key, level)`, fuzzy-matching
  the banner text so OCR reading `Wit` as `WRt` still resolves. Returns
  `(None, 0)` off the training screen, which is how callers detect that.
- `core/execute.py` - `training_pos()`, `select_training()`,
  `wait_for_training_screen()`; `check_training()` and `do_train()` rewritten to
  the protocol above; the now-unused `training_types` icon dict removed.

`level` is currently best-effort and usually comes back `0`: the `Lvl N` digit is
small and OCR drops it. Nothing consumes it yet, and forcing a second, upscaled
OCR pass per facility would add five reads per turn to the hot path for a value
no logic uses - so it is left as a cheap by-product until something needs it.

## Also fixed: `go_to_training()` searched the whole desktop

It called `click("assets/buttons/training_btn.png")` with **no `region`**. The
template is a short generic strip, and a full-screen search matched unrelated
desktop UI at `(1324, 58)` - outside the game entirely. `click()` then reported
success while the game never left the lobby, so `check_training()` ran against
the lobby every time. Now scoped to `SCREEN_BOTTOM_REGION`, where it matches the
real button at `(553, 871)` with score 0.968.

## Verified live

Full `go_to_training()` -> `check_training()` -> `do_train()` cycle against the
running game: 5/5 facilities read per turn with no template matching and no
accidental commits, and `do_train("pwr")` selected then trained Power
(Power 189 -> 214, Stamina 284 -> 308).

---

# Career Profile panel (right-hand column, 4th button)

The game is 1920x1080 but the bot only ever looks at the `x = 150..950` strip.
There is a second panel at `x = 1030..1690` and a vertical menu column at
`x = 1755..1920` (`Jukebox / Sparks / Log / Career Profile / Agenda /
Item Request / Menu`). **Career Profile** is where the run's setup lives:

- Trainee: name, `Potential Lvl`, star rating
- Legacy Umamusume: the two inheritance parents and their ranks
- **Support Cards**: all six, each with rarity (SSR/SR), level, and a type icon
  in the top-right corner - blue shoe = Speed, red heart = Stamina,
  green cap = Wit, and a pink `Friends` banner for a Friend card
- Event Bonus Umamusume and the `Event Bonus Total` percentage

This is the reliable way to read the deck. The training screen's right rail only
shows the cards placed on the currently selected facility this turn.

Note the `Career` entry in the hamburger menu is *not* this - that one is race
history (Class / Career Record / Fans Earned / Major Wins).

# Supervised runs

`scratchpad/run_career.py` runs `career_lobby()` on a worker thread and watches
it, so a hung bot exits with a code instead of sitting there:

| Code | Meaning |
|---|---|
| 0 | stopped cleanly (a `STOP` file was created next to the runner) |
| 2 | stalled - log stopped growing (240s), or the turn counter never moved (1200s) |
| 3 | Umamusume window lost |
| 4 | `career_lobby()` raised (traceback is printed first) |
| 5 | exceeded `MAX_RUNTIME` |

Screen hashing is useless as a liveness signal here - the lobby animates
constantly, so the screen changes every frame even when the bot is wedged. Log
growth catches a hard hang; the turn counter catches the bot spinning happily on
one screen forever. Progress is mirrored to `status.json` each poll.

---

# URA Finale race day

The Finale replaces the six-button lobby with a **two-button layout**: `Skills`
on the left and a pink **`URA Finale Race!`** on the right at **(690, 905)**.
The turn box reads `Race Day` and the year reads `Finale Underway`
(`year_parts` is only 2 elements, so `len(year_parts) > 3` guards short-circuit).

None of the existing race templates match that button - `race_day_btn.png` peaks
at 0.47, `race_btn.png` at 0.32 - so before this run the bot could never start
the Finale. `assets/buttons/ura_finale_race_btn.png` is cut from the
animation-stable core of the button (the sparkle and sprite edges move, this
band does not): it scores 0.998-1.000 across frames and 0.35-0.42 on the lobby,
training and skills screens.

**The stats row also sits ~50px lower here** than in the normal lobby, because
of the extra `Race Day` banner. `SKILL_PTS_REGION = (755, 720, 85, 42)`
therefore reads the "Skill Pts" *label* instead of the number, `check_skill_pts()`
returns -1, and `auto_buy_skill()` bails at `-1 < SKILL_PTS_CHECK` - so skills
are never bought on Finale race days. This run finished with **1927 unspent
skill points**. Still open.

# The main loop could wedge permanently

`career_lobby()` had:

```python
if not matches["tazuna"]:
    print(".", end="")   # stdout only - never written to logs/log.txt
    continue             # and no way back
```

Left on any screen the loop does not recognise - the skill list is the easy way
to get there, via `auto_buy_skill()` - it polled forever, writing nothing. A
log-watching supervisor cannot tell that apart from a healthy quiet bot, which
is why the first stall detector kept mis-firing before this was found. It now
counts consecutive misses, warns every 20, and clicks Back. It fired 4 times in
the completed run, each time recovering a would-be hang.

## One-time dialogs and the generic Cancel (2026-09-15)

The generic `matches["cancel"]` click logs nothing, so any dialog that pairs
Cancel with an accept button and has no branch of its own gets dismissed, and
the bot repeats whatever opened it. Two in one career on a fresh install:

- Rest / Recreation / Infirmary confirmations: turned off in Options.
- "Race Playback" (Landscape / Portrait, "Do not show again."), opened by Race
  on the race preview. The log showed only "Race preview; starting the race."
  every ~17 s for 10 minutes. Title centre (552, 347), checkbox (426, 587),
  OK (686, 703), Cancel (419, 703; cancel_btn 0.997). Now handled by the
  `race_playback` branch: tick the box, then OK. `umatool click` did not open
  this dialog; a gliding `control.moveTo(..., duration=0.225)` then `click()`
  did, so reproduce race-preview presses the way `click()` makes them.

A run of one identical log line with no turn change is the signature: look for
an unlogged Cancel before touching the handler that logged.

---

# The game can lose fullscreen without losing focus

Seen mid-run: the game silently drops exclusive fullscreen while **remaining the
foreground window**. `GetForegroundWindow()` still returns `Umamusume`, so any
focus check based on the window title sees nothing wrong - but the Windows
taskbar is now drawn over the bottom of the screen at y~1040, which is exactly
where `Back`, `Next`, `Skip` and `Quick` live.

Measured on the same screen:

| | taskbar over the game | after refocus |
|---|---|---|
| `back_btn.png` best match | **0.455** | **1.000** at (222, 1039) |
| bottom strip `[1050:1075, 0:200]` mean | **65** | **231** |

Every button in that strip becomes unmatchable, so the bot wedges. The lobby
recovery fires correctly and logs, but its Back click cannot land - it recovered
only after the window was refocused by hand.

Detect it by **pixels, not by window title**: sample the bottom strip and treat
anything below ~120 as occluded. `scratchpad/run_career.py` does this in
`taskbar_covering_game()` and refocuses. That check is written but has not yet
been exercised in a run.

---

# Unity Cup scenario

Unity Cup reuses the URA shell almost entirely - lobby, training screen, events,
skills and the three URA Finals races are identical, and `check_training()` works
unmodified. What differs is a handful of extra screens and three places where the
layout quietly breaks an existing reader.

## Screens that only exist in Unity

| Screen | How to recognise it | Asset |
|---|---|---|
| Scenario tutorial | full-screen dialogue, no Back, no choice icons | none - tap `DIALOG_ADVANCE_MOUSE_POS` |
| Help carousel | `Back` / `Close` / `Help` + page dots | `close_btn.png` (Close, **not** Back) |
| Team Showdown | header reads `Team Showdown`, no Tazuna hint | `unity_cup_race_btn.png` (550, 922) |
| Select Opponent | three ranked teams + `Select Opponent` | `select_opponent_btn.png` (552, 912) |
| Confirmation | per-discipline ◎/○/△ row, `Begin Showdown!` | `begin_showdown_btn.png` (688, 777) |
| Matchup | 5 races, `Watch Main Race` / `See All Race Results` | `see_all_race_results_btn.png` (685, 1015) |

Team race chain, all five rounds:

    Team Showdown -> Unity Cup -> Select Opponent -> Begin Showdown! -> See All Race Results

The **Finals** round skips the opponent picker - the Unity Cup button opens the
confirmation modal directly (Rank S+ Team Zenith).

## Readers Unity breaks

- **`check_turn`** - Unity adds an "N turn(s) Until the Unity Cup" box *below* the
  goal box, which pushes the goal number up (y~82 vs URA's y~108) and puts a
  second number inside the old region. Fixed by covering both boxes and taking
  the **topmost** number, with a 5x upscale because Unity's goal digits are small
  enough that OCR read `9` as `0` and missed `11` entirely.
- **Race day says `GOAL`**, not `Race Day` and not a number. Without treating it
  as a race day the turn falls through to the number rule, picks up the Unity
  countdown, and the bot hunts for a Training button the race-day lobby lacks.
- **`YEAR_REGION`** - Unity shifts the year banner right, clipping it to `"Juni"`
  and silently breaking every `year_parts[0] == "Junior"` check. Widening it has
  a trap: starting above y=32 catches the top of URA's turn box and prefixes a
  stray digit instead.

## The Unity Cup button toggles its own modal

Clicking it opens the confirmation modal; clicking it **again closes it**. Any
loop that presses it whenever it matches will flip the modal open and shut
forever. Only press it when `unity_begin_showdown` is absent.

This took a long time to find because the button also pulses, so its template
match oscillates ~0.38 <-> 0.99, which looks like a matching problem. It is not -
sampling the modal state before *and* after each click is what showed the toggle.

## Spirit Burst

`assets/icons/unity_burst_ready.png` - a white flame bubble with two orange
chevrons at a support card's top-right, meaning that member's gauge is full and
the next Unity Training with them triggers a burst. Matches 1.000 when present,
<=0.55 when not. **Captured but not wired to anything yet.**

---

# Grand Concert scenario

"Brighter Together! Our Grand Concert", JP "Grand Live" (GL); on Global from
2026-07-22. Captured 2026-09-11 on Mihono Bourbon [CODE: ICING], Deck 8.
Fixtures are in `tests/fixtures/grand_concert/`.

The career setup is the usual one (Scenario Select -> Trainee -> Legacy ->
Support Formation -> Final Confirmation, 30 TP). The Final Confirmation adds a
`Normal Career` / `Independent Training` tab pair and an `Event Boost (TP Usage
x2)` checkbox; both left at their defaults.

## Lobby

Turns 1-4 look like URA except for a fourth bottom button, a locked grey `?`.
On turn 5 a Main Scenario Event (`Not an Order`) and a `Tutorial` event
("Yes, I'd like to know more." / "No, I think I'm okay.") unlock the scenario,
and the lobby gains:

| Element | Where | Notes |
|---|---|---|
| `Concert in N turn(s)` | under the turn box, `(262..375, 112..155)` | inside `TURN_REGION`; `check_turn` still takes the upper number |
| Hype Level gauge | `(160..280, 160..260)` | "Mild Hype" at 0 songs |
| Performance Points | `(160..255, 265..570)` | Da/Pa/Vo/Vi/Co, value over `/200`, rows 55px apart |
| Lessons | `(622, 955)` | `!` badge at `(674, 912)` when a card is learnable; `Scheduled` tag or a note badge otherwise |

Bottom row, left to right: Infirmary `(343, 972)`, Recreation `(483, 975)`,
Lessons `(622, 955)`, Races `(762, 975)`. The existing row-2 templates still
match the smaller buttons (infirmary 0.84, recreation 0.85, races 0.80 while
locked). Rest/Training/Skills/Tazuna are unchanged (0.97-1.00).

Recreation moving left takes its friend-outing badge out of
`RECREATION_BADGE_BBOX`; `GC_RECREATION_BADGE_BBOX` covers the new spot.

## Lessons screen (header `Lessons`)

Point totals across the top (`y ~ 105`), then three cards 230px apart. Card 1:

| Part | Box |
|---|---|
| Title (white on the header colour) | `(290, 196, 385, 32)` |
| Kind tag `Technique` / `Song` | `(680..810, 200..222)` |
| Gold `Learnable!` ribbon | `(700..825, 176..204)` |
| Effect lines | `(468, 248, 350, 38)` and `(468, 307, 350, 38)` |
| Cost row Da/Pa/Vo/Vi/Co | `(425..815, 368..392)` |
| Red `Scheduled` pill (songs) | `(300..400, 332..356)` |

Header colour is the kind: Technique green `(143, 218, 71)`, Song purple
`(173, 141, 236)`. A buyable card has the ribbon (~800 gold pixels, 0 on a
locked card) and a bright cost row (mean 226 vs 136). `Full Stats (748, 914)`,
`Concert Info (872, 914)`, `Back (222, 1039)`.

Tapping a card opens a dialog with Cancel `(419, 997)` and an accept button
`(686, 997)`:

- learnable -> `Confirmation`, `Learn`: "Spend performance points to learn this
  technique? Your trainee won't be able to learn the other 2 options."
- locked song -> `Schedule`: "Not enough performance points. Schedule this
  song?", then `Scheduling Complete` with `Close (553, 703)`.

After `Learn`, a `TECHNIQUE LEARNED!` overlay wants a tap. The board is then
replaced: after the first Technique of the run it was three Songs, none
affordable (`Run n' Run!`, `Believe in Miracles!`, `Here Comes Our Time`).

## Training screen

Same five buttons, plus a colour-coded hexagon chip over each naming the
Performance type it pays this turn (Da blue, Pa red, Vo pink, Vi orange, Co
purple). Observed: Speed Da, Stamina Vo, Power Vo, Guts Vi, Wit Co. The
Performance panel shows the selected facility's gain (`+10` beside Co for Wit)
and, when a song is scheduled, red `N more` badges for the shortfall. The
Light Hello NPC appears on the support rail without a friendship bar.

## Concert turns

A concert is not a turn of its own. On each half-year's last turn (Junior Late
Dec, Classic Late Jun, Classic Late Dec, Senior Late Jun, Senior Late Dec) the
box under the turn counter reads `Concert begins after this turn`, and that
turn is trained normally. After it the lobby is replaced by a concert screen:
header `Concert`, no Tazuna hint, no Back, a big `Lessons` button at
`(425, 912)` and a `Concert` button at `(682, 915)` under a red `Goal` ribbon,
plus the Hype gauge ("Great Hype" / MAX at three songs).

Sequence, all verified on the 1st Concert:

1. Possibly a `Schedule Notification` over it: "The song you scheduled can now
   be learned." `Close (419, 774)` / `To Lessons (686, 774)`. It can also
   appear over the ordinary lobby after any turn.
2. `Concert` -> `Confirmation` "Ready to start the concert?" `Cancel` /
   `Start (686, 774)`.
3. The performance is skipped with Skip on two arrows; `GREAT SUCCESS` with an
   ordinary `Next`.
4. The concert schedule (1st..4th, Grand Concert, turns left), `Next`.
5. A Main Scenario Event (`After the First Concert`, new supporters join),
   then the next half-year's lobby.

The game's Log records "Performed 3 songs with Great Success." `Make Debut!`
counts as one of the three; two learned songs filled the gauge.

The DIALOG_ADVANCE_ALT tap `(756, 980)` lands on the Concert button, which is
why the concert screen needs its own branch rather than the lobby recovery.

Learning a song while a *different* one is scheduled raises a second, smaller
`Confirm` dialog on top: "Your trainee won't be able to learn the scheduled
song." `Cancel` / `OK (686, 774)`, title at `y ~ 276`. `Scheduling Complete`
is titled mid-screen too (`y ~ 347`).

## The Grand Concert and the end of the career (verified 2026-09-11)

- **Senior Late Dec** is a race day (Arima Kinen goal on this trainee), and
  the Grand Concert screen follows it. Its button reads `Grand Concert`, in
  lettering `concert_btn.png` does not match, so it has its own crop.
- Its confirmation adds a **`Skip the Grand Concert cutscene`** checkbox at
  `(395, 665)`: grey tick when unticked, green when ticked. Start is where it
  always is.
- Then an **`ON STAGE!`** disc at `(553, 615)`, over a screen whose only other
  button is `Back`. The lobby recovery would press Back.
- `GREAT SUCCESS` -> reward story (+12 all stats) -> the five-concert summary
  -> **`Extended Phase: URA Finale Start!`**. Grand Concert ends in the URA
  Finale: a training turn, Qualifier, training turn, Semifinal, training turn,
  Finals.
- The finale race-day lobby is **Skills (352) / URA Finale Race! (553) /
  Lessons (752)**. `ura_finale_race_btn.png` scores 0.75 there and the URA
  fallback position `(690, 905)` is on the Lessons button's edge, so Grand
  Concert uses `GC_FINALE_RACE_MOUSE_POS`.
- The **career-complete screen** is **Skills (352) / Complete Career (553) /
  Lessons (752)** over a `Remaining Performance Points` panel.
  `complete_career_btn.png` still matches (0.918); the URA Skills position
  `(425, 888)` is the gap beside Complete Career.
- Lessons there: the board is drawn **dimmed** (technique green (91, 136, 46))
  and the `Concert Info` button has become **`Songs Learned`**.
- `Finish this Career playthrough?` lists remaining skill **and** Performance
  points: "You will lose any unused skill and performance points."

## Song plan, Performance-aware training, the lyrics event (2026-09-11)

**Songs.** The game shows no running total of songs learned, so the bot counts
its own purchases per concert segment and keeps them in
`logs/grand_concert_progress.json` (a restart mid-career used to zero them).
"Make Debut!" counts toward the 18 for "I Wanna Win With You"; "Girls' Legend
U" does not, and the check is taken at the Senior Early December turn. Songs
follow a running plan, `grand_concert.song_plan` = 4 / 8 / 12 / 16 / 18 total
by the end of each segment: behind plan buys, ahead of plan saves. The concert
screen always tops up to three songs for Hype (two in the first and last
cycles, which count Make Debut and Girls' Legend U). The Grand Concert visit
spends everything, and so does every URA Finale visit: points keep coming in
on the Finale turns and the board still sells - a song's concert bonus "won't
take effect as the concert is over", but its on-learn stats do (career 3 bought
Dream Sky, Wit +22, on the Finals race day). Only the career-end board, after
the last race, is dead (drawn dimmed).

**The Lessons button moves.** `lessons.ready()` finds the "Lessons" label
(`lessons_btn.png`) inside `LESSONS_LABEL_SEARCH_BBOX` and looks for the "!"
relative to it, returning where to tap:

| Lobby | Label centre | Badge | Tap |
|---|---|---|---|
| Normal (Infirmary / Recreation / Lessons / Races) | (623, 980) | (674, 912) | (622, 955) |
| Summer camp (Rest & Recreation merged) | (552, 980) | (613, 912) | (552, 955) |
| URA Finale race day (Skills / Race / Lessons) | (753, 940) | (814, 872) | (753, 915) |

Before this, three careers never visited Lessons in July or August: the badge
was looked for at the normal position only (fixtures `lobby_summer_camp.png`,
`lobby_finale_race_day.png`).

**Performance-aware training.** The training screen shows a chip over each
facility naming the type(s) it pays this turn (templates `chip_*.png`, 1.000 on
our captures), and the Performance panel puts a red "N more" badge on the rows
a scheduled song is short of (x~222, rows 55px apart from y~302). Each chip of a
short type adds `grand_concert.performance_short_points` (0.75) to that
facility's training score.

**"Closer Together"** (Senior Early Nov, needs 16 songs): five lyric lines, the
gold hint if that character is the trainee or a support card. The bot takes
`grand_concert.lyrics_option` and recognises the event by name or by its
options naming 3+ of the lyric skills.

**Turn counter.** `read_turn_digits()` reads the calendar number glyph by
glyph: a "1" is 13-14px wide, other digits 25-30px, and only the wide ones go to
OCR. It fixed "11" -> "17"; the old whole-number OCR stays as the fallback.

## Points strategy (second research pass, 2026-09-11)

`core/lessons.py::choose()` now reads the five point totals off the Lessons
screen (`LESSON_POINTS_*_BBOX`) and each card's cost row
(`LESSON_COST_TEXT_REGION`, read as one line and split into five slots), and
prices songs from `data/grand_concert_songs.json` (21 songs, cost per type,
the segment each unlocks in; totals match GameTora). Rules:

- Songs follow the running plan; once a segment's target is met, points are
  held - no filler techniques - except within 40 of a type's cap
  (200 + 50 per concert), energy-only when energy is low, and the carry-over.
- Short of the target, the technique bought is the one that eats least into
  the reserve for the next songs (the cheapest remaining songs' cost vectors).
  Career 2 lost the gold skill to Da: Senior songs are Da/Vi heavy and Speed
  techniques spend Da.
- Behind pace, and always in Senior H2 (whose songs only count toward 18),
  the cheapest learnable song; the Senior H2 pace ends at Late Oct.
- The technique pattern (1-2-3-4-4..., 2-2-2-4-5..., 2-2-2-4-3...) is tracked
  and resets at each concert. On the concert screen with Hype secured, a song
  page is left on the board to carry over (it counts as the next pattern's
  first step); a page one or two techniques away is bought into first.

Career 3 (2026-09-11) confirmed the pattern live in every segment it saw, and
added:

- `SONG_COST_SLACK` (6): buying cheapest-first, or reserving the song closest
  to affordable, a better-ranked song within 6 points still wins. Career 3
  bought Ring Ring Diary (42, ranked 19) over the scheduled Run n' Run! (44,
  ranked 5). Pre-Debut no longer counts as behind pace (Make Debut is only
  credited once run).
- One Lessons visit per turn: a visit that bought and then stopped used to be
  reopened on the same turn.
- A points total of "1" reads by glyph (easyocr drops a lone narrow digit).
- All 18 in Senior H2: techniques are bought by value instead of held, so the
  stats land before the Japan Cup and Arima rather than at the Grand Concert.

## The daily reset and the spark flow (2026-09-12)

**Daily reset, mid-career** (22:00 local): `Date Changed / It's a new day!` over
the lobby, OK at (552,703) -> the client reloads ("Connecting") -> login bonus,
skip at (903,1024) -> the game's home screen -> CAREER at (712,930) ->
`Continue Career` with Resume at (686,774). Templates `assets/ui/date_changed.png`
and `assets/ui/continue_career.png`, plus `assets/buttons/resume_btn.png`.
Fixtures in `tests/fixtures/out_of_career/`.

**Sparks.** Rows are found by their gold stars (a filled star band spans x
715-795; one star reaches ~x+17, two ~x+43, three ~x+68) rather than by fixed
offsets, because the list screen puts the first row at y=169 and the selection
screen at y=198. The pill colour names the row: blue (98,200,248) stat, pink
(255,144,191) aptitude, green (153,215,55) unique, grey (225,224,225) skill.
Reroll Sparks (423,993) -> "Spend 30 TP to reroll Sparks?" Reroll (686,703) ->
~6s animation -> Next (552,994) -> notice Next (552,703) -> Spark Selection,
two pages with arrows at (298,128)/(806,128) and the label between them ->
Confirm (552,994) -> "Keep this set of Sparks?" Confirm (685,997).

Career 6 (2026-09-12) added two more, both aimed at the 18th song:

- `filter_by_stat_caps` keeps a capped facility when it is the only one paying
  a type the board is urgently short of (career 6: Guts, capped at 400 with 556
  trained, held the only Vi chip for turns).
- `gold_push_action` takes a safe facility paying a needed type ahead of the
  rest and summer-camp rules, but only while `grand_concert.always_buy_gold_skill`
  is on and Senior H2 is short of 18. Never below `skip_training_energy`, never
  over `maximum_failure`.

Career 4 (2026-09-11) added:

- `PACE_TOLERANCE` (1.0): a segment's pace line climbs from its first turn but
  its first song page is two techniques away, so half a song behind is noise.
- `lessons.blocked_types()`: a board of three locked techniques shows no "!",
  so it sits frozen (career 4: Classic Early Oct - Late Dec, Senior Late Mar -
  Early Jun). The visit that finds it locked records the nearest card's short
  types (persisted with the song counts) and `check_training` adds them to the
  Performance "short" list. At the flat `performance_short_points` weight
  (0.75) it tipped none of the turns checked (Senior Late Mar - Late May: Vi
  chips on offer, Power/Speed trained).
- Missed the 18th song: 17 at the Early Dec check. A locked song page sat from
  Senior Late Sep with Vi 9 of 26, and a Vi chip was on offer three times
  without being taken. Open: the Performance weight needs to scale with
  urgency in Senior H2, and scheduling there should take the closest song
  regardless of rank (the slack picked rank 3 at 17 short over rank 20 at 12).
