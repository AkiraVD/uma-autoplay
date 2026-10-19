"""A board too good to pass up is trained at a failure the config refuses.

Run with `python tests/test_gamble_board.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader.

Taken from a real turn in career 13 (15:04:15, Classic Year Early Oct, Grand
Concert, 28 energy): SPD carried 3 own-type rainbows and printed +87 Speed at
52% failure, and the bot trained a 0-support WIT at 12% for +4 Speed instead.
The failure filter is a hard cutoff, so the strongest board of the whole career
was refused exactly as a one-support board would have been. Taking it was worth
0.48 x 87 = 42 Speed in expectation against the 4 the turn actually banked.

The ceiling is the other half of the rule: the same career showed 3 rainbows and
+73 Speed at 83%, and that one has to stay refused.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

fake = types.ModuleType("core.state")
fake.PRIORITY_STAT = ["spd", "sta", "pwr", "wit", "guts"]
fake.PRIORITY_EFFECTS_LIST = {0: 4.5, 1: 1.4, 2: 1.4, 3: 0.0, 4: 0.6}
fake.PRIORITY_WEIGHT = "HEAVY"
fake.STAT_CAPS = {"spd": 1600, "sta": 800, "pwr": 850, "guts": 600, "wit": 1100}
fake.CURRENT_YEAR = "Classic Year"
# The bar the career actually ran under, so the board really is over it.
fake.MAX_FAILURE = 18
# The rule's own settings now live in config under `gamble_board`.
fake.GAMBLE_ENABLED = True
fake.GAMBLE_CEILING_FAILURE = 60
fake.GAMBLE_MIN_RAINBOWS = 2
fake.GAMBLE_MIN_GAIN_POINTS = 45
fake.GAMBLE_EV_MARGIN = 1.25
fake.SKIP_TRAINING_ENERGY = 35
fake.NEVER_REST_ENERGY = 75
fake.SPIRIT_GAUGE_POINTS = 1.0
fake.SPIRIT_BURST_POINTS = 2.0
fake.SPIRIT_BURST_EX_POINTS = 3.0
fake.BURST_ENABLED_STATS = []
fake.ALWAYS_BUY_GOLD_SKILL = False
fake.UNITY_SEEN = False
fake.GRAND_CONCERT_SEEN = True
fake.URA_CHASE_DUELS = False
ENERGY = [27.97]
MAX_ENERGY = 104
STATS = {"spd": 1058, "sta": 571, "pwr": 640, "guts": 390, "wit": 487}
fake.check_energy_level = lambda *a, **k: (ENERGY[0], MAX_ENERGY)
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

def facility(stat, own_rainbows=0, supports=1, failure=0, gains=None,
             energy_cost=0):
  data = {key: {"friendship_levels": levels()} for key in KEYS}
  data[stat] = {"friendship_levels": levels(max=own_rainbows)}
  data["total_supports"] = supports
  data["total_hints"] = 0
  data["total_friendship_levels"] = levels(max=own_rainbows)
  data["failure"] = failure
  data["unity"] = {"spirit": 0, "burst": 0, "burst_ex": 0}
  data["gains"] = gains or {}
  data["energy_cost"] = energy_cost
  return data

def the_logged_turn():
  """15:04:15 - SPD is three rainbows deep at 52%, and only WIT is safe."""
  return {
    "spd": facility("spd", own_rainbows=3, supports=3, failure=52,
                    gains={"spd": 87, "pwr": 6}, energy_cost=-25),
    "sta": facility("sta", supports=1, failure=32,
                    gains={"sta": 12, "guts": 9}, energy_cost=-18),
    "pwr": facility("pwr", supports=0, failure=48,
                    gains={"sta": 5, "pwr": 11}, energy_cost=-20),
    "guts": facility("guts", supports=2, failure=51,
                     gains={"spd": 7, "pwr": 4, "guts": 13}, energy_cost=-20),
    "wit": facility("wit", supports=0, failure=12,
                    gains={"spd": 4, "wit": 10}, energy_cost=0),
  }

def main():
  L.set_stat_headroom(dict(STATS))
  L.set_energy_level(ENERGY[0], MAX_ENERGY)

  board = the_logged_turn()
  picked = L.gamble_action(board, ENERGY[0], MAX_ENERGY)
  ok("the three-rainbow 52% board is taken", picked and picked[0] == "spd",
     repr(picked))
  ok("and it says why in the log line",
     bool(picked) and "52% failure" in picked[1], repr(picked and picked[1]))

  # The whole point: the real career trained the safe 0-support wit instead.
  ok("do_something trains it rather than the safe thin wit",
     L.do_something(the_logged_turn()) == "spd")

  # The ceiling, from the same career's Senior Late Jul board.
  over = the_logged_turn()
  over["spd"]["failure"] = 83
  ok("an 83% board stays refused",
     L.gamble_action(over, ENERGY[0], MAX_ENERGY) is None)

  # The boundary itself, either side of it.
  at = the_logged_turn()
  at["spd"]["failure"] = fake.GAMBLE_CEILING_FAILURE
  ok(f"a board exactly at the {fake.GAMBLE_CEILING_FAILURE}% ceiling is allowed",
     bool(L.gamble_action(at, ENERGY[0], MAX_ENERGY)))
  past = the_logged_turn()
  past["spd"]["failure"] = fake.GAMBLE_CEILING_FAILURE + 1
  ok("one point past the ceiling is not",
     L.gamble_action(past, ENERGY[0], MAX_ENERGY) is None)

  # The quality gates. A risky board that is merely ordinary must not qualify,
  # or the rule becomes a blanket raise of maximum_failure.
  thin = the_logged_turn()
  thin["spd"][ "spd"] = {"friendship_levels": levels(max=1)}
  ok("one rainbow is not enough",
     L.gamble_action(thin, ENERGY[0], MAX_ENERGY) is None)

  small = the_logged_turn()
  small["spd"]["gains"] = {"spd": 20, "pwr": 4}
  ok("a small printed board is not enough",
     L.gamble_action(small, ENERGY[0], MAX_ENERGY) is None)

  # Skill points are not stat points, so they must not carry the gate.
  skill_only = the_logged_turn()
  skill_only["spd"]["gains"] = {"spd": 20, "skill": 60}
  ok("skill points do not get a board over the gains gate",
     L.gamble_action(skill_only, ENERGY[0], MAX_ENERGY) is None)

  # A board the tank cannot pay for is a stall, not a gamble: the energy goes
  # whether or not the training succeeds.
  ok("a board costing more energy than the tank holds is refused",
     L.gamble_action(the_logged_turn(), 20.0, MAX_ENERGY) is None)

  # Nothing to override: at or under the bar the ordinary scorers own the turn.
  safe = the_logged_turn()
  safe["spd"]["failure"] = fake.MAX_FAILURE
  ok("a board inside the failure bar is not handled here",
     L.gamble_action(safe, ENERGY[0], MAX_ENERGY) is None)

  # It has to beat what the turn could otherwise train, not merely exist.
  rival = the_logged_turn()
  rival["wit"] = facility("wit", own_rainbows=3, supports=3, failure=5,
                          gains={"spd": 40, "wit": 70}, energy_cost=0)
  ok("a strong safe board keeps the turn",
     L.gamble_action(rival, ENERGY[0], MAX_ENERGY) is None)

  # Wit returns energy, so it is never the facility this rule reaches for.
  wit_gamble = the_logged_turn()
  wit_gamble["wit"] = facility("wit", own_rainbows=3, supports=3, failure=52,
                               gains={"wit": 90}, energy_cost=0)
  wit_gamble["spd"]["failure"] = 5
  ok("wit is never the gamble",
     L.gamble_action(wit_gamble, ENERGY[0], MAX_ENERGY) is None)

  # The config's own settings reach the rule, so the page can tune it.
  fake.GAMBLE_CEILING_FAILURE = 50
  ok("a ceiling lowered in config refuses the 52% board",
     L.gamble_action(the_logged_turn(), ENERGY[0], MAX_ENERGY) is None)
  fake.GAMBLE_CEILING_FAILURE = 60

  fake.GAMBLE_MIN_RAINBOWS = 4
  ok("a rainbow bar raised in config refuses it too",
     L.gamble_action(the_logged_turn(), ENERGY[0], MAX_ENERGY) is None)
  fake.GAMBLE_MIN_RAINBOWS = 2

  fake.GAMBLE_ENABLED = False
  ok("config gamble_board.enabled=false turns the rule off",
     L.gamble_action(the_logged_turn(), ENERGY[0], MAX_ENERGY) is None)
  fake.GAMBLE_ENABLED = True

  # The off switch, so tools/career_replay.py's base arm is really the old bot.
  L.GAMBLE_ON_GREAT_BOARD = False
  ok("the replay flag turns the whole rule off",
     L.gamble_action(the_logged_turn(), ENERGY[0], MAX_ENERGY) is None)
  L.GAMBLE_ON_GREAT_BOARD = True

  print()
  if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    return 1
  print("all checks passed")
  return 0

if __name__ == "__main__":
  sys.exit(main())
