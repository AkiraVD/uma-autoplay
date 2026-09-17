"""Setting the story Skip to x2 and Quick Mode to "Shorten all events".

Run with `python tests/test_career_start.py` from the repo root. No OCR, so it
is fast.

Both are once-per-career settings the bot never touched. The story Skip resets
to Off with every new career, and with Skip off the bot taps each story line
about every 9 s - a career intro that read as a stall. Quick Mode's dialog was
confirmed with whatever was selected.

Fixtures in tests/fixtures/career_start/, all captured live on 2026-09-17 while
the Quick Mode dialog held the scene still:
  skip_state_off.png / _x1.png / _x2.png  the three states of the Skip button
  quick_mode_shorten_all.png              the dialog with the wanted radio set
  quick_mode_dont_use.png                 and with a different radio set
"""
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import utils.constants as C                  # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "career_start")
# multi_match_templates and match_template both use 0.85.
THRESHOLD = 0.85

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def skip_scores(fixture):
  """Every Skip template scored inside SKIP_BUTTON_BBOX, as match_template does."""
  left, top, right, bottom = C.SKIP_BUTTON_BBOX
  crop = cv2.imread(os.path.join(FIXTURES, fixture))[top:bottom, left:right]
  return {name: cv2.matchTemplate(crop, cv2.imread(path), cv2.TM_CCOEFF_NORMED).max()
          for name, path in (("off", "assets/buttons/skip_off.png"),
                             ("x1", "assets/buttons/skip_x1.png"),
                             ("x2", "assets/buttons/skip_x2.png"))}

def test_the_templates_fit_the_region():
  """A template larger than the crop makes matchTemplate throw, not return 0."""
  left, top, right, bottom = C.SKIP_BUTTON_BBOX
  for path in ("assets/buttons/skip_off.png", "assets/buttons/skip_x1.png",
               "assets/buttons/skip_x2.png"):
    tpl = cv2.imread(path)
    ok(f"{os.path.basename(path)} fits SKIP_BUTTON_BBOX",
       tpl is not None and tpl.shape[1] <= right - left and tpl.shape[0] <= bottom - top,
       None if tpl is None else f"{tpl.shape[1]}x{tpl.shape[0]} in {right-left}x{bottom-top}")

def test_each_state_reads_as_itself():
  """The state is read, never counted from an assumed starting point.

  x1 and x2 are similar enough to score 0.832 against each other, so the
  margin above 0.85 is what makes reading safe.
  """
  for expected in ("off", "x1", "x2"):
    scores = skip_scores(f"skip_state_{expected}.png")
    ok(f"skip_state_{expected} reads as {expected}",
       scores[expected] >= THRESHOLD, f"{scores[expected]:.3f}")
    others = {k: v for k, v in scores.items() if k != expected}
    ok(f"and not as {'/'.join(others)}",
       all(v < THRESHOLD for v in others.values()),
       ", ".join(f"{k}={v:.3f}" for k, v in others.items()))

def test_the_press_position_is_on_the_button():
  """Where the button actually sits, so the press is not aimed from memory."""
  left, top, right, bottom = C.SKIP_BUTTON_BBOX
  crop = cv2.imread(os.path.join(FIXTURES, "skip_state_off.png"))[top:bottom, left:right]
  tpl = cv2.imread("assets/buttons/skip_off.png")
  result = cv2.matchTemplate(crop, tpl, cv2.TM_CCOEFF_NORMED)
  _, _, _, loc = cv2.minMaxLoc(result)
  centre = (left + loc[0] + tpl.shape[1] // 2, top + loc[1] + tpl.shape[0] // 2)
  x, y = C.SKIP_BUTTON_MOUSE_POS
  ok("SKIP_BUTTON_MOUSE_POS is on the button",
     abs(centre[0] - x) <= 8 and abs(centre[1] - y) <= 8, f"{centre} vs {(x, y)}")

def radio_green(fixture, pos):
  """The chosen radio is filled green; the rest are grey."""
  img = np.array(cv2.imread(os.path.join(FIXTURES, fixture)))[:, :, ::-1]
  x, y = pos
  patch = img[y - 9:y + 9, x - 9:x + 9].reshape(-1, 3)
  return sum(1 for r, g, b in patch if g > 140 and r < 170 and b < 120)

def test_the_quick_mode_radio_position():
  """The radios are 68px apart, not the 112px of the event-choice list.

  They match event_choice_1.png at 0.974, so deriving them from
  LAST_EVENT_CHOICE_ICON_TOP is tempting and wrong.
  """
  chosen = radio_green("quick_mode_shorten_all.png", C.QUICK_MODE_SHORTEN_ALL_MOUSE_POS)
  other = radio_green("quick_mode_dont_use.png", C.QUICK_MODE_SHORTEN_ALL_MOUSE_POS)
  ok("'Shorten all events' reads as selected when it is", chosen > 200, chosen)
  ok("and as unselected when another radio is", other == 0, other)

def test_the_radio_is_clicked_before_confirm():
  """Confirm commits, so a Confirm above the radio click would commit the old
  choice - which is what "leaving the default" used to do."""
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  branch = source.index('if matches["quick_mode"]')
  body = source[branch:branch + 1200]
  radio = body.index("QUICK_MODE_SHORTEN_ALL_MOUSE_POS")
  confirm = body.index("confirm_btn.png")
  ok("the radio is selected before Confirm is pressed", radio < confirm)

def test_skip_is_set_once_per_career():
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  ok("the lobby sets it behind a flag", 'if not _career_start["skip_set"]' in source)
  ok("and the flag is cleared when a career completes",
     '_career_start["skip_set"] = False' in source)
  ok("the helper bails on stop_event, so F1 still works",
     "stop_event.is_set()" in source[source.index("def set_skip_x2"):
                                     source.index("def set_skip_x2") + 900])

for test in [test_the_templates_fit_the_region, test_each_state_reads_as_itself,
             test_the_press_position_is_on_the_button,
             test_the_quick_mode_radio_position,
             test_the_radio_is_clicked_before_confirm,
             test_skip_is_set_once_per_career]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
