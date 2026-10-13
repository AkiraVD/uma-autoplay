# Backtesting against recorded careers

A career is the only honest test of the training logic. Fixtures cover readers
and scorers in isolation; nothing else answers "would this change have played
the career better". But `logs/` is gitignored and `utils/log.py` keeps only ten
1 MB backups, so a career's evidence is gone after about ten more runs - and a
career long enough to pass 1 MB rotates *mid-run*, leaving its own first hours
in `log.txt.1` while `log.txt` holds only the tail.

So finished careers are lifted out of their logs into
`tests/fixtures/careers/*.json`, which is tracked. One record per lobby turn:
the board exactly as `check_training` read it, the energy the decision was made
on, and what the bot then did.

`tools/career_extract.py` writes them. `tests/test_career_fixture.py` checks
their shape.

## Recorded careers

| Fixture | Run | Scenario / trainee | Turns | Decisions | Splits | Outcome |
|---|---|---|---|---|---|---|
| `trackblazer_20260918.json` | 2026-09-18, 23:57-01:55 | Trackblazer, `[Hot☆Summer Night]` Maruzensky, Deck 6 + borrowed SSR group card | 77 (57 scored) | 43 train / 14 rest - spd 24, wit 10, pwr 4, guts 3, sta 2 | **no** - predates the change | **RANK 1**, Twinkle Star Climax won, 3 warnings, 0 errors |
| `trackblazer_20260918b.json` | 2026-09-18, 11:42-13:33 | same trainee and deck, `prioritize_g1_race` on (which turned out to be inert here) | 77 (54 scored) | 39 train / 15 rest | **yes** - 54 of 54 scored turns | **RANK 1**, spd 1064 / sta 325 / pwr 626 / guts 304 / wit 509 |

Prefer **`...918b`** for anything touching the scorers: it is the only one that can
replay `rainbow_training` and `training_score`. The first is still useful for
the rest-vs-train rules, and it holds the turn the last-five-turns rescue was
written for.

What that one is good for:

- **The last-five-turns rest rule.** It contains the turn the rule was written
  for (01:36:21, TS Climax): four facilities at 20%, WIT safe at 0% with no
  supports, energy 38.98. The old logic rested; the new one takes WIT. It also
  contains the case the rule must *not* break - Senior Early Dec, where nothing
  cleared the failure bar and resting was correct.
- **The planner.** Every scored turn carries the advisory verdict beside what
  the bot actually did, so the two can be diffed without re-running anything.
  The turn that forced the goal-before-energy reorder is in there.
- **The Trackblazer turn counter.** Eleven Classic turns reading `5` against a
  true `24..13`, `11` reading as `1` in all three years, and `-1` through the
  Climax. See the turn-counter item in `TODO.md`.
- **Junior through Climax**, so a replay is not quietly missing a year.

It covers every lobby turn from the first to the last. The final Climax race
and the completion sequence produce no lobby turn, so they are not records; the
raw log is the only source for those.

## Recording a new one

```bash
python tools/career_extract.py logs/log.txt.1 logs/log.txt \
    --since 23:57:17 \
    --out tests/fixtures/careers/<scenario>_<yyyymmdd>.json
```

Pass the rotated backup **first**, and `--since` the timestamp of that run's
`[BOT] Starting` line: one log file holds several careers, and a long one has
already rotated by the time it finishes. Archive the raw log too
(`logs/archive_<name>.txt`) - it is gitignored, so it survives rotation but not
a lost machine, and the JSON is the durable copy.

## What a turn record holds

Top level is `label`, `source` (`{logs, since}`) and `turns`.

| Key | On | Meaning |
|---|---|---|
| `time`, `year` | every turn | timestamp and the year string as OCR'd |
| `turn`, `criteria` | 76 of 77 | the counter (int, or `"Race Day"`) and the goal text |
| `facilities` | every turn | per-facility `supports`, `levels`, `failure`, `gains`, `energy_cost` |
| `energy` | 76 | **the reading the decision was made on** |
| `energy_after` | 76 | the last reading of the turn, after it acted |
| `stats`, `caps`, `headroom` | 57 | as `do_something` published them |
| `planner` | 57 | `{verdict, why, goal, scores}` - advisory only |
| `action`, `decided_by` | 57 | `train` or `rest`, and the line it was read from |
| `trained` | 43 | the facility, when the action was a train |

A turn with no `facilities` is a race day, a story screen or a partial read.
They are kept on purpose: "what did it do on the turns it could not score" is
exactly what a backtest asks.

## Traps, all of which produced a wrong fixture first

The extractor was wrong twice before it was right, and **both times the output
looked completely healthy**. Anything reading these logs will hit the same
things:

- **`do_rest` logs nothing at all.** It clicks the rest button with no `text=`,
  so a rest is only visible through logic.py's reason lines, or inferred from a
  scored turn that never trained. The extractor marks those
  `decided_by: "inferred: ..."`.
- **Junior logs no selection.** `focus_max_friendships` has no
  `Training selected:` line, so keying on that alone records `action: None` for
  the entire year while the fixture still looks full. `do_train`'s
  `Training {KEY}.` is the one signal every path emits.
- **Energy is logged several times a turn.** `do_something` reads it before
  deciding, `most_support_card` reads it again, and the *next* turn's pre-read
  lands in the same block because it comes before the next `Year:` line. Taking
  the last gives every turn the energy *after* it acted: the rescue turn
  recorded 44.07, the post-WIT refund, where the choice was made at 38.98.
  Take the first reading of the block.
- **`Selecting X training.` is not a decision.** It fires once per facility
  while `check_training` scans - five times a turn.
- **Search `logs/log.txt*`, never `logs/*.txt`.** The glob matches no rotated
  backup, and the silence is indistinguishable from a clean run: it made a
  career with 3 warnings look like it had none.

## The per-type split, and what older careers cannot do

`Levels:` in the log is `total_friendship_levels` - one aggregate over all six
card types (spd, sta, pwr, guts, wit and **friend**). But a rainbow is a card of
the facility's *own* type at yellow or max, which `rainbow_training` reads from
the per-type split, and `training_score` needs the same structure. A sum cannot
be split back into its parts: `Levels:{'max': 3}` is equally three own-type
cards (three rainbows) or one own-type plus two friend cards (one rainbow), and
those two boards pick different facilities.

Since **2026-09-18** the debug line carries the split as well, flat and only
where it is non-zero, because nested braces five times a turn are unreadable
and `spd:max=1` parses without them:

```
[SPD] → Total Supports 3, Levels:{...} , Fail: 20%, Gains: {...}, Energy -26, Split:[spd:max=1, friend:max=2]
```

`career_extract.py` stores it as `facilities.<key>.split`. Careers recorded
*before* that date have no `Split:` clause and simply carry no `split` key -
their `total_supports`, `failure`, `gains`, `energy_cost` and
`total_friendship_levels` replay exactly, so `focus_max_friendships` (the Junior
scorer) replays in full, but `rainbow_training` and `training_score` cannot be
replayed against them at all. `trackblazer_20260918.json` is one of those: it
predates the change by a few hours.

## The replay harness

`tools/career_replay.py` (2026-10-12). It drives the **real**
`core.logic.do_something`, with only the four readers that function opens with
stubbed from the record, so the choice comes out of the actual filters, duel
and camp rules, Junior branch, `rainbow_training` and rest fallbacks rather
than out of a second copy of the scorer that would drift from them.

```bash
# fidelity only: does the harness reproduce what the career did?
.venv/bin/python tools/career_replay.py tests/fixtures/careers/<career>.json

# and what a different weighting would have chosen
.venv/bin/python tools/career_replay.py tests/fixtures/careers/<career>.json \
    --override '{"priority_weights": [2.5, 1.5, 0.7, 0.5, -1],
                 "priority_weight": "HEAVY"}'
```

Two arms over the same turns: `base` is `--config` (default `config.json`),
`alt` is that with `--override` merged in. It prints the pick counts, the stat
points the chosen facility actually printed (clipped to that turn's headroom),
and every turn the two arms disagreed on. "What counts as a regression" is
still a judgement call, which is why the output is a diff and a stat-point
total rather than a pass/fail.

**Read the fidelity line first.** A replay that cannot reproduce the recorded
career is measuring its own reconstruction. On
`grandconcert_kitasan_20261012` it reproduces 59 of 60 comparable turns
(98.3%); the one miss is a Junior turn, and the 3 Recreation outings are
excluded because `should_recreate` - not `do_something` - made that choice, so
the scorer cannot be marked right or wrong on them.

Two inputs are genuinely absent from a fixture and are rebuilt:

- `total_hints` never reaches the log as a number, only as a flat +0.5 on
  `base`, so it is recovered from the recorded `scores.<stat>.base`.
- the per-type split is missing on pre-2026-09-18 careers. The harness refuses
  those rather than replaying them wrongly. A board with **no supports** also
  prints no split, but it has no rainbow either, so that absence costs nothing.

Both arms share whatever reconstruction error is left, so a *difference*
between them is real even where the absolute choice is not.

### The trap in replaying `maximum_failure`

`check_training` short-circuits: a facility reading over `MAX_FAILURE + 5`
is written down as exactly `MAX_FAILURE + 5`, and so is **every facility
scanned after it that turn** (`core/execute.py`, `margin = 5`). On
`grandconcert_kitasan_20261012`, 64 of 315 facility reads are that clamp - the
value 20, under a `maximum_failure` of 15 - and not a measurement at all.

So replaying with `maximum_failure: 20` lets all 64 through the filter as if
they had been read at exactly 20%, when what the game actually showed was
"more than 20". That arm reported 10 extra trainings and +359 Speed, which is
fiction. Replaying at **18** is sound: it admits the real 16/17/18% reads and
still rejects the clamped 20s. **Raising the bar to the clamp value of the
career being replayed cannot be backtested at all** - only measured live.

### The trap in the energy cap

A log never records how long the energy bar is, and `None` is **not** a neutral
stand-in for it. `logic.energy_points` reads a missing cap as an *empty tank*
and prices energy at its top rate on every turn, and `logic.energy_value` used
to raise `TypeError` on it outright - which does not make a facility score
lower, it takes the whole decision down another branch. That is what dropped
the 2026-10-13 replay from 97% reproduced to 39%, and it read exactly like a
scoring regression.

`career_replay.energy_cap()` therefore estimates one per fixture: 100 for the
ordinary bar, or the highest reading when that is higher, because the Grand
Concert widens it - the 2026-10-13 career sat at 97-104 for eighteen turns and
peaked at 104.24. Anything new that prices energy has to be given a cap here,
and `energy_value` now clips nothing rather than raising when it has none.

### What a replay cannot tell you

A replay scores each turn against the board and the energy the career actually
recorded, so it never sees the *consequences* of a different choice. The sharpest
case is wit: lifting the old `WIT_MIN_RAINBOWS` gate turned four to six recorded
rests a career into wit trainings, and the harness scores those as free stats -
correctly, since wit costs no energy. What it cannot show is the turn after,
because wit hands back only 5-15 energy where the rest it replaced returned
about 50, so the tank it leaves behind is a different one. Treat a replay's
verdict on an energy-shaped change as an upper bound, and check the energy
trajectory of the live career that follows.

## Careers recorded with Performance data

`performance_bonus` is scored off the Grand Concert `Performance:` line, which
`career_extract.py` only started storing on 2026-10-12. The two Bakushin
fixtures carry none, so that term replays as 0.0 on them and the harness says
so in its header. A Grand Concert change therefore has to be measured against
a career recorded since - which is also a useful control: a career with no
Performance data proves the change is inert where it should be.

## Two extractor bugs, both found by the harness

Fixed 2026-10-12, and both had been producing fixtures that looked healthy:

- **`All trainings are unsafe, but WIT is safe...` is not a rest.** `logic.py`
  follows that line with `return "wit"`. It was in `DECISIONS` as a rest, so
  two WIT trainings were recorded as rests and the replay looked like it
  disagreed with the career on turns where it had matched it exactly. The real
  rest message is `No safe training found`.
- **A Recreation outing is neither a train nor a rest.** The turn trains
  nothing, so it was inferred as a rest. It is now its own `action: "outing"`,
  which is what lets the harness exclude it instead of scoring it.

Fidelity on that career went 92.1% -> 98.3% on those two alone.
