"""Scrolling and scanning a list menu, with the calibration kept per menu.

Every scrollable list in this game is read the same way: rewind to the top,
find the anchor icon that marks a row, read the row, drag down by exactly one
screen, repeat until the picture stops changing. What differs between menus is
not the procedure but the numbers - where it is safe to press, how far a drag
actually travels, how long the list keeps moving after release.

So the procedure lives here once and the numbers live in a calibration dict per
menu. `SKILL_BUY` below is the profile measured on the skill purchase screen;
a new menu gets its own profile rather than new arguments here.

**Screen positions are stored as constant names, not values.** A profile holds
the string "SKILL_SCROLL_UP_FROM_MOUSE_POS" and looks it up on
`utils.constants` at the moment it is used, so a calibration change there
reaches every profile.
"""
import time

import numpy as np
import utils.control as control
from PIL import ImageGrab

import utils.constants as constants
import core.state as state
from core.recognizer import match_template
from utils.log import debug
from utils.tools import sleep

def calibration(name, anchor, list_bbox, scroll_up_from, scroll_down_from,
                default_step, anchor_threshold=0.9,
                hold_before=1.0, travel=1.2, hold_after=0.5, travel_ratio=1.0,
                rewind_settle=1.4, rewind_limit=20,
                min_step=120, max_step=420, passes=24, still=0.5):
  """One menu's numbers. See SKILL_BUY for what each was measured from."""
  return {
    "name": name,
    "anchor": anchor,
    "anchor_threshold": anchor_threshold,
    "list_bbox": list_bbox,
    "scroll_up_from": scroll_up_from,
    "scroll_down_from": scroll_down_from,
    "default_step": default_step,
    "hold_before": hold_before,
    "travel": travel,
    "hold_after": hold_after,
    "travel_ratio": travel_ratio,
    "rewind_settle": rewind_settle,
    "rewind_limit": rewind_limit,
    "min_step": min_step,
    "max_step": max_step,
    "passes": passes,
    "still": still,
  }

# The skill purchase screen, and the only profile calibrated against the real
# game so far. Every number here was measured, not guessed:
#
# - hold_before / travel / hold_after: the list has inertia. A quick flick keeps
#   gliding after the button comes up and anything read during the glide is
#   garbage - names came back as "0 chasers late-race:" and prices as nothing.
#   Holding still at both ends makes the game treat it as a deliberate drag and
#   the list stops dead. Settling time after release measured 3.64s at
#   hold_after 0.0, 0.81s at 0.5 and 0.79s at 1.5, so 0.5 buys all of it.
# - travel_ratio: the list travels slightly less than the pointer. Measured
#   150/157, 239/250 and 299/313 - a constant 0.9556 at every distance. The
#   first value tried was 0.96, and half a percent short on every pass compounds
#   down the list: the overlap grew pass by pass and the last rows arrived late.
# - rewind_settle: the list bounces at the top; the bounce measured 1.25-1.27s.
# - scroll positions: x=400. x=320 does not scroll at all (the skill icon
#   swallows the drag) and x=560 is close enough to Confirm to be a hazard.
#   y=460 and y=860 are symmetric about the middle so an up-drag is not clamped
#   by the bottom of a 1080-high screen - dragging up from y=850 targeted y=1300
#   and travelled 229px instead of 450.
SKILL_BUY = calibration(
  name="skill list",
  anchor="assets/icons/buy_skill.png",
  list_bbox="SKILL_LIST_BBOX",
  scroll_up_from="SKILL_SCROLL_UP_FROM_MOUSE_POS",
  scroll_down_from="SKILL_SCROLL_DOWN_FROM_MOUSE_POS",
  default_step="SKILL_SCROLL_DISTANCE",
  hold_after=0.5,
  travel_ratio=0.9556,
  rewind_settle=1.4,
)

def const(prof, key):
  """Resolve a profile field that names a constant. See the module docstring."""
  value = prof[key]
  return getattr(constants, value) if isinstance(value, str) else value

def slow_drag(prof, x, y_from, y_to):
  """Press, hold, drag slowly, hold again, release."""
  control.moveTo(x, y_from, duration=0.2)
  control.mouseDown()
  time.sleep(prof["hold_before"])
  control.moveTo(x, y_to, duration=prof["travel"])
  time.sleep(prof["hold_after"])
  control.mouseUp()

def scroll(prof, up, distance=None):
  """Drag the list one step. No trailing click - it could hit a real button."""
  x, y = const(prof, "scroll_up_from" if up else "scroll_down_from")
  step = distance or const(prof, "default_step")
  # Ask for more than we want, because the list under-travels.
  step = int(round(step / prof["travel_ratio"]))
  slow_drag(prof, x, y, y + step * (1 if up else -1))

def anchors(prof):
  """Every row anchor on screen, as boxes, top to bottom."""
  found = match_template(prof["anchor"], threshold=prof["anchor_threshold"])
  return sorted(found or [], key=lambda b: b[1])

def anchor_ys(prof):
  """y of every row anchor on screen, near-duplicates collapsed."""
  ys = []
  for x, y, w, h in anchors(prof):
    if not any(abs(y - seen) < 20 for seen in ys):
      ys.append(y)
  return ys

def advance_one_screen(prof):
  """Scroll so the last visible row becomes the first, keeping it in view.

  Guaranteeing an overlap is what stops rows being missed. A fixed step cannot:
  rows are not all the same height, so a step that clears two short rows steps
  over a tall one, and a row that lands under the panel header has its name
  clipped and reads as nothing. Swinging Maestro and Fall Runner were both lost
  that way, and with them Burning Spirit SPD - a scan that saw 23 skills saw 46
  once the step was measured from the rows instead of fixed.

  Dragging by (last anchor y - first anchor y) advances exactly as far as the
  visible rows allow and leaves the last one on screen, so every row is seen at
  least twice at different heights. Duplicates are the caller's problem.
  """
  ys = anchor_ys(prof)
  step = (ys[-1] - ys[0]) if len(ys) >= 2 else const(prof, "default_step")
  step = max(prof["min_step"], min(step, prof["max_step"]))
  scroll(prof, up=False, distance=step)
  return step

def frame(prof):
  """The scrollable region, for telling movement from stillness."""
  return np.asarray(ImageGrab.grab(bbox=const(prof, "list_bbox")).convert("L"),
                    dtype=float)

def still(prof, before, after):
  return float(np.mean(np.abs(after - before))) < prof["still"]

def wait_for_list(prof, limit=3.0, quiet=0.5):
  """Block until the list stops moving.

  Reading during the glide finds anchors at positions the rows have already
  left, so a crop lands on a neighbouring row. The old drag ended with a stray
  click, which happened to give the list time to settle; removing that click -
  it could press Confirm - took the accidental wait away with it, so the wait
  is now explicit.
  """
  deadline = time.time() + limit
  previous = frame(prof)
  while time.time() < deadline:
    time.sleep(quiet / 2)
    now = frame(prof)
    if still(prof, previous, now):
      return
    previous = now

def scroll_to_top(prof):
  """Rewind until the picture stops changing.

  Counting drags does not work - the list is longer than any fixed count, and a
  scan that starts halfway down silently covers the wrong rows.
  """
  previous = None
  for step in range(prof["rewind_limit"]):
    if state.stop_event.is_set():
      return
    now = frame(prof)
    if previous is not None and still(prof, previous, now):
      debug(f"{prof['name'].capitalize()} rewound to the top after {step} drags.")
      time.sleep(prof["rewind_settle"])
      return
    previous = now
    scroll(prof, up=True)
  debug(f"{prof['name'].capitalize()} still moving after {prof['rewind_limit']}"
        " drags; scanning from here.")

def rows(prof, passes=None):
  """Walk the list top to bottom, yielding one anchor box per row per pass.

  Reads only - nothing is clicked. Scrolling changes every box, so a caller
  that wants to click has to scan again and match on what it read rather than
  reuse a position from an earlier pass.

  **Rewinds first.** Scanning only ever scrolls down, so a second scan would
  start where the first left the list - at the bottom - and walk further down
  over rows it had already passed. The skill planner scans twice, once to
  decide and once to buy, and without this the buying pass never saw the rows
  the plan had chosen: a career planned 8 skills and bought none of them.

  **Stops at the bottom, not after a fixed count.** Ten passes did not reach
  the end of a real skill list, so the last rows were never offered.
  """
  passes = passes or prof["passes"]
  scroll_to_top(prof)
  for i in range(passes):
    if state.stop_event.is_set():
      return
    if i > 8:
      sleep(0.5)
    found = anchors(prof)
    for box in found:
      yield box
    debug(f"{prof['name'].capitalize()} scan pass {i + 1}/{passes},"
          f" {len(found)} row(s) on screen.")
    before = frame(prof)
    advance_one_screen(prof)
    # Let the list settle before deciding whether it moved. At the bottom the
    # drag over-scrolls and the list springs back, so a frame grabbed straight
    # after release differs from the one before it even though the list ends up
    # exactly where it started. Measured on a 10-row list: the region is
    # perfectly static when idle (diff 0.000 over 5s), yet comparing before the
    # bounce settled gave 25-42 every time, the bottom was never detected, and
    # the scan burned all 24 passes re-reading the last two rows.
    wait_for_list(prof)
    if still(prof, before, frame(prof)):
      debug(f"Reached the bottom of the {prof['name']} after {i + 1} passes.")
      return
