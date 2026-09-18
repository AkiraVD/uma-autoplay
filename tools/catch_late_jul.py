"""Capture the turn box on the turns where the counter is known to misread.

`Late Jul` reads `1` where the truth is `11`, in every year of every career
measured so far - six times across two careers on 2026-09-18. But
`read_turn_digits` reads both `11` fixtures in `tests/fixtures/turn/` correctly,
and the whole suite passes, so the bug is *not* reproducible from anything
recorded. The live frame must differ from every fixture we hold.

This waits for a career to reach one of those turns and saves the exact crop
`read_turn_digits` would have been given, plus the full frame for context, so
the failure can be reproduced offline instead of guessed at.

  python tools/catch_late_jul.py                     # default: Late Jul, any year
  python tools/catch_late_jul.py --match "Late Dec"  # the -1 turns instead

Run it with DISPLAY pointing at the game (`DISPLAY=:1` under run_background.sh).
It watches the log rather than the screen, because the year string is what says
which turn this is, and the bot has already OCR'd it.

Each hit writes three files into tests/fixtures/turn/candidates/:
  <tag>_digits.png   the TURN_DIGITS_REGION crop - the reader's actual input
  <tag>_box.png      the wider TURN_REGION, what the OCR fallback sees
  <tag>_frame.png    the whole screen, for context
and prints what read_turn_digits makes of the crop next to what the bot logged,
so a disagreement is visible immediately.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

import utils.constants as constants  # noqa: E402

OUT = os.path.join("tests", "fixtures", "turn", "candidates")
LOG = os.path.join("logs", "log.txt")


def tail_years(path, start_line):
  """Year/Turn pairs written after start_line, oldest first."""
  pairs, year = [], None
  try:
    with open(path, encoding="utf-8", errors="ignore") as handle:
      for i, line in enumerate(handle):
        if i < start_line:
          continue
        if " INFO    Year: " in line:
          year = line.split("Year: ", 1)[1].strip()
        elif " INFO    Turn: " in line and year is not None:
          pairs.append((line[:8], year, line.split("Turn: ", 1)[1].strip()))
          year = None
  except FileNotFoundError:
    pass
  return pairs


def grab(tag):
  """Save the two regions the two readers use, plus the whole frame."""
  import core.state as state          # imported late: builds the easyocr Reader
  from utils.screenshot import capture_region

  os.makedirs(OUT, exist_ok=True)
  digits = capture_region(constants.TURN_DIGITS_REGION)
  box = capture_region(constants.TURN_REGION)
  digits.save(os.path.join(OUT, f"{tag}_digits.png"))
  box.save(os.path.join(OUT, f"{tag}_box.png"))
  try:
    import mss
    import numpy as np
    with mss.mss() as sct:
      shot = np.array(sct.grab({"left": 0, "top": 0, "width": 1920, "height": 1080}))
      Image.fromarray(shot[:, :, :3][:, :, ::-1]).save(os.path.join(OUT, f"{tag}_frame.png"))
  except Exception as e:                                  # frame is a nicety
    print(f"    (full frame not saved: {e})")
  return state.read_turn_digits(crop=digits)


def main():
  ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  ap.add_argument("--match", default="Late Jul",
                  help="year-string fragment to catch (default: Late Jul)")
  ap.add_argument("--minutes", type=int, default=180, help="give up after this long")
  a = ap.parse_args()

  with open(LOG, encoding="utf-8", errors="ignore") as handle:
    start = sum(1 for _ in handle)
  print(f"watching {LOG} from line {start} for a year containing {a.match!r}")

  seen = set()
  deadline = time.time() + a.minutes * 60
  while time.time() < deadline:
    for stamp, year, turn in tail_years(LOG, start):
      if a.match not in year or stamp in seen:
        continue
      seen.add(stamp)
      tag = f"{year.replace(' ', '_')}_{stamp.replace(':', '')}"
      print(f"\n{stamp}  {year}  bot logged Turn: {turn}")
      got = grab(tag)
      print(f"    read_turn_digits on the saved crop -> {got}")
      if str(got) != turn:
        print(f"    *** DISAGREES with the log ({turn}) - the live frame is the bug ***")
      else:
        print("    matches the log; if the log is wrong, the crop reproduces it")
      print(f"    saved {tag}_digits.png / _box.png / _frame.png in {OUT}")
    time.sleep(20)
  print("gave up waiting")
  return 0


if __name__ == "__main__":
  sys.exit(main())
