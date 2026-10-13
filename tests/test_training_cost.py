"""Per-facility training energy costs, and that wit is not charged for one.

Run with `python tests/test_training_cost.py` from the repo root.

logic used a flat TRAINING_ENERGY_COST = 25. The game's own numbers are Speed
-21, Stamina -19, Power -20, Guts -22 and Wit **+5**: wit hands energy back.
Charging wit 25 made an outing look better than it was on exactly the turns
WIT_ENERGY_BAND exists to rescue, so the sign is the thing worth pinning.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.training_cost as T  # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def main():
  print("-- costs come out per facility, not flat")
  changes = {stat: T.change(stat) for stat in ("spd", "sta", "pwr", "guts", "wit")}
  ok("the four stat facilities all cost energy",
     all(changes[s] < 0 for s in ("spd", "sta", "pwr", "guts")), changes)
  ok("and they are not all the same number",
     len({changes[s] for s in ("spd", "sta", "pwr", "guts")}) > 1, changes)

  print("\n-- wit returns energy rather than spending it")
  ok("wit's change is positive", changes["wit"] > 0, changes["wit"])
  ok("so wit is charged nothing", T.cost("wit") == 0, T.cost("wit"))
  ok("while a stat facility is charged what it costs",
     T.cost("spd") == -changes["spd"] > 0, T.cost("spd"))

  print("\n-- the built-in fallback agrees with the database, scenario by scenario")
  # If master.mdb is present the two must match; if it is absent the fallback is
  # what change() returned anyway, so this holds either way and catches a
  # fallback that drifts away from the real values.
  #
  # FALLBACK is keyed by master.mdb scenario id since 2026-10-13, because the
  # modes DISAGREE - Grand Concert is Speed -19 and Guts -20 where URA is -21
  # and -22 - and the query used to take whichever row came first, always URA's.
  saved_scenario = T._scenario
  try:
    for scenario, table in T.FALLBACK.items():
      T.set_scenario(scenario)
      for stat, value in table.items():
        ok(f"scenario {scenario} fallback {stat} matches what change() reports",
           T.change(stat) == value, f"{T.change(stat)} vs {value}")
  finally:
    T.set_scenario(saved_scenario)

  print("\n-- wit hands energy back in every mode")
  # The sign fix this module was written for has to hold whichever mode the
  # career is, so it is not quietly a URA-only truth.
  try:
    for scenario in T.FALLBACK:
      T.set_scenario(scenario)
      ok(f"scenario {scenario}: wit returns energy", T.change("wit") > 0, T.change("wit"))
      ok(f"scenario {scenario}: and is charged nothing", T.cost("wit") == 0)
  finally:
    T.set_scenario(saved_scenario)

  print("\n-- an unknown facility does not crash or come back free")
  ok("unknown facility falls back to the default cost",
     T.cost("nonsense") == T.DEFAULT_COST, T.cost("nonsense"))

  print()
  if failures:
    print(f"{len(failures)} failing: " + ", ".join(failures))
    return 1
  print("all good")
  return 0

if __name__ == "__main__":
  sys.exit(main())
