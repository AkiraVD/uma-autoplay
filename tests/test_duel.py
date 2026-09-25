"""Chasing the URA Happy Meek duel: which facility the badge buys.

Run with `python tests/test_duel.py` from the repo root. core.state is stubbed,
so this never builds an easyocr Reader.

A duel pays a stat, skill points, a stat-cap raise and a Racing Spirit hint on
top of the training's own gains, at no extra energy - but **only if the training
succeeds**, because a failed training cancels the duel. That is why the bar here
is 0% failure rather than MAX_FAILURE, and why the rule sits ahead of the
scorers instead of being weighted into them.
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
fake.STAT_CAPS = {"spd": 1400, "sta": 1400, "pwr": 1400, "guts": 400, "wit": 1400}
fake.CURRENT_YEAR = "Classic Year"
fake.MAX_FAILURE = 15
fake.SKIP_TRAINING_ENERGY = 35
fake.NEVER_REST_ENERGY = 75
fake.SPIRIT_GAUGE_POINTS = 1.0
fake.SPIRIT_BURST_POINTS = 2.0
fake.SPIRIT_BURST_EX_POINTS = 3.0
fake.BURST_ENABLED_STATS = []
fake.ALWAYS_BUY_GOLD_SKILL = False
fake.URA_CHASE_DUELS = True
fake.UNITY_SEEN = False
fake.GRAND_CONCERT_SEEN = False
STATS = {"spd": 415, "sta": 232, "pwr": 311, "guts": 390, "wit": 244}
fake.check_energy_level = lambda *a, **k: (60.0, 100)
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


def facility(stat, supports=1, failure=0, duel=False, burst_ex=0):
  data = {key: {"friendship_levels": levels()} for key in KEYS}
  data[stat] = {"friendship_levels": levels(yellow=0)}
  data["total_supports"] = supports
  data["total_hints"] = 0
  data["total_friendship_levels"] = levels()
  data["failure"] = failure
  data["unity"] = {"spirit": 0, "burst": 0, "burst_ex": burst_ex}
  data["gains"] = {}
  data["duel"] = duel
  return data


def board(**overrides):
  out = {key: facility(key) for key in KEYS}
  out.update(overrides)
  return out


def test_a_safe_badge_is_taken():
  print("\n-- test_a_safe_badge_is_taken")
  b = board(wit=facility("wit", supports=1, failure=0, duel=True))
  ok("the badged facility is taken", L.duel_action(b, 60.0) == "wit")
  ok("and a clean board takes nothing", L.duel_action(board(), 60.0) is None)


def test_stamina_wins_when_it_is_badged():
  """Option 1 of a duel is always the trained facility's own stat, so Stamina
  is the only way `Contest of stamina!` is guaranteed to be offered."""
  print("\n-- test_stamina_wins_when_it_is_badged")
  b = board(sta=facility("sta", supports=1, failure=0, duel=True),
            wit=facility("wit", supports=5, failure=0, duel=True))
  ok("Stamina beats a fatter badged facility", L.duel_action(b, 60.0) == "sta")
  b2 = board(pwr=facility("pwr", supports=1, failure=0, duel=True),
             wit=facility("wit", supports=5, failure=0, duel=True))
  ok("without Stamina the best badged facility wins",
     L.duel_action(b2, 60.0) == "wit", f"got {L.duel_action(b2, 60.0)}")


def test_risk_refuses_the_duel():
  """A failed training cancels the duel, so anything above 0% is not worth it -
  even though MAX_FAILURE would allow it."""
  print("\n-- test_risk_refuses_the_duel")
  for failure in (1, 10, 15):
    b = board(wit=facility("wit", failure=failure, duel=True))
    ok(f"{failure}% failure is refused", L.duel_action(b, 60.0) is None)
  b = board(wit=facility("wit", failure=0, duel=True))
  ok("0% is taken", L.duel_action(b, 60.0) == "wit")


def test_an_empty_tank_refuses_the_duel():
  print("\n-- test_an_empty_tank_refuses_the_duel")
  b = board(wit=facility("wit", failure=0, duel=True))
  ok("below skip_training_energy the duel is skipped",
     L.duel_action(b, 34.0) is None)
  ok("at the threshold it is taken", L.duel_action(b, 35.0) == "wit")


def test_the_config_switch_and_other_scenarios():
  print("\n-- test_the_config_switch_and_other_scenarios")
  b = board(wit=facility("wit", failure=0, duel=True))
  fake.URA_CHASE_DUELS = False
  ok("ura.chase_duels off means never", L.duel_action(b, 60.0) is None)
  fake.URA_CHASE_DUELS = True
  for flag in ("UNITY_SEEN", "GRAND_CONCERT_SEEN"):
    setattr(fake, flag, True)
    ok(f"{flag} means this is not a URA career", L.duel_action(b, 60.0) is None)
    setattr(fake, flag, False)
  ok("and it is back on for URA", L.duel_action(b, 60.0) == "wit")


def test_a_capped_facility_keeps_its_badge():
  """Guts is capped at 400 with 390 trained, so a +4 cap raise and a hint are
  exactly what that facility can still pay. filter_by_stat_caps has to keep it."""
  print("\n-- test_a_capped_facility_keeps_its_badge")
  stats = dict(STATS, guts=400)
  b = board(guts=facility("guts", failure=0, duel=True))
  kept = L.filter_by_stat_caps(b, stats)
  ok("a capped but badged facility survives the cap filter", "guts" in kept)
  plain = L.filter_by_stat_caps(board(), stats)
  ok("a capped facility without a badge is still dropped", "guts" not in plain)


def test_recreation_does_not_steal_the_turn():
  print("\n-- test_recreation_does_not_steal_the_turn")
  reason = L.should_recreate(2.0, False, 20.0, 100, 2, 2, True, False,
                             duel_ready=True)
  ok("an outing stands aside for a badge", reason is None, f"got {reason!r}")


for test in (test_a_safe_badge_is_taken,
             test_stamina_wins_when_it_is_badged,
             test_risk_refuses_the_duel,
             test_an_empty_tank_refuses_the_duel,
             test_the_config_switch_and_other_scenarios,
             test_a_capped_facility_keeps_its_badge,
             test_recreation_does_not_steal_the_turn):
  test()

print()
if failures:
  print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
  sys.exit(1)
print("all checks passed")
