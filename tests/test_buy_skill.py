"""The buying rules: what to buy mid-career, and what to buy at the end.

Run with `python tests/test_buy_skill.py` from the repo root. The screen is
never touched - every check drives the decision functions directly, with the
readings that `scan_rows` would have produced passed in by hand.

The two jobs are deliberately different:

  mid-career  only what this Uma can use, and only at max hint, because hints
              keep arriving and a point spent early cannot be spent again
  career end  unspent points are destroyed, so the optimizer spends them
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

from update_config import update_config    # noqa: E402
update_config()

import core.state as state                 # noqa: E402
state.reload_config()

import core.masterdb as masterdb           # noqa: E402
import core.skill as K                     # noqa: E402
import core.skill_score as S               # noqa: E402
import core.skill_tiers as T               # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

SKILLS = masterdb.skills()
BY_NAME = {s["name"]: s for s in SKILLS}
HAVE_DB = bool(SKILLS)

def with_aptitudes(style, distance):
  """Swap the configured aptitudes for one check."""
  saved = (state.SKILL_RUN_STYLE, state.SKILL_DISTANCE)
  state.SKILL_RUN_STYLE, state.SKILL_DISTANCE = style, distance
  return saved

def restore(saved):
  state.SKILL_RUN_STYLE, state.SKILL_DISTANCE = saved

def test_config_is_wired():
  ok("skill_distance is read from config", isinstance(state.SKILL_DISTANCE, list),
     repr(state.SKILL_DISTANCE))
  ok("skill_run_style is read from config",
     state.SKILL_RUN_STYLE is None or isinstance(state.SKILL_RUN_STYLE, str),
     repr(state.SKILL_RUN_STYLE))
  ok("uma_aptitudes reports them", K.uma_aptitudes()[0] == state.SKILL_RUN_STYLE)

def test_only_usable_skills():
  """A skill gated on a style or distance the Uma lacks can never fire."""
  if not HAVE_DB:
    print("skip  master.mdb not present")
    return
  saved = with_aptitudes("front", ["sprint", "mile"])
  try:
    ok("a general skill is usable", K.usable_here(BY_NAME["Professor of Curvature"]))
    ok("a Front skill is usable for a Front runner", K.usable_here(BY_NAME["Escape Artist"]))
    ok("a Pace-only skill is not", not K.usable_here(BY_NAME["Speed Star"]))
    ok("a Mile skill is usable when the Uma runs Mile",
       K.usable_here(BY_NAME["Mile Corners ○"]))
    ok("a Long skill is not", not K.usable_here(BY_NAME["Long Corners ○"]))
    ok("a debuff is never usable", not K.usable_here(BY_NAME["Fukushima Racecourse ×"]))
    ok("an unreadable row is not usable", not K.usable_here(None))
  finally:
    restore(saved)

def test_only_A_tier_and_above_is_bought():
  """core/skill_tiers.py is the drive now - the configured list is gone.

  B tier stays in that file on purpose: it is real, sourced information a future
  feature may want. The floor is a buying decision, not a claim that B skills
  do nothing.
  """
  if not HAVE_DB:
    return
  saved = with_aptitudes("front", ["sprint", "mile"])
  try:
    ok("an SS skill is bought", K.usable_here(BY_NAME["Professor of Curvature"]))
    ok("an A skill is bought", K.usable_here(BY_NAME["Concentration"]))
    ok("a B skill is not", not K.usable_here(BY_NAME["Plan X"]))
    ok("an unranked skill is not", not K.usable_here(BY_NAME["Lone Wolf"]))

    # The floor is about worth; the aptitude test is about whether it can fire.
    # Both have to pass, and they fail for different reasons.
    ok("Speed Star is rated well enough", T.worth_buying("Speed Star"))
    ok("but is still refused on aptitude", not K.usable_here(BY_NAME["Speed Star"]))

    ok("B tier is still in the curated list for later",
       T.tier_of("Plan X") == "B")
  finally:
    restore(saved)

def test_the_floor_is_mid_career_only():
  """A tier gates mid-career buying. The end of a career does not use it.

  While a career is running there is a reason to be picky - a point spent now
  cannot be spent on something better later. At the end there is no later, the
  points are destroyed, so the only question is which affordable set is worth
  most.

  The tier list is also built for race performance, and Team Trials pays for
  activation whatever a skill does. Checked against the reference optimizer on a
  real screen, the floor rejected six of its picks, all cheap reliable proccers
  that no race-performance list ranks.
  """
  if not HAVE_DB:
    return
  saved = with_aptitudes("late", ["medium"])
  try:
    # Mid-career: the floor is doing its job.
    ok("an unranked skill is refused mid-career",
       not K.usable_here(BY_NAME["Hesitant Front Runners"]))
    ok("a B-tier skill is refused mid-career", not K.usable_here(BY_NAME["Trick (Rear)"]))
    ok("an SS skill is taken mid-career", K.usable_here(BY_NAME["Professor of Curvature"]))

    # Career end: the optimizer decides alone.
    source = open(os.path.join("core", "skill.py"), encoding="utf-8").read()
    planned = source[source.index("def buy_planned"):source.index("def buy_anything_affordable")]
    ok("buy_planned does not consult the tier list", "worth_buying" not in planned)
    ok("but it still refuses debuffs", "beneficial" in planned)
    ok("and still refuses what cannot fire", "applicable" in planned)

    # An unranked skill has to be reachable by the end-of-career planner.
    offered = [dict(BY_NAME[n], cost=c) for n, c in
               [("Hesitant Front Runners", 104), ("Trick (Rear)", 112)]]
    chosen = S.plan(offered, 400, style="late", distance=["medium"])
    ok("unranked skills can be planned at career end", len(chosen) == 2,
       str([c["name"] for c in chosen]))
  finally:
    restore(saved)

def test_the_configured_list_is_gone():
  ok("state no longer carries SKILL_LIST", not hasattr(state, "SKILL_LIST"))
  ok("and skill.py no longer matches against one", not hasattr(K, "is_skill_match"))

def test_max_hint_is_the_signal():
  if not HAVE_DB:
    return
  skill = BY_NAME["Professor of Curvature"]      # base 180
  ok("max hint means buy now",
     K.at_max_discount(skill, 180, {"level": K.MAX_HINT_LEVEL, "discount": 40}))
  ok("a partial hint does not",
     not K.at_max_discount(skill, 108, {"level": 2, "discount": 20}))

  # The hint level wins outright: it is the thing that sets the price, so a
  # cheap-looking row at hint 2 is still going to get cheaper.
  ok("hint level beats a tempting price",
     not K.at_max_discount(skill, 100, {"level": 2, "discount": 20}))

  # The badge states the same fact twice, so either half is enough. Measured
  # live: "Hint Lvl 2 20% OFFI" parses to both, and OCR mangles the tail.
  ok("the discount alone is enough",
     K.at_max_discount(skill, 108, {"level": None, "discount": 40}))
  ok("and a partial discount alone is enough to refuse",
     not K.at_max_discount(skill, 144, {"level": None, "discount": 20}))
  ok("an empty badge falls through to the price",
     K.at_max_discount(skill, 108, None))

def test_price_is_the_fallback():
  """When the hint badge will not read, the price says the same thing."""
  if not HAVE_DB:
    return
  skill = BY_NAME["Professor of Curvature"]      # base 180, so 40% off is 108
  ok("a fully discounted price passes", K.at_max_discount(skill, 108, None))
  ok("a partly discounted price does not", not K.at_max_discount(skill, 144, None))
  ok("full price does not", not K.at_max_discount(skill, 180, None))

  # Fast Learner takes another 10% off everything, so cheaper than expected has
  # to pass too - the test is "at least this discounted", not "exactly".
  ok("cheaper than the max hint still passes", K.at_max_discount(skill, 97, None))

  # Neither reading available is not evidence of a bargain.
  ok("no hint and no price means no", not K.at_max_discount(skill, None, None))
  ok("an unknown skill means no", not K.at_max_discount(None, 100, None))

def test_end_of_career_plans_within_budget():
  if not HAVE_DB:
    return
  saved = with_aptitudes("front", ["sprint", "mile"])
  try:
    offered = [BY_NAME[n] for n in
               ["Professor of Curvature", "Escape Artist", "Concentration",
                "Taking the Lead", "Mile Corners ○", "Speed Star",
                "Fukushima Racecourse ×"]]
    style, distance = K.uma_aptitudes()
    chosen = S.plan(offered, 400, style=style, distance=distance)
    spend = sum(c["cost"] for c in chosen)
    ok("the plan fits the budget", spend <= 400, f"spent {spend}")
    ok("it buys something", chosen)
    names = {c["name"] for c in chosen}
    ok("the Pace-only skill is not planned", "Speed Star" not in names, str(names))
    ok("the debuff is not planned", "Fukushima Racecourse ×" not in names, str(names))
  finally:
    restore(saved)

def test_screen_price_overrides_the_database():
  """The price on screen includes the hint discount; the database price does not.

  Planning on the database price would under-spend, leaving points to be
  destroyed at career end - which is the one thing the end-of-career pass exists
  to prevent.
  """
  if not HAVE_DB:
    return
  full = dict(BY_NAME["Professor of Curvature"])          # 180
  discounted = dict(full, cost=108)                        # what the screen shows
  ok("the discounted copy is cheaper", discounted["cost"] < full["cost"])

  # 300 points buys one at full price, two at the discounted one.
  one = S.plan([full, dict(BY_NAME["Escape Artist"])], 300, style="front")
  two = S.plan([discounted, dict(BY_NAME["Escape Artist"], cost=108)], 300, style="front")
  ok("a discount buys more skills", len(two) >= len(one), f"{len(two)} vs {len(one)}")

def test_the_screen_price_wins():
  """The screen is what will be charged; the database is only a reference.

  This test used to assert the opposite - that a price above the database's
  need_skill_point was a misread - on the reasoning that a hint only makes a
  skill cheaper. Photographing the crop disproved it: "Professor of Curvature"
  really is listed at 306 with the database saying 180, and "On Your Left!" at
  342 against 180. The OCR was right and the rule was wrong.

  It mattered because rejecting those prices made the planner fall back to 180
  for a skill costing 306, understating the spend and letting a plan overrun
  the budget it was supposed to respect.
  """
  if not HAVE_DB:
    return
  ok("a price above the database is kept",
     K.plausible_cost(BY_NAME["It's On!"], 306) == 306)
  ok("a discounted price is kept", K.plausible_cost(BY_NAME["It's On!"], 102) == 102)
  ok("the undiscounted price is kept", K.plausible_cost(BY_NAME["It's On!"], 170) == 170)

  # Only genuinely impossible values are refused.
  ok("zero is not a price", K.plausible_cost(BY_NAME["It's On!"], 0) is None)
  ok("nothing is not a price", K.plausible_cost(BY_NAME["It's On!"], None) is None)
  low, high = K.SKILL_COST_RANGE
  ok("absurdly low is refused", K.plausible_cost(BY_NAME["It's On!"], low - 1) is None)
  ok("absurdly high is refused", K.plausible_cost(BY_NAME["It's On!"], high + 1) is None)

  # And the discount test must not read an expensive listing as a bargain.
  ok("a high price is not max discount",
     not K.at_max_discount(BY_NAME["It's On!"], 306, None))

def test_the_budget_comes_from_the_buy_screen():
  """The lobby's counter is in a different place, and reads garbage here.

  This is what silently disabled the optimizer for a whole career: budget 0
  meant no plan could be made, so the end-of-career pass fell through to buying
  whatever was affordable.
  """
  import utils.constants as C
  ok("the buy screen has its own region", hasattr(C, "SKILL_BUY_PTS_REGION"))
  ok("and it is not the lobby's", C.SKILL_BUY_PTS_REGION != C.SKILL_PTS_REGION)
  ok("it carries the _REGION suffix for its (left, top, width, height) format",
     "SKILL_BUY_PTS_REGION".endswith("_REGION"))

def test_reading_failures_are_safe():
  """Every unreadable thing has to mean 'do not buy', not 'buy anyway'.

  The cost and hint offsets have never been measured against a live buy screen.
  If they are wrong, this is what keeps that from spending points badly.
  """
  if not HAVE_DB:
    return
  skill = BY_NAME["Professor of Curvature"]
  ok("no readings at all means no purchase", not K.at_max_discount(skill, None, None))
  ok("a cost of zero is not a bargain", not K.at_max_discount(skill, 0, None))
  ok("an unknown record is never usable", not K.usable_here(None))

for test in [test_config_is_wired, test_only_usable_skills,
             test_only_A_tier_and_above_is_bought, test_the_floor_is_mid_career_only,
             test_the_configured_list_is_gone,
             test_max_hint_is_the_signal,
             test_price_is_the_fallback, test_end_of_career_plans_within_budget,
             test_screen_price_overrides_the_database,
             test_the_screen_price_wins,
             test_the_budget_comes_from_the_buy_screen,
             test_reading_failures_are_safe]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
