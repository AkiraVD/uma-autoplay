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

def test_parked_mode_is_reported_not_adopted():
  """A parked mode has no flag to set, so auto must not silently take it.

  Trackblazer was removed on 2026-09-21. Its screens still exist and a career
  in it can still be started by hand, so saw_scenario has to say so once and
  leave the flags alone rather than fall through to the mismatch warning,
  which would name a mode that is no longer selectable.
  """
  use("auto")
  S.apply_scenario(new_career=True)
  S.saw_scenario("trackblazer", "Shop button in the lobby")
  ok("a parked mode sets no flag", flags() == (False, False), flags())
  ok("and is warned about once", "trackblazer" in S._scenario_warned, S._scenario_warned)
  ok("and is not a selectable mode", "trackblazer" not in S.SCENARIOS, S.SCENARIOS)
  ok("but is named for the warning", "trackblazer" in S.PARKED_SCENARIOS)

def test_parked_mode_in_config_falls_back_to_auto():
  """A config saved before the removal must degrade, not crash."""
  ok("a parked mode in config becomes auto",
     S.resolve_scenario("trackblazer") == "auto")
  ok("an unknown mode does too", S.resolve_scenario("nonsense") == "auto")
  ok("a missing mode does too", S.resolve_scenario(None) == "auto")
  ok("a live mode is kept", S.resolve_scenario("grand_concert") == "grand_concert")

def test_fixed():
  for scenario, expected in (("ura", (False, False)), ("unity", (True, False)),
                             ("grand_concert", (False, True))):
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
  test_parked_mode_is_reported_not_adopted()
  test_parked_mode_in_config_falls_back_to_auto()
  test_fixed()
  test_unity_scan_skipped()
  if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
  print("\nall ok")
