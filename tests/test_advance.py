"""What `umatool advance` does with each screen, against captured frames.

Run with `python tests/test_advance.py` from the repo root. No OCR, so it is fast.

Started from the title screen, `advance` used to tap the character art on the
game's home screen until its 180 s timeout, because the only screen it knew how
to finish on was the career lobby (2026-09-15).

Fixtures in tests/fixtures/out_of_career/:
  in_career.png                   a career lobby: done
  date_changed.png                the Date Changed dialog, where the lobby hint scores 0.80
  continue_career.png             Continue Career: press Resume
  game_home.png, game_home_gl.png,
  home_mid_career.png             the home screen: tap Career
  scenario_select.png,
  trainee_select.png              career setup, reached when no career is in progress: stop
  login_bonus.png, career_complete.png  neither home nor setup
"""
import os
import sys

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import umatool as U                 # noqa: E402
import utils.constants as C         # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "out_of_career")

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def decide(name):
  return U.advance_decision(cv2.imread(os.path.join(FIXTURES, name)))

def test_lobby():
  action, _, detail = decide("in_career.png")
  ok("the career lobby ends the advance", action == "lobby", detail)
  action, _, detail = decide("date_changed.png")
  ok("the Date Changed dialog is not mistaken for the lobby", action != "lobby", f"{action} ({detail})")

def test_continue_career():
  action, point, detail = decide("continue_career.png")
  ok("Continue Career presses Resume", action == "resume", detail)
  ok("at the Resume button", point and abs(point[0] - 686) <= 6 and abs(point[1] - 775) <= 6, point)

def test_home_screen():
  for name in ("game_home.png", "game_home_gl.png", "home_mid_career.png"):
    action, point, detail = decide(name)
    ok(f"{name}: the home screen taps Career", action == "career", f"{action} ({detail})")
    ok(f"{name}: at the Career button", point == C.CAREER_BUTTON_MOUSE_POS, point)

def test_career_setup_stops():
  for name in ("scenario_select.png", "trainee_select.png"):
    action, point, detail = decide(name)
    ok(f"{name}: career setup stops with no click", action == "setup" and point is None, f"{action} ({detail})")

def test_other_screens_are_not_home():
  for name in ("login_bonus.png", "career_complete.png"):
    action, _, detail = decide(name)
    ok(f"{name}: not taken for home, setup or the lobby",
       action not in ("career", "setup", "lobby"), f"{action} ({detail})")

if __name__ == "__main__":
  test_lobby()
  test_continue_career()
  test_home_screen()
  test_career_setup_stops()
  test_other_screens_are_not_home()
  if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
  print("\nall ok")
