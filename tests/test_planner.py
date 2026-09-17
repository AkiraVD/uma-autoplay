"""The race-vs-train planner: core/planner.py.

Run with `python tests/test_planner.py` from the repo root. Pure logic, no OCR
and no stubbing needed - core.planner imports nothing from core.

The cases that matter are the ones drawn from real turns, so they are marked.
Every goal string here was copied out of a log, OCR damage and all.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.planner as P   # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def test_parses_the_two_measurable_goals():
  """Fans give the remainder directly; Result Pts give target and progress."""
  ok("fans: the 'to go' figure is the remainder",
     P.parse_goal("Earn 5000 fans Progress 3,828 fan(s) to go") == ("fans", 3828))
  ok("result pts: remaining is target minus done",
     P.parse_goal("300 Result Pts Progress Aftert 88 pts") == ("points", 212))
  ok("and the other OCR spelling of After",
     P.parse_goal("300 Result Pts Progress After' 128 pts") == ("points", 172))

def test_the_fans_target_is_ignored_on_purpose():
  """A real log reads 'Earn 3000 fans ... 4,434 to go' - the target is wrong."""
  got = P.parse_goal("Earn 3000 fans Progress 4,434 fan(s) to go")
  ok("the impossible target is not used", got == ("fans", 4434), got)

def test_goals_with_nothing_to_decide():
  for text in ("50 Result Pts Goal Achievedl MAX",
               "50 Result Pts Goal Achievedl MMAX",
               "Earn 3000 fans Goal Achievedl"):
    ok(f"achieved -> None ({text[:24]}...)", P.parse_goal(text) is None)
  ok("a forced race is not the planner's business",
     P.parse_goal("Place Ist in Tenno Sho (Autumn) Entry criteria metl") is None)
  ok("top-3 objectives likewise",
     P.parse_goal("Place top 3 in Arima Kinen Entry criteria metl") is None)
  ok("unrecognised text is None, not a guess",
     P.parse_goal("Run in Junior Make Debut") is None)
  ok("and so is empty", P.parse_goal("") is None and P.parse_goal(None) is None)

def test_energy_decides_before_anything_else():
  """Measured: three of seven turns were settled by energy alone.

  The sharpest was energy 33 against a threshold of 35, on the turn holding the
  joint-highest training score in the sample. The bot rested. Under this rule
  it races instead, which is your gate.
  """
  standout = {"spd": 5.76, "pwr": 3.51, "sta": 2.81, "guts": 0.83, "wit": 0.78}
  action, why = P.decide(("points", 100), 10, 33, standout, skip_training_energy=35)
  ok("energy 33 < 35 races rather than rests", action == "race", f"{action}: {why}")
  action, _ = P.decide(("points", 100), 10, 1.7, standout, skip_training_energy=35)
  ok("and energy 1.7 too, since 1.7 > 0", action == "race")
  action, why = P.decide(("points", 100), 10, 0, standout, skip_training_energy=35)
  ok("but zero energy cannot race either", action is None, why)

def test_no_slack_forces_a_race():
  """Your example: need 2, none banked, only 2 chances left - must race."""
  standout = {"spd": 8.42, "sta": 3.54, "pwr": 2.22, "wit": 0.71, "guts": 0.66}
  action, why = P.decide(("points", 2), 2, 60, standout, skip_training_energy=35)
  ok("slack 0 races even past a standout board", action == "race", why)
  action, _ = P.decide(("points", 3), 2, 60, standout, skip_training_energy=35)
  ok("and negative slack races too", action == "race")

def test_with_slack_the_board_decides():
  """The ratio, not the absolute score - both boards clear an absolute bar."""
  flat = {"guts": 2.98, "sta": 2.81, "wit": 2.53, "pwr": 2.04, "spd": 1.10}
  standout = {"spd": 8.42, "sta": 3.54, "pwr": 2.22, "wit": 0.71, "guts": 0.66}
  a1, w1 = P.decide(("points", 2), 10, 60, flat, skip_training_energy=35)
  a2, w2 = P.decide(("points", 2), 10, 60, standout, skip_training_energy=35)
  ok("a flat board is cheap to spend racing", a1 == "race", w1)
  ok("a standout board is kept for training", a2 == "train", w2)
  ok("both would clear an absolute bar of 2.0",
     max(flat.values()) >= 2.0 and max(standout.values()) >= 2.0)

def test_the_ratio_matches_the_measured_turns():
  """Ratios seen live ran 1.18 to 3.79; the threshold sits between them."""
  turns = [("Late Nov flat", {"a": 2.98, "b": 2.53, "c": 1.10}, False),
           ("Late Dec standout", {"a": 8.42, "b": 2.22, "c": 0.66}, True)]
  for label, scores, expect_keep in turns:
    got = P.training_is_worth_keeping(scores)
    ok(f"{label} -> keep={expect_keep}", got == expect_keep, got)

def test_degenerate_boards():
  ok("no scores is not worth keeping", P.training_is_worth_keeping({}) is False)
  ok("all zero is not worth keeping", P.training_is_worth_keeping({"a": 0, "b": 0}) is False)
  ok("a single positive option counts", P.training_is_worth_keeping({"a": 1.0}) is True)

def test_no_opinion_cases():
  """None must mean 'use the existing logic', never 'do nothing'."""
  a, _ = P.decide(None, 10, 60, {"a": 3.0}, skip_training_energy=35)
  ok("no measurable goal -> no opinion", a is None)
  a, _ = P.decide(("points", 5), None, 60, {"a": 3.0}, skip_training_energy=35)
  ok("no race count -> no opinion", a is None)
  a, _ = P.decide(("points", 5), 10, None, {"a": 3.0}, skip_training_energy=35)
  ok("unknown energy -> no opinion", a is None)
  a, _ = P.decide(("points", 0), 10, 60, {"a": 3.0}, skip_training_energy=35)
  ok("an already-met goal -> no opinion", a is None)

def test_slack_arithmetic():
  ok("spare chances", P.slack(2, 5) == 3)
  ok("exactly enough is no slack", P.slack(5, 5) == 0)
  ok("impossible is negative", P.slack(9, 5) == -4)

for test in [test_parses_the_two_measurable_goals,
             test_the_fans_target_is_ignored_on_purpose,
             test_goals_with_nothing_to_decide,
             test_energy_decides_before_anything_else,
             test_no_slack_forces_a_race,
             test_with_slack_the_board_decides,
             test_the_ratio_matches_the_measured_turns,
             test_degenerate_boards,
             test_no_opinion_cases,
             test_slack_arithmetic]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
