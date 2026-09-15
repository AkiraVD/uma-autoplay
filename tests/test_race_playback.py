"""The Race Playback dialog, against captured frames.

Run with `python tests/test_race_playback.py` from the repo root. It imports
core.execute, which builds the easyocr Reader, so it is slow to start.

Fixtures in tests/fixtures/race_playback/ (Kitasan Black, Hanshin Umamusume
Stakes, 2026-09-15):
  dialog_unticked.png   "Race Playback" over the preview, "Do not show again." off
  dialog_ticked.png     the same dialog with the box ticked
  race_preview.png      the preview alone, which must not read as the dialog
  after_ok_loading.png  the loading screen after OK
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.execute as E                            # noqa: E402
from core.recognizer import multi_match_templates   # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "race_playback")

def fixture(name):
  return Image.open(os.path.join(FIXTURES, name)).convert("RGB")

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def found(screen, name):
  return bool(multi_match_templates({name: E.templates[name]}, screen=screen)[name])

def test_detection():
  ok("the unticked dialog is found", found(fixture("dialog_unticked.png"), "race_playback"))
  ok("and the ticked one", found(fixture("dialog_ticked.png"), "race_playback"))
  ok("but not the preview behind it", not found(fixture("race_preview.png"), "race_playback"))
  ok("nor the loading screen after OK", not found(fixture("after_ok_loading.png"), "race_playback"))
  # Why the branch has to run before the generic handlers: both of these match
  # on the dialog frame, and either would loop it.
  ok("the generic Cancel does match the dialog", found(fixture("dialog_unticked.png"), "cancel"))

def test_checkbox():
  ok("unticked box reads as unticked", not E.playback_box_ticked(fixture("dialog_unticked.png")))
  ok("ticked box reads as ticked", E.playback_box_ticked(fixture("dialog_ticked.png")))

if __name__ == "__main__":
  test_detection()
  test_checkbox()
  if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
  print("\nall ok")
