"""The Recreation panel reader, against captured frames.

Run with `python tests/test_recreation_panel.py` from the repo root. This one
imports the real core.state, so it builds an easyocr Reader and is slow to
start - the name on the panel is OCR'd and there is no honest way to stub that.

Fixtures in tests/fixtures/recreation/:
  panel_riko_step3.png       the panel open, Riko Kashimoto, 3 of 5 chevrons filled
  team_showdown_no_panel.png a frame with no panel, so nothing must match
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.state as S          # noqa: E402
import core.outings as O        # noqa: E402
import core.execute as E        # noqa: E402
from core.recognizer import multi_match_templates  # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "recreation")
PANEL = os.path.join(FIXTURES, "panel_riko_step3.png")
NO_PANEL = os.path.join(FIXTURES, "team_showdown_no_panel.png")

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def test_reader():
  panel = S.check_recreation_panel(Image.open(PANEL))
  ok("the panel is read at all", panel is not None)
  ok("the card name is read", panel["card"] == "Riko Kashimoto", repr(panel["card"]))
  ok("three chevrons are filled", panel["filled"] == 3, str(panel["filled"]))

  # Two empty chevrons sit beside the three filled ones and must not be counted.
  ok("empty chevrons are not counted", panel["filled"] < 5)

  # A frame with no panel must count nothing rather than inventing a position.
  ok("no chevrons off-panel", S.count_filled_chevrons(Image.open(NO_PANEL)) == 0)

def test_dispatch():
  """The panel has to be recognised, and recognised before the cancel handler."""
  matched = multi_match_templates(E.templates, screen=Image.open(PANEL))
  hits = {k for k, v in matched.items() if v}
  ok("the panel template matches", "recreation_panel" in hits, str(sorted(hits)))
  ok("the friend row is located", "event_progress" in hits)
  # This is the whole reason the panel needs a branch: its Cancel button is a
  # 0.982 match, so a generic cancel handler dismisses the outing.
  ok("cancel also matches, which is the trap", "cancel" in hits)

  keys = list(E.templates)
  ok("the panel is dispatched before cancel",
     keys.index("recreation_panel") is not None and _branch_order_ok(),
     "recreation_panel branch sits above the generic handlers in career_lobby")

  box = matched["event_progress"][0]
  y = box[1] + box[3] // 2 - 30
  ok("the friend row click lands in the row, clear of its widgets",
     360 <= y <= 380, f"y={y}")

  ok("nothing matches on a frame without the panel",
     not [k for k, v in multi_match_templates(E.templates,
                                              screen=Image.open(NO_PANEL)).items() if v])

def _branch_order_ok():
  """career_lobby must handle the panel above the generic cancel handler."""
  src = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  body = src[src.index("def career_lobby("):]
  return body.index('matches["recreation_panel"]') < body.index('matches["cancel"]')

def test_position():
  panel = S.check_recreation_panel(Image.open(PANEL))
  O.reset()
  ok("the panel sets the chain position",
     O.set_position(panel["card"], panel["filled"]) == ("riko-kashimoto", 3))
  _, label = O.next_outing()
  # Filled chevrons are steps already done, so three filled means step 4 is next.
  # That mapping comes from watching the bar go from zero filled to one filled
  # across a single outing.
  ok("three filled means step 4 is next", "step 4/5" in label, label)
  ok("two steps are left", O.steps_remaining() == 2, str(O.steps_remaining()))

def main():
  for test in (test_reader, test_dispatch, test_position):
    print(f"--- {test.__name__}")
    test()
  print("")
  print("FAILED: " + ", ".join(failures) if failures else "all checks passed")
  return 1 if failures else 0

if __name__ == "__main__":
  sys.exit(main())
