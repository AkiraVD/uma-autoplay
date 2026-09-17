"""Where an event's options sit, and what happens when the configured option
is higher than the number on screen.

Run with `python tests/test_event_choice_geometry.py` from the repo root. It
imports core.execute, which builds the easyocr Reader, so it starts slowly.

Event choices are bottom-anchored: the last one always sits at
constants.LAST_EVENT_CHOICE_ICON_TOP, so the first moves up one 112px row per
extra option. Anchors seen in the logs: 736 (1 option), 624 (2), 513 (3),
290 (5).

"Closer Together" opens with a one-option prompt before its five lyric lines.
With grand_concert.lyrics_option = 2 the bot clicked 848 - one row below the
only option - so nothing was pressed and the event re-prompted. That pattern
("anchor 736 -> clicked 848") appears eight times across the career logs.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.execute as E          # noqa: E402
import utils.constants as C       # noqa: E402

LAST = C.LAST_EVENT_CHOICE_ICON_TOP

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def test_option_count_from_the_anchor():
  for anchor, expected in ((736, 1), (624, 2), (513, 3), (401, 4), (290, 5)):
    ok(f"anchor {anchor} means {expected} option(s)", E.option_count(anchor) == expected,
       str(E.option_count(anchor)))

def test_the_last_option_is_always_bottom_anchored():
  for anchor in (736, 624, 513, 401, 290):
    count = E.option_count(anchor)
    _, y, _, _ = E.choice_point((272, anchor, 41, 41), count)
    ok(f"anchor {anchor}: option {count} lands on the bottom row", abs(y - LAST) <= 2, y)

def test_a_five_option_list_picks_each_row():
  for chosen, expected in ((1, 290), (2, 402), (3, 514), (4, 626), (5, 738)):
    x, y, count, picked = E.choice_point((272, 290, 41, 41), chosen)
    ok(f"five options: line {chosen} clicks y={expected}", y == expected and picked == chosen,
       f"y={y} picked={picked} count={count}")

def test_too_high_a_choice_is_clamped():
  x, y, count, picked = E.choice_point((272, 736, 41, 41), 2)
  ok("lyrics_option 2 on a one-option prompt stays on that option", y == 736 and picked == 1,
     f"y={y} picked={picked} count={count}")
  ok("and no longer clicks 848, which pressed nothing", y != 848, y)
  # The measured anchors are a pixel off a perfect 112px grid (513, not 512),
  # so the bottom row lands within a pixel or two of LAST rather than exactly.
  _, y3, _, picked3 = E.choice_point((272, 513, 41, 41), 5)
  ok("line 5 on a three-option prompt takes the last one", abs(y3 - LAST) <= 2 and picked3 == 3,
     f"y={y3} picked={picked3}")

def test_a_low_choice_is_left_alone():
  _, y, _, picked = E.choice_point((272, 624, 41, 41), 1)
  ok("the top option of a two-option prompt is unchanged", y == 624 and picked == 1, y)

if __name__ == "__main__":
  test_option_count_from_the_anchor()
  test_the_last_option_is_always_bottom_anchored()
  test_a_five_option_list_picks_each_row()
  test_too_high_a_choice_is_clamped()
  test_a_low_choice_is_left_alone()
  if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
  print("\nall ok")
