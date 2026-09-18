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
  """Both kinds report what is still outstanding, not what has been earned."""
  ok("fans: the 'to go' figure is the remainder",
     P.parse_goal("Earn 5000 fans Progress 3,828 fan(s) to go") == ("fans", 3828))
  ok("result pts: the trailing figure IS the remainder",
     P.parse_goal("300 Result Pts Progress Aftert 88 pts") == ("points", 88))
  ok("and the other OCR spelling of After",
     P.parse_goal("300 Result Pts Progress After' 128 pts") == ("points", 128))


def test_the_result_pts_countdown_measured_live():
  """One goal watched start to finish, 2026-09-18, Trackblazer/Maruzensky.

  This is the sequence that caught the inversion. The figure opens at the
  target with nothing earned and falls to near zero before the goal reads
  achieved, so it is the remainder. Read as progress it would have to start
  at 0 and climb, and `target - figure` would call this fresh goal met on its
  very first turn.
  """
  seen = ["300 Result Pts Progress Aftert 300 pts",
          "300 Result Pts Progress Aftert 240 pts",
          "300 Result Pts Progress Aftert 200 pts",
          "300 Result Pts Progress After' 140 pts",
          "300 Result Pts Progress Aftert 100 pts",
          "300 Result Pts Progress After' 20 pts"]
  got = [P.parse_goal(line) for line in seen]
  ok("the first turn of a 300 pt goal needs all 300",
     got[0] == ("points", 300), got[0])
  ok("the last turn before achieved needs only 20",
     got[-1] == ("points", 20), got[-1])
  values = [g[1] for g in got]
  ok("and the remainder falls monotonically",
     all(a > b for a, b in zip(values, values[1:])), values)
  ok("then achieved is nothing to plan for",
     P.parse_goal("300 Result Pts Goal Achievedl MAX") is None)

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

def test_a_met_goal_never_races_however_low_the_energy():
  """The ordering bug, straight off a live turn.

  Senior Early Dec 2026-09-18, two turns from the finale: the goal read
  `300 Result Pts Goal Achievedl MAX` and energy was 22 against a floor of 35.
  The energy rule fired before the goal was examined and advised racing for a
  goal that needed nothing - which would have spent the turn and reached the
  finale weaker. The real logic rested, and was right.
  """
  board = {"spd": 9.30, "sta": 4.91, "wit": 0.71, "guts": 0.66, "pwr": 0.63}
  a, why = P.decide(("points", 0), 2, 22, board, skip_training_energy=35)
  ok("a met goal on an empty tank is not a race", a is None, f"{a}: {why}")
  a, _ = P.decide(None, 2, 22, board, skip_training_energy=35)
  ok("and no goal at all is no opinion either", a is None)
  # The rule this must not have broken: an open goal on the same empty tank
  # still races, because resting there pays nothing toward a live deadline.
  a, why = P.decide(("points", 40), 2, 22, board, skip_training_energy=35)
  ok("but an open goal on an empty tank still races", a == "race", f"{a}: {why}")


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
  # A missing count no longer means "no opinion" on its own: the slack branch
  # is skipped and the board decides instead, so a flat one is needed here.
  # test_missing_count_falls_through_to_the_board covers both sides.
  a, _ = P.decide(("points", 5), None, 60, {"a": 2.0, "b": 1.9, "c": 1.8},
                  skip_training_energy=35)
  ok("no race count and a flat board -> no opinion", a is None)
  a, _ = P.decide(("points", 5), 10, None, {"a": 3.0}, skip_training_energy=35)
  ok("unknown energy -> no opinion", a is None)
  a, _ = P.decide(("points", 0), 10, 60, {"a": 3.0}, skip_training_energy=35)
  ok("an already-met goal -> no opinion", a is None)

def test_a_unit_mismatch_is_not_urgency():
  """Caught when the advisory was first wired, and worth pinning.

  `remaining` is in points or fans; a caller with only the turn counter would
  pass turns. 212 points against 9 turns gives slack -203, so every single turn
  reads as "no time left" and the board never gets a say - the planner would
  have said "race" for a whole career and looked like it was working.
  """
  flat = {"a": 2.98, "b": 2.53, "c": 1.10}
  standout = {"a": 8.42, "b": 2.22, "c": 0.66}
  a1, w1 = P.decide(("points", 212), 9, 60, flat, skip_training_energy=35)
  a2, w2 = P.decide(("points", 212), 9, 60, standout, skip_training_energy=35)
  ok("a mismatched count does not force a race", a1 != "race", f"{a1}: {w1}")
  ok("and the board still decides", a2 == "train", f"{a2}: {w2}")
  ok("the two boards disagree, which is the point", a1 != a2, f"{a1} vs {a2}")

def test_missing_count_falls_through_to_the_board():
  standout = {"a": 8.42, "b": 2.22, "c": 0.66}
  flat = {"a": 2.98, "b": 2.53, "c": 1.10}
  a1, _ = P.decide(("points", 50), None, 60, standout, skip_training_energy=35)
  a2, _ = P.decide(("points", 50), None, 60, flat, skip_training_energy=35)
  ok("no count + standout -> keep the turn", a1 == "train")
  ok("no count + flat board -> no opinion", a2 is None)

def test_a_credible_count_still_uses_slack():
  """A count goal in its own units must keep working."""
  standout = {"a": 8.42, "b": 2.22, "c": 0.66}
  a, w = P.decide(("points", 2), 2, 60, standout, skip_training_energy=35)
  ok("2 needed against 2 chances still races", a == "race", w)

def test_slack_arithmetic():
  ok("spare chances", P.slack(2, 5) == 3)
  ok("exactly enough is no slack", P.slack(5, 5) == 0)
  ok("impossible is negative", P.slack(9, 5) == -4)

for test in [test_parses_the_two_measurable_goals,
             test_the_result_pts_countdown_measured_live,
             test_the_fans_target_is_ignored_on_purpose,
             test_goals_with_nothing_to_decide,
             test_a_met_goal_never_races_however_low_the_energy,
             test_energy_decides_before_anything_else,
             test_no_slack_forces_a_race,
             test_with_slack_the_board_decides,
             test_the_ratio_matches_the_measured_turns,
             test_degenerate_boards,
             test_no_opinion_cases,
             test_a_unit_mismatch_is_not_urgency,
             test_missing_count_falls_through_to_the_board,
             test_a_credible_count_still_uses_slack,
             test_slack_arithmetic]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
