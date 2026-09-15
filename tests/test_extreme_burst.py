"""An Extreme Spirit Burst outranks every rest gate.

Run with `python tests/test_extreme_burst.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader.

Taken from a real turn in the log (18:31:58, Unity Cup, Mihono Bourbon): WIT
was showing an Extreme burst, 0% failure and 58 wit + 39 skill, and the bot
rested because energy had fallen to 25. The rest gate in most_support_card is
an energy check, not a safety check, and an Extreme burst is exactly the case
where low energy no longer argues for resting - the failure chance is 0 by
definition and the gains are several times a normal facility.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

fake = types.ModuleType("core.state")
fake.PRIORITY_STAT = ["spd", "wit", "sta", "pwr", "guts"]
fake.PRIORITY_EFFECTS_LIST = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
fake.PRIORITY_WEIGHT = "MEDIUM"
fake.STAT_CAPS = {"spd": 1316, "sta": 1100, "pwr": 700, "guts": 400, "wit": 1100}
fake.CURRENT_YEAR = "Classic Year"
fake.MAX_FAILURE = 15
fake.SKIP_TRAINING_ENERGY = 35
fake.NEVER_REST_ENERGY = 75
fake.SPIRIT_GAUGE_POINTS = 1.0
fake.SPIRIT_BURST_POINTS = 2.0
fake.SPIRIT_BURST_EX_POINTS = 3.0
fake.BURST_ENABLED_STATS = []
# Off: this is not a Grand Concert run, so the 18-song push must not weigh in.
fake.ALWAYS_BUY_GOLD_SKILL = False
ENERGY = [25.0]
# The stats that turn had, so the cap filter behaves as it did in the career.
STATS = {"spd": 415, "sta": 232, "pwr": 311, "guts": 217, "wit": 244}
fake.check_energy_level = lambda *a, **k: (ENERGY[0], 100)
fake.stat_state = lambda *a, **k: dict(STATS)
fake.stat_caps_state = lambda *a, **k: None
fake.check_current_year = lambda *a, **k: fake.CURRENT_YEAR
fake.check_aptitudes = lambda *a, **k: None
sys.modules["core.state"] = fake

import core
core.state = fake
import core.logic as L  # noqa: E402

KEYS = ["spd", "sta", "pwr", "guts", "wit"]
failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def levels(**kw):
  base = {"gray": 0, "blue": 0, "green": 0, "yellow": 0, "max": 0}
  base.update(kw)
  return base

def facility(stat, own_rainbows=0, supports=1, hints=0, failure=0,
             burst_ex=0, gains=None):
  data = {key: {"friendship_levels": levels()} for key in KEYS}
  data[stat] = {"friendship_levels": levels(yellow=own_rainbows)}
  data["total_supports"] = supports
  data["total_hints"] = hints
  data["total_friendship_levels"] = levels()
  data["failure"] = failure
  data["unity"] = {"spirit": 0, "burst": 0, "burst_ex": burst_ex}
  data["gains"] = gains or {}
  return data

def the_logged_turn():
  """18:31:58 - wit carries the burst, everything else is thin and risky."""
  return {
    "spd": facility("spd", supports=0, failure=20),
    "sta": facility("sta", supports=0, failure=20),
    "pwr": facility("pwr", supports=0, failure=20),
    "guts": facility("guts", supports=0, failure=20),
    "wit": facility("wit", own_rainbows=2, supports=3, failure=0, burst_ex=1,
                    gains={"spd": 15, "wit": 58, "skill": 39}),
  }

def main():
  L.set_stat_headroom({"spd": 901, "sta": 868, "pwr": 389, "guts": 183, "wit": 856})
  L.set_energy_level(ENERGY[0])

  ok("the burst facility is the one found",
     L.best_extreme_burst(the_logged_turn()) == "wit")
  ok("and nothing is found when no burst is up",
     L.best_extreme_burst({"spd": facility("spd", supports=3)}) is None)

  # The bug, straight from the log.
  ENERGY[0] = 25.0
  L.set_energy_level(25.0)
  ok("energy 25 no longer rests the burst away",
     L.most_support_card(the_logged_turn()) == "wit")

  # Without the burst the same turn should still rest - the gate is not gone.
  bare = the_logged_turn()
  bare["wit"]["unity"]["burst_ex"] = 0
  ok("and a burst-less low-energy turn still rests",
     L.most_support_card(bare) is None)

  # do_something is the net over every path, including rainbow_training's None
  # and the two rests inside the "only 1 support" branches.
  ok("do_something trains the burst rather than resting",
     L.do_something(the_logged_turn()) == "wit")

  # A capped stat is still worth nothing, burst or not.
  fake.STAT_CAPS = dict(fake.STAT_CAPS, wit=200)
  ok("a burst on a capped stat is not resurrected",
     L.do_something(the_logged_turn()) != "wit")
  fake.STAT_CAPS = dict(fake.STAT_CAPS, wit=1100)

  # The support-count ladder rests on thin facilities to bank the energy. A
  # burst has no odds left to improve on, so thinness stops mattering.
  # Energy above SKIP_TRAINING_ENERGY so the first gate is not what answers,
  # and below NEVER_REST_ENERGY so the ladder really would have skipped.
  ENERGY[0] = 50.0
  L.set_energy_level(50.0)
  thin = {"wit": facility("wit", supports=1, failure=0, burst_ex=1,
                          gains={"wit": 44, "skill": 32})}
  ok("a one-support burst is trained, not banked",
     L.most_support_card(thin) == "wit")
  thin["wit"]["unity"]["burst_ex"] = 0
  ok("and a one-support WIT with no burst is still skipped",
     L.most_support_card(thin) is None)

  # An outing bids highest when the tank is low, which is the same turn a burst
  # is most at risk. The outing keeps until next turn; the burst does not.
  L.outings.next_outing = lambda *a, **k: ({"energy": 40.0}, "step 2")
  args = (0.5, False, 25.0, 100, 2, 3, True, False)
  ok("Recreation would otherwise take this turn",
     L.should_recreate(*args) is not None)
  ok("but not with a burst ready",
     L.should_recreate(*args, burst_ready=True) is None)

  # Two bursts: the better facility wins.
  both = the_logged_turn()
  both["spd"] = facility("spd", own_rainbows=3, supports=5, failure=0, burst_ex=1,
                         gains={"spd": 90, "skill": 40})
  ok("with two bursts the stronger facility is chosen",
     L.best_extreme_burst(both) == "spd")

  print()
  if failures:
    print(f"{len(failures)} failing: " + ", ".join(failures))
    return 1
  print("all good")
  return 0

if __name__ == "__main__":
  sys.exit(main())
