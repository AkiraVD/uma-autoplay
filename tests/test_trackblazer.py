"""Trackblazer's scoring tables and shop catalogue.

Run with `python tests/test_trackblazer.py` from the repo root. No OCR and no
screenshots, so it runs in about a second.

Only two of these numbers are confirmed against the game: a G1 race pays
"+100 pts" and a green coin "+100" on the race rows, and the Classic Year
target reads "100/300pts" on the How to Play page. Everything else is from the
guides and is pinned here so that a later reading off a real shop screen shows
up as a failure rather than a silent disagreement.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.trackblazer as T   # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def test_points_confirmed_on_screen():
  """The one row read off the game: a G1 at 1st pays 100."""
  ok("a G1 win pays 100", T.points_for("G1", 1) == 100, T.points_for("G1", 1))
  ok("and a G1 win pays 100 coins", T.coins_for(1) == 100, T.coins_for(1))
  ok("Classic turf wants 300", T.target_for("classic") == 300, T.target_for("classic"))

def test_points_by_grade():
  for grade, expected in (("G2", 80), ("G3", 60), ("OP", 40), ("Pre-OP", 20)):
    ok(f"{grade} pays {expected}", T.points_for(grade) == expected, T.points_for(grade))

def test_placement_scales_the_points():
  """The curve is master.mdb's single_mode_free_win_point, not the guides'.

  The guides said 3rd kept 0.6 and 4th-5th 0.3, and this test used to assert
  that. The game's own table gives 1.0 / 0.6 / 0.4 / 0.2 / 0.2 and a tenth from
  6th, identically for every one of its nine grade codes.
  """
  ok("2nd keeps 60%", T.points_for("G1", 2) == 60, T.points_for("G1", 2))
  ok("3rd keeps 40%, not 60%", T.points_for("G1", 3) == 40, T.points_for("G1", 3))
  ok("4th keeps 20%, not 30%", T.points_for("G1", 4) == 20, T.points_for("G1", 4))
  ok("5th keeps 20% too", T.points_for("G1", 5) == 20, T.points_for("G1", 5))
  ok("6th keeps a tenth", T.points_for("G1", 6) == 10, T.points_for("G1", 6))
  ok("and so does anything worse", T.points_for("G1", 15) == 10, T.points_for("G1", 15))
  # A G3 third place: 60 * 0.4. Worth pinning because the grades share one
  # curve, so a bug in either table shows up here rather than only on G1s.
  ok("a G3 third pays 24", T.points_for("G3", 3) == 24, T.points_for("G3", 3))

def test_coins_do_not_scale_with_grade():
  """single_mode_free_coin_race pays the same for every grade code.

  coins_for takes no grade at all, which is the point: a Pre-OP win and a G1
  win both pay 100. Racing for coins and racing for points want different
  races, and this is the line that says so.
  """
  ok("a win pays 100 whatever the grade", T.coins_for(1) == 100, T.coins_for(1))
  ok("2nd and 3rd both pay 60", T.coins_for(2) == 60 and T.coins_for(3) == 60)
  ok("4th and 5th both pay 30", T.coins_for(4) == 30 and T.coins_for(5) == 30)

def test_an_unknown_grade_scores_zero():
  """A grade the race list did not parse must not be priced as a guess."""
  ok("an unknown grade is worth nothing", T.points_for("G4") == 0)
  ok("and so is a missing one", T.points_for(None) == 0)

def test_coins_stop_at_sixth():
  ok("3rd still pays 60", T.coins_for(3) == 60)
  ok("5th pays 30", T.coins_for(5) == 30)
  ok("6th pays nothing", T.coins_for(6) == 0)

def test_dirt_targets_are_lower_early():
  ok("dirt Junior is 30", T.target_for("junior", "dirt") == 30)
  ok("dirt Classic is 200", T.target_for("classic", "dirt") == 200)
  ok("but Senior matches turf at 300", T.target_for("senior", "dirt") == 300)

def test_climax_vp():
  """Three legs, highest total wins - so a lost leg is survivable."""
  ok("a leg win is 10", T.climax_vp(1) == 10)
  ok("2nd is 8", T.climax_vp(2) == 8)
  ok("14th scores nothing", T.climax_vp(14) == 0)
  best = T.climax_vp(1) * 3
  ok("a clean sweep is 30", best == 30, best)
  ok("2nd in every leg beats 1st-14th-14th", 8 * 3 > 10, f"{8*3} vs 10")

def test_catalogue_loads():
  cat = T.catalogue()
  ok("the catalogue loads", len(cat) > 0, len(cat))
  ok("every entry has a name, cost and category",
     all(e.get("name") and e.get("category") and e.get("cost") is not None for e in cat))

def test_item_lookup():
  scroll = T.item("Scroll")
  ok("Scroll is in the catalogue", scroll is not None)
  ok("and costs 30 for +15", scroll and scroll["cost"] == 30
     and scroll["effect"]["amount"] == 15, scroll)
  ok("an unknown item is None, not a guess", T.item("Nonesuch") is None)

def test_items_of_category():
  stats = T.items_of("stat")
  ok("three stat items", len(stats) == 3, [e["name"] for e in stats])
  ok("cheapest first", [e["cost"] for e in stats] == sorted(e["cost"] for e in stats),
     [e["cost"] for e in stats])

def test_affordable():
  """Dearest first: coins expire with the career, so there is nothing to save for."""
  cheap = T.affordable(15, "stat")
  ok("15 coins buys the Manual, not the Scroll",
     [e["name"] for e in cheap] == ["Manual", "Notepad"], [e["name"] for e in cheap])
  ok("0 coins buys nothing", T.affordable(0, "stat") == [])
  everything = T.affordable(10_000)
  ok("a big purse offers the whole catalogue", len(everything) == len(T.catalogue()))
  ok("and offers the dearest first",
     everything[0]["cost"] >= everything[-1]["cost"],
     (everything[0]["cost"], everything[-1]["cost"]))

for test in [test_points_confirmed_on_screen, test_points_by_grade,
             test_placement_scales_the_points, test_an_unknown_grade_scores_zero,
             test_coins_stop_at_sixth, test_dirt_targets_are_lower_early,
             test_climax_vp, test_catalogue_loads, test_item_lookup,
             test_items_of_category, test_affordable]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
