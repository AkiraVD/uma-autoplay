"""The Game mode setting: how config `scenario` drives the mode flags.

Run with `python tests/test_scenario.py` from the repo root. It imports
core.state, which builds the easyocr Reader, so it is slow to start.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.state as S   # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def flags():
  return (S.UNITY_SEEN, S.GRAND_CONCERT_SEEN)

def use(scenario, unity=False, gc=False):
  S.SCENARIO = scenario
  S.UNITY_SEEN, S.GRAND_CONCERT_SEEN = unity, gc
  S._scenario_warned.clear()

def test_auto():
  use("auto")
  S.apply_scenario()
  ok("auto starts with no mode", flags() == (False, False), flags())
  S.saw_scenario("grand_concert", "Lessons button in the lobby")
  ok("auto takes Grand Concert from the screen", flags() == (False, True), flags())
  S.apply_scenario()
  ok("a restart mid-career keeps what auto saw", flags() == (False, True), flags())
  S.apply_scenario(new_career=True)
  ok("a new career clears it", flags() == (False, False), flags())
  S.saw_scenario("unity", "Spirit gauge on the training screen")
  ok("and auto takes Unity Cup the same way", flags() == (True, False), flags())

def test_fixed():
  for scenario, expected in (("ura", (False, False)), ("unity", (True, False)), ("grand_concert", (False, True))):
    use(scenario, unity=True, gc=True)
    S.apply_scenario()
    ok(f"{scenario} sets the flags at start", flags() == expected, flags())
    use(scenario)
    S.apply_scenario(new_career=True)
    ok(f"{scenario} sets them again for a new career", flags() == expected, flags())

  use("ura")
  S.apply_scenario()
  S.saw_scenario("grand_concert", "Lessons button in the lobby")
  ok("a fixed mode ignores a disagreeing screen", flags() == (False, False), flags())
  ok("but remembers it warned", "grand_concert" in S._scenario_warned, S._scenario_warned)
  S.saw_scenario("ura", "URA screen")
  ok("and never warns about its own mode", "ura" not in S._scenario_warned, S._scenario_warned)

def test_unity_scan_skipped():
  use("grand_concert")
  ok("a fixed non-Unity mode skips the icon scan",
     S.check_unity_icons() == {"spirit": 0, "burst": 0, "burst_ex": 0})

if __name__ == "__main__":
  test_auto()
  test_fixed()
  test_unity_scan_skipped()
  if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
  print("\nall ok")
