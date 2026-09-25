"""The URA `Duel!` badge reader, against real frames.

Fixtures come from one live URA career (2026-09-25). The positives cover all
four facilities the badge was seen on, both disc states, and the squashed frame
of its bounce animation; the negatives include the pink `!` event markers,
which sit in the same corner of the same discs and are the only thing on the
board that could plausibly be mistaken for it.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

from PIL import Image  # noqa: E402

import core.state as S  # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "duel")

failures = []


def ok(label, condition, detail=""):
  print(("ok   " if condition else "FAIL ") + label + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def fixture(name):
  return Image.open(os.path.join(FIXTURES, name))


# name -> the facility the badge is on
POSITIVES = {
  "badge_wit_0.png": "wit",
  "badge_wit_1.png": "wit",
  "badge_wit_2.png": "wit",
  "badge_spd_0.png": "spd",
  "badge_spd_1_selected_disc.png": "spd",
  "badge_pwr_0.png": "pwr",
  "badge_pwr_1.png": "pwr",
  "badge_guts_0.png": "guts",
}

NEGATIVES = [
  "nobadge_0.png",
  "nobadge_1_hint_pwr.png",
  "nobadge_2_hints.png",
  "nobadge_3_hints.png",
  "nobadge_4.png",
]


def test_positives_name_the_right_facility():
  print("\n-- test_positives_name_the_right_facility")
  for name, want in sorted(POSITIVES.items()):
    got = S.check_duel_badges(fixture(name))
    ok(f"{name} reads a badge on {want.upper()}",
       got == {want: True}, f"got {got}")


def test_a_clean_board_reads_as_nothing():
  print("\n-- test_a_clean_board_reads_as_nothing")
  for name in NEGATIVES:
    got = S.check_duel_badges(fixture(name))
    ok(f"{name} reads no badge", got == {}, f"got {got}")


def test_the_pink_event_marker_is_not_a_duel():
  """The hard negatives, called out separately because they are the whole risk.

  A pink `!` sits in the same corner of the same disc. If the template ever
  drifts loose enough to match one, every turn looks like a duel turn.
  """
  print("\n-- test_the_pink_event_marker_is_not_a_duel")
  for name in ("nobadge_1_hint_pwr.png", "nobadge_2_hints.png", "nobadge_3_hints.png"):
    got = S.check_duel_badges(fixture(name))
    ok(f"{name} (carries pink '!') is not read as a duel", got == {}, f"got {got}")


def test_a_frame_with_both_still_reads_the_duel():
  """badge_spd_1_selected_disc.png carries a Duel! on Speed *and* a pink `!`
  elsewhere, on a raised disc. It has to report exactly the one."""
  print("\n-- test_a_frame_with_both_still_reads_the_duel")
  got = S.check_duel_badges(fixture("badge_spd_1_selected_disc.png"))
  ok("a duel and a pink '!' on one board reads only the duel",
     got == {"spd": True}, f"got {got}")


def test_other_scenarios_read_nothing():
  print("\n-- test_other_scenarios_read_nothing")
  before = S.SCENARIO
  try:
    for mode in ("unity", "grand_concert"):
      S.SCENARIO = mode
      got = S.check_duel_badges(fixture("badge_wit_0.png"))
      ok(f"scenario {mode!r} reads no badge", got == {}, f"got {got}")
    for mode in ("auto", "ura"):
      S.SCENARIO = mode
      got = S.check_duel_badges(fixture("badge_wit_0.png"))
      ok(f"scenario {mode!r} still reads it", got == {"wit": True}, f"got {got}")
  finally:
    S.SCENARIO = before


for test in (test_positives_name_the_right_facility,
             test_a_clean_board_reads_as_nothing,
             test_the_pink_event_marker_is_not_a_duel,
             test_a_frame_with_both_still_reads_the_duel,
             test_other_scenarios_read_nothing):
  test()

print()
if failures:
  print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
  sys.exit(1)
print("all checks passed")
