"""The calendar box's turns-left number, read glyph by glyph.

Run with `python tests/test_turn_digits.py` from the repo root. Builds an
easyocr Reader for the wide digits, so it is slow to start.

Fixtures in tests/fixtures/turn/ are TURN_DIGITS_REGION crops named after what
they show: "11_purple.png" is 11 turns left in Grand Concert's purple box,
"_blue" is the URA/Unity box. The one that started this is 11_purple: read as a
whole number, easyocr returned "17". goal_purple is a race day, where the box
says GOAL and the reader must return None rather than a number, and
none_career_complete has no calendar at all.
"""
import glob
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.state as S  # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

for path in sorted(glob.glob(os.path.join("tests", "fixtures", "turn", "*.png"))):
  name = os.path.splitext(os.path.basename(path))[0]
  got = S.read_turn_digits(crop=Image.open(path))
  want = None if name.startswith(("goal", "none")) else int(name.split("_")[0])
  ok(f"{name} reads {want}", got == want, got)

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
