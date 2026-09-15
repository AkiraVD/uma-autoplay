"""Skill buying decisions, scored the way Team Trials pays out.

Run with `python tests/test_skill_score.py` from the repo root. No easyocr and
no screenshots - this is pure logic over master.mdb, so it runs in a second.

Each of the first three tests pins a mistake the planner actually made while it
was being written. They are not hypotheticals: every one of them spent a whole
budget on something worthless before it was fixed.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.masterdb as masterdb    # noqa: E402
import core.skill_score as S        # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

SKILLS = masterdb.skills()
BY_NAME = {s["name"]: s for s in SKILLS}

def have(*names):
  """Skip a check when the database is not on this machine."""
  return SKILLS and all(n in BY_NAME for n in names)

def test_database_present():
  if not SKILLS:
    print("skip  master.mdb not present; the rest of this suite needs it")
    return
  ok("skills load with costs", sum(1 for s in SKILLS if s["cost"]) > 400)
  ok("and with conditions", sum(1 for s in SKILLS if s["condition"]) > 500)

def test_debuffs_are_never_bought():
  """The planner spent 400 points on ten of these before `beneficial` existed.

  "Fukushima Racecourse x" moderately DECREASES performance. They cost 40-50 SP,
  the cheapest things in the game, so a scorer weighing consistency against cost
  ranks them top.
  """
  if not SKILLS:
    return
  negatives = [s for s in SKILLS if not S.beneficial(s)]
  ok("the debuff skills are identified", len(negatives) > 20, str(len(negatives)))
  ok("every one has a negative grade_value",
     all(s["grade_value"] < 0 for s in negatives))

  # grade_value is used instead of the name glyph because it catches more:
  # Gatekept, Defeatist and Packphobia are debuffs with ordinary names.
  crossed = [s for s in negatives if s["name"].rstrip().endswith("×")]
  ok("the field catches debuffs the × glyph would miss",
     len(negatives) > len(crossed), f"{len(negatives)} against {len(crossed)}")
  ok("Gatekept is one of them - a debuff with an ordinary name",
     any(s["name"] == "Gatekept" for s in negatives))

  chosen = S.plan(SKILLS, 400, style="front", distance=["sprint", "mile"], surface="turf")
  ok("and none is ever planned", all(S.beneficial(c) for c in chosen))

def test_volatile_greens_are_excluded():
  """A racecourse passive pays out only if the draw sends you to that venue.

  Nothing picks the venue in Team Trials, so these are close to worthless - but
  they are cheap and their conditions look easy, so the planner took eleven of
  them in a row until they were filtered.
  """
  if not have("Fukushima Racecourse ○", "Concentration"):
    return
  ok("a racecourse passive is volatile",
     S.is_volatile_green(BY_NAME["Fukushima Racecourse ○"]))
  ok("an always-on skill is not",
     not S.is_volatile_green(BY_NAME["Concentration"]))

  chosen = S.plan(SKILLS, 900, style="front", distance=["sprint", "mile"], surface="turf")
  ok("none is planned by default", not any(S.is_volatile_green(c) for c in chosen))
  allowed = S.plan(SKILLS, 900, style="front", distance=["sprint", "mile"],
                   surface="turf", allow_volatile_greens=True)
  ok("but they can be allowed back in", len(allowed) >= len(chosen))

def test_the_objective_is_expected_sv_not_the_composite():
  """Maximising the composite counts cost twice and buys whatever is cheapest.

  The composite already divides value by cost; a knapsack accounts for cost
  through its budget. Using the composite as the objective produced a 400-point
  plan of five 70-point passives over any gold skill.
  """
  if not have("Concentration"):
    return
  chosen = S.plan(SKILLS, 400, style="front", distance=["sprint", "mile"], surface="turf")
  golds = sum(1 for c in chosen if c["rarity"] == S.GOLD_RARITY)
  ok("a 400-point plan is mostly gold skills", golds >= len(chosen) - 1,
     f"{golds} of {len(chosen)}")
  ok("and Concentration is in it - always==1, the most reliable trigger there is",
     any(c["name"] == "Concentration" for c in chosen),
     str([c["name"] for c in chosen]))

def test_aptitude_filter():
  """The mistake sitting in the live config: Speed Star is Pace-only."""
  if not have("Speed Star", "Escape Artist"):
    return
  ok("a Pace-only skill is refused for a Front runner",
     not S.applicable(BY_NAME["Speed Star"], style="front"))
  ok("and accepted for a Pace runner",
     S.applicable(BY_NAME["Speed Star"], style="pace"))
  ok("a Front skill is accepted for a Front runner",
     S.applicable(BY_NAME["Escape Artist"], style="front"))

  # An Uma with two distance aptitudes runs both, so a set must be accepted.
  if have("Mile Corners ○"):
    mile = BY_NAME["Mile Corners ○"]
    ok("Mile skills are dead for a Sprint-only Uma",
       not S.applicable(mile, distance="sprint"))
    ok("but fine for one that runs Sprint and Mile",
       S.applicable(mile, distance=["sprint", "mile"]))

  ok("an unset aptitude filters nothing", S.applicable(BY_NAME["Speed Star"]))

def test_condition_scoring():
  ok("always==1 is the most reliable timing", S.timing_score("always==1") > 0.95)
  ok("a random phase is much less so", S.timing_score("phase_random==1") < 0.7)

  # Having to be in the lead is the narrowest requirement in the game.
  ok("order==1 collapses breadth", S.breadth_score("order==1") <= 0.18)
  ok("a wide order range does not", S.breadth_score("order<=5") > 0.4)

  ok("being blocked is penalised",
     S.scenario_score("blocked_front==1") < S.scenario_score("always==1"))
  ok("so is needing an overtake",
     S.scenario_score("is_overtake==1") < S.scenario_score("always==1"))

  # Two ways to fire beat one, because either will do.
  one = S.consistency({"condition": "phase_random==1"})
  two = S.consistency({"condition": "phase_random==1", "condition_2": "phase_random==2"})
  ok("two condition blocks are more reliable than one", two > one, f"{two:.3f} vs {one:.3f}")

def test_a_tier_chain_is_one_choice():
  """A gold skill is an upgrade of a white one, not an addition to it.

  Buying the gold grants the white, so the game lists the gold at its own
  discounted price PLUS the white's. Measured live: Professor of Curvature at
  306 beside Corner Adept at 180; buying Corner Adept for 180 dropped Professor
  to 126, and 126 + 180 = 306.

  Taking both is paying for the white twice - and then the white cannot even be
  clicked, because the gold already granted it. A career staged a cart with both
  and four of its eleven picks silently failed to click.
  """
  if not SKILLS:
    return
  pairs = [("Corner Adept ○", "Professor of Curvature"),
           ("Nimble Navigator", "No Stopping Me!")]
  for white, gold in pairs:
    if white not in BY_NAME or gold not in BY_NAME:
      continue
    ok(f"{white} and {gold} share a group",
       S.tier_group(BY_NAME[white]) == S.tier_group(BY_NAME[gold]),
       f"{S.tier_group(BY_NAME[white])} vs {S.tier_group(BY_NAME[gold])}")
    ok(f"{gold} is the upper tier", BY_NAME[gold]["group_rate"] > BY_NAME[white]["group_rate"])

    # The screen price of the gold already covers the white.
    chosen = S.plan([dict(BY_NAME[gold], cost=306), dict(BY_NAME[white], cost=180)],
                    600, style="late", distance=["medium"])
    names = [c["name"] for c in chosen]
    ok(f"only one of the {gold} chain is planned", len(names) <= 1, str(names))

  # Skills from different chains are still independent.
  a, b = BY_NAME.get("Professor of Curvature"), BY_NAME.get("Homestretch Haste")
  if a and b:
    ok("different chains are not grouped", S.tier_group(a) != S.tier_group(b))

  # And a skill with no group still falls back to its rank-stripped name.
  ok("a groupless skill falls back to its name",
     S.tier_group({"name": "Made Up ○"}) == "made up")
  ok("both ranks of a groupless skill collide",
     S.tier_group({"name": "Made Up ○"}) == S.tier_group({"name": "Made Up ◎"}))

def test_plan_respects_its_constraints():
  if not SKILLS:
    return
  for budget in (0, 120, 400, 1200):
    chosen = S.plan(SKILLS, budget, style="front", distance=["sprint"], surface="turf")
    spend = sum(c["cost"] for c in chosen)
    ok(f"budget {budget} is not exceeded", spend <= budget, f"spent {spend}")

  chosen = S.plan(SKILLS, 900, style="front", distance=["sprint", "mile"], surface="turf")
  # Both ranks of one skill is wasted points - the fold has to hold in the plan.
  bases = [S.re.sub(r"\s+[○◎×]$", "", c["name"]).lower() for c in chosen]
  ok("no skill is bought at two ranks", len(bases) == len(set(bases)), str(bases))
  ok("a bigger budget is worth at least as much",
     sum(S.expected_sv(c) for c in S.plan(SKILLS, 1200, style="front"))
     >= sum(S.expected_sv(c) for c in S.plan(SKILLS, 600, style="front")))

def test_no_budget_buys_nothing():
  ok("zero budget plans nothing", S.plan(SKILLS, 0) == [])
  ok("a negative budget plans nothing", S.plan(SKILLS, -50) == [])
  ok("an empty skill list plans nothing", S.plan([], 500) == [])

for test in [test_database_present, test_debuffs_are_never_bought,
             test_volatile_greens_are_excluded,
             test_the_objective_is_expected_sv_not_the_composite,
             test_aptitude_filter, test_condition_scoring,
             test_a_tier_chain_is_one_choice,
             test_plan_respects_its_constraints, test_no_budget_buys_nothing]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
