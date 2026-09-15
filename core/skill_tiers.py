"""Curated list of skills worth buying, with their tier.

`skill_score` can tell how *reliably* a skill fires and what it costs, but not
whether the thing it does is worth having - master.mdb states a magnitude, not
whether that magnitude matters. This file is the missing half: a hand-curated
opinion about which skills are actually good, taken from a public tier list.

Two deliberate splits of responsibility:

- **Tiers come from here.** They are judgement, and no database has them.
- **Categories do NOT.** Which skills are general, which are locked to a
  distance and which to a running style is derived at load from the conditions
  in master.mdb, because the game states it and a scraped page gets it wrong -
  the source page files "Front Runner Corners" and "Mile Corners" under
  Universal, and both are plainly restricted.

Names are stored rather than ids. Ids are stabler, but nobody hand-edits a tier
list of `200331`, the repo already keys skills by name in config.json, and the
names are validated against master.mdb on load - so a typo or a renamed skill
fails loudly instead of silently dropping out. `unknown_skills()` reports them.

Source: game8 "Best Skills Tier List", September 2026. Single-sourced, so treat
the ordering as a reasonable prior rather than settled fact.
"""
import re

import core.masterdb as masterdb
from utils.log import debug, warning

# How much a tier is worth as a multiplier on a skill's expected value. A tier
# list is ordinal, not cardinal, so these are a shape rather than a measurement:
# SS is roughly twice as wanted as A, and B is barely wanted at all.
TIER_WEIGHT = {"SS": 1.5, "S": 1.25, "A": 1.0, "B": 0.75}

# Anything absent from the list. Not zero - the tier list is not exhaustive, and
# a skill it never mentions is unranked rather than known-bad.
UNRANKED_WEIGHT = 0.85

# Best tier first. Used to compare two tiers and to express a floor.
TIER_ORDER = ["SS", "S", "A", "B"]

# Only A and above are bought. B tier is deliberately kept in the list rather
# than deleted: it is real, sourced information, and a future feature - a
# bigger budget, a cheap filler pass, a different scenario - may want it. The
# floor is a buying decision, not a statement that B skills are worthless.
#
# An unranked skill does not clear the floor either. The list is not
# exhaustive, so that will skip some good skills; spending points on a skill
# nobody rated is the worse mistake.
MIN_BUY_TIER = "A"

def worth_buying(name):
  """True when a skill is rated at or above MIN_BUY_TIER."""
  tier = tier_of(name)
  if tier is None:
    return False
  return TIER_ORDER.index(tier) <= TIER_ORDER.index(MIN_BUY_TIER)

TIERS = {
  "SS": [
    "Angling and Scheming", "Budding Blossom", "Encroaching Shadow", "From the Brink",
    "Groundwork", "Lightning Surge", "Moving Past, and Beyond", "My True Strength",
    "Neck and Neck", "On Your Left!", "Scramble", "Taking the Lead", "Turbo Sprint",
    "564 Escapades", "Barcarole of Blessings", "Big-Sisterly", "Blast Forward",
    "Daring Strike", "Down in the Dirt ○", "End Closer Corners ◎", "Escape Artist",
    "Front Runner Corners ◎", "Front Runner Straightaways ◎", "In Body and Mind",
    "It's On!", "Joyful Voyage!", "Late Surger Corners ◎", "Late Surger Straightaways ◎",
    "Long Corners ◎", "Long Straightaways ◎", "Medium Corners ◎", "Mile Corners ◎",
    "Mile Maven", "Mile Straightaways ◎", "Moonlit Flash", "Pace Chaser Corners ◎",
    "Pace Chaser Straightaways ◎", "Professor of Curvature", "Refraction Arc",
    "See Ya Later!", "Shocking Flash", "Slipstream", "Sprint Corners ◎",
    "Sprint Straightaways ◎", "Superstan", "Tail Nine", "Top Runner",
    "Triumphant Pulse", "Unstoppable",
  ],
  "S": [
    "Be the Center!", "Burning Spirit PWR", "Burning Spirit SPD", "Claw Forward",
    "Condor's Fury", "Furious Feat", "Louder! Tracen Cheer!", "No Stopping Me!",
    "Rapid Gain", "Shooting for Victory!", "Shooting Star", "Unrestrained",
    "114th Time's the Charm", "A Kiss for Courage", "Ambitious Breeze",
    "Anchors Aweigh!", "Beeline Burst", "Behold Thine Emperor's Divine Might",
    "Best in Japan", "Blue Rose Closer", "Can't Keep Me Down", "Certain Victory",
    "Chance of Victory", "Changing Gears", "Come What May", "Cut and Drive!",
    "Elated", "Feature Act", "Firelight", "Flash Forward", "Full of Vigor",
    "Guten Appetit ♪", "Headliner", "Hephaestus", "Lightning Flare",
    "Maestro of the Mud", "Of Calm Mind", "One True Color", "Perfect Spot!",
    "Petrifying Gaze", "Right-Handed Demon", "Solid Strike", "Stamina Siphon",
    "Strong Steps", "White Lightning Comin' Through!",
  ],
  "A": [
    "Corner Connoisseur", "Determined Descent", "Highlander", "Second Wind",
    "Sunny Breeze", "Technician", "Downhill Speedster", "Familiar Ground",
    "Fighting Spirit", "All Set", "Be Still", "Lie in Wait", "Rushing Gale!",
    "Red-Hot Discipline!", "Hard Worker", "Shatterproof", "Mad Dash",
    "Full Throttle", "Keep Going!", "Fearless", "Dauntless", "Wild Wind",
    "Free-Spirited", "I Never Goof Up!", "Master of the Sands", "Corner Adept",
    "Straightaway Adept", "Corner Recovery", "Straightaway Recovery", "Gap Closer",
    "Nimble Navigator", "Prepared to Pass", "Outer Swell", "Up-Tempo",
    "Homestretch Haste", "Early Lead", "Speed Star", "Keen Eye", "Focus",
    "Concentration", "Ramp Up", "Nothing Ventured", "Center Stage", "Risk-Maker",
  ],
  "B": [
    "KEEP IT REAL.", "Plan X", "Step on the Gas!", "Serenity", "Risky Business",
    "Early Start", "Crusader", "Battle Formation", "Trick (Front)", "Trick (Rear)",
    "A Small Breather", "Inside Scoop", "Strategist", "Lane Legerdemain",
    "The Coast is Clear!", "I Can See Right Through You", "Tactical Tweak",
  ],
}

STYLE_NAMES = {1: "front", 2: "pace", 3: "late", 4: "end"}
DISTANCE_NAMES = {1: "sprint", 2: "mile", 3: "medium", 4: "long"}
SURFACE_NAMES = {1: "turf", 2: "dirt"}

RANK_SUFFIX = re.compile(r"\s+[○◎×]$")

def base(name):
  return RANK_SUFFIX.sub("", (name or "").strip()).strip().lower()

_tier_of = None
_grouped = None
_unknown = None

def tier_of(name):
  """Tier string for a skill name, ignoring its rank glyph, or None."""
  global _tier_of
  if _tier_of is None:
    _tier_of = {}
    # Built worst-first so a skill listed twice keeps its best tier.
    for tier in ("B", "A", "S", "SS"):
      for skill in TIERS[tier]:
        _tier_of[base(skill)] = tier
  return _tier_of.get(base(name))

def weight_of(name):
  """Multiplier for a skill's value. Unranked skills are not zero."""
  return TIER_WEIGHT.get(tier_of(name), UNRANKED_WEIGHT)

def _restrictions(skill):
  """Which running styles / distances / surfaces the skill's condition names."""
  import core.skill_score as skill_score
  found = {}
  for key, table in (("running_style", STYLE_NAMES),
                     ("distance_type", DISTANCE_NAMES),
                     ("ground_type", SURFACE_NAMES)):
    values = set()
    for text in skill_score.condition_groups(skill):
      values |= {int(v) for v in re.findall(key + r"\s*==\s*(\d+)", text)}
    named = sorted(table[v] for v in values if v in table)
    if named:
      found[key] = named
  return found

def grouped():
  """The curated skills, split by what restricts them.

  {"general": [...], "distance": {"sprint": [...]}, "style": {...},
   "surface": {...}} - each entry a master.mdb record with a "tier" key added.

  A skill restricted on two axes appears under both, because the restrictions
  are an AND: "Mile Corners" is in `distance.mile`, and a skill gated on both a
  distance and a style is in both lists. `skill_score.applicable` is what
  enforces the conjunction at decision time; these groups are for reading and
  for narrowing the candidate set.
  """
  global _grouped, _unknown
  if _grouped is not None:
    return _grouped

  import core.skill_score as skill_score
  by_base = {}
  for record in masterdb.skills():
    by_base.setdefault(base(record["name"]), record)

  _grouped = {"general": [], "distance": {}, "style": {}, "surface": {}}
  _unknown = []
  for tier in ("SS", "S", "A", "B"):
    for name in TIERS[tier]:
      record = by_base.get(base(name))
      if record is None:
        _unknown.append(name)
        continue
      # Unbuyable or harmful skills are opinion we cannot act on.
      if not record.get("cost") or not skill_score.beneficial(record):
        continue

      entry = dict(record, tier=tier)
      found = _restrictions(record)
      if not found:
        _grouped["general"].append(entry)
      for key, axis in (("running_style", "style"), ("distance_type", "distance"),
                        ("ground_type", "surface")):
        for value in found.get(key, []):
          _grouped[axis].setdefault(value, []).append(entry)

  if _unknown:
    warning(f"{len(_unknown)} tier-list skills are not in master.mdb and were"
            f" dropped: {', '.join(_unknown)}")
  debug(f"Curated skills: {len(_grouped['general'])} general, "
        + ", ".join(f"{len(v)} {k}" for k, v in sorted(_grouped["distance"].items()))
        + ", " + ", ".join(f"{len(v)} {k}" for k, v in sorted(_grouped["style"].items())))
  return _grouped

def unknown_skills():
  """Curated names master.mdb does not have - a typo, or a renamed skill."""
  grouped()
  return list(_unknown)

def for_uma(style=None, distance=None, surface=None):
  """Curated skills this Uma can actually use, best tier first.

  General skills plus the restricted ones its aptitudes allow. Deduplicated,
  because a skill can be reached through more than one axis.
  """
  import core.skill_score as skill_score
  groups = grouped()
  candidates = list(groups["general"])
  for axis, value in (("style", style), ("distance", distance), ("surface", surface)):
    if value is None:
      continue
    values = value if isinstance(value, (list, tuple, set, frozenset)) else [value]
    for one in values:
      candidates.extend(groups[axis].get(str(one).strip().lower(), []))

  seen, usable = set(), []
  order = {"SS": 0, "S": 1, "A": 2, "B": 3}
  for entry in candidates:
    if entry["name"] in seen:
      continue
    seen.add(entry["name"])
    # A skill can be listed under one aptitude and still be ruled out by
    # another - Mile Corners is fine for a Mile Uma but not if it is also
    # gated on a running style this Uma does not have.
    if skill_score.applicable(entry, style, distance, surface):
      usable.append(entry)
  usable.sort(key=lambda e: (order[e["tier"]], -skill_score.expected_sv(e)))
  return usable

def reset():
  """Drop the caches, for tests that swap the database."""
  global _tier_of, _grouped, _unknown
  _tier_of = _grouped = _unknown = None
