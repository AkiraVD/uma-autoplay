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

The code template-matches the first choice icon and steps **down** by
`core/execute.py::CHOICE_VERTICAL_GAP = 112`, then clamps the choice to the
options on screen (`option_count`, `choice_point`).

Choice icons are colour-coded by index (1 green, 2 yellow, 3 pink), which is why
a template of the green icon anchors on choice 1: it matches once per frame,
verified on the choices fixtures on 2026-09-16.

Re-measured from six careers' logs on 2026-09-16: the anchor of the first
option is 736 for one option, 624 for two, 513 for three and 290 for five, so
the last row sits at ~736-738 and the step is 112. The 753 / 111 px above comes
from an earlier session and does not match those captures; treat 736 / 112 as
current, and note the anchors are a pixel off a perfect grid.

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

**"Race Details ... Enter race?" (2026-09-21)** - the confirmation the race
list raises on its Race button, and the last screen before a race starts. The
same trap, found the hard way: the bot pressed Race on the list, the dialog
opened, nothing matched it, and the generic Cancel closed it again. One
`Race preview; starting the race.` in the log and then silence, because the
cancel passes no text. The bot was stopped by hand ~30s in, so the observed
loop is short; what was found 17 minutes later was the career parked back on
the race list, which is the state the cycle returns to and would have held
indefinitely.

The cause is two thousandths. `race_preview_btn.png` was cut from the race
*preview* screen, whose Race button is wider than this dialog's, so it scores
**0.848** here against `multi_match_templates`' **0.85** threshold - while
matching **0.850** on the race list one click earlier, which is why the list
half worked and the dialog half did not. `cancel_btn.png` scores **1.000**.

Measured on the live frame, and on a Trackblazer Twinkle Star Climax capture
from four days earlier that puts every element on the same pixel:

| Element | Position |
|---|---|
| "Race Details" header | (553, 277) |
| "Enter race?" | (553, 711) |
| Cancel / Race | (419, 775) / (686, 775) |

Note this dialog is **taller** than the Race Playback / consecutive-races /
scheduled-race family, which share a layout with their buttons at y~703. Its
banner pushes the buttons to y 775, so it cannot reuse their constants.

Handled by the `race_confirm` branch, keyed on the "Enter race?" line
(`assets/ui/enter_race_confirm.png`, 1.000 on both positives against a best
negative of 0.631 over 23 frames). The template is message text, so it must not
be clicked at its own centre; the branch finds the Race button with
`race_btn.png` (0.923 on both) and falls back to
`RACE_CONFIRM_RACE_MOUSE_POS`. `race_day()` and `race_select()` never needed
this - they drive the dialog blind by pressing `race_btn.png` twice - so it
only bites when the loop arrives here through the generic handlers, which is
what a bot started on the race list does.

A run of one identical log line with no turn change is the signature: look for
an unlogged Cancel before touching the handler that logged.

---

# The client can stop drawing while the career carries on (2026-09-21)

Seen ~7.5h into one client's uptime: the portrait game panel went flat white
the instant the Japanese Derby started and never redrew, and the side panel
froze on a stale frame at the same moment. Nothing on it matched any template,
so the loop fell into the blind-tap branch and stayed there for twelve minutes.

**It is not X, and not the career.** `Xorg.1.log` was clean, the display
answered with backlog 0, screenshots kept updating, and the window was still in
the X tree. The race ran server-side: after a `close`/`launch` the Continue
Career dialog showed the goal still in progress with stats matching the
pre-race reading, and Resume landed on the results screen with the trainee 2nd.
Only a client restart clears it.

**Detect it by variance, not by any template.** Greyscale standard deviation
over `GAME_SCREEN_REGION`:

| Frame | std |
|---|---|
| dead panel (two captures, 20 min apart) | **0.00** |
| race list, home, title, race results | **44 - 66** |

`game_panel_blank()` in `core/execute.py` trips below **3.0**, counted over
`BLANK_PANEL_LIMIT` frames rather than one, because the game does draw
sub-second flat frames during transitions. It stops the bot with a message
naming the restart, rather than tapping a window that cannot answer.

Whether uptime is really the trigger is a guess from one occurrence - log the
client's uptime if it happens again.

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

Measured again on 2026-09-16, over six careers' logs:

- The event opens with a **one-option prompt**, then shows the five lines. The
  configured line was applied to both, so on the first prompt the click landed
  a row below the only option and did nothing; the event then re-prompted and
  the second, five-option screen took the right line. `choice_point()` in
  `core/execute.py` now clamps a choice to the options on screen.
- **Options are bottom-anchored**, so the first one's y gives the count:
  736 = 1, 624 = 2, 513 = 3, 401 = 4, 290 = 5. `assets/icons/event_choice_1.png`
  matches the first option only (one hit per frame), so it is a reliable anchor.
- The **Choices panel reports four options** for this event in every career
  (Full Tilt, Focus, Rosy Outlook, and one with no hint) although the list holds
  five, so the panel is not a way to count them.
- `master.mdb` holds the event's title (`text_data`, category 181) but no choice
  text, so the on-screen list is the only source for the lines themselves.

What the database does say about the five lines (2026-09-16), after the question
came up of whether the deck changes them:

- Each line is one **skill pair sharing a `group_id`**, white and gold:
  Full Tilt / Full Speed! (20228), Focus / Concentration (20043),
  Rosy Outlook / Trackblazer (20071), All I've Got / Come What May (20170),
  Go with the Flow / Lane Legerdemain (20050). The panel names the white one.
- **No support card teaches any of them**: expanding every
  `support_card_data.skill_set_id` through `skill_set` gives zero hits. The
  skill sets that do contain them belong to race NPCs.
- The **trainees that can learn them are many** (Focus: Kitasan Black,
  Maruzensky, Mejiro McQueen, Mihono Bourbon, Silence Suzuka, Eishin Flash,
  Mayano Top Gun; Lane Legerdemain: Air Groove, Eishin Flash), and Full Speed!
  has no trainee owner at all. So "one line per character" does not hold, and
  the older note calling line 5 "anyone" is wrong.
- Which lines appear, and which carry a hint, therefore cannot be derived from
  the data files. `core/events.py` now saves the event's frame to the log
  directory (`lyrics_event_<date>.png`) so a career's list can be compared
  against the deck that produced it.

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

## The gacha menu after a career (2026-09-17)

Careers kept ending in the Scout (summon) menu. The cause is geometric, not a
misread: the loop's alternate blind tap, `DIALOG_ADVANCE_ALT_MOUSE_POS`
**(756, 980)**, sits in the Scout column of the game's own bottom navigation.

The bar - **Enhance / Story / Home / Race / Scout** - is drawn on every screen
outside a career. Measured on `game_home.png`: the tiles span **y 996-1074**,
Scout's tile **x 748-840**, and its event badges reach up to y~975. The tap
lands at the tile's top edge, under the badge.

That point was chosen for the career-start Inspiration screen and reasoned only
against the *career's* own Skip/Quick row at y~1050. Nothing had measured it
against the game's menus, because the loop was never meant to be there.

Why the loop was there at all: `team_rank` is absent from some of the screens
the game walks through after a career, and `login_bonus` matched nothing in the
dispatch dict, so both fell through to the blind taps. The walk after career 12
took **3m19s** (01:39:40 sparks confirmed -> 01:42:59 home recognised), spent
alternating taps with the Close/Back probes that backed out of Scout again.

Two templates close it, both cut from the fixtures and checked with `sep`:

| Template | Positives | Best negative | Margin |
|---|---|---|---|
| `assets/ui/game_nav_scout.png` | 0.930-1.000 (home, home GL, home mid-career, Scenario Select, trainee select) | 0.693 (`continue_career`) | +0.237 |
| `assets/ui/game_nav_race.png` | 0.781-0.945 (same set bar `game_home`, plus the Scout screen at 0.942) | 0.691 (`continue_career`) | +0.090 alone, **+0.237 in union with `game_nav`** |
| `assets/ui/login_bonus.png` | 1.000 (`login_bonus`) | 0.249 | +0.751 |

`game_nav` joins `team_rank` in the branch that stops the loop, so the blind tap
is never reached on a screen carrying the bar. (A third template, `game_nav_alt`,
joined that branch on 2026-09-19 to cover the Scout screen - see below.) `login_bonus` presses that
screen's Skip at **(903, 1024)**, located by template inside the branch - the
dispatch dict deliberately does *not* key on `skip_btn.png`, which is the race
skip `race_prep()` drives inside a career.

Covered by `tests/test_out_of_career.py`; the bar matches no in-career frame
across the grand_concert and sparks fixtures.

**The bar went blind on the Scout screen itself - fixed 2026-09-19 by reading
two tiles.**
`game_nav_scout.png` is cut from the Scout tile in its *inactive* state, so it
matches every screen where Scout is not the open tab and fails on the one
screen where it is - which is exactly where the blind tap puts the bot.
Measured live with the Menu panel open over Scout: `game_nav` **0.451**,
`team_rank` **0.363**. One tap on Home later, the same two read **0.976** and
**0.944**. `team_rank` is not merely low there, it is absent: the Scout screen
draws gacha currency top-left where the TEAM RANK badge normally sits.

Kept as `out_of_career/game_scout_active.png`, where it scores **0.428** -
level with `login_bonus.png` and +0.004 over `in_career.png` - so no threshold
separates it. The template's margin on the original set is unchanged at +0.237,
so this is a missing case, not a regression.

**Swapping in a different tile only moves the blind spot.** `game_home.png` was
captured with the *Race* tab open, so a Race-tile template fails on it for
exactly the same reason. But only one tab can be active at a time, so for any
two distinct tiles at least one is always in its normal state - a union of two
is complete **by construction**, not by luck. Hence `game_nav_alt`
(`assets/ui/game_nav_race.png`, the Race tile) beside `game_nav`, and a branch
reading `team_rank or game_nav or game_nav_alt`.

Partner chosen by measurement, unions scored over the fixture set at the
production threshold of **0.85**:

| Pairing | Union worst-positive | Best negative | Margin |
|---|---|---|---|
| `game_nav` + **race** | 0.930 | **0.693** | **+0.237** |
| `game_nav` + enhance | 0.918 | 0.763 | +0.155 |
| `game_nav` + story | 0.930 | **0.844** | +0.086 |

Story is the trap: 0.844 on `continue_career` against a 0.85 threshold is six
thousandths away from calling a live career finished. Race adds no new negative
risk at all - its worst negative is the same 0.693 as `game_nav`'s.

**The race tile is not independently trustworthy.** `sep` rates it +0.090 alone
(worst positive 0.781 on `scenario_select`, *under* the 0.85 threshold), so it
must never replace `game_nav` - only sit beside it.

An earlier sweep here reported every candidate as hopeless (race -0.385,
enhance -0.015, story +0.047, scout -0.346). That was wrong twice over: the
crops were placed by eye instead of anchored on the shipped template's own
match position, and reporting only min/max hid the fact that each candidate
failed on exactly **one** frame - a different one each time, which is precisely
what makes the union work.

## Career start: story Skip and Quick Mode (2026-09-17)

Both are once-per-career settings the bot never touched. Measured live while the
Quick Mode dialog held the scene still - it blocks everything until Confirm, so
the Skip button below it can be cycled without anything else moving.

**Story Skip**, bottom-left of the story UI and of the lobby, at **(567, 1052)**
(`SKIP_BUTTON_MOUSE_POS`, read inside `SKIP_BUTTON_BBOX` = 500,1028,680,1078).
It cycles **Off -> x1 -> x2** and resets to Off with every new career. Two
presses from Off reached x2. Each state matches its own template at 1.000:

| Frame | skip_off | skip_x1 | skip_x2 |
|---|---|---|---|
| Off | **1.000** | 0.430 | 0.318 |
| x1 | 0.090 | **1.000** | 0.832 |
| x2 | 0.085 | 0.832 | **1.000** |

x1 and x2 score 0.832 against each other, so the state is **read between
presses, never counted** from an assumed start - one missed press would
otherwise leave a whole career on x1. With Skip off the bot taps each story
line about every 9 s, which reads as a stall.

**Quick Mode Settings**, the one-time dialog at the start of every career.
Four radios, **68px apart** - note that is *not* the 112px event-choice
spacing, although the radios match `event_choice_1.png` at 0.974, so deriving
them from `LAST_EVENT_CHOICE_ICON_TOP` lands wrong:

| Radio | Position |
|---|---|
| Don't use Quick Mode | (308, 460) |
| **Shorten all events** | **(308, 529)** |
| Only shorten scenario events | (308, 597) |
| Only shorten trainee events | (308, 664) |
| Confirm | (553, 773) |

The selected radio reads ~273 green pixels in an 18x18 patch against 0 for the
rest. "Shorten all events" is the game's default, but the branch picks it
explicitly rather than trusting a default across accounts and patches; clicking
a radio only moves the pending choice, and Confirm commits.

Fixtures in `tests/fixtures/career_start/`, covered by `tests/test_career_start.py`.

### The setup screens, walked by hand (2026-09-18)

Scenario Select -> Trainee Select -> Legacy Select -> Support Formation ->
Final Confirmation, starting a Trackblazer career on Maruzensky. Every position
below was clicked live at 1920x1080, so they are measured rather than derived.

| Screen | Element | Position |
|---|---|---|
| Home | CAREER banner | (712, 930) (`CAREER_BUTTON_MOUSE_POS`) |
| | TP `+`, opens Recover TP | (570, 47) |
| Recover TP | each row's Use | x = 763 (`TP_RESTORE_USE_X`), rows ~115 apart |
| | Toughness 30 label centre -> its Use | (446, 244) -> (763, 269) |
| | Close | (552, 996) |
| Recover TP quantity | Cancel / OK | (419, 774) / (689, 774) |
| Trainee Select | Next | (551, 908) |
| | trainee tiles | x 322/435/551/665/779, rows y 617 / 750 |
| Legacy Select | Change, Legacy 1 / 2 | (409, 751) / (695, 751) |
| | Reset / Auto-Select | (418, 821) / (685, 821) |
| Support Formation | deck slots | x 373/553/731, rows y 345 / 573 |
| | deck page arrows | (275, 482) / (835, 482) |
| | Reset / Auto-Fill | (415, 771) / (683, 771) |
| | Back / Start Career! / Perks | (211, 910) / (585, 910) / (873, 909) |
| Borrow Card | first row of the borrow list | (545, 250) |
| | rows below it | ~148px apart: 397 / 545 / 692 / 840 |
| | Close | (552, 997) |
| Support Select | card tiles | x 328/440/552/665/777, rows 145 apart from y 165 |
| | Close | (552, 997) |
| Final Confirmation | Normal Career / Independent Training | (408, 181) / (696, 181) |
| | Event Boost (TP Usage x2) checkbox | (311, 809) |
| | Cancel / Start Career! | (419, 997) / (686, 997) |

**Starting a career costs 30 TP, and the game asks before it blocks you**
(2026-09-19). Pressing `Start Career!` below the TP cost raises a Confirm
dialog - *"You need 13 more TP to start a Career Scenario, and 43 more TP if
you wish to use Event Boost. Would you like to restore TP?"* - with **No**
(419,704) / **Restore** (686,704). Read at TP 17/100, so the career itself is
**30 TP** and Event Boost a further **30** on top. `Restore` only opens Recover
TP; nothing is spent until a second dialog is confirmed.

The TP bottle is **`Toughness 30`** (Recovery 30). Rows measured on the Recover
TP list, label then its `Use` about 27px below at `TP_RESTORE_USE_X`:

| Row | Label y | Use y |
|---|---|---|
| Carats | 115 | 141 |
| **Toughness 30** | 232 | **259** |
| Oguri Cap's Handmade Chocolate | 345 | 373 |
| El Condor Pasa's Handmade Chocolate | 460 | 486 |
| Mihono Bourbon's Handmade Chocolate | 577 | 603 |
| Meisho Doto's Handmade Chocolate | 689 | 719 |
| Nice Nature's Handmade Chocolate | 804 | 833 |
| Close | | 984 |

All five chocolates also restore 30, so they are interchangeable with the
bottle and are the ones to burn first if they ever expire. The quantity dialog
that follows names the item, the resulting TP (`48/100`) and the holding before
and after (`156` -> `155`), with Cancel / OK at y~762 - so it can be verified
before committing rather than confirmed blind.

**The Friends slot is not filtered to friend-type cards** (2026-09-19). It is
the *borrowed* slot - a card taken from another player - and it accepts any
type, so the list behind it is every borrowable card rather than the five
friend cards `core/outings.py` names. Measured: the top row was
`[Esteemed and Adored] Heirs to the Throne`, which master.mdb records as
**type3** (Power), while the `Pal` cards sat second, third and fourth. So
"first row" in the table above means the first row of the list, not the first
friend - tapping (545,250) blind puts whatever happens to sort first into the
slot. Read the row, or check the type with `tools/support_cards.py find <name>`,
which prints it (`Pal` = friend).

**A disabled `Start Career!` looks exactly like a swallowed click.** It renders
disabled - desaturated olive with pale grey-blue text, against the vivid green
and crisp white of `Auto-Fill` right above it - and there are **two** separate
causes, either of which is enough on its own:

- a deck holding a support card of the *same character as the trainee*, which
  wears an orange `Trainee` banner with a red `!`;
- an **empty Friends slot**. A five-card deck will not start. Measured
  2026-09-18 on a deck with no conflict at all: the button was disabled until
  the borrow was taken, and went vivid the moment slot six was filled.

The two were conflated when this was first written, because the borrow happened
before the button was ever pressed. Neither an ordinary
click nor a `deliberate_click`-style move/settle/hold press does anything, and
nothing is logged, so it presents as the spark-screen wedge and sends you down
the input-delivery path. It is not an input problem. Compare the button against
a known-enabled green one in the same frame before suspecting the click, and
check the deck for a `!` badge. Swapping the offending card out enables the
button immediately.

**How to tell it apart, measured (2026-09-19).** Mean HSV over the button
faces, disabled `Start Career!` against an enabled `Auto-Fill` in the same
frame:

| Button | Saturation | Value |
|---|---|---|
| `Start Career!` (disabled, empty Friends slot) | 0.842 | **0.512** |
| `Auto-Fill` (enabled, same frame) | 0.892 | **0.822** |

**Brightness is the discriminator, not saturation.** The two differ by 0.05 in
saturation and 0.31 in value, so a saturation-only check misses the disabled
state entirely - which is worth stating because "desaturated olive" invites
exactly that check.

One caveat that cost a measurement here: **never compare while a confirm modal
is up.** The overlay is a white wash, not a dimmer - it drops saturation while
*raising* brightness. Legacy Select's enabled `Auto-Select` read sat 0.432 /
val 0.888 under the Confirm Auto-Select dialog and sat 0.878 / val 0.815 once
it closed, so under a modal both buttons look alike and the comparison says
nothing.

This bites whenever a saved deck is reused for a trainee it was not built for,
which is the normal case when switching trainee between careers.

### Verified end-to-end (2026-09-17, career 13)

A full Grand Concert career run with the fix in place ended on the game's own
screens without ever entering Scout:

    05:00:03  Career complete.
    05:01:39  Confirming the kept set.      (sparks done)
    05:04:28  Leaving the finished career.  (to_home)
    05:04:40  The game is on its own screens, so the career is over.
    05:04:40  [BOT] Stopped.

The post-spark walk took **3m01s**: 7 Next presses, 4 blind taps and a single
back-out. No repeated Close/Back cycling, which pre-fix was the signature of
the loop tapping Scout open and backing out of it again.

Two things this run did **not** establish:

- **Which template stopped it.** The branch is
  `team_rank or game_nav or game_nav_alt` and all three share one message, so
  the log cannot say which matched - on the home screen all three do. Naming
  the matched template in that line would make the next such run
  self-evidencing.
- **The `login_bonus` branch has still never fired** (0 occurrences in any log).
  That screen appears after a reload or the daily reset, not after every
  career, so it remains covered by fixtures only.

**Confirmed twice more on 2026-09-21**, both Grand Concert, both ending on the
nav bar's **Home** tile with Scout untouched:

| | career A | career B |
|---|---|---|
| `Career complete.` | 03:32:31 | 09:15:37 |
| `The game is on its own screens` | 03:36:22 | 09:19:09 |
| post-complete walk | 3m51s | 3m32s |
| skill points spent at the buzzer | 2516 / 2547 | 2229 / 2238 |

Career B's purchases included `Front Runner Straightaways` and
`Front Runner Savvy`, which is the config's `skill_run_style` reaching the
optimiser rather than a coincidence.

The first caveat above still stands: the message does not name which of the
three templates matched.

## Trackblazer: research and the screens outside a career (2026-09-17)

Global's **third** permanent scenario, "Trackblazer - Start of the Climax",
released 2026-03-12 - before Grand Concert, not after it. Nothing in the bot
handles it yet. Everything below outside the career was measured on the live
client; everything inside one is still unverified.

### What the game itself says

Walked Scenario Select -> Scenario Details -> How to Play, all five pages.

- **Points have two names.** The HUD reads **"Track Pts"** - a star icon,
  `<Year> Track Pts`, `100/300pts` and a progress bar. The body text calls them
  **"Result Points"**. Guides call them "Grade Points", which appears nowhere in
  the game; prefer "Track Pts" for anything read off the screen.
- `There are no character-specific goals in this Career scenario`, and
  `You can choose for yourself which races to enter`.
- Classic Year target is **300**, matching the guides.
- **Best Umamusume Award**, which no guide consulted mentioned: every year at
  the end of the Late December turn an award goes to the highest performing
  Umamusume, driven by supporter bonds, race results and fans, and winning it
  raises the trainee's Unique Skill level. This is very likely what uma.guide's
  otherwise unexplained "5,000 fans + 19 bond post-Junior" thresholds describe.
- Finale: `Reach every Career goal to take on the Twinkle Star Climax`, three
  races, winner becomes the "Twinkle Top Star".

### Race rows carry everything race selection needs

Each row on the race list shows, in one place: a **G1/G2/G3 badge**, the track
line (`Tokyo Turf 2000m (Med) Left`), a gold star **`+100 pts`**, a green coin
**`+100`**, `+15,000 fans`, and **Turf / Medium aptitude chips**. So grade,
points, coins, distance, surface and aptitude are all on screen - master.mdb is
only needed to cross-check. Note `data/races.json` has **no grade field**;
`server/master_data.py`'s mdb-backed races do (`"grade": "G3"`).

### Measured geometry (1920x1080 Steam)

| Screen | Element | Position |
|---|---|---|
| Scenario Select | left / right arrow | (177, 494) / (935, 494) |
| | page dots (4 = 4 scenarios, Trackblazer 3rd) | ~(515-590, 857) |
| | Scenario Details | (800, 277) |
| | Back / Next | (212, 910) / (552, 909) |
| Career Scenario Details | How to Play | (744, 385) |
| | Close | (552, 997) |
| How to Play (5 pages) | Next / Back | (552, 1019) / (320, 1019) |
| | page dots | ~(525-585, 975) |

`assets/trackblazer/scenario_select_title.png` is the wordmark off the
Scenario Select card: 1.000 on that card against a best negative of 0.294 over
five other frames, margin +0.706.

### OCR note

The Track Pts counter reads cleanly at a generous crop; a tight one returned
`100/30pt5`. Large outlined display digits, the same class of glyph that needed
`core/gains.py`'s template bank - expect to read this counter by digit
templates rather than easyocr.

### Inside a career: the lobby (2026-09-17, Junior Pre-Debut)

Measured on a live Trackblazer career, Maruzensky, Junior Year Pre-Debut.

- **The lobby HUD is not called "Track Pts".** The badge sits top-left under
  the turn counter, a gold ribbon with a star: `Junior Result Pts` over
  `0 pts`, roughly (150-310, 160-245), label at ~(228,185) and value at
  ~(225,225). No `/300` and no progress bar - the year prefix changes, the
  target never shows. "Track Pts" with a bar came from the How to Play
  mock-up, so prefer "<Year> Result Pts" for anything read off the lobby.
- That badge lands in the region the training banner reader OCRs: the log
  carries `Training banner not recognized: 'junior result pts 0 pts'`.
  Harmless so far, but it is the first thing to suspect if a Trackblazer
  career starts misreading the banner.
- **The turn counter sits lower than URA's, with taller digits** (measured
  2026-09-19 on three full frames). The white card spans `y 82..150` and the
  digits `y 84..131` - h 47, w 16-17 a glyph, at x 284-339 - against URA's
  36-40px. The shared `TURN_DIGITS_REGION` ends at `y 106`, so it keeps only
  the top 22px of every glyph and `read_turn_digits` returned `None` on all 49
  live frames, falling through to the OCR fallback every turn. Read it through
  `scenarios.get("turn_digits_region")`, which gives Trackblazer
  `TB_TURN_DIGITS_REGION = (258, 78, 112, 58)`: the same 112x58 window shifted
  30px down onto the card. Do not move the shared constant - URA's and Grand
  Concert's boxes are correct on it.
- The right rail runs at x~1838: Jukebox 75, Sparks 230, Log 390, Career
  Profile 540, Agenda 700, Item Request 855, Menu 1010, with a red "!" at
  (1893,820) and a "NEW" tag at (1793,948).
- **"Item Request" is not the shop**, and what it is is still unknown. It is
  greyed with a red "!" and inert at Junior Pre-Debut: clicks at (1837,850)
  and (1838,822) changed nothing, while (1838,230) switched the panel to
  Sparks in the same session, so input was reaching the game. It was still
  greyed after the debut race, when the real shop had already opened
  elsewhere, so the "!" is not stock waiting to be spent.

#### The Agenda tab and My Agendas (2026-09-20)

The Agenda tab (right rail, ~(1838,700)) opens `Scheduled Races`: year tabs
Junior/Classic/Senior at y~153 (centres 1157 / 1356 / 1553) over a 4-column
grid of turn slots, with `Reset` (1110,982) and `My Agendas` (1568,982) at the
foot. At Junior Pre-Debut, Early Apr..Late Jun are greyed and every later turn
carries a green `+`. A schedule is **authored by hand** - the bot cannot create
one - then saved into a named slot, and the game truncates that name at 10
characters (`Mile+Sprin`).

`My Agendas` lists the saved slots (~8 seen: `TB-TMG`, `TB-TME`, `Mile+Sprin`,
`Dirt - All`, `Mile-Med`, `Haru`, `Agenda 7`), each a scrolling row.

| Element | Position |
|---|---|
| dialog header | y ~53 |
| `Currently Scheduled Races` pill + (i) | y ~281 - **not a row** |
| list rows, green name bar | 386, 568, 751, 933 |
| row pitch | **183 px** |
| `Save Here` / `Load List` centre x | ~754 |
| row (i) button | x ~421 |
| `My Agendas` section header | y 315..334 |
| list bbox (L,T,R,B) | **(285, 340, 820, 945)** - 3 rows visible |
| scrollbar groove | x 826..846 |

Offsets from the `Save Here` anchor's top edge (y 410 on row 1): name bar
-24, `Save Here` +18, `Load List` +73, `Scheduled N` pill and its (i) +97.

- **Anchor**: `assets/trackblazer/agenda_save_here.png` (118x37, cut at
  (696,410)). `sep` gives worst positive 1.000, best negative 0.485, margin
  +0.515; the Agenda tab *without* the dialog scores 0.481, so it does not
  leak. Prefer it over the `Scheduled` pill, which also matches the header
  section at y~267 and would be read as a fourth row.
- **travel_ratio 0.911**, from two 90px drags that each moved the list 82px.
- **Empty rows are pixel-identical**, so any before/after shift aliases on the
  183px pitch: a real -93 reads as +90. Keep a calibration drag under half a
  pitch, or measure against the scrollbar thumb, which cannot alias. A band
  match across rows returns 1.000 on the *wrong* row and is worthless here.
- Dragging inside the list re-seats what sits under the press point; re-pick it
  from a fresh frame each pass or a release lands on a row's (i).

#### Agenda Details, reached by a row's (i) (2026-09-20)

| Element | Position |
|---|---|
| header | y ~52 |
| agenda name + edit pencil | name ~(553,141), pencil (694,141) |
| content area top | y ~207 |
| `Scheduled N` badge | x 275..362, y ~866 |
| `Copy` | (757,925) |
| `Close` / `Edit My Agendas` | (419,997) / (686,997) |

Empty, it prints `No scheduled races` at ~(553,521). Measured populated on
2026-09-20 against a 32-race agenda ("Test Agend").

**Rows are not found by template here, and that is deliberate.** Three anchors
were cut and all three failed `sep`, so do not retry them:

- the pink fans icon (20x20) - margin +0.248, suggested threshold 0.88, which
  is *above* the production 0.85;
- the turn band's right-hand "//" end-cap (36x28) - margin **+0.002**. That
  motif is the game's shared green section-header decoration: it scores 0.998
  on My Agendas and 0.990 on Home;
- a wider icon crop (44x40) - **11 self-matches in a frame holding 4 cards**,
  because most of the crop is flat grey card background.

Nothing in a row is both per-row and stable: the grade chip changes colour with
the grade, the aptitude pills change text, and the "Can compete with N fans or
more." overlay vanishes once the trainee has the fans. So the screen is
identified by template and the rows are then found geometrically, the way
`core/parked/shop.py` (parked 2026-09-21) separates "am I here" from "what is
on the shelf".

| Element | Position |
|---|---|
| screen anchor | `assets/trackblazer/agenda_details_btn.png`, 242x64 at (566,966) |
| `sep` | worst positive 1.000, best negative 0.405, **margin +0.595** |
| turn bands | full-width green, x 285..820, h 12..30, >=300 green px/row |
| band mids (4 visible) | 227, 388, 550, 712, 873 |
| **row pitch** | **161.5 px** (measured 161/162/162/161) |
| dialog panel | x 257..848 |
| scrollbar | groove x 838..842; thumb 89px of 683 = 0.130 |
| **travel_ratio** | **0.915** |

Offsets from a turn band's mid: detail line **+46** (`Niigata Turf 1600m (Mile)
Left / Outer`), lock-overlay text +82, fans line **+108** (`+3,100 fans`), fans
icon +111. The overlay sits *between* the two text lines, so both stay
readable - it hides neither.

The thumb ratio implies ~31 rows against the badge's `Scheduled 32`, which is a
useful cross-check that the list was fully counted.

**The aliasing trap applies here too, and worse.** Rows are 161.5px apart and
look alike, so a drag shift is only meaningful modulo the pitch: three
calibration drags read +98, -64 and +106, which unwrap to 63.5, 64 and 55.5px
of travel. Keep a calibration drag under half a pitch, or measure the scrollbar
thumb, which cannot alias - it moved 7-8px on every drag and its arithmetic
gives ~61px independently.

Numbers on this screen are warm brown, **RGB(121, 64, 22)**, not near-black: a
`R < 110` mask matches nothing. `Scheduled N` glyphs sit at x 386..406 in both
the row and the header. Grade tallies: row pills at x 586..636, y 409/436/463
(pitch 27); header pills at x 672..722, y 160/190/220 (pitch 30).

#### Reading the schedule without opening anything (2026-09-20)

The `Scheduled Races` grid itself says which turns race. A filled slot carries a
pink **"Scheduled"** badge; an empty one shows a green `+`. Badge presence is
the signal and needs no OCR, which matters because the tile art renders the
race name as stylised text over a thumbnail - a poor OCR target.

| Element | Position |
|---|---|
| column centres | 1137, 1283, 1434, 1576 (pitch ~146) |
| row centres | 655, 780, 903 (pitch ~124) |
| badge | ~97x21, centred under the tile |

Detect the badge by position within the tile rather than by blob size: one
badge measured 116x45 because it merged with the magenta `Hanshin Juvenile
Fillies` tile art. Do not bother detecting the green `+` - absence of a badge
already means the slot is empty, and a naive green-blob pass also catches the
`My Agendas` button at y~982.

What the populated dialog gives, per the user's capture, is a turn header
(`Junior Year Late Jul`) over a card carrying grade, track, terrain, distance
and `+N fans` - all clean UI text, unlike the stylised race name on the
thumbnail. That is enough to identify the race exactly: `(year, date,
racetrack, terrain, meters, grade, fans_gained)` is unique across all 212
master.mdb races (0 collisions; dropping grade+fans leaves 9). A parser on that
tuple resolved 5/5 rows from the capture and 212/212 on a round-trip.

The catch looked downstream: `race_select` (core/execute.py:723) clicks a race
only via `assets/races/<name>.png`, and 169 of those 212 races have no picture,
which would leave most of a schedule unclickable.

**Measured on a live career, 2026-09-20. Both a badge and a window exist, at
different moments** - this note twice said otherwise and both versions were
wrong, each generalised from a single frame.

- **On a turn-change lobby** (observed at Junior Late Aug) there is no popup.
  The race announces itself only as a pink **"Scheduled Race"** ribbon on the
  Races button; the facility row is intact and every other control is normal.
- **On entering a career** whose agenda has a race this turn (observed at
  Junior Late Dec, after a Session Error forced a relaunch) the game raises
  **"Scheduled Race Available - You have a scheduled race. Proceed to the Races
  screen?"** carrying the race card, with `Close` and `Race` at the usual
  (419,704) / (686,704). Template `assets/trackblazer/scheduled_race_available.png`,
  `sep` margin +0.453 (best negative 0.547, the consecutive-races warning,
  which shares the green header).

The lesson is the generalisation, not the fact: one lobby frame cannot show
that a window never appears, only that it did not appear then.

| Element | Position |
|---|---|
| badge template | `assets/trackblazer/scheduled_race_badge.png`, 146x118 at (687,892) |
| `sep` | worst positive 1.000, best negative 0.482, **margin +0.518** |
| click target | the match's own centre, ~(760,951), inside the Races button |

The cut deliberately spans the ribbon *and* part of the Races button, so the
match doubles as the click target - the `gc_to_lessons` pattern, one asset that
both recognises and aims.

**`check_turn()` reports an ordinary number on that turn**, not `"Race Day"`:
the live log read `Year: Junior Year Late Aug` with `Turn: 9`. So the branch at
core/execute.py:1507 never fires for a scheduled race, and nothing on that path
consults the agenda.

That has a consequence the code does not currently handle. Because the turn is
ordinary and the facility row is present, `matches["tb_shop"]` is true and the
shop hook at core/execute.py:1533 fires **first** - on the live run the bot went
shopping on its own scheduled race turn, then decided to race and found
`Training button is not found`, because it was standing in the shop. The
comment at :1521 justifying the shop hook's position reasons only about
`"Race Day"` turns, where the facility row is replaced; it does not cover a
scheduled race, which looks like any other turn.

#### The Race List on a scheduled turn (2026-09-20)

**The agenda has already chosen.** Clicking Races opens the list with the
scheduled race selected: banner art loaded, a selection frame, and a pink
`Scheduled` badge on its card. So the bot never searches the list and never
matches a picture - `has_image` is irrelevant on this path, which is what
retires the "169 races have no asset" problem for scheduled races.

| Element | Position |
|---|---|
| `Scheduled` badge on the selected card | (360,704), 107x30 |
| green `Race` button | (552,911), 236x61 |
| `Predictions` / `Back` | (345,913) / (216,1039) |

Measured against the bot's existing templates on that exact frame:

| template | best score | what it means |
|---|---|---|
| `match_track.png` | **1.000, two hits** | fires on *both* cards |
| `race_btn.png` | 0.926 | sound target for pressing Race |
| `race_preview_btn.png` | 0.850 | exactly the threshold - a coin flip |
| `scheduled_race_badge.png` | 0.272 | correctly absent off the lobby |

Two traps follow. **`race_select(False, None)` must not run here**: it clicks an
aptitude-match badge, and the losing card (`Clover Sho`, OP Sapporo Turf 1500m)
carries one too, so the "any" path can deselect the scheduled race and enter the
wrong one. Press Race on what is already chosen, and use the card's `Scheduled`
badge to confirm the right race before pressing. And **do not lean on
`race_preview_btn.png`** for this screen: 0.850 against a production threshold
of 0.85 is not a match, it is a tie; `race_btn.png` at 0.926 is the one to use.

The threat is precise. The generic `matches["cancel"]` at core/execute.py:1360
clicks Cancel and passes no `text=`, so it logs **nothing** - the same handler
that dismissed the Race Playback dialog and had the bot pressing Race every
~17s for ten minutes (2026-09-15). Two more generics click a green race button
outright, `race_preview_btn.png` (:1352) and `race_lineup_btn.png` (:1354), and
the comment at :1336 records that an overlay does **not** reliably suppress a
match underneath it. Copy the `gc_to_lessons` pattern (:1072-1083): cut the
template from the popup's own accept button so the match doubles as the click
target, register the key near the other race keys (:47-72) - `race_notice` is
free, `race_day` and `race_btn` are not - and put the branch between :1035 and
:1110, well above the generics.

Still unknown, and visible in the same frame as the window: whether a scheduled
race makes `check_turn()` report `Race Day` (core/state.py:946) or an ordinary
turn number. If `Race Day`, the existing branch at :1507 may already drive the
race and the popup is only a confirmation; if a number, the popup is the only
way in, and nothing on that path consults `state.RACE_SCHEDULE`.

### Inside a career: after the debut race (2026-09-17, Junior Early Sep)

The debut race is what changes the lobby. Measured with the bot stopped.

- **The shop is a lobby facility button**, taking the locked "?" slot in the
  facility grid between Recreation and Races. Click (622,952) - verified. It
  carries its own coin balance at ~(645,998) and a pink "N turn(s)" badge at
  ~(672,915).
- **The rival-race marker is a "VS" badge on the Races button**, at ~(717,915);
  the Races button itself centres ~(760,970).
- **A "Training Items" button appears** at ~(713,650), left of Full Stats
  (~(795,650)). On the shop screen the same pair sits at ~(715,290) and
  ~(795,290).
- The Result Pts badge counts up (70 pts after one win) and the rank pill under
  the portrait moved Debut -> **Bronze** at (344,666).

#### The shop screen

| Element | Position |
|---|---|
| Shop Coins value | ~(742,352) |
| item list bbox | ~(275, 400, 840, 810) |
| scrollbar | x ~842 |
| row 1 name / cost / effect | y 429 / 466 / 492 |
| row pitch | **121 px** (names 429, 550, 671, 792) |
| row checkbox | x ~765, first row y ~459 |
| row "N turn(s)" | x ~765, first row y ~422 |
| NEW badge / icon | ~(300,412) / ~(330,462) |
| Confirm / Reset | (552,913) / (771,913) |
| Back | (216,1039) |
| prompt text | (552,843) |

#### Catalogue cross-check against `data/trackblazer_shop.json`

First live reading of the shop the file asked for. The whole stock was read by
dragging (550,700) -> (550,450) three times; the third drag changed nothing, so
the list had bottomed out. **Every one of the seven costs matches the file.**

| # | On screen | Cost | Effect shown | Turns | vs the file |
|---|---|---|---|---|---|
| 1 | Royal Kale Juice | 70 | Energy +100, Mood -1 | 1 | exact: name, cost, effect |
| 2 | Wit Scroll | 30 | Wit +15 | 1 | "Scroll" 30, +15 one stat |
| 3 | Guts Ankle Weights | 50 | Increase training gains/Energy cost | 1 | "Ankle Weights" 50 - cost only |
| 4 | Guts Manual | 15 | Guts +7 | 2 | "Manual" 15, +7 one stat |
| 5 | Speed Notepad | 10 | Speed +3 | 2 | "Notepad" 10, +3 one stat |
| 6 | Glow Sticks | 15 | Race fan gain +50% | 2 | "Glow Stick" 15, "race reward boost" |
| 7 | Coaching Megaphone | 40 | Training stat gain +20% for 4 turns | 2 | "Megaphone (small)" 40, +20% for 4 turns |

What this changes:

- **The shop shows 7 items; the catalogue holds 25.** So the file is the
  universe of items and the shop is a rotating subset of it - it is not a list
  to be matched wholesale.
- **Live names are stat-prefixed** ("Speed Notepad", "Guts Manual", "Wit
  Scroll", "Guts Ankle Weights"). This said the catalogue held the bare noun and
  that `item()` therefore needed canonicalising - **no longer true**: the file
  was regenerated from master.mdb and holds the prefixed names, and on
  2026-09-19 all seven of the rows below resolved through
  `core/trackblazer.py::item()` exactly, with matching costs. No name mapping is
  needed until a row is seen that does not resolve.
- **The Megaphone tiers have real names, not sizes.** The 40-coin one is
  "Coaching Megaphone", matching the file's guessed "Megaphone (small)" on both
  cost and effect. The 55 and 70 tiers are still unnamed.
- **Glow Stick's `unverified` flag can be cleared**, and its vague "race reward
  boost" replaced with the game's own wording, **"Race fan gain +50%"**.
- ~~**Ankle Weights is the one effect mismatch.**~~ **Resolved 2026-09-19.**
  This read the file as not mentioning the Energy cost the game's row text
  names. It does: the regenerated catalogue carries two clauses per item,
  `training_bonus` 50% for 1 turn and `energy_cost_up` 20% for 1 turn, both
  scoped to the item's facility, and master.mdb agrees exactly
  (`effect_type` 11 and 12, `effect_value_1` the facility code,
  `effect_value_2` 50 and 20, `turn` 1). The shelf row text is simply
  abbreviated, naming both effects without either number. See the effect-code
  table below; the file's numbers are no longer unconfirmed.
- **"N turn(s)" is per item, not a shop-wide refresh.** The seven rows read
  1,1,1,2,2,2,2 at the same moment, which the file's single `refresh_turns: 6`
  does not describe. Whether it counts down to expiry or to restock is
  unresolved.

Scroll calibration for a future reader: a 250 px drag moved the list exactly
two rows (242 px), a travel ratio of ~0.97, and three drags cover the stock.

#### Training Items

The lobby's "Training Items" button (713,650) opens a modal listing what has
been bought, and it is where items are actually spent. Empty on this career -
"You do not own the selected training items." - so its populated form still
needs a purchase before it can be read. Close (419,997), Confirm Use
(686,997), prompt "Choose how many to use." (552,936), panel roughly
(258,32)-(848,1052). The same button repeats on the shop screen (715,290) and
on the Race List (188,217).

#### Buying and using an item (2026-09-17, Senior Early Nov)

Walked end to end on a live career: bought a Wit Manual for 15 of 1,240 coins
and used it, and the lobby's Wit went 444 -> 451. Both halves are proven.

**The purchase is four screens deep, not two.** Confirm is not the commit:

| Step | Screen (title bar) | Press |
|---|---|---|
| 1 | `Shop` shelf | row checkbox, x ~765 at the row's y |
| 2 | `Shop` shelf | **Confirm** (552,913) |
| 3 | **`Confirm Exchange`** | **Exchange** (686,997) |
| 4 | **`Exchange Complete`** | quantity **+** (797,222), then **Confirm Use** (686,997) |
| 5 | **`Confirm Use`** | **Use Training Items** (686,997) |

**Three different green buttons sit at (686,997)** across steps 3, 4 and 5, and
the Cancel/Close beside them is always (419,997). They can only be told apart
by the title bar, so a reader must match on the title and never on position.
The Training Items modal reuses the same pair again.

**Two previews make verification cheap**, and both are better signals than
button colour:

- Ticking a row deducts the cost from the coin counter immediately, before any
  commit - 1,240 became 1,225 on the tick, and stayed 1,225 after. So a
  selection can be confirmed by re-reading the counter.
- The quantity stepper shows `Held 1 > 0` and the `Confirm Use` screen shows
  the whole stat block with `Wit 444 (+7)` and `+0` on the rest.

Other measured bits: the stepper is **-** (706,222), the count (751,222), **+**
(797,222); the item tile on the `Confirm Use` screen is (327,767) showing
`1/1`; `Confirm Exchange` carries a **"Do not show again"** checkbox at
(449,887), which should be left alone - ticking it removes step 3 for this
save only, so the bot's screen sequence would stop matching a fresh install.

**A bought item leaves the shelf.** After the purchase the Wit Manual row was
gone entirely and the rows below shifted up, revealing a new one. So the
lineup is "what is still for sale", not a fixed list with held counts.

Buying and using are joined: step 4 rolls straight into the use flow, so an
item bought and used in one visit never passes through the Training Items
modal at all. That modal is only for items bought on an earlier turn.

**Several items can be bought in one go**, and it is worth doing: ticking three
rows summed correctly (1,225 -> 1,033 for 40 + 32 + 120) and `Confirm Exchange`
listed all three stacked, each with its own `Held 0 > 1`, over a single
combined coin line. The dialog grows its list downward and **the footer stays
put**, so Cancel/Exchange remain at (419,997)/(686,997) however many items are
in the basket.

`Exchange Complete` then shows one **- / 0 / +** stepper per row, at
x 706 / 751 / 797, rows at y 222 / 337 / 452 (115 px pitch), every one
defaulting to 0.

**Row order is not stable between the two screens.** The basket listed Ankle
Weights, Megaphone, Training Application; `Exchange Complete` listed them
Training Application, Megaphone, Ankle Weights. A reader must match rows by
name, never by index.

#### Training Items, stocked

Same modal as the empty one, reached from the lobby's Training Items button
(713,650), listing what was bought earlier and not used. Each row shows
`Held N > N` and its own stepper at the same x 706 / 751 / 797.

**Its rows sit higher than `Exchange Complete`'s**: first row y **151**, then
266, 381, the same 115 px pitch. `Exchange Complete` starts at 222 because it
carries the "Purchased the selected training items" line above the list. The
two screens are otherwise near-identical and share Close/Confirm Use at
(419,997)/(686,997), so they can only be told apart by the title bar - and
their row grids must not be shared.

**Only buy-and-use the books.** The flat stat items - Notepad (+3), Manual
(+7), Scroll (+15), the `stat` category in `data/trackblazer_shop.json` - have
no timing to get wrong, so using them the moment they are bought costs
nothing. Everything else should be bought and left in the inventory for the
turn that wants it: a Coaching Megaphone spends its +20% over the next four
turns whether or not those were training turns, an energy item is worth most
when energy is actually low, and a Good-Luck Charm is worth most on a turn
with a training the bot would otherwise skip for failure risk.

The game agrees with this by default: the `Exchange Complete` quantity starts
at **0** with Confirm Use dimmed, so storing is what happens if nothing is
pressed, and using on purchase is the opt-in. A buying routine should step the
quantity up only for the `stat` category and press **Close** (419,997) for
everything else, then come back to the Training Items modal later.

#### What a training bonus actually does (measured 2026-09-19)

A `training_bonus` percentage is a **multiplier on the training's gains**, not a
flat addition. Measured by reading the board twice on a single turn - Classic
Late Nov, turn 3 - with a Motivating Megaphone (+40% for 3 turns) used in
between, so supports, levels, energy costs and failure rates were identical on
both sides:

| Facility | Supports | Before | After |
|---|---|---|---|
| SPD | 0 | spd 13, pwr 5, skill 2 | spd **19**, pwr **7**, skill 2 |
| STA | 0 | sta 7, guts 3, skill 2 | sta **9**, guts **4**, skill 2 |
| PWR | 1 | sta 5, pwr 9, skill 2 | sta **7**, pwr **12**, skill 2 |
| GUTS | 1 | spd 4, pwr 3, guts 7, skill 2 | spd **5**, pwr **4**, guts **9**, skill 2 |
| WIT | 2 | spd 5, wit 17, skill 6 | spd **7**, wit **23**, skill **8** |

Nothing moved by 40, so the flat reading is refuted outright; every ratio
clusters on x1.4, the spread being rounding noise on small integers (13 x 1.4 =
18.2 showing 19, 7 x 1.4 = 9.8 showing 9). Also established:

- **It multiplies the final gain, after support bonuses.** PWR and WIT carried
  supports and scaled like the zero-support facilities did.
- **It scales skill points too** (WIT skill 6 -> 8). A `skill: 2` holding at 2
  is 2 x 1.4 truncating, not a counter-example.
- **Energy cost and failure rate are untouched** - identical on both sides.

The game says as much itself, in the Log entry the use writes: *"Use Motivating
Megaphone. All stats gained from training will be increased by 40% for 3
turns."*

This settles `TRAINING_BONUS_IS_PERCENT` in `core/parked/shop_choice.py`, which was
carrying a sevenfold valuation swing.

#### Item effects live in master.mdb, keyed by code (2026-09-19)

`single_mode_free_shop_item` joins `single_mode_free_shop_effect` on
`effect_group_id`; the effect row carries `effect_type`, four `effect_value_N`
columns and `turn`. A shop reader should key on these rather than parse the
on-screen effect text. An item can own several effect rows under one group.

**`effect_value_1` is a target code** wherever the effect is scoped: `1` spd,
`2` sta, `3` pwr, `4` guts, `5` wit for direct stat adds; `10` energy, `11` max
energy, `20` mood; and for facility-scoped effects `101` spd, `102` pwr, `103`
guts, `105` sta, `106` wit. **`0` means every facility.**

| type | What it is | Items | Shape |
|---|---|---|---|
| 1 | direct add | Notepad / Manual / Scroll, Vita, Kale, Energy Drink, Cupcake | `[target, amount]`, turn 0 |
| 2 | training level +1 | the five Training Applications | `[facility, 1]` |
| 3 | unresolved | Yummy Cat Food, Grilled Carrots | `[?, ?, 5]` |
| 6 | condition cure / hint | Mirror, Binoculars, Miracle Cure | `[kind, id]` |
| 10 | reset | Reset Whistle | no values |
| **11** | **training bonus - a multiplier** | **Megaphones, Ankle Weights** | `[facility or 0, percent]`, `turn` |
| 12 | energy-cost increase | Ankle Weights only | `[facility, 20]`, turn 1 |
| 13 | failure rate | Good-Luck Charm | no values, turn 1 |
| 14 | race / fan bonus | Cleat Hammers, Glow Sticks | `[kind, percent]`, turn 1 |

The Megaphones are `effect_type 11` with `effect_value_1 = 0`, `effect_value_2`
of 20 / 40 / 60 and `turn` 4 / 3 / 2 for the 40 / 55 / 70-coin tiers - which is
why the measured buff scaled *every* facility.

**Note the mdb stores a bare integer.** Nothing in the schema says "percent":
`effect_value_2 = 40` is identical whether the game means x1.4 or +40, so
master.mdb could never have settled that question on its own, and
`data/trackblazer_shop.json`'s `"percent"` key is an interpretation added when
that file was generated, not something the mdb asserts. The measurement above
is what supplies the unit.

Two things this settles beyond the Megaphone:

- **Ankle Weights share `effect_type 11` with the Megaphones**, so the measured
  multiplier applies to them too - scoped to one facility
  (`effect_value_1` 101/102/103/105) at **50** for **1 turn**, i.e. x1.5 on that
  facility. The catalogue's "+50% to one training for 1 turn" was right after
  all.
- **Their energy penalty is a second row at `effect_type 12`**, same facility,
  value **20**, 1 turn - the half the game's shelf text means by "Increase
  training gains/Energy cost". `data/trackblazer_shop.json` already carries
  both rows per item (`training_bonus` 50/1 and `energy_cost_up` 20/1, each
  facility-scoped), so the mdb confirms the catalogue here rather than
  correcting it.

Royal Kale Juice is the worked example of a multi-row item: two rows under one
group, `[10, 100]` energy +100 and `[20, -1]` mood -1, matching its shelf text
exactly.

#### Read the name, never the price

Measured against a saved shop frame with the project's own reader. **Item names
OCR perfectly** - three of three exact, including the 26-character
`Speed Training Application`. So a shop reader should identify a row by its
name and look the item up in the catalogue; no icon templates are needed, and
none have been cut.

**The price does not read reliably**, because a discounted row prints the old
price struck through beside the new one and the strike-through corrupts the
read:

    '~50- 40'     50 -> 40
    '-40- 32'     40 -> 32
    '458 120'     150 -> 120, and "150" came back as "458"

So the price must come from the catalogue, not from OCR. What is actually
charged can then be confirmed exactly: tick the row and read the coin counter,
which deducts before any commit (1,240 -> 1,225 on a 15-coin tick). That turns
an unreliable read into arithmetic.

**Discounts are 10-20%**, per GameTora - every one measured here was 20%, which
is only the top of the range, so nothing should assume a flat multiplier.

#### Why there are no icon assets

Worth recording so nobody repeats the search. The item icons are not
obtainable:

- Game8 and GameTora both serve lazy-loaded base64 placeholder GIFs in place of
  item images, so no web source yields them.
- `master.mdb` holds no icon reference for shop items: `single_mode_free_shop_item`
  has only `motion_id` (an animation), and `item_data`'s 194 rows are the
  general inventory, not these.
- The art does ship locally, as `UnityFS` bundles (Unity 2022.3.62f2) among
  171,347 files in `UmamusumePrettyDerby_Data/Persistent/dat/`, but the `meta`
  index beside them is encrypted - header `fd 45 78 d1 b1 54 ff d7`, no SQLite
  magic, no readable strings - so there is no way to find the right bundle
  short of brute-forcing all of them, and it would need UnityPy installed.
- Even extracted, a source texture would not match the rendered row, which
  composites the icon onto a patterned tile with an `x1` overlay. It would fail
  `umatool sep` the same way a downloaded icon would.

Since the names OCR cleanly, none of this is worth doing.

The shop restocked between visits with a completely different lineup (Junior:
Royal Kale Juice, Wit Scroll, Guts Ankle Weights...; Senior: Wit Manual, Guts
Manual, Guts Scroll, Good-Luck Charm...), and the Senior visit was badged
**ON SALE!** at (318,357) with the shopkeeper saying "We're having a sale!" -
matching uma.guide's note that a refresh can discount the new items.

Per-row `N turn(s)` is **item expiry**, confirmed twice over: the Senior rows
read 3,3,2,2 where the Junior rows read 1,1,1,2 at their own moment, and the
values do not match effect durations either (Coaching Megaphone showed 2 while
its effect lasts 4). The 6-turn cycle in `single_mode_free_shop` is the
restock, which adds to the shelf.

#### The Race List, and the rival race

Reached from the lobby's Races button (760,970). Its "VS" badge is not
decoration: it marks a turn that offers a rival race.

| Element | Position |
|---|---|
| title "Race List" | (216,17) |
| banner grade badge / race name | (681,196) / (681,255) |
| **"Rival Race!" pill** + its (i) | (665,348) / (782,348) |
| Full Gate N Runners | (620,383) |
| weather / season row | (620,411) |
| "Held" + date | (600,465) |
| **Result Pts pill** | (305,467) |
| turn nav: « ‹ label › » | (285,546) (347,546) (552,547) (758,546) (820,546) |
| row 1 **"VS RIVAL RACE!" ribbon** | ~(750,603) |
| row 1 picture tile / track line | (361,657) / (612,627) |
| row 1 pts / coins / fans | (543,663) / (640,663) / (545,690) |
| row 1 aptitude chips | (773,659) and (773,686) |
| row pitch | **128 px** (row 1 name 627, row 2 name 755) |
| Predictions / Race / Back | (346,913) / (552,913) / (216,1039) |

This confirms the earlier research note that a race row carries everything race
selection needs, in one place: grade badge, track line
(`G3 Sapporo Turf 1800m (Mile) Right`), `+ 60 pts`, a coin `+ 100`,
`+3,100 fans`, and Turf / Mile aptitude chips.

**First live check of `core/trackblazer.py`'s tables, and they hold:**

- The G3 row pays **`+60 pts`**, matching `POINTS_BY_GRADE["G3"] = 60`.
- The row's coin reward reads **`+100`**, consistent with
  `COINS_BY_PLACEMENT[1] = 100` - though the row does not say which placement
  it is quoting, so read that as consistent rather than confirmed.
- The Junior goal reads **`60 Result Pts`**, matching
  `TARGETS["turf"]["junior"] = 60`.

#### The Twinkle Star Climax (2026-09-17)

Trackblazer's replacement for the URA Finale: three races, highest total wins.
Measured from one frame on a Race Day, so treat the positions as approximate.

**It introduces a year string nothing else produces**: `TS Climax Races
Underway`, with the title bar reading `TS CLIMAX`. The goal line is
`Win the Twinkle Star Climax series` with `Current Rank <trophy> RANK -`; the
rank is a badge rather than text, so OCR returns the literal word "RANK".

**On a Climax race day there is no turn counter**: the box that normally holds
"N turn(s) left" is replaced by a red **Race Day** pill, so anything parsing
turns left has nothing to read. `check_turn()` returns the string `"Race Day"`
here, not a number - worth knowing, because `decide_race_for_goal` compares
`turn` against integers and would raise on it if it were ever reached.

**Between the races the ordinary lobby comes back.** After round 1 the counter
read `1 turn(s) left` and the full facility row returned - Rest, Training,
Skills, Infirmary, Recreation, Shop - with Races relabelled **TS Climax** and
carrying a padlock. So the layout below describes the race day only; a normal
turn sits between rounds and trains as usual.

**The RANKING badge tracks the series**: after a 5th place it read `5th`,
`3 pt(s)`, `1/3 Races`, which confirms `CLIMAX_VP[5] = 3` against the live
game. The results screen also showed 3rd=6, 4th=4, 5th=3 and 6th=3 side by
side, matching the whole table.

**Climax races pay no shop coins.** The balance was 1,033 before round 1 and
1,033 after, where `COINS_BY_PLACEMENT[5]` would have predicted +30. The
rewards screen shows a medal icon worth 600 of something, but it is not the
Climax Store coin, so `coins_for()` must not be applied to these three races.

#### Driving a Climax race: the six screens

Walked twice by hand, rounds 1 and 2, with identical positions both times.

**The bot does drive this, and needs none of it.** Corrected 2026-09-18, when a
Trackblazer career ran the Climax unattended: `race_day()` pressed
`assets/trackblazer/ts_climax_race_btn.png` and the entire sequence collapsed
into one `Next.` - about 45 s from press to the lobby returning. The game's own
readback recorded the result (`Run in TS Climax Race 1 (EX)`, "Competed as the
number 1 favorite and won"), and the standings read `RANK 1 /16`, `10 pt(s)`.

The six steps below were measured *by hand, pressing each screen through*. The
`Skip >>` and `Quick` buttons sitting at the bottom of these screens collapse
them, which is why the hand-walk looked like six presses needing six templates
and the bot needs one. Keep the table: it is still the manual recipe, and still
what a deliberate handler would drive if one is ever wanted. Just do not read it
as a list of blockers - in particular the uncut templates at steps 5 and 6 are
not stopping anything.

| # | Screen | Press |
|---|---|---|
| 1 | Climax lobby (Race Day pill) | **TS Climax Race!** (537,908) |
| 2 | Race List | **Race** (552,913) |
| 3 | `Race Details` - "Enter race?" | **Race** (686,775) |
| 4 | Race prep (stats, strategy) | **Race** (642,990) |
| 5 | Lineup, **full 1920 width** | **Race!** (960,999) |
| 6 | race running | skip, then Next (679,992) |

Then two more screens before the lobby returns: a rewards screen whose **Next
is a decorated button at (552,1000)** that matches no template we have, and a
standings screen (`RANK n /16`) with Next at (553,939).

Two traps in there. Step 5 is drawn at the full screen width rather than in the
usual x 148-958 panel, so its button sits at x=960. And the race view's skip is
`skip_btn_big.png` at **(1685,987)**, outside `SCREEN_BOTTOM_REGION` (x
125-1000) - which is why `tools/umatool.py skiprace`, which searches the whole
screen, drives this fine while `race_day()`'s region-scoped searches cannot.
Skip count varies with the cinematic: 3 clicks for round 1, 5 for round 2.

**The facility row on a race day is replaced.** No Rest, Training, Infirmary,
Recreation or Races - only three buttons:

| Element | Position |
|---|---|
| title `TS CLIMAX` / year label | (203,17) / (347,45) |
| **Race Day** pill (where the turn counter was) | ~(310,115) |
| goal EX badge / text / Details | (410,88) / (595,73) / (805,86) |
| **RANKING** badge / points / **`0/3 Races`** | (222,185) / (222,265) / (213,308) |
| Training Items (+ count badge) / Full Stats | (713,708) + (738,682) / (793,708) |
| Skills / **TS Climax Race!** / Shop | (350,915) / (550,900) / (752,915) |
| shop coin balance | ~(752,963) |

**The shop stays open through the Climax**, still holding its coin balance.
That matches uma.guide's note that a hammer can be bought just before the
finals, and it is the last chance to spend coins, which expire with the career.
The Training Items button shows a count badge for stored items.

**Gotcha for the race schedule.** `career_lobby()` guards the schedule block
with `len(year_parts) > 3 and year_parts[3] not in ["Jul", "Aug"]`. This year
string splits to `["TS", "Climax", "Races", "Underway"]`, so `year_parts[3]` is
`"Underway"` and the guard passes - the schedule block runs during the Climax.
Harmless with an empty schedule, but a configured one would try to select a
scheduled race on a Climax race day, where the Races button does not exist.

### Still unverified - only exists inside a career

The shop / Climax Store itself and its 6-turn refresh and costs, rival races
and their red/blue VS icon, and race route epithets.
