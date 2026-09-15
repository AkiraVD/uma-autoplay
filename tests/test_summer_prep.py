"""Banking energy for summer camp.

Run with `python tests/test_summer_prep.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader.

Camp is Early Jul to Late Aug of the Classic and Senior years - four turns
whose trainings are the strongest of the career. In the Classic camp of a live
run the bot trained three of the four and rested the fourth on energy 30, so
the turns before camp now bank energy instead of spending it. Wit is preferred
to a plain rest where it still leaves camp in reach, because wit hands energy
back rather than spending it.
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
fake.STAT_CAPS = {"spd": 1316, "sta": 1100, "pwr": 1100, "guts": 300, "wit": 1100}
fake.CURRENT_YEAR = "Senior Year Late Jun"
fake.MAX_FAILURE = 15
fake.SKIP_TRAINING_ENERGY = 35
fake.NEVER_REST_ENERGY = 75
fake.SPIRIT_GAUGE_POINTS = 1.0
fake.SPIRIT_BURST_POINTS = 2.0
fake.SPIRIT_BURST_EX_POINTS = 3.0
fake.BURST_ENABLED_STATS = []
# Off: this is not a Grand Concert run, so the 18-song push must not weigh in.
fake.ALWAYS_BUY_GOLD_SKILL = False
ENERGY = [26.7]
STATS = {"spd": 1088, "sta": 672, "pwr": 770, "guts": 500, "wit": 419}
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

def facility(stat, own_rainbows=0, supports=1, failure=0, burst_ex=0):
  data = {key: {"friendship_levels": levels()} for key in KEYS}
  data[stat] = {"friendship_levels": levels(yellow=own_rainbows)}
  data["total_supports"] = supports
  data["total_hints"] = 0
  data["total_friendship_levels"] = levels()
  data["failure"] = failure
  data["unity"] = {"spirit": 0, "burst": 0, "burst_ex": burst_ex}
  data["gains"] = {}
  return data

def board(wit_rainbows=0, wit_failure=0, burst_on=None):
  b = {k: facility(k, supports=2) for k in KEYS}
  b["wit"] = facility("wit", own_rainbows=wit_rainbows, supports=2, failure=wit_failure)
  if burst_on:
    b[burst_on] = facility(burst_on, own_rainbows=2, supports=3, burst_ex=1)
  return b

def camp_board(wit_rainbows=1, wit_failure=12, others_failure=20, burst_on=None):
  """Senior Early Aug as it actually read: wit alone under the threshold.

  [WIT] 1 support at max bond, Fail 12%, Burst 1, Gains {spd 4, wit 33, skill 13}
  every other facility Fail 20%, over MAX_FAILURE of 15.
  """
  b = {k: facility(k, supports=2, failure=others_failure) for k in KEYS}
  b["wit"] = facility("wit", own_rainbows=wit_rainbows, supports=1,
                      failure=wit_failure)
  if burst_on:
    b[burst_on] = facility(burst_on, own_rainbows=2, supports=3,
                           failure=others_failure, burst_ex=1)
  return b

def main():
  # --- the calendar ------------------------------------------------------
  ok("Late Jun of Senior is one turn from camp",
     L.turns_until_summer("Senior Year Late Jun") == 1)
  ok("Early Jun is two",
     L.turns_until_summer("Classic Year Early Jun") == 2)
  ok("Junior has no camp",
     L.turns_until_summer("Junior Year Late Jun") is None)
  ok("nothing to prepare once camp has started",
     L.turns_until_summer("Senior Year Early Jul") is None)
  ok("and nothing in the second half of the year",
     L.turns_until_summer("Senior Year Late Oct") is None)
  for odd in ("Junior Year Pre-Debut", "Finale Season", "", None):
     ok(f"{odd!r} does not blow up", L.turns_until_summer(odd) is None)

  # --- the decision ------------------------------------------------------
  # The real parked turn: Senior Late Jun on 26.7 energy, no rainbow wit.
  ok("one turn out and far short: rest",
     L.summer_prep_action(board(), "Senior Year Late Jun", 26.7) == L.SUMMER_REST)

  # Same turn, but wit carries a rainbow. One turn is not enough for wit to
  # close a 43-energy gap, so the rest still wins.
  ok("a rainbow wit does not rescue the last turn from a big gap",
     L.summer_prep_action(board(wit_rainbows=2), "Senior Year Late Jun", 26.7)
     == L.SUMMER_REST)

  # Two turns out, same tank: wit now, rest later, and camp is still reached.
  ok("two turns out with a rainbow wit: train wit, not rest",
     L.summer_prep_action(board(wit_rainbows=2), "Classic Year Early Jun", 26.7) == "wit")
  ok("two turns out without one: defer, train normally",
     L.summer_prep_action(board(), "Classic Year Early Jun", 26.7) is None)

  # A tank so low that the last turn alone could not close it.
  ok("very low two turns out: rest now",
     L.summer_prep_action(board(), "Classic Year Early Jun", 12) == L.SUMMER_REST)

  # Close to the target, one turn out: wit both trains and tops up.
  ok("nearly there with a rainbow wit: take wit",
     L.summer_prep_action(board(wit_rainbows=1), "Senior Year Late Jun", 66) == "wit")

  # An unsafe wit is not a banking option.
  ok("an unsafe wit is not taken",
     L.summer_prep_action(board(wit_rainbows=2, wit_failure=40),
                          "Senior Year Late Jun", 66) == L.SUMMER_REST)

  # Already stocked.
  ok("no prep when the tank is already full enough",
     L.summer_prep_action(board(), "Senior Year Late Jun", 70) is None)

  # An Extreme burst outranks the whole thing.
  ok("an Extreme burst still wins the turn",
     L.summer_prep_action(board(burst_on="spd"), "Senior Year Late Jun", 26.7) == "spd")

  # --- end to end through do_something ------------------------------------
  L.set_stat_headroom({k: 400 for k in KEYS})
  ENERGY[0] = 26.7
  L.set_energy_level(26.7)
  fake.CURRENT_YEAR = "Senior Year Late Jun"
  ok("do_something rests on the parked turn", L.do_something(board()) is None)
  fake.CURRENT_YEAR = "Classic Year Early Jun"
  ok("do_something takes the rainbow wit two turns out",
     L.do_something(board(wit_rainbows=2)) == "wit")
  fake.CURRENT_YEAR = "Senior Year Early Jul"
  ok("and does nothing special once camp has started",
     L.do_something(board(wit_rainbows=2)) is not None)

  # --- inside camp -------------------------------------------------------
  ok("Early Jul has four camp turns left",
     L.camp_turns_left("Senior Year Early Jul") == 4)
  ok("Late Aug has one",
     L.camp_turns_left("Classic Year Late Aug") == 1)
  ok("June is not camp",
     L.camp_turns_left("Senior Year Late Jun") is None)
  ok("and neither is Junior July",
     L.camp_turns_left("Junior Year Early Jul") is None)

  # The rescue lives in do_something now, so it catches every road to a
  # rest rather than only the ones an empty tank caused.
  fake.CURRENT_YEAR = "Senior Year Early Aug"
  ENERGY[0] = 26.7
  L.set_energy_level(26.7)
  ok("a rest inside camp becomes the safe wit",
     L.do_something(camp_board()) == "wit")
  fake.CURRENT_YEAR = "Senior Year Late Aug"
  ok("even on the last camp turn, where a rest is still a wasted turn",
     L.do_something(camp_board()) == "wit")
  ok("but not when wit is unsafe too - nothing to rescue it with",
     L.do_something(camp_board(wit_failure=40)) is None)
  ok("a thin wit still beats resting, rainbows or not",
     L.do_something(camp_board(wit_rainbows=0)) == "wit")

  # Classic Late Aug, live: energy 38.98 - above the rest gate - but every
  # facility except a no-support wit read 20% failure, so the turn rested
  # through the "only 1 support and it is WIT" branch. The old rescue keyed
  # on energy and never saw it.
  fake.CURRENT_YEAR = "Classic Year Late Aug"
  ENERGY[0] = 38.98
  L.set_energy_level(38.98)
  ok("a high-failure board rests no camp turn either",
     L.do_something(camp_board(wit_rainbows=0, wit_failure=0)) == "wit")
  ok("and outside camp that same board still rests",
     (lambda: (setattr(fake, "CURRENT_YEAR", "Classic Year Late Oct"),
               L.do_something(camp_board(wit_rainbows=0, wit_failure=0)))[1])() is None)
  ENERGY[0] = 26.7
  L.set_energy_level(26.7)

  # Preventive: 52 energy would train down to 27 and push the rest to the
  # next turn, so a rainbow wit takes this one instead.
  ok("a training that would empty the tank yields to a rainbow wit",
     L.camp_action(camp_board(others_failure=0), "Senior Year Late Jul", 52.1) == "wit")
  ok("but not on the last turn, which has nothing left to protect",
     L.camp_action(camp_board(others_failure=0), "Senior Year Late Aug", 52.1) is None)
  ok("and not without a rainbow wit to take",
     L.camp_action(camp_board(wit_rainbows=0, others_failure=0),
                   "Senior Year Late Jul", 52.1) is None)

  # A full tank early in camp just takes the best training.
  ok("a full tank leaves the turn to the normal path",
     L.camp_action(camp_board(others_failure=0), "Senior Year Early Jul", 77.5) is None)

  # An Extreme burst outranks the wit steering either way.
  ok("an Extreme burst wins the rescue case",
     L.camp_action(camp_board(burst_on="spd"), "Senior Year Early Aug", 26.7) == "spd")

  # Outside camp none of this applies.
  ok("no camp steering in October",
     L.camp_action(camp_board(), "Senior Year Early Oct", 26.7) is None)

  print()
  if failures:
    print(f"{len(failures)} failing: " + ", ".join(failures))
    return 1
  print("all good")
  return 0

if __name__ == "__main__":
  sys.exit(main())
