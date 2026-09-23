"""The "back to the title screen" dialog, and walking into the career from it.

Run with `python tests/test_session_error.py` from the repo root.

"Returning to Title screen due to inactivity." has a single Title Screen button
and no Cancel, so the generic dismisser has nothing to take and the blind-tap
recovery cannot advance it - DIALOG_ADVANCE_MOUSE_POS (553,400) lands on empty
dialog body. It stalls rather than loops, so the one-repeating-log-line
signature that gives an ordinary wedge away is absent too.

It has been got wrong twice, each time by keying on something that varies.

First a pixel gate looking for a green button - and this dialog's button is
white. Then the message line, "Returning to Title screen due to inactivity.",
which was blind to the second wording four days later: "A session verification
error occurred.", under a different header, scoring 0.544. That miss cost 41
minutes of blind tapping, an Alarm Clock spent on a phantom Retry, and the
career (2026-09-23 17:57).

It is now keyed on the **button**, which is the one thing both wordings share -
to the pixel, x 434-671 and y 672-735 in both - and which is also the thing the
handler presses. The lesson is in the ordering: match what you are going to
click, not what happens to be written above it.

Fixtures:
  out_of_career/session_error.png              "...due to inactivity."
  out_of_career/session_verification_error.png "A session verification error..."
  out_of_career/game_home.png                  home, which has "To Title Screen"
  out_of_career/in_career.png                  a career lobby
  sparks/spark_selection_notice.png            another one-button dialog
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.execute as E                              # noqa: E402
import utils.constants as constants                   # noqa: E402
from core.recognizer import multi_match_templates     # noqa: E402

FIXTURES = os.path.join("tests", "fixtures")
DIALOG = os.path.join(FIXTURES, "out_of_career", "session_error.png")
HOME = os.path.join(FIXTURES, "out_of_career", "game_home.png")
LOBBY = os.path.join(FIXTURES, "out_of_career", "in_career.png")
SPARK_NOTICE = os.path.join(FIXTURES, "sparks", "spark_selection_notice.png")
VERIFICATION = os.path.join(FIXTURES, "out_of_career", "session_verification_error.png")

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def matches(path):
  return multi_match_templates(E.templates, screen=Image.open(path))

def test_the_template_is_registered():
  ok("session_error is in the dispatch templates", "session_error" in E.templates)
  ok("and its asset exists", os.path.exists(E.templates["session_error"]),
     E.templates["session_error"])

def test_both_wordings_are_recognised():
  """The point of keying on the button: one template, every wording."""
  for path, what in ((DIALOG, "...due to inactivity"),
                     (VERIFICATION, "A session verification error occurred")):
    if not os.path.exists(path):
      print(f"skip  no fixture {path}")
      continue
    ok(f"matched: {what}", bool(matches(path)["session_error"]))

def test_the_dialog_is_recognised():
  if not os.path.exists(DIALOG):
    print("skip  no session error fixture")
    return
  found = matches(DIALOG)
  ok("the Session Error dialog matches", bool(found["session_error"]))
  # It is raised over whatever was on screen, so nothing else about the frame
  # can be relied on - including the lobby hint, which is absent here only
  # because this capture was taken on Scenario Select.
  ok("and the lobby hint is not found on it", not found["tazuna"])

def test_ordinary_screens_do_not_match():
  for path in (HOME, LOBBY, SPARK_NOTICE):
    if not os.path.exists(path):
      print(f"skip  no fixture {path}")
      continue
    ok(f"{os.path.basename(path)} does not match session_error",
       not matches(path)["session_error"])

def test_the_branch_runs_before_the_home_screen_stop():
  """Ordering, and it is the whole point of where the branch sits.

  The dialog can be raised *at* the home screen - that is where the 2026-09-21
  one came from, on the first press after a ~3h gap - and the nav bar is still
  drawn behind it. Read there as a finished career, the bot would stop on a
  career that is perfectly alive.
  """
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  session = source.index('if matches["session_error"]')
  home = source.index('if matches["team_rank"] or matches["game_nav"]')
  date = source.index('if matches["date_changed"]')
  ok("session_error is handled before the home-screen stop", session < home)
  ok("and before the date-changed reload", session < date)

def test_the_walk_back_is_bounded_and_resumes():
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  branch = source[source.index('if matches["session_error"]'):]
  branch = branch[:branch.index("# The career is over")]
  ok("it presses the Title Screen button",
     "SESSION_ERROR_BUTTON_MOUSE_POS" in branch)
  ok("then taps the title screen", "TITLE_SCREEN_TAP_MOUSE_POS" in branch)
  ok("and hands the reload to the resume path",
     "RESUMING_CAREER = SEEN_LOBBY" in branch)
  ok("bounded by SESSION_ERROR_LIMIT", "SESSION_ERROR_LIMIT" in branch)
  ok("a Session Error cannot be pressed at forever",
     isinstance(E.SESSION_ERROR_LIMIT, int) and 0 < E.SESSION_ERROR_LIMIT <= 5,
     str(E.SESSION_ERROR_LIMIT))

def test_the_button_sits_where_the_dialog_draws_it():
  bx, by = constants.SESSION_ERROR_BUTTON_MOUSE_POS
  # Measured on both captures, which agree to the pixel: x 434-671, y 672-735.
  ok("the press lands inside the button", 434 < bx < 671 and 672 < by < 735,
     f"({bx},{by})")
  # The template *is* the button now, so unlike the message it replaced it can
  # be clicked at its own centre - and a drifting dialog would take the press
  # with it rather than leaving it behind.
  ok("and the template is the button, not the message",
     "title_screen_btn" in E.templates["session_error"],
     E.templates["session_error"])
  # The title tap is the one fixed point of the startup walk, and it is outside
  # the game panel, so a press that missed cannot hit anything.
  tx, _ = constants.TITLE_SCREEN_TAP_MOUSE_POS
  left, _, width, _ = constants.GAME_SCREEN_REGION
  ok("the title tap is clear of the game panel", tx > left + width,
     f"x {tx} vs panel right edge {left + width}")

if __name__ == "__main__":
  test_the_template_is_registered()
  test_both_wordings_are_recognised()
  test_the_dialog_is_recognised()
  test_ordinary_screens_do_not_match()
  test_the_branch_runs_before_the_home_screen_stop()
  test_the_walk_back_is_bounded_and_resumes()
  test_the_button_sits_where_the_dialog_draws_it()
  print()
  if failures:
    print(f"{len(failures)} failed: " + ", ".join(failures))
    sys.exit(1)
  print("all ok")
