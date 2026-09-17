"""Trackblazer: the scoring tables and the shop catalogue.

Global's third permanent scenario (2026-03-12). Races replace the career goals:
each year wants a number of points, and the Umamusume's own goals are switched
off. The points have two names in game - the HUD says **Track Pts**, the body
text says Result Points - so this module says "points" and the log says
"Track Pts", which is what a person reading the screen will see. Guides call
them "Grade Points"; that name appears nowhere in the game.

**This module is data and arithmetic only.** Nothing here reads the screen or
clicks, because the shop, the rival-race marker and the in-lobby points counter
only exist inside a running career and have not been seen yet. Adding geometry
by guesswork is how the skill-buy offsets ended up wrong, so the readers wait
for a real career. docs/screen-map.md has what is measured; docs/TODO.md has
what is left.
"""
import json
import os

from utils.log import warning

SHOP_FILE = os.path.join("data", "trackblazer_shop.json")

# Points a race is worth at 1st place, by grade. Confirmed on screen: the race
# rows on the How to Play page show G1 races at "+100 pts".
POINTS_BY_GRADE = {"G1": 100, "G2": 80, "G3": 60, "OP": 40, "Pre-OP": 20}

# What a placement keeps of that. 1st takes all; 6th and worse keep a tenth.
# From the guides - only the 1st-place row is confirmed on screen.
PLACEMENT_KEPT = {1: 1.0, 2: 0.6, 3: 0.6, 4: 0.3, 5: 0.3}
PLACEMENT_KEPT_TAIL = 0.1

# Shop coins by placement. Confirmed on screen for 1st: the race rows show a
# green coin "+100" beside the points star.
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

  Exact rather than fuzzy on purpose: the shop rows have not been read off a
  real screen yet, so there is no measured OCR damage to match against. Once
  there is, canonicalise here the way core/skill.py does for skill names.
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
