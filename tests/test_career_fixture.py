"""The recorded careers in tests/fixtures/careers/.

Run with `python tests/test_career_fixture.py` from the repo root. Pure JSON -
no OCR, no stubbing - so it is fast.

They exist so a change to the scorers can be replayed against a real career
instead of a hand-built board. `logs/` is gitignored and `utils/log.py` keeps
only ten 1 MB backups, so a career's evidence is gone after about ten more
runs; a long career also rotates *mid-run*, which is how the 2026-09-18 career
ended up with its own first two hours in `log.txt.1`. Regenerate with
`tools/career_extract.py`.

Most of what follows guards against the extractor lying quietly, which it did
twice while being written - and both times the output looked entirely healthy:

  - it recorded the energy *after* each turn acted, because a turn logs energy
    several times and the last reading belongs to the next turn;
  - it recorded no decision at all for Junior year, because
    focus_max_friendships logs no selection and do_rest logs nothing whatsoever.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CAREERS = sorted(glob.glob(os.path.join("tests", "fixtures", "careers", "*.json")))
LIVE = os.path.join("tests", "fixtures", "careers", "trackblazer_20260918.json")
failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def load(path):
  with open(path, encoding="utf-8") as handle:
    return json.load(handle)


def test_there_is_something_to_replay():
  ok("at least one recorded career", len(CAREERS) >= 1, f"{len(CAREERS)} found")


def test_every_fixture_is_structurally_sound():
  for path in CAREERS:
    name = os.path.basename(path)
    data = load(path)
    turns = data.get("turns") or []
    ok(f"{name}: has turns", len(turns) > 0, len(turns))
    ok(f"{name}: records the logs it came from",
       bool((data.get("source") or {}).get("logs")))
    scored = [t for t in turns if t.get("facilities")]
    ok(f"{name}: has scored boards", len(scored) > 0, len(scored))
    # levels/gains are Python dict literals in the log; a parse failure stores
    # None, which would read as "no supports" rather than as an error.
    bad = [(t["time"], key) for t in scored for key, face in t["facilities"].items()
           if not isinstance(face.get("levels"), dict)
           or not isinstance(face.get("gains"), dict)]
    ok(f"{name}: every board parsed its levels and gains", not bad, bad[:4])


def test_each_fixture_holds_exactly_one_career():
  """A fixture spanning two careers passes every other check in this file.

  `--since` used to run to the end of the log, so extracting from a file that
  held several careers produced one fixture containing all of them: 195 turns,
  Junior passed three times, every per-turn check green. Two such files were
  built and deleted on 2026-09-19 before the extractor learned to stop at the
  next `[BOT] Starting`.

  **Time is the invariant, not turn counts.** The first version of this check
  counted rows per era and failed anything over 26, on the reasoning that a year
  holds 24 dated turns. That was wrong twice over: it condemned two perfectly
  clean Grand Concert careers, because that scenario re-reads the lobby after
  each concert screen and legitimately logs the same date twice 30-70 seconds
  apart; and it would have passed real contamination that happened to stay under
  the threshold. Duplicate dates are not evidence of anything on their own.

  A career runs forward in time. Two careers spliced together show a backwards
  jump at the seam - the second run's clock starts over - and that holds
  whatever the scenario, the turn count or the calendar.

  **The log carries no date**, only `HH:MM:SS`, so a career that crosses
  midnight wraps: `trackblazer_20260918.json` runs 23:57:17 -> 01:40:52 and its
  first step is 23:57:17 -> 00:02:43. Comparing the strings calls that a
  backwards jump. Simply allowing one jump would gut the check, because a
  spliced file also shows exactly one (10:57:16 -> 02:02:42 when two real
  careers are joined). So a wrap is *carried* - a day is added and the run must
  stay forward afterwards - which separates five minutes over midnight from
  nine hours backwards.
  """
  def seconds(stamp):
    h, m, s = (int(p) for p in stamp.split(":"))
    return h * 3600 + m * 60 + s

  for path in CAREERS:
    name = os.path.basename(path)
    turns = load(path)["turns"]
    stamps = [t["time"] for t in turns if t.get("time")]
    day, wraps = 0, 0
    for previous, current in zip(stamps, stamps[1:]):
      if seconds(current) < seconds(previous):
        day += 86400
        wraps += 1
    # A career is a couple of hours, so it can cross midnight at most once.
    # More than one wrap means the clock restarted, which is a splice.
    ok(f"{name}: crosses midnight at most once", wraps <= 1, f"{wraps} wraps")
    # With the wrap carried, the whole run must span less than a day: two
    # careers joined span the gap between them, which is far longer.
    if stamps:
      total = seconds(stamps[-1]) + (86400 if wraps else 0) - seconds(stamps[0])
      ok(f"{name}: spans one sitting, not two", 0 < total < 6 * 3600,
         f"{total // 3600}h{(total % 3600) // 60:02d}m")


def test_every_scored_turn_carries_a_decision():
  """A turn that read a board and then did nothing is a hole, not a rest.

  Junior is the case that caught this: it goes through focus_max_friendships,
  which logs no selection line, so the whole year recorded `action: None` while
  the fixture still looked full.
  """
  for path in CAREERS:
    name = os.path.basename(path)
    scored = [t for t in load(path)["turns"] if t.get("facilities")]
    missing = [t["time"] for t in scored if not t.get("action")]
    ok(f"{name}: no scored turn without an action", not missing, missing[:5])
    trained = [t for t in scored if t.get("action") == "train"]
    ok(f"{name}: every train names its facility",
       all(t.get("trained") for t in trained), f"{len(trained)} trains")


def test_energy_is_the_reading_the_decision_was_made_on():
  """Pinned to the live rescue turn.

  The choice was made at 38.98 and WIT then refunded the tank to 44.07.
  Recording the second figure would make every energy-gated turn in the
  fixture unreplayable, while looking perfectly plausible.
  """
  if not os.path.exists(LIVE):
    ok("the 2026-09-18 career is present", False, "missing")
    return
  turns = load(LIVE)["turns"]
  rescue = [t for t in turns if "resting this late" in (t.get("decided_by") or "")]
  ok("the last-turn rescue is captured", len(rescue) == 1, len(rescue))
  if not rescue:
    return
  turn = rescue[0]
  ok("energy is the pre-decision reading", turn.get("energy") == 38.98, turn.get("energy"))
  ok("and the post-action reading is kept apart",
     turn.get("energy_after") == 44.07, turn.get("energy_after"))
  ok("it trained rather than rested",
     turn.get("action") == "train" and turn.get("trained") == "wit",
     f"{turn.get('action')}/{turn.get('trained')}")
  others = {k: f["failure"] for k, f in turn["facilities"].items() if k != "wit"}
  ok("on a board where everything but WIT was over the failure bar",
     all(v > 15 for v in others.values()), others)


def test_the_split_is_carried_where_the_career_is_new_enough():
  """Careers recorded from 2026-09-18 11:42 on must carry the per-type split.

  `Levels:` is an aggregate over six card types, so on its own it cannot say
  how many of a facility's cards are its OWN type - which is what a rainbow is,
  and what `rainbow_training` and `training_score` both read. Without the split
  those two scorers cannot be replayed at all.

  This is pinned because a regression would be silent: drop the clause and
  every other check in this file still passes, exactly as they did before the
  split existed.
  """
  newer = os.path.join("tests", "fixtures", "careers", "trackblazer_20260918b.json")
  if not os.path.exists(newer):
    ok("the split-bearing career is present", False, "missing")
    return
  scored = [t for t in load(newer)["turns"] if t.get("facilities")]
  missing = [t["time"] for t in scored
             if not any("split" in f for f in t["facilities"].values())]
  ok("every scored turn carries a split", not missing, missing[:5])

  # A split must never contradict the aggregate it was taken from: summing the
  # per-type buckets has to reproduce total_friendship_levels exactly.
  bad = []
  for turn in scored:
    for key, face in turn["facilities"].items():
      split = face.get("split") or {}
      if not split:
        continue
      for level in ("gray", "blue", "green", "yellow", "max"):
        summed = sum(b.get(level, 0) for b in split.values())
        if summed != (face["levels"] or {}).get(level, 0):
          bad.append((turn["time"], key, level, summed, face["levels"].get(level)))
  ok("and the split sums back to the aggregate", not bad, bad[:3])

  # The whole point: at least one turn where an own-type rainbow is recoverable
  # and the aggregate alone could not have told you.
  demo = [(t["time"], k) for t in scored for k, f in t["facilities"].items()
          if (f.get("split") or {}).get(k, {}).get("yellow")
          or (f.get("split") or {}).get(k, {}).get("max")]
  ok("and own-type rainbows are recoverable", demo, f"{len(demo)} such facilities")


def test_the_career_covers_the_whole_run():
  """Junior through the Climax, so a replay is not quietly missing a year."""
  if not os.path.exists(LIVE):
    return
  turns = load(LIVE)["turns"]
  years = {(t.get("year") or "").split(" Year")[0] for t in turns if t.get("year")}
  for era in ("Junior", "Classic", "Senior"):
    ok(f"covers {era}", era in years, sorted(years))
  ok("and reaches the Climax",
     any("Climax" in (t.get("year") or "") for t in turns))


for test in [test_there_is_something_to_replay,
             test_every_fixture_is_structurally_sound,
             test_each_fixture_holds_exactly_one_career,
             test_every_scored_turn_carries_a_decision,
             test_energy_is_the_reading_the_decision_was_made_on,
             test_the_split_is_carried_where_the_career_is_new_enough,
             test_the_career_covers_the_whole_run]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
