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
  home = source.index('if matches["to_home"]')
  generic = source.index("# Generic handlers.")
  cancel = source.index('matches["cancel"]', generic)
  ok("team_rank is checked before to_home", rank < home)
  ok("to_home is above the generic handlers", home < generic)
  ok("and above the generic cancel", home < cancel)

def test_stopping_is_a_return_not_a_click():
  """A finished career must stop the loop, not try to navigate.

  Anything else is guessing at menus the bot has no model of, on a screen with
  Purchase Carats and To Title Screen on it. There are now three ways out, and
  the order between them is what this pins: the daily reset and the Session
  Error walk-back both leave a career in progress behind this screen and resume
  it through Career, and only then may career_start walk a *new* one.
  """
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  branch = source.index('if matches["team_rank"]')
  # To the next branch, not a fixed slice. This used to take 800 characters,
  # which stopped covering the branch the moment career_start was added to it
  # and failed on a missing "return" that had simply moved out of the window.
  body = source[branch:source.index('if matches["to_home"]', branch)]
  ok("the branch returns", "return" in body)
  resume = body.index("if RESUMING_CAREER")
  ok("the resume path is gated on RESUMING_CAREER", resume < body.index("return"))
  ok("and it taps the Career button, nothing else",
     "CAREER_BUTTON_MOUSE_POS" in body[resume:body.index("return")])
  # A career still in progress is resumed before a new one is ever started,
  # or an interrupted career would be abandoned and paid for twice.
  ok("resuming is checked before starting a new career",
     resume < body.index("CAREER_START_ENABLED"))
  ok("and starting a new one is still behind its setting",
     "state.CAREER_START_ENABLED" in body)
  # Set by the three reloads that leave the career in progress, and by nothing
  # else: the daily reset, the Session Error walk-back, and the restart after a
  # frozen client. All three land on this same home screen, and without it any
  # of them reads a live career as finished - or, with career_start on, starts
  # a new one on top of a career that is still running.
  ok("RESUMING_CAREER is only set by a reload that keeps the career",
     source.count("RESUMING_CAREER = SEEN_LOBBY") == 3,
     f"{source.count('RESUMING_CAREER = SEEN_LOBBY')} sites")
  ok("and cleared as soon as a lobby is seen again",
     "SEEN_LOBBY = True\n    RESUMING_CAREER = False" in source)

def test_the_game_navigation_bar():
  """The bar along the bottom of the game's own screens, which carries Scout.

  The team rank badge is missing from some of the screens the game walks
  through after a career, and there the loop fell through to its blind taps -
  one of which, DIALOG_ADVANCE_ALT_MOUSE_POS, lands in the Scout column. That
  is the gacha, and it is why careers kept ending up in the summon menu. The
  bar is on the game's own screens and on none of the career's, so stopping on
  it is safe in the direction that matters.

  One tile is not enough, which cost a whole evening. `game_nav` is cut from
  the Scout tile in its INACTIVE state, so it matches every screen where Scout
  is not the open tab and fails on the one screen where it is - the Scout
  screen, which is exactly where the blind tap lands. Measured 2026-09-19:
  0.451 there against 0.976 one tap later on Home.

  Cutting a different tile only moves the blind spot: `game_home.png` was
  captured with the Race tab open, so a Race-tile template fails on it for the
  same reason. But only one tab can be active at a time, so for any two
  distinct tiles at least one is always in its normal state - the union is
  complete by construction rather than by luck. Race is the partner because
  its worst negative is 0.693 where story reaches 0.844 against a threshold of
  0.85.
  """
  def on_bar(name):
    m = matches(os.path.join(FIXTURES, name))
    return bool(m["game_nav"] or m["game_nav_alt"])

  for name in ("game_home.png", "game_home_gl.png", "home_mid_career.png",
               "scenario_select.png", "trainee_select.png",
               "game_scout_active.png"):
    ok(f"{name}: the navigation bar is found", on_bar(name))
  for name in ("in_career.png", "career_complete.png", "login_bonus.png",
               "date_changed.png", "continue_career.png"):
    ok(f"{name}: and not there", not on_bar(name))

def test_the_alt_tap_is_the_reason():
  """Kept as a measurement rather than a memory: where that blind tap lands.

  The Scout tile spans x 748-840, y 996-1074 on game_home.png; the tap sits in
  that column at the tile's top edge, under its event badge.
  """
  import utils.constants as C
  x, y = C.DIALOG_ADVANCE_ALT_MOUSE_POS
  ok("the alternate blind tap is in the Scout column", 748 <= x <= 840, x)
  ok("and level with the navigation bar", 960 <= y <= 1080, y)

def test_the_login_bonus_is_recognised():
  """The one post-career screen that matched nothing at all, so it was tapped at."""
  found = matches(os.path.join(FIXTURES, "login_bonus.png"))
  ok("the login bonus is recognised", bool(found["login_bonus"]))
  for name in ("in_career.png", "game_home.png", "career_complete.png",
               "date_changed.png", "scenario_select.png"):
    ok(f"{name}: the login banner does not match",
       not matches(os.path.join(FIXTURES, name))["login_bonus"])

def test_both_are_read_before_the_blind_taps():
  """Order is the whole point: read below the fallback, they would never fire."""
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  bar = source.index('matches["game_nav"]')
  login = source.index('if matches["login_bonus"]')
  # The comment above the template names the constant too, so anchor on the
  # use rather than the prose - the first plain mention is 1000 lines earlier.
  taps = source.index("constants.DIALOG_ADVANCE_ALT_MOUSE_POS")
  ok("the navigation bar is checked before the blind taps", bar < taps)
  ok("and so is the login bonus", login < taps)
  # skip_btn.png is the race skip that race_prep() drives inside a career.
  # Keyed here it would match mid-race, which is why the login branch locates
  # it for itself instead.
  skips = [key for key, path in E.templates.items() if path.endswith("skip_btn.png")]
  ok("the dispatch dict does not key on the race skip", not skips, skips)

for test in [test_templates_are_registered, test_the_home_screen_is_recognised,
             test_the_career_complete_screen_is_recognised,
             test_neither_fires_inside_a_career, test_dispatch_order,
             test_stopping_is_a_return_not_a_click,
             test_the_game_navigation_bar, test_the_alt_tap_is_the_reason,
             test_the_login_bonus_is_recognised,
             test_both_are_read_before_the_blind_taps]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
