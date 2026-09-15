"""The curated skill list, and the categories derived from master.mdb.

Run with `python tests/test_skill_tiers.py` from the repo root. No easyocr and
no screenshots.

The point of most of these checks is the split of responsibility: tiers are
opinion and come from the list, categories are fact and come from the game's
own conditions. The source page gets the categories wrong, so anything that
trusted its grouping would inherit that.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.masterdb as masterdb      # noqa: E402
import core.skill_tiers as T          # noqa: E402
import core.skill_score as S          # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

HAVE_DB = bool(masterdb.skills())

def test_the_list_itself():
  everything = [n for tier in T.TIERS.values() for n in tier]
  ok("the list is not empty", len(everything) > 100, str(len(everything)))

  # A skill in two tiers keeps the better one, so duplicates are survivable -
  # but a duplicate inside one tier is just an editing slip.
  for tier, names in T.TIERS.items():
    bases = [T.base(n) for n in names]
    ok(f"{tier} has no duplicates", len(bases) == len(set(bases)),
       str([b for b in bases if bases.count(b) > 1][:3]))

  ok("every tier has a weight", set(T.TIERS) <= set(T.TIER_WEIGHT))
  ok("weights are ordered SS > S > A > B",
     T.TIER_WEIGHT["SS"] > T.TIER_WEIGHT["S"] > T.TIER_WEIGHT["A"] > T.TIER_WEIGHT["B"])
  ok("an unlisted skill is unranked, not worthless",
     T.weight_of("Some Skill That Does Not Exist") == T.UNRANKED_WEIGHT)

def test_tier_lookup_ignores_rank():
  ok("a listed skill has its tier", T.tier_of("Taking the Lead") == "SS")
  ok("the rank glyph is ignored", T.tier_of("Sprint Corners ○") == T.tier_of("Sprint Corners ◎"))
  ok("an unlisted skill has none", T.tier_of("Nothing Like This Exists") is None)

def test_every_name_resolves():
  """A name master.mdb does not have is a typo or a rename, and must be visible.

  This is the whole reason names are stored rather than ids: they are readable,
  and the database catches them when they drift.
  """
  if not HAVE_DB:
    print("skip  master.mdb not present")
    return
  ok("no curated name is unknown to the game", T.unknown_skills() == [],
     str(T.unknown_skills()))

def test_categories_come_from_the_game_not_the_page():
  """The source page files these under "Universal". They are plainly not."""
  if not HAVE_DB:
    return
  groups = T.grouped()
  names = lambda bucket: {e["name"] for e in bucket}

  ok("Front Runner Corners is filed under front, not general",
     any("Front Runner Corners" in n for n in names(groups["style"].get("front", []))))
  ok("and not under general",
     not any("Front Runner Corners" in n for n in names(groups["general"])))

  ok("Mile Corners is filed under mile",
     any("Mile Corners" in n for n in names(groups["distance"].get("mile", []))))
  ok("Turbo Sprint is filed under sprint",
     "Turbo Sprint" in names(groups["distance"].get("sprint", [])))

  ok("general skills really have no aptitude condition",
     all(not T._restrictions(e) for e in groups["general"]))

def test_all_four_of_each_axis_are_populated():
  if not HAVE_DB:
    return
  groups = T.grouped()
  for axis, expected in (("distance", ["sprint", "mile", "medium", "long"]),
                         ("style", ["front", "pace", "late", "end"])):
    for value in expected:
      ok(f"{axis}/{value} has entries", len(groups[axis].get(value, [])) > 0,
         str(len(groups[axis].get(value, []))))

def test_nothing_harmful_or_unbuyable_is_listed():
  if not HAVE_DB:
    return
  groups = T.grouped()
  everything = list(groups["general"])
  for axis in ("distance", "style", "surface"):
    for bucket in groups[axis].values():
      everything.extend(bucket)
  ok("no debuff is in the curated groups", all(S.beneficial(e) for e in everything))
  ok("everything has a career cost", all(e["cost"] for e in everything))

def test_for_uma_filters_by_aptitude():
  if not HAVE_DB:
    return
  front = T.for_uma(style="front", distance=["sprint", "mile"], surface="turf")
  names = {e["name"] for e in front}
  ok("a Front Uma gets Front skills", any("Front Runner" in n for n in names))
  ok("and not Pace skills", not any("Pace Chaser" in n for n in names))
  ok("and not Long skills", not any(n.startswith("Long ") for n in names))
  ok("Sprint and Mile skills both appear",
     any("Sprint " in n for n in names) and any("Mile " in n for n in names))

  ok("general skills are always included",
     any(e["name"] == "Professor of Curvature" for e in front))

  # Best tier first, so a caller that truncates keeps the good ones.
  order = {"SS": 0, "S": 1, "A": 2, "B": 3}
  tiers = [order[e["tier"]] for e in front]
  ok("results are ordered by tier", tiers == sorted(tiers))

  ok("an Uma with no stated aptitudes gets only general skills",
     {e["name"] for e in T.for_uma()} == {e["name"] for e in T.grouped()["general"]})

for test in [test_the_list_itself, test_tier_lookup_ignores_rank, test_every_name_resolves,
             test_categories_come_from_the_game_not_the_page,
             test_all_four_of_each_axis_are_populated,
             test_nothing_harmful_or_unbuyable_is_listed, test_for_uma_filters_by_aptitude]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
