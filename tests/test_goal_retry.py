"""Which career goals retry without limit when the race is lost.

Run with `python tests/test_goal_retry.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader.

A Retry offer is the game saying the goal was just lost, and each press spends
an Alarm Clock. `max_race_retries` capped every one of them until 2026-10-19,
which is the wrong shape for the only goals a retry can actually rescue: a goal
pinned to one named race gets one running of that race a career, and losing it
ends the run. Career 23 spent its single clock on the first loss and ended on
the second four minutes later; career 24 lost the URA Finale with the cap
already used.

So a named-race goal now retries until it is won, and the cap binds only the
goals another race can still meet.

The cases below are not invented: they are the distinct goal strings the logs
held on 2026-10-19, careers 1-25, OCR damage and all. That is what pins the rule to the
**shape** rather than the race name - "Japan C", "Saudi Arabia RC",
"Sprinters $." and "St: Lite Kinen" would none of them match `constants.RACES`,
and 1st reads as "Ist" more often than not.
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
fake.MAX_RACE_RETRIES = 1
fake.check_current_year = lambda: "Senior Year"
fake.stat_state = lambda: {}
fake.stat_caps_state = lambda: {}
fake.check_energy_level = lambda: 100
fake.check_aptitudes = lambda: {}
sys.modules["core.state"] = fake

import core.logic as L

FAILED = 0

def ok(label, cond):
  global FAILED
  if cond:
    print(f"ok    {label}")
  else:
    FAILED += 1
    print(f"FAIL  {label}")

# Every distinct "names a race" string in logs/, with the OCR as it came out.
NAMED = [
  "Place Ist in Arima Kinen",
  "Place Ist in Osaka Hai",
  "Place Ist in Sprinters $.",
  "Place Ist in Takamatsunomiya Kinen",
  "Place Ist in Tenno Sho (Autumn)",
  "Place Ist in URA Finale Finals",
  "Place Ist in URA Finale Qualifier",
  "Place Ist in URA Finale Semifinal",
  "Place Ist in Yasuda Kinen",
  "Place top 2 in Japan C",
  "Place top 3 in Arima Kinen",
  "Place top 3 in Hakodate Sprint $.",
  "Place top 3 in Japan C.",
  "Place top 3 in Kikuka Sho",
  "Place top 3 in Ocean $.",
  "Place top 3 in Osaka Hai",
  "Place top 3 in Spring $.",
  "Place top 3 in St. Lite Kinen",
  "Place top 3 in St: Lite Kinen",
  "Place top 3 in Takarazuka Kinen",
  "Place top 3 in Tenno Sho (Spring)",
  "Place top 5 in Aoi $.",
  "Place top 5 in Asahi Hai F.S:",
  "Place top 5 in Fantasy $.",
  "Place top 5 in Fillies' Revue",
  "Place top 5 in Hanshin J.F",
  "Place top 5 in Japanese Derby",
  "Place top 5 in Oka Sho",
  "Place top 5 in Satsuki Sho",
  "Place top 5 in Saudi Arabia RC",
  # "Run in X" asks only for a start, so it looks unloseable - but the Retry
  # offer is only drawn when the goal HAS failed, so a goal that cannot fail
  # never reaches the rule. Deciding here which named races are safe would
  # only add a way to be wrong.
  "Run in Arima Kinen",
  "Run in Junior Make Debut",
  # The lobby prints the entry line under the goal; goal_criteria cuts it, but
  # the match must not depend on that having worked.
  "Place top 5 in Satsuki Sho Entry criteria metl",
]

# And every distinct one that names no race at all. The fans and Result Pts
# goals are met by whatever race comes next, and the Climax series is a rank
# rather than a finish, so no single result loses any of them.
CAPPED = [
  "Earn 3000 fans Progress 4,434 fan(s) to go",
  "Earn 5000 fans Goal Achievedl",
  "Zarn 5000 fans Progress 3,601 fan(s) to go",
  "300 Result Pts Progress Aftert 240 pts",
  "50 Result Pts Goal Achievedl MAX",
  "Win the Twinkle Star Climax series Current Rank RANK 1",
  "",
  None,
]

def test_the_goals_a_retry_can_rescue():
  """The shapes the logs hold that name a race, against the ones that don't.

  2,494 of the 2,995 goal reads logs/ held on 2026-10-19 name one - 2,039
  "Place top N / 1st in X" and 455 "Run in X" - against 501 that name none.
  The lists below drop only the spellings that differ from a sibling by a
  trailing OCR mark. No string in either is a judgement call: the split is
  those three shapes against everything else, and it misfiles none of them.
  """
  missed = [t for t in NAMED if not L.goal_names_a_race(t)]
  if missed:
    print(f"      missed: {missed}")
  ok(f"all {len(NAMED)} named-race goals retry without limit", not missed)
  wrong = [t for t in CAPPED if L.goal_names_a_race(t)]
  if wrong:
    print(f"      wrongly named: {wrong}")
  ok(f"none of the {len(CAPPED)} other goals does", not wrong)

def test_a_count_of_races_is_not_a_named_race():
  """The one shape that would read as named but isn't.

  No career has printed it yet, which is exactly why it is pinned: a goal
  asking for a placing across several races is met by any of them, so it must
  not inherit the unlimited retry.
  """
  ok("'Place top 3 in 2 races' is not a named race",
     not L.goal_names_a_race("Place top 3 in 2 races"))
  ok("'Place top 5 in 3 race(s)' is not either",
     not L.goal_names_a_race("Place top 5 in 3 race(s)"))

def test_it_falls_back_to_the_last_lobby_read():
  """Called with nothing, it asks goal_criteria, which is the lobby's copy.

  The Retry offer is on a result screen where the goal is not drawn at all, so
  the no-argument call is the one the bot actually makes.
  """
  L.set_goal_context("Place Ist in URA Finale Finals Entry criteria metl", 1)
  ok("the Finale leg the bot lost career 24 on retries without limit",
     L.goal_names_a_race())
  L.set_goal_context("Earn 5000 fans Progress 3,601 fan(s) to go", 1)
  ok("a fan goal does not", not L.goal_names_a_race())
  L.set_goal_context("", 1)
  ok("an unread goal does not: an unknown goal keeps the cap",
     not L.goal_names_a_race())

if __name__ == "__main__":
  test_the_goals_a_retry_can_rescue()
  test_a_count_of_races_is_not_a_named_race()
  test_it_falls_back_to_the_last_lobby_read()
  print("FAILED" if FAILED else "all ok")
  sys.exit(1 if FAILED else 0)
