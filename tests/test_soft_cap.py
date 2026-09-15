"""Past-1200 gains are scored in pre-halving units.

The game halves a stat gain once the stat passes 1200, and the training screen
prints the halved figure - measured over 1353 reads from careers 6-10, Speed's
printed median was 20 below the line and 10 at or above it. Those ten points
cost a whole training either way, so the scorer doubles the part that lands
above the cap.

Run with `python tests/test_soft_cap.py` from the repo root. core.state is
stubbed, as in test_gain_caps.py: importing the real one builds an easyocr
Reader, which takes longer than the whole check.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

fake = types.ModuleType("core.state")
fake.PRIORITY_STAT = ["spd", "pwr", "wit", "sta", "guts"]
fake.PRIORITY_EFFECTS_LIST = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
fake.PRIORITY_WEIGHT = "MEDIUM"
fake.STAT_CAPS = {"spd": 1600, "sta": 1600, "pwr": 1600, "guts": 1600, "wit": 1600}
fake.CURRENT_YEAR = "Senior Year"
fake.MAX_FAILURE = 15
for name in ("check_current_year", "stat_state", "stat_caps_state",
             "check_energy_level", "check_aptitudes"):
  setattr(fake, name, lambda *a, **k: None)
sys.modules["core.state"] = fake

import core
core.state = fake
import core.logic as L  # noqa: E402

failures = []

def check(label, got, want):
  ok = abs(got - want) < 1e-9
  print(f"{'ok  ' if ok else 'FAIL'} {label}: got {got:.4f}, want {want:.4f}")
  if not ok:
    failures.append(label)

def main():
  # Entirely below the line: nothing changes.
  L.set_stat_headroom({"spd": 900})
  check("below the soft cap is untouched", L.soft_cap_value("spd", 20), 20.0)

  # Entirely above: every point cost double the training.
  L.set_stat_headroom({"spd": 1300})
  check("above the soft cap doubles", L.soft_cap_value("spd", 10), 20.0)

  # Straddling: only the part that crosses is doubled. 1190 + 20 means ten
  # points below the line and ten above, so 10 + 10x2, not 40.
  L.set_stat_headroom({"spd": 1190})
  check("straddling splits at the cap", L.soft_cap_value("spd", 20), 30.0)

  # Exactly on the line: all of it is above.
  L.set_stat_headroom({"spd": L.STAT_SOFT_CAP})
  check("exactly at the cap is all above", L.soft_cap_value("spd", 10), 20.0)

  # An unread stat is -1 and left out of _stat_current. Guessing would inflate
  # a facility the bot cannot see, so it scores flat.
  L.set_stat_headroom({"spd": -1})
  check("unread stat is not doubled", L.soft_cap_value("spd", 20), 20.0)

  # The headroom clip still runs first: a gain is capped before it is doubled,
  # so a stat with four points of room scores those four (doubled), not twenty.
  L.set_stat_headroom({"spd": 1596})  # cap 1600 in the stub
  four_points = L.weighted_stat_points({"spd": 20})
  L.set_stat_headroom({"spd": 1596})
  check("headroom clips before the doubling",
        four_points, L.weighted_stat_points({"spd": 4}))

  # Skill points are not a stat and must not be doubled.
  L.set_stat_headroom({"spd": 1300})
  check("skill points are untouched by the soft cap",
        L.gain_score({"gains": {"skill": 30}, "unity": {}}, "spd"),
        30 * L.SKILL_PT_WEIGHT * L.STAT_GAIN_POINTS)

  print()
  if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    return 1
  print("all checks passed")
  return 0

if __name__ == "__main__":
  sys.exit(main())
