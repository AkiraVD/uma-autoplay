"""Keeping shots/ from growing without bound.

Run with `python tests/test_shots.py` from the repo root. No OCR, so it is fast.

`umatool click` saves a frame on every press and `health` one on every check,
including every `/health` sent from a phone. Left alone they reached 1,062
files and about a gigabyte. They are also the least valuable frames in there -
each one is a moment already gone, and only the last few ever get looked at.

What this pins is mostly what prune must *not* touch: the hand-named frames
under shots/gl/ are cited by name from docs/screen-map.md and were the source
of two templates this week, so a tidy-up that reached them would be a bad
trade for a few megabytes.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import shots                                   # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def populate(d, n=50):
  """n stamped captures, oldest first by mtime, plus things that must survive."""
  for i in range(n):
    path = os.path.join(d, f"click_{i:06d}.png")
    open(path, "w").write("x")
    os.utime(path, (i, i))
  for name in ("click_notes.png", "shot_123456.png", "health_000001.png"):
    open(os.path.join(d, name), "w").write("x")
  os.mkdir(os.path.join(d, "gl"))
  open(os.path.join(d, "gl", "click_000001.png"), "w").write("x")

def test_it_keeps_the_newest_and_drops_the_rest():
  with tempfile.TemporaryDirectory() as d:
    populate(d)
    removed = shots.prune(d, "click_")
    stamped = sorted(f for f in os.listdir(d)
                     if f.startswith("click_") and f != "click_notes.png")
    ok("the oldest go", removed == 50 - shots.KEEP, str(removed))
    ok("and the newest stay", len(stamped) == shots.KEEP, str(len(stamped)))
    ok("it is the *newest* that stay, by mtime",
       stamped[0] == f"click_{50 - shots.KEEP:06d}.png", stamped[0])
    ok("running it again changes nothing", shots.prune(d, "click_") == 0)

def test_it_touches_nothing_else():
  """The expensive mistake would be reaching a frame somebody named by hand."""
  with tempfile.TemporaryDirectory() as d:
    populate(d)
    shots.prune(d, "click_")
    ok("a hand-named frame survives",
       os.path.exists(os.path.join(d, "click_notes.png")))
    ok("another prefix survives",
       os.path.exists(os.path.join(d, "shot_123456.png")))
    ok("the other automated prefix survives too",
       os.path.exists(os.path.join(d, "health_000001.png")))
    # shots/gl/ is where c6_deck.png and c7_borrow2.png came from.
    ok("and a subdirectory is never walked into",
       os.path.exists(os.path.join(d, "gl", "click_000001.png")))

def test_it_never_raises():
  """It runs after a capture is already saved: failing to tidy up must not fail
  the capture, the health check, or the click that prompted it."""
  ok("a missing directory is survivable", shots.prune("/no/such/dir", "click_") == 0)
  with tempfile.TemporaryDirectory() as d:
    ok("an empty directory is survivable", shots.prune(d, "click_") == 0)
    ok("a prefix with nothing under it is survivable",
       shots.prune(d, "nothing_") == 0)

def test_both_writers_call_it():
  health = open(os.path.join("tools", "health.py"), encoding="utf-8").read()
  ok("health prunes after saving its frame",
     health.index('img.save(path)') < health.index('shots.prune(SHOTS, "health_")'))
  umatool = open(os.path.join("tools", "umatool.py"), encoding="utf-8").read()
  ok("umatool prunes after a click's capture",
     'shots.prune(SHOTS, "click_")' in umatool)
  ok("and the cap is a number a session can work with",
     isinstance(shots.KEEP, int) and 10 <= shots.KEEP <= 200, str(shots.KEEP))

if __name__ == "__main__":
  test_it_keeps_the_newest_and_drops_the_rest()
  test_it_touches_nothing_else()
  test_it_never_raises()
  test_both_writers_call_it()
  print()
  if failures:
    print(f"{len(failures)} failed: " + ", ".join(failures))
    sys.exit(1)
  print("all ok")
