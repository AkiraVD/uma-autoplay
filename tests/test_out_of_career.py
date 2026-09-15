"""Leaving a finished career instead of tapping at it forever.

Run with `python tests/test_out_of_career.py` from the repo root.

Two careers ended the same way: the loop walked out of the career, landed on the
game's own home screen, and tapped at the character art until the supervisor's
stall timer killed it - 52 minutes on career 4, 21 on career 5. The taps were
harmless (DIALOG_ADVANCE_MOUSE_POS lands on artwork, clear of every menu
button), but the run was over and nothing said so.

Fixtures in tests/fixtures/out_of_career/:
  career_complete.png  the "Career Complete - To Home / Edit Team" screen
  game_home.png        the game's home screen, career already over
  in_career.png        a career lobby, where neither must ever match
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.execute as E                              # noqa: E402
from core.recognizer import multi_match_templates     # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "out_of_career")
COMPLETE = os.path.join(FIXTURES, "career_complete.png")
HOME = os.path.join(FIXTURES, "game_home.png")
IN_CAREER = os.path.join(FIXTURES, "in_career.png")

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def matches(path):
  return multi_match_templates(E.templates, screen=Image.open(path))

def test_templates_are_registered():
  ok("to_home is in the dispatch templates", "to_home" in E.templates)
  ok("team_rank is in the dispatch templates", "team_rank" in E.templates)
  for key in ("to_home", "team_rank"):
    ok(f"{key}'s asset exists", os.path.exists(E.templates[key]), E.templates[key])

def test_the_home_screen_is_recognised():
  if not os.path.exists(HOME):
    print("skip  no home fixture")
    return
  found = matches(HOME)
  ok("the team rank badge is found on the home screen", bool(found["team_rank"]))
  ok("and the lobby hint is not", not found["tazuna"])

def test_the_career_complete_screen_is_recognised():
  if not os.path.exists(COMPLETE):
    print("skip  no career-complete fixture")
    return
  found = matches(COMPLETE)
  ok("To Home is found", bool(found["to_home"]))
  # The badge belongs to the game's own screens; this one is still the career's.
  ok("the team rank badge is not", not found["team_rank"])

def test_neither_fires_inside_a_career():
  """The dangerous direction: stopping a healthy run."""
  if not os.path.exists(IN_CAREER):
    print("skip  no in-career fixture")
    return
  found = matches(IN_CAREER)
  ok("team_rank does not match in a career", not found["team_rank"])
  ok("to_home does not match in a career", not found["to_home"])
  ok("and the lobby is still recognised", bool(found["tazuna"]))

def test_dispatch_order():
  """team_rank is checked before to_home, and both before the generic handlers.

  A frame showing both should read as "already out" rather than clicking. And
  either sitting below the generic block would be eaten by next/cancel, which
  is the mistake four other screens in this scenario have already made.
  """
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  rank = source.index('if matches["team_rank"]')
  home = source.index('if click(boxes=matches["to_home"]')
  generic = source.index("# Generic handlers.")
  cancel = source.index('matches["cancel"]', generic)
  ok("team_rank is checked before to_home", rank < home)
  ok("to_home is above the generic handlers", home < generic)
  ok("and above the generic cancel", home < cancel)

def test_stopping_is_a_return_not_a_click():
  """A finished career must stop the loop, not try to navigate.

  Anything else is guessing at menus the bot has no model of, on a screen with
  Purchase Carats and To Title Screen on it. The one exception is the daily
  reset, which reloads the game to this same screen with the career still in
  progress: there the bot taps Career to resume, and only when a lobby has
  already been seen this run.
  """
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  branch = source.index('if matches["team_rank"]')
  body = source[branch:branch + 800]
  ok("the branch returns", "return" in body)
  resume = body.index("if RESUMING_CAREER")
  ok("the resume path is gated on RESUMING_CAREER", resume < body.index("return"))
  ok("and it taps the Career button, nothing else", "CAREER_BUTTON_MOUSE_POS" in body[resume:body.index("return")])
  ok("RESUMING_CAREER is only set by the date-changed reload",
     source.count("RESUMING_CAREER = SEEN_LOBBY") == 1)
  ok("and cleared as soon as a lobby is seen again",
     "SEEN_LOBBY = True\n    RESUMING_CAREER = False" in source)

for test in [test_templates_are_registered, test_the_home_screen_is_recognised,
             test_the_career_complete_screen_is_recognised,
             test_neither_fires_inside_a_career, test_dispatch_order,
             test_stopping_is_a_return_not_a_click]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
