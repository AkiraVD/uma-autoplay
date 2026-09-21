"""Reading Trackblazer's Climax Store shelf, against captured frames.

Run with `python tests/test_shop_read.py` from the repo root. Imports the real
core/parked/shop.py, which builds the easyocr Reader, so it starts slowly.
PARKED with the mode on 2026-09-21; still run so the parked code cannot rot.

Fixtures in tests/fixtures/trackblazer/shop/ are full 1920x1080 frames taken on
2026-09-19:
  shelf_top.png     the shelf at the top, three whole rows visible
  shelf_bottom.png  scrolled to the bottom, four anchors - the top row's name
                    clipped by the panel header
  shelf_ticked.png  the same view with one row ticked

`shelf_ticked` is the one that matters most. The obvious anchor for a row is
its checkbox, and that was tried first: ticking a row turns its checkbox green,
so a checkbox template finds only three of the four rows here and goes blind on
exactly the row a buying pass most needs to find again. The shipped anchor is
the per-row "Cost" label instead, which does not change with selection.
"""
import glob
import os
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.parked.shop as shop              # noqa: E402
import core.parked.shop_choice as shop_choice  # noqa: E402
import core.trackblazer as trackblazer  # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "trackblazer", "shop")
ANCHOR = "assets/trackblazer/shop_cost_label.png"
# The production threshold multi_match_templates uses.
THRESHOLD = 0.85

failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def anchors(name):
  """Anchor boxes (x, y) on one fixture, top to bottom."""
  img = cv2.imread(os.path.join(FIXTURES, name))
  tpl = cv2.imread(ANCHOR)
  result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
  found = []
  for y, x in zip(*np.where(result >= THRESHOLD)):
    if not any(abs(int(y) - py) < 20 for _, py in found):
      found.append((int(x), int(y)))
  return sorted(found, key=lambda p: p[1])


def screen(name):
  return Image.open(os.path.join(FIXTURES, name)).convert("RGB")


def test_the_fixtures_and_the_anchor_exist():
  ok("the anchor asset is on disk", os.path.isfile(ANCHOR), ANCHOR)
  found = sorted(os.path.basename(p) for p in glob.glob(os.path.join(FIXTURES, "*.png")))
  ok("three shelf frames are kept", len(found) == 3, found)


def test_the_anchor_survives_a_ticked_row():
  """The whole reason the anchor is the Cost label and not the checkbox.

  A checkbox template finds three rows here, not four, because the ticked row
  renders green. Losing a row mid-purchase is how a buying pass ends up ticking
  the wrong thing, so this is pinned.
  """
  bottom = anchors("shelf_bottom.png")
  ticked = anchors("shelf_ticked.png")
  ok("the bottom view has four rows", len(bottom) == 4, len(bottom))
  ok("and ticking one loses none of them", len(ticked) == len(bottom),
     f"{len(ticked)} vs {len(bottom)}")
  ys = [y for _, y in ticked]
  ok("including the row that was ticked",
     any(abs(y - 648) < 25 for y in ys), ys)


def test_a_whole_shelf_page_reads():
  frame = screen("shelf_top.png")
  rows = [shop.read_row(box, frame) for box in anchors("shelf_top.png")]
  read = [r for r in rows if r]
  ok("every row on the top page reads", len(read) == 3, [r["name"] for r in read])
  ok("and every name resolves in the catalogue",
     all(trackblazer.item(r["name"]) for r in read),
     [r["name"] for r in read if not trackblazer.item(r["name"])])


def test_a_clipped_row_is_dropped_not_guessed():
  """The row under the panel header keeps its Cost label but loses its name.

  It must come back None. Returning a row with an empty name would put an
  unresolvable entry in front of the planner, which would read as a hole in
  data/trackblazer_shop.json rather than as a scroll artefact. The overlap in
  menu_scan.advance_one_screen is what gets this row read properly, lower down,
  on a later pass.
  """
  frame = screen("shelf_bottom.png")
  boxes = anchors("shelf_bottom.png")
  ok("the bottom view has a clipped top row", bool(boxes), len(boxes))
  if not boxes:
    return
  ok("and it reads as nothing rather than as a bad row",
     shop.read_row(boxes[0], frame) is None)
  rest = [shop.read_row(b, frame) for b in boxes[1:]]
  named = [r for r in rest if r]
  ok("while the rows below it read", len(named) == len(boxes) - 1,
     [r["name"] for r in named])


def test_the_sale_price_is_the_one_charged():
  """A sale prints the old price struck through beside the new one.

  Taking the first number overpays the plan by the discount and can make an
  affordable basket look unaffordable, so the last number wins.
  """
  for text, want in (("45- 12", 12), ("-55- 44", 44), ('458" 120', 120),
                     ("15", 15), ("", None), ("Cost", None)):
    ok(f"read_cost({text!r}) == {want}", shop.read_cost(text) == want,
       shop.read_cost(text))


def test_the_shelf_cost_beats_the_catalogue_cost():
  """score_row must charge what the shelf says, not what the file says."""
  frame = screen("shelf_top.png")
  rows = [r for r in (shop.read_row(b, frame) for b in anchors("shelf_top.png")) if r]
  discounted = [r for r in rows
                if (trackblazer.item(r["name"]) or {}).get("cost", 0) > r["cost"]]
  ok("the sale frame really is discounted", discounted,
     [(r["name"], r["cost"]) for r in rows])
  for row in discounted[:1]:
    entry = trackblazer.item(row["name"])
    scored = shop_choice.score_row(row)
    ok("and score_row prices it off the shelf",
       scored is not None and abs(scored[0] - scored[1] / row["cost"]) < 1e-9,
       f"{row['name']} shelf {row['cost']} vs catalogue {entry.get('cost')}")


for test in [test_the_fixtures_and_the_anchor_exist,
             test_the_anchor_survives_a_ticked_row,
             test_a_whole_shelf_page_reads,
             test_a_clipped_row_is_dropped_not_guessed,
             test_the_sale_price_is_the_one_charged,
             test_the_shelf_cost_beats_the_catalogue_cost]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
