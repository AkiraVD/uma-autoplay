"""The Lessons board in a recorded career, and replaying it.

Run with `python tests/test_lessons_replay.py` from the repo root. Slow to
start: tools/career_replay imports core.state, which builds the easyocr Reader.

The board was always logged card by card - lessons.describe writes the kind,
name, effects, lock state and cost row - but three of choose()'s inputs were
not: the energy at the visit, the bar's cap, and the per-segment song counts
that hype_songs_needed reads. Without them a Lessons decision could not be
scored against what the career actually saw, so `Lessons inputs:` was added on
2026-10-13 and this pins the whole round trip: log lines in, fixture out,
`choose` replayed, decision matched.
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

failures = []


def ok(label, cond, detail=""):
  print(("ok   " if cond else "FAIL ") + label + (f"   [{detail}]" if detail else ""))
  if not cond:
    failures.append(label)


# One visit, exactly as a career logs it. The decision is the one the current
# rule gives: 60 + 30 + 0 = 90 against a 105 bar, so it fits and is bought.
LOG = """\
07:00:00 INFO    Year: Classic Year Early Apr
07:00:01 DEBUG   Turn: 30
07:00:02 DEBUG   Remaining energy guestimate = 60.0
07:00:03 DEBUG   Current stats: {'spd': 500, 'sta': 400, 'pwr': 400, 'guts': 300, 'wit': 300}
07:00:04 DEBUG   Lesson card 1: technique 'Relaxing Body Massage' [Energy +30] (learnable) 20/0/0/0/0
07:00:04 DEBUG   Lesson card 2: technique 'Dance Step Advanced' [Speed +12] (locked) 0/0/0/30/0
07:00:04 DEBUG   Lesson card 3: technique "Watch an Idol's Concert" [Skill Pts +8] (locked) 0/0/0/0/16
07:00:05 DEBUG   Performance points {'da': 54, 'pa': 27, 'vo': 30, 'vi': 1, 'co': 12}, reserve {'da': 21, 'pa': 0, 'vo': 0, 'vi': 21, 'co': 0}, 2 technique(s) to the next song page.
07:00:06 DEBUG   Lessons inputs: energy 60.0/105.0, wit returns 0, segment 1, songs 4 {0: 2, 1: 2}, page 2, spend_all False.
07:00:07 INFO    Learning technique 'Relaxing Body Massage': energy first.
"""


def extract_fixture(tmpdir):
  import career_extract as E
  log = os.path.join(tmpdir, "log.txt")
  with open(log, "w", encoding="utf-8") as handle:
    handle.write(LOG)
  turns = E.extract([log])
  # The finalisation that main() does: drop half-recorded visits.
  for turn in turns:
    turn.pop("_board", None)
    boards = [b for b in (turn.get("lessons") or []) if b.get("action")]
    if boards:
      turn["lessons"] = boards
    else:
      turn.pop("lessons", None)
  return {"label": "synthetic", "source": {}, "turns": turns}


def main():
  with tempfile.TemporaryDirectory() as tmpdir:
    fixture = extract_fixture(tmpdir)

  turns = fixture["turns"]
  boards = [b for t in turns for b in (t.get("lessons") or [])]
  ok("the visit is extracted", len(boards) == 1, f"{len(boards)} board(s)")
  if not boards:
    print("\nFAILED: nothing to check")
    return 1
  board = boards[0]

  ok("all three cards are read", len(board["cards"]) == 3, str(len(board["cards"])))
  ok("the Energy card keeps its effect line",
     board["cards"][0]["effects"] == ["Energy +30"], str(board["cards"][0]["effects"]))
  ok("...and is the learnable one",
     board["cards"][0]["learnable"] and not board["cards"][1]["learnable"])
  ok("a name holding an apostrophe survives the repr quoting",
     board["cards"][2]["name"] == "Watch an Idol's Concert", board["cards"][2]["name"])
  ok("the cost row maps onto POINT_KEYS order",
     board["cards"][0]["cost"] == {"da": 20, "pa": 0, "vo": 0, "vi": 0, "co": 0},
     str(board["cards"][0]["cost"]))
  ok("the Performance totals come through", board["points"]["da"] == 54, str(board["points"]))
  ok("and the inputs choose() needs: energy", board["energy"] == 60.0, str(board["energy"]))
  ok("...the bar's cap", board["cap"] == 105.0, str(board["cap"]))
  ok("...the wit return", board["wit_return"] == 0.0, str(board["wit_return"]))
  ok("...the per-segment song counts", board["songs_by_segment"] == {0: 2, 1: 2},
     str(board["songs_by_segment"]))
  ok("...and the page countdown", board["page"] == 2, str(board["page"]))
  ok("the decision is recorded", (board["action"], board["chose"]) == ("learn", "Relaxing Body Massage"),
     f"{board['action']}:{board['chose']}")

  # --- and now replay it ------------------------------------------------------
  import career_replay as R
  with open("config.json", encoding="utf-8") as handle:
    config = json.load(handle)
  same, differed, skipped, misses = R.replay_lessons(turns, config, "base")
  ok("the recorded visit is replayable", skipped == 0, f"{skipped} skipped")
  ok("and the replay reproduces what the career bought", same == 1 and differed == 0,
     f"same={same} differed={differed} {misses}")

  # A board logged before `Lessons inputs:` cannot be replayed, and must be
  # reported as such rather than counted as a miss.
  stripped = json.loads(json.dumps(turns))
  for turn in stripped:
    for b in turn.get("lessons") or []:
      b.pop("songs_by_segment", None)
  same2, differed2, skipped2, _ = R.replay_lessons(stripped, config, "base")
  ok("an old board is skipped, not counted wrong",
     skipped2 == 1 and same2 == 0 and differed2 == 0,
     f"same={same2} differed={differed2} skipped={skipped2}")

  print()
  if failures:
    print(f"{len(failures)} check(s) failed:")
    for label in failures:
      print("  - " + label)
    return 1
  print("all checks passed")
  return 0


if __name__ == "__main__":
  sys.exit(main())
