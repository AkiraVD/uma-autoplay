"""rainbow_training's filter, and what wit's energy return is worth.

Run with `python tests/test_rainbow.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader.

Two things are pinned here.

**The filter.** The wit guard used to run after max() and return None, so a
facility that won on points but failed its check took every other rainbow
candidate down with it and dropped the bot into most_support_card. Candidates
are filtered before max() now, so the runner-up stands. The wit guard itself is
gone (see below), so the failure limit is what exercises it.

**Wit's energy return.** WIT_MIN_RAINBOWS, a hard exclusion needing two of
wit's own rainbows, and WIT_ENERGY_BAND, a flat bonus between 30 and 70 energy,
both came out on 2026-10-13. Wit now competes on its board like any other
facility, and the energy it hands back is added as a priced bonus. The point of
the change: wit costs NO energy, so on a turn that would otherwise be a rest it
is free stats - the gate was refusing them. Replaying the three recorded Grand
Concert careers, lifting it turned four to six rests a career into wit
trainings.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

fake = types.ModuleType("core.state")
fake.PRIORITY_STAT = ["spd", "pwr", "wit", "sta", "guts"]
fake.PRIORITY_EFFECTS_LIST = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
fake.PRIORITY_WEIGHT = "MEDIUM"
fake.STAT_CAPS = {"spd": 1500, "sta": 500, "pwr": 1200, "guts": 500, "wit": 1100}
fake.CURRENT_YEAR = "Senior Year"
fake.MAX_FAILURE = 15
# core/logic.py::gamble_action reads these off state; they live under
# `gamble_board` in config.json.
fake.GAMBLE_ENABLED = True
fake.GAMBLE_CEILING_FAILURE = 60
fake.GAMBLE_MIN_RAINBOWS = 2
fake.GAMBLE_MIN_GAIN_POINTS = 45
fake.GAMBLE_EV_MARGIN = 1.25
fake.SPIRIT_GAUGE_POINTS = 1.0
fake.SPIRIT_BURST_POINTS = 2.0
fake.SPIRIT_BURST_EX_POINTS = 3.0
fake.BURST_ENABLED_STATS = []
for name in ("check_current_year", "stat_state", "stat_caps_state",
             "check_energy_level", "check_aptitudes"):
  setattr(fake, name, lambda *a, **k: None)
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

def facility(stat, own_rainbows=0, supports=1, hints=0, failure=0, maxed=0):
  """One entry of check_training()'s dict.

  `own_rainbows` are cards of the facility's own type at max bond - the only
  ones that count as rainbows. `maxed` is how many of those sit at the "max"
  level specifically, which is what the energy return is paid on: a card below
  max bond triggers no friendship training and hands back nothing.
  """
  data = {key: {"friendship_levels": levels()} for key in KEYS}
  data[stat] = {"friendship_levels": levels(yellow=own_rainbows, max=maxed)}
  data["total_supports"] = supports
  data["total_hints"] = hints
  data["failure"] = failure
  data["unity"] = {"spirit": 0, "burst": 0, "burst_ex": 0}
  data["gains"] = {}
  return data

def test_wit_energy_return():
  """What a wit training hands back, and what the scorers pay for it."""
  # The measurement this is built on: 0 rainbows +5.1, one +9.3/+9.8, two
  # +14.4, across tests/fixtures/careers. See WIT_RECOVERY_BASE.
  bare = facility("wit")
  one = facility("wit", maxed=1)
  two = facility("wit", maxed=2)
  ok("with no wit card at max bond, wit returns the base",
     L.wit_energy_gain(bare) == L.WIT_RECOVERY_BASE,
     f"{L.wit_energy_gain(bare)}")
  ok("one max-bond wit card adds its recovery",
     L.wit_energy_gain(one) > L.wit_energy_gain(bare))
  ok("and two stack - the additions are not capped",
     (L.wit_energy_gain(two) - L.wit_energy_gain(one)
      == L.wit_energy_gain(one) - L.wit_energy_gain(bare)),
     f"{L.wit_energy_gain(bare)} / {L.wit_energy_gain(one)}"
     f" / {L.wit_energy_gain(two)}")
  # A rainbow below max bond pays nothing: it triggers no friendship training.
  ok("a yellow wit card is not a max-bond one and adds nothing",
     L.wit_energy_gain(facility("wit", own_rainbows=2)) == L.WIT_RECOVERY_BASE)

  # The bonus is worth more the emptier the tank, and nothing on a full one.
  L.set_energy_level(20.0, 100.0)
  lowtank = L.wit_energy_bonus("wit", two)
  L.set_energy_level(60.0, 100.0)
  midtank = L.wit_energy_bonus("wit", two)
  L.set_energy_level(100.0, 100.0)
  fulltank = L.wit_energy_bonus("wit", two)
  ok("the energy bonus is worth most on an empty tank", lowtank > midtank > fulltank,
     f"{lowtank:.3f} > {midtank:.3f} > {fulltank:.3f}")
  ok("...and nothing at all on a full one", fulltank == 0.0, f"{fulltank:.3f}")
  ok("only wit is paid for its energy", L.wit_energy_bonus("spd", two) == 0.0)

  # An unreadable cap must not raise. energy_value used to, and a scorer that
  # throws does not score lower - it takes the decision down another branch,
  # which dropped the 2026-10-13 replay from 97% reproduced to 39%.
  L.set_energy_level(50.0, None)
  try:
    unknown = L.wit_energy_bonus("wit", two)
    raised = None
  except Exception as exc:                                    # noqa: BLE001
    unknown, raised = None, exc
  ok("an unreadable energy cap does not raise", raised is None, str(raised))
  ok("...and still prices the return as worth something", (unknown or 0) > 0,
     f"{unknown}")

  # It is a nudge, not an override: a clearly better training still wins.
  L.set_energy_level(40.0, 100.0)
  results = {
    "wit": facility("wit", own_rainbows=1, supports=2, maxed=1),
    "spd": facility("spd", own_rainbows=3, supports=5),
  }
  ok("a genuinely good training still beats wit's energy",
     L.rainbow_training(results) == "spd")
  L.set_energy_level(None, None)

def main():
  L.set_stat_headroom({"spd": 400, "sta": 300, "pwr": 400, "guts": 300, "wit": 500})
  L.set_energy_level(50.0, 100.0)

  # The filter, with the failure limit as the thing that disqualifies: wit
  # outscores everything on points but is unsafe. It must not take spd with it.
  results = {
    "wit": facility("wit", own_rainbows=2, supports=5, failure=90),
    "spd": facility("spd", own_rainbows=3, supports=3),
  }
  pick = L.rainbow_training(results)
  ok("a disqualified wit leaves the runner-up standing", pick == "spd", str(pick))

  # The whole point: it used to return None here and fall through to the
  # weaker most_support_card scorer.
  ok("and does not abandon rainbow training", pick is not None)

  # Wit is no longer held to a rainbow count of its own. A wit board that wins
  # on supports wins, which is what turns a rest into a free training.
  results = {
    "wit": facility("wit", own_rainbows=1, supports=5, maxed=1),
    "spd": facility("spd", own_rainbows=1, supports=1),
  }
  ok("wit wins on its board, with no rainbow quota to clear",
     L.rainbow_training(results) == "wit")

  # Rainbows still belong to the facility's own type. Cards of other types
  # sitting on the wit tile are not wit rainbows, however friendly they are -
  # they count as supports and nothing more.
  results = {"wit": facility("wit", own_rainbows=0, supports=1)}
  results["wit"]["spd"] = {"friendship_levels": levels(yellow=3)}
  ok("other types at max bond do not count as wit rainbows",
     L.rainbow_training(results) is None)

  # Nothing on the board at all still means no rainbow training.
  results = {"wit": facility("wit", own_rainbows=0, supports=0)}
  ok("an empty wit tile yields nothing", L.rainbow_training(results) is None)

  test_wit_energy_return()

  print("")
  print("FAILED: " + ", ".join(failures) if failures else "all checks passed")
  return 1 if failures else 0

if __name__ == "__main__":
  sys.exit(main())
