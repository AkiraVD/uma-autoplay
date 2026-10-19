"""Replay a recorded career's turns through the real training logic.

`docs/backtest.md` ended on "there is no replay harness". This is it.

The point is to answer "would this change have played the career better" with
the career's own boards instead of a hand-built one. Every turn in a fixture
carries the board exactly as `check_training` read it, so the scorers can be
fed the real thing; what they cannot be fed is a screenshot, so the four
readers `do_something` opens with are stubbed from the record and nothing else
about the decision path is touched. The decision therefore comes out of
`core.logic.do_something` itself - filters, duel and camp rules, the Junior
branch, rainbow_training, the rest fallbacks - rather than out of a second
implementation of the scorer that would have to be kept in step with it.

Two arms are run over the same turns: `base`, the config the career was
recorded under, and `alt`, that config with `--override` applied. Only the
turns where the two arms disagree are interesting, and for each the stat gains
the game actually printed are known, so the difference can be totalled in
stat points rather than in score units.

    # fidelity only: does the harness reproduce what the career did?
    .venv/bin/python tools/career_replay.py tests/fixtures/careers/x.json

    # and what a different weighting would have chosen
    .venv/bin/python tools/career_replay.py tests/fixtures/careers/x.json \
        --override '{"priority_weights": [2.5, 1.5, 0.7, 0.5, -1],
                     "priority_weight": "HEAVY", "maximum_failure": 20}'

**Fidelity is reported, not assumed.** A replay that cannot reproduce the
recorded decisions is measuring its own reconstruction, so the `base` arm is
diffed against what the career did and the mismatch rate is printed first. Two
inputs are genuinely absent from a fixture and are rebuilt here:

  - `total_hints` never reaches the log as a number - it only shows up as a
    flat +0.5 on `base` - so it is recovered from the recorded `base` when the
    career carries a score breakdown, and assumed 0 otherwise.
  - the per-type split is missing on careers recorded before 2026-09-18 and on
    any board with no supports at all (nothing to print). Without it a rainbow
    cannot be told from a friend card, so such a career is refused for the
    scorer arms rather than replayed wrongly.

Both arms share whatever reconstruction error is left, so a *difference*
between them is real even where the absolute choice is not.
"""
import argparse
import copy
import math
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

TYPES = ["spd", "sta", "pwr", "guts", "wit", "friend"]
LEVELS = ["gray", "blue", "green", "yellow", "max"]
TRAINING = ["spd", "sta", "pwr", "guts", "wit"]
NON_MAX = ["gray", "blue", "green"]


def build_results(turn):
  """The dict `check_training` would have handed `do_something` for this turn.

  Shaped by core/state.py::check_support_card: a per-facility record holding
  the aggregate counts, one sub-dict per card type, and the reads the main
  loop attaches afterwards (gains, energy cost, Performance, Unity, duel).
  """
  results = {}
  performance = turn.get("performance") or {}
  for key, face in (turn.get("facilities") or {}).items():
    split = face.get("split") or {}
    record = {
      "total_supports": face.get("supports") or 0,
      "total_hints": 0,
      "total_friendship_levels": {lv: (face.get("levels") or {}).get(lv, 0)
                                  for lv in LEVELS},
      "hints_per_friend_level": {lv: 0 for lv in LEVELS},
      "failure": face.get("failure"),
      "gains": face.get("gains") or {},
      "energy_cost": face.get("energy_cost"),
      # Unity readers return zeros outside Unity Cup, which is what a Grand
      # Concert or URA career recorded, so a flat zero is the real reading.
      "unity": {"spirit": 0, "burst": 0, "burst_ex": 0},
      "duel": False,
      "performance": ({"types": (performance.get("chips") or {}).get(key, []),
                       "short": performance.get("short") or [],
                       "urgent": bool(performance.get("urgent"))}
                      if performance else {}),
    }
    for card_type in TYPES:
      levels = split.get(card_type) or {}
      record[card_type] = {
        "supports": sum(levels.values()),
        "hints": 0,
        "friendship_levels": {lv: levels.get(lv, 0) for lv in LEVELS},
      }
    results[key] = record

  # `total_hints` only ever reaches the log folded into `base`, so where the
  # career recorded the breakdown it can be read back out of it. Anything that
  # is not a clean half point is left alone rather than guessed at.
  for key, record in results.items():
    logged = ((turn.get("scores") or {}).get(key) or {}).get("base")
    if logged is None:
      continue
    bonds = sum(record[t]["friendship_levels"][lv]
                for t in TRAINING for lv in NON_MAX)
    remainder = logged - record["total_supports"] - 0.5 * bonds
    if abs(remainder - 0.5) < 1e-6:
      record["total_hints"] = 1
  return results


def splits_missing(turns):
  """Facility records with supports but no split - the boards that cannot replay.

  A board with no supports prints no `Split:` clause because there is nothing
  to print, and it has no rainbow either, so its absence costs nothing.
  """
  missing = 0
  for turn in turns:
    for face in (turn.get("facilities") or {}).values():
      if (face.get("supports") or 0) > 0 and "split" not in face:
        missing += 1
  return missing


def energy_cap(turns):
  """The energy bar's cap for this career, estimated from the readings.

  Nothing in a log states it. 100 is the ordinary bar, but the Grand Concert
  widens it - the 2026-10-13 career sat at 97-104 for eighteen turns - so the
  highest reading wins when it is higher, rounded up to a whole point.
  """
  seen = [t["energy"] for t in turns if isinstance(t.get("energy"), (int, float)) and t["energy"] > 0]
  return max(100.0, math.ceil(max(seen))) if seen else 100.0

def stub_readers(state, logic, turn, max_energy=None):
  """Point the four readers `do_something` opens with at this turn's record.

  Patched on **both** modules. `core/logic.py` does
  `from core.state import check_energy_level, ...`, which binds the function
  objects at import, so replacing them on `core.state` alone leaves logic
  calling the real readers - they return -1 with no game on screen, and the
  replay then scores every turn on an empty tank. Same trap CLAUDE.md records
  for the config globals, in the other direction.

  max_energy matters as much as the level. A career's log does not record the
  bar's cap, so it is estimated per fixture by energy_cap() - and passing None
  is NOT neutral: logic.energy_points reads a missing cap as an empty tank and
  prices energy at its highest rate on every turn, which flipped two turns of
  the 2026-10-13 replay on margins of hundredths.
  """
  stats = turn.get("stats") or {}
  caps = turn.get("caps") or {}
  energy = turn.get("energy")
  year = turn.get("year") or ""
  for module in (state, logic):
    module.check_current_year = lambda: year
    module.stat_state = lambda: dict(stats)
    module.stat_caps_state = lambda: dict(caps)
    module.check_energy_level = lambda: (energy, max_energy)
  # The turn counter only feeds the advisory planner line, but leaving it on
  # the previous career's value makes that line misleading to read back.
  state.CURRENT_TURN = turn.get("turn")
  state.CURRENT_YEAR = year


def replay_lessons(turns, config, label):
  """Replay every recorded Lessons board through the real `choose`.

  The training arm stubs four screen readers; this one stubs the board module's
  running state instead - the song counts, the page countdown, the energy cap
  and the wit return - because all four are published rather than derived, and
  a fixture records what they were. Feeding them back is the honest way round:
  simulating lessons' own state machine over a career would be a second
  implementation of it, and the thing under test is `choose`.

  Returns (same, differed, unreplayable).
  """
  import core.state as state
  import core.lessons as lessons

  state.load_config = lambda: copy.deepcopy(config)
  state.reload_config()
  state.apply_scenario()

  boards = [(t, b) for t in turns for b in (t.get("lessons") or [])]
  same = differed = skipped = 0
  misses = []
  saved = (lessons._songs.copy(), dict(lessons._pattern), lessons._energy_cap,
           lessons._wit_return, lessons._energy_reach)
  try:
    for turn, board in boards:
      if board.get("energy") is None or not board.get("points"):
        skipped += 1
        continue
      by_segment = board.get("songs_by_segment")
      if by_segment is None:
        # Logged before 2026-10-13: the per-segment split is not recoverable
        # from the total, and hype_songs_needed reads it.
        skipped += 1
        continue
      lessons._songs.clear()
      lessons._songs.update({int(k): v for k, v in by_segment.items()})
      lessons._energy_cap = board.get("cap") or None
      lessons.set_wit_return(board.get("wit_return"))
      if board is boards[0][1]:
        lessons._energy_reach = None
      page = board.get("page")
      restore_page = lessons.techs_to_next_page
      if page is not None:
        lessons.techs_to_next_page = lambda year, _p=page: _p
      try:
        action, card, _why = lessons.choose(
          [dict(c) for c in board["cards"]], board["energy"],
          turn.get("year") or "", board.get("spend_all", False),
          turn.get("turn"), board.get("points"))
      except Exception as exc:                                  # noqa: BLE001
        misses.append((board["at"], board.get("action"), f"ERROR:{exc}"))
        differed += 1
        continue
      finally:
        lessons.techs_to_next_page = restore_page
      got = (action, card["name"] if card else None)
      was = (board["action"], board.get("chose"))
      if got == was:
        same += 1
      else:
        differed += 1
        misses.append((board["at"], f"{was[0]}:{was[1]}", f"{got[0]}:{got[1]}"))
  finally:
    lessons._songs.clear()
    lessons._songs.update(saved[0])
    lessons._pattern.update(saved[1])
    lessons._energy_cap = saved[2]
    lessons.set_wit_return(saved[3])
    lessons._energy_reach = saved[4]
  return same, differed, skipped, misses


def replay(turns, config, label):
  """Every scored turn's decision under `config`. None means rest."""
  import core.state as state
  import core.logic as logic

  state.load_config = lambda: copy.deepcopy(config)
  state.reload_config()
  state.apply_scenario()
  # A fixture records one career, and the scenario flags are what tell the
  # scorers which bonuses exist. `reload_config` sets them from the config, so
  # they are already right for a career recorded under this one.

  cap = energy_cap(turns)
  out = []
  for turn in turns:
    if not turn.get("stats"):
      continue
    stub_readers(state, logic, turn, cap)
    results = build_results(turn)
    try:
      choice = logic.do_something(results)
    except Exception as e:
      choice = f"ERROR:{type(e).__name__}: {e}"
    out.append((turn, choice))
  return out


def recorded(turn):
  """What the career actually did: a facility, None for rest, "?" if neither.

  A Recreation outing comes back "?" on purpose. `do_something` is not the
  function that chose it - `should_recreate` weighs the outing against
  whatever training this scorer picked, after it has picked one - so the
  scorer cannot be marked right or wrong on that turn. Counting those as
  misses understated fidelity by three turns; counting them as hits would
  credit the scorer with a decision it never made.
  """
  if turn.get("action") == "train":
    return (turn.get("trained") or "").lower() or None
  if turn.get("action") == "rest":
    return None
  return "?"


def gains_of(turn, facility):
  """The stat gains the game printed for this facility, clipped to headroom.

  Clipped because points over a cap do not land, which is the same thing
  `gain_score` does when it scores them.
  """
  if not facility or facility.startswith("ERROR"):
    return {}
  face = (turn.get("facilities") or {}).get(facility) or {}
  head = turn.get("headroom") or {}
  out = {}
  for stat, amount in (face.get("gains") or {}).items():
    if stat not in TRAINING:
      continue
    room = head.get(stat)
    if room is not None:
      amount = min(amount, room)
    if amount > 0:
      out[stat] = amount
  return out


def totals(rows):
  out = {s: 0 for s in TRAINING}
  for turn, choice in rows:
    for stat, amount in gains_of(turn, choice).items():
      out[stat] += amount
  return out


def fidelity(rows):
  """How often the base arm reproduced the career, and the score error."""
  same = diff = unknown = 0
  worst = []
  for turn, choice in rows:
    was = recorded(turn)
    if was == "?":
      unknown += 1
    elif was == choice:
      same += 1
    else:
      diff += 1
      worst.append((turn.get("time"), turn.get("year"), was, choice))
  return same, diff, unknown, worst


def main():
  ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  ap.add_argument("fixture")
  ap.add_argument("--config", default="config.json",
                  help="the config the career was recorded under (default config.json)")
  ap.add_argument("--override", default=None,
                  help="JSON object merged over it for the alt arm")
  ap.add_argument("--show", type=int, default=40,
                  help="how many disagreeing turns to print")
  ap.add_argument("--alt-flag", default=None, metavar="NAME",
                  help="a core.logic module flag naming a rule that is not in"
                       " the config: the base arm replays with it False and the"
                       " alt arm with it True. For backtesting a new rule the"
                       " recorded career ran without.")
  a = ap.parse_args()

  with open(a.fixture, encoding="utf-8") as f:
    fixture = json.load(f)
  turns = fixture["turns"]
  with open(a.config, encoding="utf-8") as f:
    base_config = json.load(f)

  scored = [t for t in turns if t.get("stats")]
  gaps = splits_missing(turns)
  print(f"fixture : {fixture.get('label')}")
  print(f"turns   : {len(turns)} ({len(scored)} scored)")
  print(f"splits  : {gaps} facility record(s) have supports but no per-type split")
  if gaps:
    print("          this career predates the split and cannot replay the scorers")
    return 1
  perf = sum(1 for t in turns if t.get("performance"))
  print(f"perf    : {perf} turn(s) carry Grand Concert Performance data"
        + ("" if perf else "  (performance_bonus replays as 0.0)"))

  # A rule that is not a config value cannot be reached by --override. The base
  # arm must replay the career as it actually ran, which is with any new rule
  # off, or the fidelity figure measures the new rule instead of the replay.
  if a.alt_flag:
    import core.logic as logic
    if not hasattr(logic, a.alt_flag):
      print(f"core.logic has no flag named {a.alt_flag!r}")
      return 1
    setattr(logic, a.alt_flag, False)
    print(f"flag    : core.logic.{a.alt_flag} is False for the base arm,"
          " True for the alt arm")

  base_rows = replay(turns, base_config, "base")
  same, diff, unknown, worst = fidelity(base_rows)
  total = same + diff
  print(f"\n--- fidelity: base arm vs what the career did ---")
  print(f"  reproduced {same}/{total}"
        + (f" ({100.0 * same / total:.1f}%)" if total else "")
        + f", differed {diff}, not comparable {unknown} (outings)")
  for row in worst[:a.show]:
    print(f"    {row[0]}  {row[1]:<28} career={str(row[2]):<5} replay={row[3]}")

  # The Lessons board, if the career recorded one. Separate arm because a visit
  # is not a turn: several boards can be read in one, and the purchase that
  # matters to the training decision is settled before it.
  lsame, ldiff, lskip, lmiss = replay_lessons(turns, base_config, "base")
  if lsame or ldiff or lskip:
    ltotal = lsame + ldiff
    print(f"\n--- fidelity: Lessons boards vs what the career bought ---")
    print(f"  reproduced {lsame}/{ltotal}"
          + (f" ({100.0 * lsame / ltotal:.1f}%)" if ltotal else "")
          + f", differed {ldiff}, not replayable {lskip}"
          + ("  (recorded before `Lessons inputs:`)" if lskip else ""))
    for row in lmiss[:a.show]:
      print(f"    {row[0]}  career={row[1]:<34} replay={row[2]}")

  if not a.override and not a.alt_flag:
    return 0

  alt_config = copy.deepcopy(base_config)
  if a.override:
    alt_config.update(json.loads(a.override))
  if a.alt_flag:
    import core.logic as logic
    setattr(logic, a.alt_flag, True)
  alt_rows = replay(turns, alt_config, "alt")

  what = a.override or ""
  if a.alt_flag:
    what = (what + " " if what else "") + f"core.logic.{a.alt_flag}=True"
  print(f"\n--- alt arm: {what} ---")
  from collections import Counter
  bc = Counter(c or "REST" for _, c in base_rows)
  ac = Counter(c or "REST" for _, c in alt_rows)
  order = ["spd", "sta", "pwr", "guts", "wit", "REST"]
  print("  picks   " + "".join(f"{k:>7}" for k in order))
  print("  base    " + "".join(f"{bc.get(k, 0):>7}" for k in order))
  print("  alt     " + "".join(f"{ac.get(k, 0):>7}" for k in order))

  bt, at = totals(base_rows), totals(alt_rows)
  print("\n  stat points from the chosen facility (printed gains, capped):")
  print("          " + "".join(f"{k:>8}" for k in TRAINING))
  print("  base    " + "".join(f"{bt[k]:>8}" for k in TRAINING))
  print("  alt     " + "".join(f"{at[k]:>8}" for k in TRAINING))
  print("  delta   " + "".join(f"{at[k] - bt[k]:>+8}" for k in TRAINING))

  changed = [(t, b, c) for (t, b), (_, c) in zip(base_rows, alt_rows) if b != c]
  print(f"\n  turns the two arms chose differently: {len(changed)}/{len(base_rows)}")
  for turn, b, c in changed[:a.show]:
    gb, gc = gains_of(turn, b), gains_of(turn, c)
    print(f"    {turn.get('time')}  {str(turn.get('year'))[:26]:<26}"
          f" {str(b or 'REST'):<5} -> {str(c or 'REST'):<5}"
          f"  {str(gb):<34} -> {gc}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
