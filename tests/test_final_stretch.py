"""Never resting on the last turns of a career.

Run with `python tests/test_final_stretch.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader.

Straight from a live career on 2026-09-17. At 23:18:23 the bot rested on
`Finale Underway, Turn: 1` - the turn before the last race - holding energy
40.25, which is above the rest gate. Four facilities read Fail 20%, over the
15% bar, so rainbow_training rejected them all; the one safe facility, WIT,
carried a single support and so fell under most_support_card's "at least two"
rule, which returned None and became a rest. WIT was free that turn: Fail 0%,
Energy -0, +15 wit with 480 points of headroom. The rest banked 50 energy that
the career then never got to spend.

The window is five turns, and it is found by the year string rather than the
turn counter, because the counter cannot do the job:

  - Inside the finale it always reads 1. It counts down to the next race day,
    not to the end of the career, so it cannot tell the three finale turns
    apart.
  - In Trackblazer's climax it reads -1, which is outside TURNS_LEFT_RANGE and
    means "unreadable". A rule keyed on the number would never fire there.
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
fake.CURRENT_YEAR = "Finale Underway"
fake.MAX_FAILURE = 15
fake.SKIP_TRAINING_ENERGY = 35
fake.NEVER_REST_ENERGY = 75
fake.SPIRIT_GAUGE_POINTS = 1.0
fake.SPIRIT_BURST_POINTS = 2.0
fake.SPIRIT_BURST_EX_POINTS = 3.0
fake.BURST_ENABLED_STATS = []
fake.ALWAYS_BUY_GOLD_SKILL = False
ENERGY = [40.25]
STATS = {"spd": 1088, "sta": 672, "pwr": 770, "guts": 500, "wit": 419}
fake.check_energy_level = lambda *a, **k: (ENERGY[0], 100)
fake.stat_state = lambda *a, **k: dict(STATS)
fake.stat_caps_state = lambda *a, **k: None
fake.check_current_year = lambda *a, **k: fake.CURRENT_YEAR
fake.check_aptitudes = lambda *a, **k: None
sys.modules["core.state"] = fake

import core  # noqa: E402
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
  """23:18:14-23:18:21 - the board the bot rested away, facility by facility."""
  return {
    "spd": facility("spd", supports=1, failure=20,
                    gains={"spd": 29, "pwr": 22, "skill": 22}),
    "sta": facility("sta", supports=2, failure=20,
                    gains={"sta": 17, "guts": 11, "skill": 12}),
    "pwr": facility("pwr", supports=1, failure=20,
                    gains={"sta": 7, "pwr": 17, "skill": 11}),
    "guts": facility("guts", supports=0, failure=20,
                     gains={"spd": 2, "pwr": 3, "guts": 10, "skill": 10}),
    "wit": facility("wit", supports=1, failure=0,
                    gains={"spd": 3, "wit": 15, "skill": 12}),
  }


def test_the_window_is_the_last_five_turns():
  """Five turns, named by the year string alone."""
  inside = ["Senior Year Early Dec", "Senior Year Late Dec",
            "Finale Underway", "TS Climax Races Underway"]
  for year in inside:
    ok(f"inside the window: {year}", L.career_ending(year) is True)

  outside = ["Junior Year Pre-Debut", "Junior Year Early Dec",
             "Junior Year Late Dec", "Classic Year Early Dec",
             "Classic Year Late Dec", "Senior Year Late Nov",
             "Senior Year Early Jul", "Senior Year Late Aug"]
  for year in outside:
    ok(f"outside it: {year}", L.career_ending(year) is False)


def test_the_earlier_december_turns_are_not_the_window():
  """The trap: only the Senior December is near the end of a career.

  Junior and Classic each have their own December, two thirds and one third of
  a career from the finale, and a rest there is banked for turns that really do
  still exist.
  """
  ok("Junior December is not career end",
     L.career_ending("Junior Year Late Dec") is False)
  ok("Classic December is not career end",
     L.career_ending("Classic Year Late Dec") is False)
  ok("but Senior December is",
     L.career_ending("Senior Year Late Dec") is True)


def test_missing_or_odd_year_text_is_not_the_window():
  for year in (None, "", "   ", "Finale"):
    ok(f"no window for {year!r}", L.career_ending(year) is False)


def test_the_logged_turn_now_trains():
  """The bug. WIT was the only safe facility, and it is what should be taken."""
  L.set_stat_headroom({"spd": 228, "sta": 428, "pwr": 330, "guts": 0, "wit": 480})
  L.set_energy_level(ENERGY[0])
  got = L.final_stretch_action(the_logged_turn())
  ok("the free WIT is taken rather than rested away", got == "wit", got)


def test_a_risky_board_still_rests():
  """An injury before the finals costs more than one turn of stats."""
  L.set_stat_headroom({"spd": 228, "sta": 428, "pwr": 330, "guts": 0, "wit": 480})
  risky = the_logged_turn()
  risky["wit"]["failure"] = 20
  ok("nothing under the failure bar means rest",
     L.final_stretch_action(risky) is None)


def test_an_extreme_burst_counts_as_safe():
  """The burst zeroes the failure chance, so it clears the bar however it reads."""
  L.set_stat_headroom({"spd": 228, "sta": 428, "pwr": 330, "guts": 0, "wit": 480})
  burst = the_logged_turn()
  burst["wit"]["failure"] = 20
  burst["spd"]["unity"]["burst_ex"] = 1
  ok("the burst facility is taken", L.final_stretch_action(burst) == "spd")


def test_the_best_safe_facility_wins_not_merely_the_first():
  L.set_stat_headroom({"spd": 228, "sta": 428, "pwr": 330, "guts": 0, "wit": 480})
  board = {
    "spd": facility("spd", supports=0, failure=0, gains={"spd": 4}),
    "sta": facility("sta", supports=3, own_rainbows=2, failure=0,
                    gains={"sta": 30, "skill": 20}),
    "wit": facility("wit", supports=1, failure=0, gains={"wit": 8}),
  }
  ok("the strongest safe board wins", L.final_stretch_action(board) == "sta")


def test_an_empty_board_is_a_rest():
  ok("nothing on the board means rest", L.final_stretch_action({}) is None)
  ok("and None means rest too", L.final_stretch_action(None) is None)


for test in [test_the_window_is_the_last_five_turns,
             test_the_earlier_december_turns_are_not_the_window,
             test_missing_or_odd_year_text_is_not_the_window,
             test_the_logged_turn_now_trains,
             test_a_risky_board_still_rests,
             test_an_extreme_burst_counts_as_safe,
             test_the_best_safe_facility_wins_not_merely_the_first,
             test_an_empty_board_is_a_rest]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
