"""Reading the Spark Selection screen and applying the reroll rule.

Run with `python tests/test_sparks.py` from the repo root.

The screens were captured at the end of careers 3, 4 and 5:
  sparks_speed3star_c4.png          Speed 3-star - the set to keep
  sparks_power2star_c5.png          Power 2-star - reroll
  sparks_wit3star_run5.png          Wit 3-star - keep
  sparks_selection_after_reroll.png the two-page screen, rerolled page
  sparks_selection_original_page.png the same screen, original page
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.sparks as S                                # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "sparks")
failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def fixture(name):
  return Image.open(os.path.join(FIXTURES, name))

def test_reader():
  cases = {
    "sparks_speed3star_c4.png": (3, 6),
    "sparks_power2star_c5.png": (2, 5),
    "sparks_wit3star_run5.png": (3, 6),
    "sparks_selection_original_page.png": (2, 5),
    "sparks_selection_after_reroll.png": (2, 6),
  }
  for name, want in cases.items():
    rows = S.read(fixture(name))
    ok(f"{name} reads as {want}", S.valid(rows) and S.rank(rows) == want, S.describe(rows))

def test_kinds():
  rows = S.read(fixture("sparks_power2star_c5.png"))
  ok("the first three rows are stat, aptitude and unique",
     [r["kind"] for r in rows[:3]] == ["stat", "aptitude", "unique"], [r["kind"] for r in rows[:3]])
  ok("and the rest are skill sparks", all(r["kind"] == "skill" for r in rows[3:]))

def test_policy():
  keep = S.read(fixture("sparks_speed3star_c4.png"))
  roll = S.read(fixture("sparks_power2star_c5.png"))
  ok("a 3-star blue is kept", not S.worth_rerolling(keep))
  ok("anything less is rerolled", S.worth_rerolling(roll))
  # Career 5: Power 2-star with 5 whites beat the rerolled Wit 1-star with 4.
  original = [{"kind": "stat", "stars": 2}] + [{"kind": "skill", "stars": 1}] * 5
  rerolled = [{"kind": "stat", "stars": 1}] + [{"kind": "skill", "stars": 1}] * 6
  ok("blue stars decide before white count", max([original, rerolled], key=S.rank) is original)
  # And with equal blue, the whites do.
  poorer = [{"kind": "stat", "stars": 2}] + [{"kind": "skill", "stars": 1}] * 4
  richer = [{"kind": "stat", "stars": 2}] + [{"kind": "skill", "stars": 1}] * 7
  ok("with equal blue, more whites wins", max([poorer, richer], key=S.rank) is richer)

def test_a_non_spark_screen_is_not_read_as_one():
  path = os.path.join("tests", "fixtures", "out_of_career", "career_complete.png")
  if not os.path.exists(path):
    print("skip  no career-complete fixture")
    return
  ok("the career-complete screen is not a spark set", not S.valid(S.read(Image.open(path))))

def test_tp_restore_reading():
  """The Recover TP list: find the bottle row and read how many are left.

  Career 6's reroll needed 10 more TP and the bot sat on the restore dialog
  pressing Reroll again every poll. Carats are money and the chocolates are
  one-offs, so only the plain bottle row counts, and only above the floor.
  """
  import numpy as np, cv2
  from core.ocr import extract_number
  # Deliberately through the module, not a local import of the helper. The
  # local import is what let this test pass while core/sparks.py itself had no
  # `enhance_for_reading` in scope: _restore_tp raised NameError the first time
  # the branch was ever reached, three careers after the code was written.
  ok("sparks.py has enhance_for_reading in scope", hasattr(S, "enhance_for_reading"))
  enhance_for_reading = S.enhance_for_reading
  path = os.path.join("shots", "gl", "c6_restore.png")
  if not os.path.exists(path):
    print("skip  no restore-list capture")
    return
  shot = Image.open(path)
  screen = np.asarray(shot.convert("RGB"))
  template = cv2.imread(S.TOUGHNESS_ROW, cv2.IMREAD_COLOR)
  ok("the bottle template loads", template is not None)
  result = cv2.matchTemplate(cv2.cvtColor(screen, cv2.COLOR_RGB2BGR), template, cv2.TM_CCOEFF_NORMED)
  _, best, _, loc = cv2.minMaxLoc(result)
  ok("the Toughness row is found on the restore list", best > 0.85, round(best, 3))
  x, y = loc
  held = extract_number(enhance_for_reading(shot.crop((x + 90, y + 20, x + 190, y + 56))), value_range=(0, 9999))
  ok("and its stock reads", held == 173, held)

def test_restore_button_is_found_and_not_confused():
  """The "You need N more TP to reroll Sparks. Restore TP?" prompt.

  _restore_tp used to look for ok_btn on this prompt. It has no OK - the
  buttons are "No" and "Restore" - so the match scored 0.53, the function
  returned before its first log line, and the bottle rule never fired once:
  three Doto careers reached a reroll short of TP and every one silently kept
  the set it had.

  The button body is the same green as Confirm, OK and Start Career!, so the
  template is cut tight to the label and the negatives below are what keep it
  honest.
  """
  import numpy as np, cv2
  template = cv2.imread(S.RESTORE_BTN, cv2.IMREAD_COLOR)
  ok("the Restore template loads", template is not None)
  if template is None:
    return

  def best(name):
    screen = cv2.cvtColor(np.asarray(fixture(name).convert("RGB")), cv2.COLOR_RGB2BGR)
    if (screen.shape[0] < template.shape[0]) or (screen.shape[1] < template.shape[1]):
      return 0.0
    return cv2.minMaxLoc(cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED))[1]

  if not os.path.exists(os.path.join(FIXTURES, "tp_prompt_restore.png")):
    print("skip  no TP prompt fixture")
    return
  hit = best("tp_prompt_restore.png")
  ok("Restore is found on the TP prompt", hit >= S.RESTORE_CONFIDENCE, round(hit, 3))

  # Any other green button scoring at the threshold would have the bot pressing
  # Restore on a screen that has none.
  for name in ("sparks_confirm_reroll.png", "sparks_keep_confirm_dialog.png",
               "spark_keep_rerolled_confirm.png", "sparks_power2star_c5.png"):
    if not os.path.exists(os.path.join(FIXTURES, name)):
      continue
    miss = best(name)
    ok(f"and not confused with {name}", miss < S.RESTORE_CONFIDENCE, round(miss, 3))

for test in [test_reader, test_kinds, test_policy, test_a_non_spark_screen_is_not_read_as_one,
             test_tp_restore_reading, test_restore_button_is_found_and_not_confused]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
