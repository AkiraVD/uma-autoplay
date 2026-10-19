"""Did the trainee win the race that just ran?

There is no text to read here. The game answers the question with a picture:
the trainee's own result banner is a gold "1st" under a crown, wrapped in a
full laurel wreath, drawn over her portrait in the middle of the window. Every
other placing is drawn in the same slot in bronze, under no crown and inside a
thinner wreath - so the banner is *counted* rather than matched, and what is
counted is saturated gold.

Counting beats a template here, for two reasons measured off 134 captured
post-race frames:

- **The banner is animated.** It slides in from the left, scales up, settles,
  then slides out again, so one fixed-scale template has to be loose enough to
  catch it part-drawn - and that is loose enough to catch other things.
- **A gold "1st" on screen is not our 1st.** The race broadcast puts a small
  "WIN 1st" pennant and a blue name plate over whoever won, which is usually
  somebody else: the captured frames of it name Taiki Shuttle on a race the
  trainee ran 8th. That pennant sits at the left edge, which is why
  RACE_PLACEMENT_REGION is centred instead of covering the game screen.

Over all 134 frames the worst own win reads 12,904 gold pixels and the best
non-win reads 3,681 - the 3rd-place banner, the closest thing to gold that is
not a win. WIN_GOLD_PIXELS sits in that gap. `tests/test_placement.py` holds
both ends of it, the broadcast pennant among the negatives.

**Not verified against a live race.** Every frame behind these numbers was
saved by the `after_race_no_next` fallback, which is the one path that writes
a frame to disk; the normal path has never been captured. The numbers are what
they are, but whether `watch()` is looking at the right moment can only be
settled by running a career.
"""

import time

import numpy as np

from core import state
from utils import constants
from utils.log import debug
from utils.screenshot import capture_region
from utils.tools import sleep

# The banner's fill. Red is pinned high and blue low, which is what separates
# gold from the bronze of every other placing; the green band is what separates
# it from skin, hair and the orange of the track.
GOLD_MIN_RED = 200
GOLD_GREEN_MIN = 140
GOLD_GREEN_MAX = 215
GOLD_MAX_BLUE = 110
# Worst own win 12,904, best non-win 3,681. Halfway is 8,000.
WIN_GOLD_PIXELS = 8000


def gold_pixels(image=None):
  """How much saturated gold is in the placement window right now."""
  if image is None:
    image = capture_region(constants.RACE_PLACEMENT_REGION)
  pixels = np.asarray(image.convert("RGB")).astype(int)
  red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
  return int(((red > GOLD_MIN_RED)
              & (green > GOLD_GREEN_MIN)
              & (green < GOLD_GREEN_MAX)
              & (blue < GOLD_MAX_BLUE)).sum())


def won(image=None):
  """True when the banner on screen is the trainee's own 1st place."""
  return gold_pixels(image) >= WIN_GOLD_PIXELS


def watch(seconds=3.0, interval=0.4):
  """Watch for an own-win banner while the result screen is up.

  One grab can miss it: the banner takes about a second to slide in, and the
  caller arrives as soon as View Results is found rather than when the drawing
  has settled. So this samples until it sees a win or runs out of time.

  A miss is reported as "not a win", never as "unknown". The only thing that
  reads this is the reroll gate, and the safe way to be wrong there is to call
  the career not-undefeated and keep the 30 TP.
  """
  deadline = time.time() + seconds
  best = 0
  while time.time() < deadline:
    if state.stop_event.is_set():
      return False
    count = gold_pixels()
    best = max(best, count)
    if count >= WIN_GOLD_PIXELS:
      debug(f"Placement banner: 1st ({count} gold px).")
      return True
    sleep(interval)
  debug(f"Placement banner: not a win (best {best} gold px of"
        f" {WIN_GOLD_PIXELS} needed).")
  return False
