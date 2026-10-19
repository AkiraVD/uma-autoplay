"""The post-race banner that says whether the trainee won.

Run with `python tests/test_placement.py` from the repo root. No OCR and no
stub: core/placement.py counts pixels, so this is the real module against real
frames.

Every fixture is a frame the bot itself saved, cropped to
`constants.RACE_PLACEMENT_REGION` (the two `full_*` ones are whole screens, so
the region constant is covered too and not just the counter).

What the negatives are for is the trap that shaped the module: the race
broadcast draws its own gold "1st" over whoever won the race, and the winner is
usually not the trainee. `loss_broadcast_win_other_213654.png` is that screen -
a gold 1st naming Taiki Shuttle, on a race the trainee ran 8th - and it has to
read as a loss. The rest are the ordinary 3rd/4th/5th/6th banners.

Measured over all 134 captured frames when this was written: worst win 12,904
gold pixels, best non-win 3,681.
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

from PIL import Image

from core import placement
from utils import constants

FIXTURES = os.path.join(ROOT, "tests", "fixtures", "placement")

failures = []

def ok(label, cond):
  print(f"{'ok  ' if cond else 'FAIL'} {label}")
  if not cond:
    failures.append(label)

def region_of(path):
  """A full frame cropped the way capture_region would grab it."""
  left, top, width, height = constants.RACE_PLACEMENT_REGION
  return Image.open(path).convert("RGB").crop(
    (left, top, left + width, top + height))

def main():
  wins = sorted(glob.glob(os.path.join(FIXTURES, "win_*.png")))
  losses = sorted(glob.glob(os.path.join(FIXTURES, "loss_*.png")))
  ok("fixtures are present", bool(wins) and bool(losses))

  win_counts = {}
  for path in wins:
    name = os.path.basename(path)
    count = placement.gold_pixels(Image.open(path).convert("RGB"))
    win_counts[name] = count
    ok(f"{name} reads as a win ({count} gold px)",
       placement.won(Image.open(path).convert("RGB")))

  loss_counts = {}
  for path in losses:
    name = os.path.basename(path)
    count = placement.gold_pixels(Image.open(path).convert("RGB"))
    loss_counts[name] = count
    ok(f"{name} reads as a loss ({count} gold px)",
       not placement.won(Image.open(path).convert("RGB")))

  # The gap is the whole claim. A threshold inside a narrow gap is a threshold
  # that a patch's lighting change walks over, so the margin is asserted, not
  # just the verdicts.
  worst_win = min(win_counts.values())
  best_loss = max(loss_counts.values())
  print(f"\nworst win {worst_win}, best non-win {best_loss},"
        f" threshold {placement.WIN_GOLD_PIXELS}")
  ok("the threshold sits between them",
     best_loss < placement.WIN_GOLD_PIXELS < worst_win)
  ok("wins read at least twice the gold of any non-win",
     worst_win >= 2 * best_loss)

  # The region constant, not just the counter: these two are whole screens.
  full_win = os.path.join(FIXTURES, "full_win_210948.png")
  full_loss = os.path.join(FIXTURES, "full_loss_broadcast_213654.png")
  ok("RACE_PLACEMENT_REGION finds the win banner on a full screen",
     placement.won(region_of(full_win)))
  # The broadcast pennant is at the left edge; this is what excluding it buys.
  ok("RACE_PLACEMENT_REGION excludes the broadcast's gold 1st",
     not placement.won(region_of(full_loss)))

  print()
  if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    return 1
  print("all checks passed")
  return 0

if __name__ == "__main__":
  sys.exit(main())
