"""Chasing the 18th song: capped facilities and the rest override.

Run with `python tests/test_gold_push.py` from the repo root.

Career 6 finished on 17 songs twice over: the one facility paying the needed
Vi was Guts, capped at 400 with 556 trained, and on two other turns the bot
banked energy for summer camp with the needed chip on the board.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.logic as logic        # noqa: E402
import core.state as state        # noqa: E402
import core.lessons as lessons    # noqa: E402

state.reload_config()
state.STAT_CAPS = {"spd": 1600, "sta": 1100, "pwr": 1100, "guts": 400, "wit": 1200}

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def facility(types, short, urgent=True, failure=0, supports=2):
  return {"performance": {"types": types, "short": short, "urgent": urgent},
          "failure": failure, "total_supports": supports, "total_friendship": 0,
          "gains": {}, "unity": {}, "levels": {}}

CAPS = {"spd": 1600, "sta": 1100, "pwr": 1100, "guts": 400, "wit": 1200}

def test_capped_facility_is_kept_when_it_alone_pays():
  results = {
    "spd": facility(["da"], ["vi"]),
    "guts": facility(["vi"], ["vi"]),
  }
  stats = {"spd": 1100, "guts": 556}          # guts is over its 400 cap
  kept = logic.filter_by_stat_caps(results, stats, CAPS)
  ok("the capped facility is kept when it is the only one paying", "guts" in kept, list(kept))
  ok("and the uncapped one is still there", "spd" in kept)
  # With another facility paying the same type, the cap holds.
  results["sta"] = facility(["vi"], ["vi"])
  stats["sta"] = 600
  kept = logic.filter_by_stat_caps(results, stats, CAPS)
  ok("but not when an uncapped facility pays it too", "guts" not in kept, list(kept))
  # And nothing changes when the board is not urgent.
  calm = {"spd": facility(["da"], ["vi"], urgent=False), "guts": facility(["vi"], ["vi"], urgent=False)}
  kept = logic.filter_by_stat_caps(calm, {"spd": 1100, "guts": 556}, CAPS)
  ok("a capped facility stays out when nothing is urgent", "guts" not in kept, list(kept))

def test_the_rest_override_is_opt_in():
  lessons.reset()
  lessons._songs.update({0: 3, 1: 4, 2: 4, 3: 4, 4: 1})    # 17 of 18
  state.CURRENT_YEAR = "Senior Year Late Sep"
  state.MAX_FAILURE = 15
  state.SKIP_TRAINING_ENERGY = 25
  state.PRIORITY_STAT = ["spd", "sta", "wit", "pwr", "guts"]
  state.PRIORITY_EFFECTS_LIST = {0: 1.25, 1: 1.25, 2: 1, 3: 0, 4: -1}
  state.PRIORITY_WEIGHT = "MEDIUM"
  state.PERFORMANCE_SHORT_POINTS, state.PERFORMANCE_URGENT_POINTS = 0.75, 4.0
  results = {"spd": facility(["da"], ["vi"]), "guts": facility(["vi"], ["vi"])}

  state.ALWAYS_BUY_GOLD_SKILL = False
  ok("off by default: no override", logic.gold_push_action(results, 60) is None)

  state.ALWAYS_BUY_GOLD_SKILL = True
  ok("on: the facility paying the needed type is taken",
     logic.gold_push_action(results, 60) == "guts", logic.gold_push_action(results, 60))
  ok("but never on an empty tank", logic.gold_push_action(results, 10) is None)
  risky = {"guts": facility(["vi"], ["vi"], failure=40)}
  ok("and never a training that would fail", logic.gold_push_action(risky, 60) is None)
  # Once the 18th is in, the push is over.
  lessons._songs.update({4: 2})
  ok("and not once 18 songs are learned", logic.gold_push_action(results, 60) is None)
  lessons.reset()
  state.ALWAYS_BUY_GOLD_SKILL = False

for test in [test_capped_facility_is_kept_when_it_alone_pays, test_the_rest_override_is_opt_in]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
