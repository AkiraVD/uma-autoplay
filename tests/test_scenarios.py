"""Per-mode differences: core/scenarios.py.

Run with `python tests/test_scenarios.py` from the repo root. It stubs
core.state the way the other pure-logic tests do, so it skips easyocr and runs
in well under a second.

The point of the module under test is that a mode with no case of its own is
loud rather than silent. Trackblazer had no case anywhere, inherited URA's
race-day button position, and spent three laps clicking into the Shop without
starting a Climax race. So the tests worth having are the ones that would have
caught that: every mode resolves to itself, Trackblazer's position and asset
differ from URA's, and asking for a field nobody defines raises.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

# Stub core.state before core.scenarios imports it: the real one builds the
# easyocr Reader at import time, and nothing here reads a screen.
stub = types.ModuleType("core.state")
stub.UNITY_SEEN = False
stub.GRAND_CONCERT_SEEN = False
stub.TRACKBLAZER_SEEN = False
sys.modules["core.state"] = stub

import core.scenarios as sc   # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def seen(unity=False, grand_concert=False, trackblazer=False):
  """Set the mode flags the way state.apply_scenario does."""
  stub.UNITY_SEEN = unity
  stub.GRAND_CONCERT_SEEN = grand_concert
  stub.TRACKBLAZER_SEEN = trackblazer

def test_each_mode_resolves_to_itself():
  for key, flags in (("ura", {}),
                     ("unity", {"unity": True}),
                     ("grand_concert", {"grand_concert": True}),
                     ("trackblazer", {"trackblazer": True})):
    seen(**flags)
    got = sc.current()["key"]
    ok(f"{key} resolves to itself", got == key, got)

def test_no_flags_is_ura():
  """URA is the base, so an unrecognised career still plays rather than stalling."""
  seen()
  ok("no flags set means URA", sc.current()["key"] == "ura")

def test_trackblazer_has_its_own_race_day():
  """The case whose absence caused the wedge."""
  seen(trackblazer=True)
  tb_pos, tb_asset = sc.get("race_day_pos"), sc.get("race_day_asset")
  seen()
  ura_pos, ura_asset = sc.get("race_day_pos"), sc.get("race_day_asset")
  ok("its position is not URA's", tb_pos != ura_pos, f"{tb_pos} vs {ura_pos}")
  ok("and sits on the TS Climax Race! button", tb_pos == (537, 908), tb_pos)
  ok("its asset is not URA's", tb_asset != ura_asset, tb_asset)

def test_grand_concert_shifts_for_its_extra_button():
  """Its lobby carries a fourth Lessons button, which moves two things left."""
  seen(grand_concert=True)
  ok("race day position differs from URA", sc.get("race_day_pos") == (545, 925),
     sc.get("race_day_pos"))
  gc_skills = sc.get("career_complete_skills_pos")
  seen()
  ok("career-complete Skills differs too", gc_skills != sc.get("career_complete_skills_pos"),
     gc_skills)

def test_unity_inherits_the_ura_race_day():
  """Unity Cup ends in the URA Finale, so it should NOT have its own position."""
  seen(unity=True)
  unity_pos = sc.get("race_day_pos")
  seen()
  ok("Unity uses URA's race day", unity_pos == sc.get("race_day_pos"), unity_pos)

def test_every_mode_names_an_asset_that_exists():
  """A named asset that is not on disk fails silently at match time."""
  for key, mode in sc.BY_KEY.items():
    path = mode["race_day_asset"]
    ok(f"{key}'s race day asset exists", os.path.isfile(path), path)

def test_a_missing_field_raises():
  """The whole point: no silent inheritance of a case nobody wrote."""
  seen(trackblazer=True)
  try:
    sc.get("shop_button_pos")
    ok("a missing field raises", False, "returned instead of raising")
  except KeyError as e:
    ok("a missing field raises", True, str(e)[:60])

def test_flags_are_read_at_call_time():
  """core/state.py's rule: read state.FOO, never capture it."""
  seen()
  before = sc.current()["key"]
  seen(trackblazer=True)
  after = sc.current()["key"]
  ok("current() follows a flag change", before == "ura" and after == "trackblazer",
     f"{before} -> {after}")

for test in [test_each_mode_resolves_to_itself, test_no_flags_is_ura,
             test_trackblazer_has_its_own_race_day,
             test_grand_concert_shifts_for_its_extra_button,
             test_unity_inherits_the_ura_race_day,
             test_every_mode_names_an_asset_that_exists,
             test_a_missing_field_raises, test_flags_are_read_at_call_time]:
  print(f"\n-- {test.__name__}")
  test()

seen()
print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
