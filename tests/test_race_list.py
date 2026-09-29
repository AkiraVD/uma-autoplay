"""Reading the Race List's rows off captured frames.

Run with `python tests/test_race_list.py` from the repo root. **Slow**: it
builds the easyocr Reader and then OCRs two strips per row across eight
frames, so give it several minutes before calling it hung.

The frames in `tests/fixtures/race_rows/` are live 1920x1080 captures from one
URA Finale career (2026-09-26):

- `late_aug_0` - the turn's own list, two races, the first one selected. The
  selection draws green brackets around the row and does *not* move its text,
  which is why the strips are measured from the fans icon and not from the card.
- `early_oct_0` / `early_oct_1` - the same list before and after one drag. Four
  races, so the second screen is the bottom and a third drag moves nothing.
- `late_nov_0`..`4` - the one turn in the game where two races are
  indistinguishable: Akamatsu Sho and Begonia Sho are both Tokyo Turf 1600m for
  +1,000 fans, and both are on this list, two rows apart. The scan must find
  both and then refuse to pick either.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

from PIL import Image  # noqa: E402

import core.race_row as R  # noqa: E402

FIXTURES = os.path.join(ROOT, "tests", "fixtures", "race_rows")

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def frame(name):
  return Image.open(os.path.join(FIXTURES, f"{name}.png")).convert("RGB")


def bare(row):
  return (row["track"], row["surface"], row["meters"], row["fans"])


def replay(names):
  """scan_list over a fixed list of frames, as if each drag showed the next.

  The last frame is repeated, which is what the real list does at the bottom -
  and is how the scan knows to stop.
  """
  frames = [frame(n) for n in names]
  state = {"i": 0}
  def grab():
    return frames[min(state["i"], len(frames) - 1)]
  def scroll():
    state["i"] += 1
  return R.scan_list(grab, scroll, lambda: False)


def main():
  print("-- one frame, two rows")
  rows = R.read_rows(frame("late_aug_0"))
  ok("both rows were found", len(rows) == 2, len(rows))
  if len(rows) == 2:
    ok("the selected row reads despite its brackets",
       bare(rows[0]) == ("Niigata", "Turf", 1600, 3100), bare(rows[0]))
    ok("and the plain row below it",
       bare(rows[1]) == ("Sapporo", "Turf", 1500, 1600), bare(rows[1]))
    ok("rows come back top to bottom", rows[0]["anchor"][1] < rows[1]["anchor"][1])

  print("\n-- the metres survive easyocr reading a round 0 as a letter O")
  # These two frames are exactly where `160Om` and `150Om` came from.
  ok("1600 is not 160", rows and rows[0]["meters"] == 1600)
  ok("1500 is not 150", len(rows) > 1 and rows[1]["meters"] == 1500)

  print("\n-- scrolling a four-race list")
  oct_rows = replay(["early_oct_0", "early_oct_1"])
  ok("all four races were read, none twice", len(oct_rows) == 4,
     [bare(r) for r in oct_rows])
  ok("in list order", [bare(r) for r in oct_rows] == [
    ("Tokyo", "Turf", 1600, 3300), ("Kyoto", "Turf", 1400, 1600),
    ("Kyoto", "Turf", 2000, 1000), ("Tokyo", "Dirt", 1600, 1000)],
     [bare(r) for r in oct_rows])
  ok("and each row remembers the screen it was read on",
     [r["step"] for r in oct_rows] == [0, 0, 1, 1],
     [r["step"] for r in oct_rows])

  print("\n-- a race is found by name, through master.mdb")
  for name, expect in (("Saudi Arabia Royal Cup", ("Tokyo", "Turf", 1600, 3300)),
                       ("Momiji Stakes", ("Kyoto", "Turf", 1400, 1600)),
                       ("Shigiku Sho", ("Kyoto", "Turf", 2000, 1000)),
                       ("Platanus Sho", ("Tokyo", "Dirt", 1600, 1000))):
    key = R.key_for(name)
    hit = R.find_row(oct_rows, key, name) if key else None
    ok(f"{name} picks its own row", hit is not None and bare(hit) == expect,
       bare(hit) if hit else "not found")

  print("\n-- Rindo Sho shares Momiji's course and is still not Momiji's row")
  # Same track, surface and distance; +1,000 fans against +1,600. This pair is
  # why the fans number is in the key at all.
  rindo = R.key_for("Rindo Sho")
  ok("Rindo Sho matches nothing on Momiji's list",
     R.find_row(oct_rows, rindo, "Rindo Sho") is None)

  print("\n-- the one ambiguous turn in the game")
  nov_rows = replay([f"late_nov_{n}" for n in range(5)])
  ok("the whole list was read", len(nov_rows) == 8, len(nov_rows))
  twins = [r for r in nov_rows if bare(r) == ("Tokyo", "Turf", 1600, 1000)]
  ok("both Tokyo Turf 1600m +1,000 rows were seen", len(twins) == 2, len(twins))
  ok("they are two different rows, not one row counted twice",
     len(twins) == 2 and twins[0]["step"] != twins[1]["step"],
     [t["step"] for t in twins])
  for name in ("Akamatsu Sho", "Begonia Sho"):
    key = R.key_for(name)
    ok(f"{name} is refused rather than guessed",
       R.find_row(nov_rows, key, name) is None)
  print("   (the refusal is the point: skipping a race costs a turn, entering"
        " the wrong one costs the race)")

  print("\n-- races on that turn that are not ambiguous still resolve")
  for name, expect in (("Tokyo Sports Hai Junior Stakes", ("Tokyo", "Turf", 1800, 3300)),
                       ("Kyoto Junior Stakes", ("Kyoto", "Turf", 2000, 3300)),
                       ("Shiragiku Sho", ("Kyoto", "Turf", 1600, 1000))):
    key = R.key_for(name)
    hit = R.find_row(nov_rows, key, name) if key else None
    ok(f"{name} picks its own row", hit is not None and bare(hit) == expect,
       bare(hit) if hit else "not found")

  print("\n-- where a click would land")
  if rows:
    x, y = R.click_point(rows[0])
    ok("the click point is on the row's banner picture",
       286 <= x <= 435 and 620 <= y <= 695, (x, y))

  print()
  if failures:
    print(f"{len(failures)} FAILED: {failures}")
    return 1
  print("all ok")
  return 0


if __name__ == "__main__":
  sys.exit(main())
