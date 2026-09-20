"""Trackblazer: the scoring tables and the shop catalogue.

Global's third permanent scenario (2026-03-12). Races replace the career goals:
each year wants a number of points, and the Umamusume's own goals are switched
off. The in-career HUD calls them "<Year> Result Pts" (the badge top-left of
the lobby reads "Junior Result Pts / 70 pts"); the How to Play mock-up says
"Track Pts" and the guides say "Grade Points", neither of which the lobby
shows. Prefer "Result Pts" for anything read off a real screen.

**This module is data and arithmetic only**, by choice rather than for want of
measurements: the shop, the rival-race VS badge and the points HUD were all
measured on a live career on 2026-09-17 and are written up in
docs/screen-map.md, but the readers and the clicking live with the rest of the
screen code. docs/TODO.md has what is left.

The numbers below come from the game's own master.mdb rather than from guides:
single_mode_free_win_point for points, single_mode_free_coin_race for coins.
"""
import json
import os

from utils.log import warning

SHOP_FILE = os.path.join("data", "trackblazer_shop.json")

# Points a race is worth at 1st place, by grade. master.mdb's
# single_mode_free_win_point pays grade codes 100/200/300/400 as 100/80/60/40,
# matching these five names, and confirmed on screen: a G3 race row showed
# "+60 pts".
#
# It also holds lower tiers - codes 500/600/700 pay 20 and 800/900 pay 10 - but
# what those print on the race row is not known, and the race table's grade
# codes do not map one-to-one onto the badges (734 races share code 100). So
# they stay out, and points_for() keeps returning 0 for a grade it cannot name.
POINTS_BY_GRADE = {"G1": 100, "G2": 80, "G3": 60, "OP": 40, "Pre-OP": 20}

# What a placement keeps of that. From single_mode_free_win_point, which gives
# the identical curve for every grade: 1st takes all, 2nd 0.6, 3rd 0.4, 4th and
# 5th 0.2, and 6th to 18th a tenth.
#
# The guides said 3rd kept 0.6 and 4th-5th 0.3, which this file used to copy.
# That over-paid 3rd and 4th-5th by half - a G1 third place is 40 points, not
# 60 - so any "is this race worth a turn" decision built on it was skewed
# toward racing.
#
# Confirmed on screen 2026-09-20, and all three at once: the after-race results
# for the G3 Niigata Junior Stakes paid 1st 60 pts, 2nd 36 and 3rd 24 - exactly
# 60 x 1.0 / 0.6 / 0.4. The award popup read "Junior Year Result Pts 70/60 MAX
# (+60 pts)" for the win. So the curve below is measured, not inferred, and the
# guides' 0.6/0.3 for 3rd and 4th-5th is definitively wrong.
#
# The G1 row is confirmed too, same day: winning the G1 Hopeful Stakes paid
# "(+100 pts)", taking the badge to 510/60 MAX. So both POINTS_BY_GRADE rows
# that a Junior year can reach are now measured against the game rather than
# taken from single_mode_free_win_point alone.
PLACEMENT_KEPT = {1: 1.0, 2: 0.6, 3: 0.4, 4: 0.2, 5: 0.2}
PLACEMENT_KEPT_TAIL = 0.1

# Shop coins by placement, from single_mode_free_coin_race. Unlike the points
# above, coins do NOT scale with grade: all nine grade codes give the same
# 100/60/30/0, so a Pre-OP win pays exactly what a G1 win pays. Racing for
# coins and racing for points therefore want different races.
COINS_BY_PLACEMENT = {1: 100, 2: 60, 3: 60, 4: 30, 5: 30}
COINS_TAIL = 0

# Points needed by the end of each year. Turf is confirmed: the How to Play
# page showed "Classic Year Track Pts 100/300pts". Dirt is from the guides.
TARGETS = {
  "turf": {"junior": 60, "classic": 300, "senior": 300},
  "dirt": {"junior": 30, "classic": 200, "senior": 300},
}

# Victory points in the Twinkle Star Climax, the three races that replace the
# URA Finale. Highest total over the three wins it, so a lost leg is survivable.
CLIMAX_VP = {1: 10, 2: 8, 3: 6, 4: 4, 5: 3, 6: 3, 7: 2, 8: 2, 9: 2,
             10: 1, 11: 1, 12: 1, 13: 1}

_catalogue = None


def points_for(grade, place=1):
  """Points a race of `grade` pays at `place`. 0 for an unknown grade.

  Unknown rather than a guess: a grade this does not recognise means the race
  list read something unexpected, and scoring it as though it were a G1 would
  quietly steer the whole year.
  """
  base = POINTS_BY_GRADE.get(grade)
  if base is None:
    return 0
  return int(base * PLACEMENT_KEPT.get(place, PLACEMENT_KEPT_TAIL))


def coins_for(place):
  """Shop coins a race pays at `place`."""
  return COINS_BY_PLACEMENT.get(place, COINS_TAIL)


def target_for(year, surface="turf"):
  """Points wanted by the end of `year` for a turf or dirt trainee."""
  return TARGETS.get(surface, TARGETS["turf"]).get(year)


def climax_vp(place):
  """Victory points for a placement in a Twinkle Star Climax leg."""
  return CLIMAX_VP.get(place, 0)


def catalogue(force=False):
  """The shop item list, or [] when the file is missing or unreadable.

  Fails soft the way core/masterdb.py does: a missing catalogue should cost the
  shop, not the career.
  """
  global _catalogue
  if _catalogue is not None and not force:
    return _catalogue
  try:
    with open(SHOP_FILE, "r", encoding="utf-8") as f:
      _catalogue = json.load(f).get("items", [])
  except (OSError, ValueError) as e:
    warning(f"TB-SHOP-READ: {SHOP_FILE} unreadable, the shop will be skipped ({e}).")
    _catalogue = []
  return _catalogue


def item(name):
  """One catalogue entry by exact name, or None.

  Exact matching is enough, and that was worth checking rather than assuming.
  This docstring used to say canonicalisation was still owed, because the rows
  read on 2026-09-17 carry a stat prefix ("Speed Notepad", "Guts Manual") where
  the catalogue then held the bare noun. The catalogue has since been
  regenerated from master.mdb and holds the prefixed names too: all seven
  measured live rows resolve here exactly, with matching costs.

  Add canonicalisation when a row is seen that does *not* resolve - with OCR
  damage to match against, the way core/skill.py does for skill names.
  """
  for entry in catalogue():
    if entry.get("name") == name:
      return entry
  return None


def items_of(category):
  """Every catalogue entry in a category, cheapest first."""
  found = [e for e in catalogue() if e.get("category") == category]
  return sorted(found, key=lambda e: e.get("cost", 0))


def affordable(coins, category=None):
  """Catalogue entries costing no more than `coins`, dearest first.

  Dearest first because the shop's whole shape is that coins expire with the
  career - there is nothing to save them for past the last shop.
  """
  found = catalogue() if category is None else items_of(category)
  return sorted([e for e in found if e.get("cost", 0) <= coins],
                key=lambda e: e.get("cost", 0), reverse=True)
