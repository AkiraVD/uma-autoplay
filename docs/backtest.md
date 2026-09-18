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

| Fixture | Run | Scenario / trainee | Turns | Decisions | Outcome |
|---|---|---|---|---|---|
| `trackblazer_20260918.json` | 2026-09-18, 23:57-01:55 | Trackblazer, `[Hot☆Summer Night]` Maruzensky, Deck 6 + borrowed SSR group card | 77 (57 scored) | 43 train / 14 rest - spd 24, wit 10, pwr 4, guts 3, sta 2 | **RANK 1**, Twinkle Star Climax won, 3 warnings, 0 errors |

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

## Not built yet

There is no replay harness. The fixture makes one straightforward - feed each
turn's `facilities`/`stats`/`caps`/`energy` into the scorers and diff the choice
against `action`/`trained` - but what counts as a regression is a judgement
call (a different facility at the same score is not obviously worse), so the
comparison has not been written.
