"""Starting the next career: the screens, the borrow, and the two guards.

Run with `python tests/test_career_walk.py` from the repo root. It reads the
Borrow Card list with easyocr, so it starts slowly and takes a minute or two.

`career_lobby()` drove a career perfectly well and then stopped dead at the
home screen, because CAREER_BUTTON_MOUSE_POS was pressed in exactly one place
and only to resume after a date change. `core/career_start.py` walks the setup
screens instead: Next, Next, Next, re-borrow the Friends card, Start Career!.

**None of this has run against a live game.** What can be tested offline is
every piece the walk decides on: that each screen is recognised from its own
header and not mistaken for its neighbours, that the borrow list reads and the
right row is chosen, that an enabled Start Career! is seen as enabled, and that
the remembered card beats the configured one. The pressing itself is the part
the first live run has to prove.

Fixtures in tests/fixtures/career_walk/ (plus two already in out_of_career/):
  legacy_select.png       Legacy Select, both parents already chosen
  support_formation.png   a full deck with the Friends slot filled
  borrow_card.png         the Borrow Card list, four rows, three Light Hello
  final_confirmation.png  "Spend 30 TP to begin training?"
  veteran_max.png         "Veteran Umamusume Max", the hard stop
"""
import json
import os
import sys
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.career_start as CS                        # noqa: E402
import core.state as state                            # noqa: E402
import utils.constants as constants                   # noqa: E402
from core.recognizer import multi_match_templates     # noqa: E402

FIXTURES = os.path.join("tests", "fixtures")
WALK = os.path.join(FIXTURES, "career_walk")
SCREENS = {
  "scenario_select": os.path.join(FIXTURES, "out_of_career", "scenario_select.png"),
  "trainee_select": os.path.join(FIXTURES, "out_of_career", "trainee_select.png"),
  "legacy_select": os.path.join(WALK, "legacy_select.png"),
  "support_formation": os.path.join(WALK, "support_formation.png"),
  "borrow_card": os.path.join(WALK, "borrow_card.png"),
  "final_confirmation": os.path.join(WALK, "final_confirmation.png"),
  "veteran_max": os.path.join(WALK, "veteran_max.png"),
}
HOME = os.path.join(FIXTURES, "out_of_career", "game_home.png")
LOBBY = os.path.join(FIXTURES, "out_of_career", "in_career.png")

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def frame(path):
  return Image.open(path).convert("RGB")

def test_every_asset_exists():
  for key, path in CS.TEMPLATES.items():
    ok(f"{key}'s asset is on disk", os.path.exists(path), path)

def test_each_screen_is_recognised_as_itself():
  """And as nothing else. The four setup screens share one header pill and
  differ only in its wording, so this is the measurement that says the wording
  is enough."""
  for key, path in SCREENS.items():
    if not os.path.exists(path):
      print(f"skip  no fixture for {key}")
      continue
    found = multi_match_templates(CS.TEMPLATES, screen=frame(path))
    ok(f"{key} matches its own frame", bool(found[key]))
    others = [k for k in CS.TEMPLATES if k != key and found[k]]
    # restore_tp is the TP prompt's green button and is a button, not a header;
    # it is allowed to appear on any frame that really carries one.
    others = [k for k in others if k != "restore_tp"]
    ok(f"{key} is not confused with another screen", not others, ", ".join(others))

def test_the_home_screen_is_not_a_setup_screen():
  """The walk begins at Home, and Home carries the same navigation bar the
  setup screens do - so the headers are what has to tell them apart."""
  for path in (HOME, LOBBY):
    if not os.path.exists(path):
      continue
    found = multi_match_templates(CS.TEMPLATES, screen=frame(path))
    hit = [k for k, v in found.items() if v]
    ok(f"{os.path.basename(path)} matches no setup screen", not hit, ", ".join(hit))

def test_the_borrow_list_reads():
  path = SCREENS["borrow_card"]
  if not os.path.exists(path):
    print("skip  no borrow fixture")
    return
  rows = CS.read_borrow_rows(frame(path))
  texts = [t for t, _, _ in rows]
  ok("the list reads at all", bool(rows), f"{len(rows)} boxes")
  ok("and the card names are among them",
     sum(1 for t in texts if "Light Hello" in t) >= 3,
     ", ".join(t for t in texts if "Hello" in t))

def test_the_right_row_is_chosen():
  """Three of the four rows offer Light Hello, so the tie-break matters: the
  topmost wins, which with the list sorted on Last Login is the most recently
  active lender. Measured on the fixture, that row's name sits at (431,417)."""
  path = SCREENS["borrow_card"]
  if not os.path.exists(path):
    print("skip  no borrow fixture")
    return
  from rapidfuzz import fuzz
  rows = CS.read_borrow_rows(frame(path))
  best, best_score = None, 0
  for text, conf, pos in rows:
    score = fuzz.partial_ratio("light hello", text.lower())
    if score > best_score:
      best, best_score = (text, pos), score
  ok("a row matches the wanted card", best_score >= constants.BORROW_NAME_MIN_RATIO,
     f"best {best_score}")
  if best:
    text, (x, y) = best
    ok("and it is the topmost Light Hello row", 380 < y < 460, f"y {y}")
    ok("the tap lands inside the list", 270 < x < 840, f"x {x}")
    ok("the position is a plain int, not numpy",
       type(x) is int and type(y) is int, f"{type(x).__name__}")

def test_a_card_that_is_not_on_the_list_is_refused():
  """The failure that matters: taking *a* card when the wanted one is absent
  would quietly spend the career on the wrong support."""
  path = SCREENS["borrow_card"]
  if not os.path.exists(path):
    print("skip  no borrow fixture")
    return
  from rapidfuzz import fuzz
  rows = CS.read_borrow_rows(frame(path))
  for wanted in ("Kitasan Black", "Tazuna Hayakawa"):
    # Same rule take_borrow applies, length guard and all. Without the guard
    # this scores 100: partial_ratio takes the best substring, so a one-glyph
    # box - the list reads several, an 'S' off a rarity badge - matches any
    # name containing that letter, and the walk borrows a rarity badge.
    best = max((fuzz.partial_ratio(wanted.lower(), t.lower())
                for t, _, _ in rows if len(t) + 2 >= len(wanted)), default=0)
    ok(f"'{wanted}', which the list does not hold, scores below the bar",
       best < constants.BORROW_NAME_MIN_RATIO, f"best {best:.0f}")
  short = [t for t, _, _ in rows if len(t) <= 2]
  ok("and the list really does read one-glyph boxes", bool(short),
     ", ".join(repr(t) for t in short))

def test_an_enabled_start_button_reads_as_enabled():
  path = SCREENS["support_formation"]
  if not os.path.exists(path):
    print("skip  no formation fixture")
    return
  ok("Start Career! reads as enabled on a full deck",
     CS.start_button_enabled(frame(path)))
  # There is no disabled capture in the tree, so the other half of this is the
  # measurement in screen-map.md (0.512 disabled against 0.822 enabled) and the
  # threshold sitting between them.
  ok("and the threshold sits between the two measured states",
     0.512 < constants.START_CAREER_ENABLED_VALUE < 0.800,
     str(constants.START_CAREER_ENABLED_VALUE))

def test_the_remembered_card_beats_the_configured_one():
  original, state.CAREER_START_BORROW_CARD = state.CAREER_START_BORROW_CARD, "From Config"
  progress = CS.PROGRESS
  try:
    with tempfile.TemporaryDirectory() as d:
      CS.PROGRESS = os.path.join(d, "career_start_progress.json")
      ok("with no record, the configured card is used",
         CS.remembered_card() == "From Config", CS.remembered_card())
      CS.remember_card("Light Hello")
      ok("once one is recorded, it wins",
         CS.remembered_card() == "Light Hello", CS.remembered_card())
      with open(CS.PROGRESS, encoding="utf-8") as f:
        ok("and the record names the card", json.load(f)["borrowed"] == "Light Hello")
      # A corrupt file must not take the walk down with it.
      with open(CS.PROGRESS, "w", encoding="utf-8") as f:
        f.write("{not json")
      ok("a corrupt record falls back to the config",
         CS.remembered_card() == "From Config", CS.remembered_card())
  finally:
    CS.PROGRESS = progress
    state.CAREER_START_BORROW_CARD = original

def test_the_walk_is_bounded_and_off_by_default():
  ok("the walk cannot run forever",
     isinstance(CS.STEP_LIMIT, int) and 0 < CS.STEP_LIMIT <= 100, str(CS.STEP_LIMIT))
  ok("nor open the borrow list forever",
     isinstance(CS.BORROW_ATTEMPTS, int) and 0 < CS.BORROW_ATTEMPTS <= 5,
     str(CS.BORROW_ATTEMPTS))
  template = json.load(open("config.template.json", encoding="utf-8"))
  ok("career_start is in the config schema", "career_start" in template)
  ok("and is off by default - it spends 30 TP",
     template["career_start"]["enabled"] is False)
  ok("state reads it", hasattr(state, "CAREER_START_ENABLED"))

def test_the_loop_only_starts_a_career_when_told_to():
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  branch = source[source.index('if matches["team_rank"] or matches["game_nav"]'):]
  branch = branch[:branch.index('if click(boxes=matches["to_home"]')]
  ok("the home-screen branch is gated on the setting",
     "state.CAREER_START_ENABLED" in branch)
  ok("it still stops when the walk fails", "return" in branch)
  ok("and a started career is treated as a new one",
     "apply_scenario(new_career=True)" in branch)
  ok("the resume path is still checked first",
     branch.index("RESUMING_CAREER") < branch.index("CAREER_START_ENABLED"))

if __name__ == "__main__":
  test_every_asset_exists()
  test_each_screen_is_recognised_as_itself()
  test_the_home_screen_is_not_a_setup_screen()
  test_the_borrow_list_reads()
  test_the_right_row_is_chosen()
  test_a_card_that_is_not_on_the_list_is_refused()
  test_an_enabled_start_button_reads_as_enabled()
  test_the_remembered_card_beats_the_configured_one()
  test_the_walk_is_bounded_and_off_by_default()
  test_the_loop_only_starts_a_career_when_told_to()
  print()
  if failures:
    print(f"{len(failures)} failed: " + ", ".join(failures))
    sys.exit(1)
  print("all ok")
