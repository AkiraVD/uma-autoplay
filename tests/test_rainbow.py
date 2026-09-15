"""rainbow_training's wit guard.

Run with `python tests/test_rainbow.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader.

The guard used to run after max() and return None, so a wit facility that won
on points but failed the rainbow requirement took every other rainbow candidate
down with it and dropped the bot into most_support_card. It is now a filter, so
the runner-up stands.
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

def facility(stat, own_rainbows=0, supports=1, hints=0, failure=0):
  """One entry of check_training()'s dict.

  `own_rainbows` are cards of the facility's own type at max bond - the only
  ones that count as rainbows.
  """
  data = {key: {"friendship_levels": levels()} for key in KEYS}
  data[stat] = {"friendship_levels": levels(yellow=own_rainbows)}
  data["total_supports"] = supports
  data["total_hints"] = hints
  data["failure"] = failure
  data["unity"] = {"spirit": 0, "burst": 0, "burst_ex": 0}
  data["gains"] = {}
  return data

def test_wit_energy_band():
  """Wit hands energy back, so mid-tank it is really buying the next turn."""
  low, high = L.WIT_ENERGY_BAND
  mid = (low + high) // 2

  # Below the band wit stays held to the strict requirement: there is not
  # enough energy left for it to get back to a safe level, so resting wins.
  L.set_energy_level(low - 10)
  ok("below the band wit still needs the full rainbow count",
     L.wit_min_rainbows() == L.WIT_MIN_RAINBOWS)
  results = {"wit": facility("wit", own_rainbows=1, supports=4)}
  ok("and a thin wit is not a candidate there",
     L.rainbow_training(results) is None)

  # Above the band the energy wit returns would spill, so it is a weak
  # training again.
  L.set_energy_level(high + 10)
  ok("above the band wit needs the full rainbow count too",
     L.wit_min_rainbows() == L.WIT_MIN_RAINBOWS)
  ok("no bonus above the band", L.wit_band_bonus("wit", 3) == 0.0)

  # Inside it, wit qualifies on fewer of its own rainbows and scores heavier.
  L.set_energy_level(mid)
  ok("inside the band the bar is lower",
     L.wit_min_rainbows() == L.WIT_BAND_MIN_RAINBOWS)
  results = {"wit": facility("wit", own_rainbows=1, supports=4)}
  ok("a thin wit becomes a candidate inside the band",
     L.rainbow_training(results) == "wit")

  # More rainbows, heavier - that is the whole point of scaling it.
  ok("the bonus scales with wit rainbows",
     L.wit_band_bonus("wit", 3) > L.wit_band_bonus("wit", 1) > 0)
  ok("and only applies to wit",
     L.wit_band_bonus("spd", 3) == 0.0)
  ok("a wit tile with no rainbows of its own gets nothing",
     L.wit_band_bonus("wit", 0) == 0.0)

  # It has to beat resting, not a real training. A clearly better facility
  # still wins inside the band.
  results = {
    "wit": facility("wit", own_rainbows=1, supports=2),
    "spd": facility("spd", own_rainbows=3, supports=5),
  }
  ok("a genuinely good training still beats a banded wit",
     L.rainbow_training(results) == "spd")

  L.set_energy_level(None)

def main():
  L.set_stat_headroom({"spd": 400, "sta": 300, "pwr": 400, "guts": 300, "wit": 500})

  # Wit outscores everything on points but has only two of its own rainbows.
  results = {
    "wit": facility("wit", own_rainbows=2, supports=5),
    "spd": facility("spd", own_rainbows=3, supports=3),
  }
  pick = L.rainbow_training(results)
  ok("a disqualified wit leaves the runner-up standing", pick == "spd", str(pick))

  # The whole point: it used to return None here and fall through to the
  # weaker most_support_card scorer.
  ok("and does not abandon rainbow training", pick is not None)

  # Wit with enough of its own rainbows is still allowed to win.
  results = {
    "wit": facility("wit", own_rainbows=L.WIT_MIN_RAINBOWS, supports=5),
    "spd": facility("spd", own_rainbows=1, supports=1),
  }
  ok("wit wins once it has its own rainbows",
     L.rainbow_training(results) == "wit")

  # Rainbows belong to the facility's own type. Cards of other types sitting on
  # the wit tile are not rainbows, however friendly they are.
  results = {"wit": facility("wit", own_rainbows=0, supports=5)}
  results["wit"]["spd"] = {"friendship_levels": levels(yellow=3)}
  ok("other types at max bond do not count as wit rainbows",
     L.rainbow_training(results) is None)

  # Wit alone and disqualified still means no rainbow training, as before.
  results = {"wit": facility("wit", own_rainbows=1, supports=4)}
  ok("wit alone and short of rainbows yields nothing",
     L.rainbow_training(results) is None)

  test_wit_energy_band()

  print("")
  print("FAILED: " + ", ".join(failures) if failures else "all checks passed")
  return 1 if failures else 0

if __name__ == "__main__":
  sys.exit(main())
