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
import core.execute as E                              # noqa: E402
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
  ok("career_start is NOT in the config schema", "career_start" not in template)
  ok("it is a bot setting, with a default", "career_start" in state.BOT_DEFAULTS)
  ok("and is off by default - it spends 30 TP",
     state.BOT_DEFAULTS["career_start"]["enabled"] is False)
  ok("state reads it", hasattr(state, "CAREER_START_ENABLED"))

def test_the_consecutive_limit():
  """How many careers one run may start, and who counts as one.

  The limit counts careers the bot *starts itself*. A career already in
  progress when the bot was started is not one of them, so "3" means three
  started here, not three played - and the Live Log's count has to be read off
  the same number or the two disagree.
  """
  ok("max_consecutive is a bot setting",
     "max_consecutive" in state.BOT_DEFAULTS["career_start"])
  ok("and defaults to no limit",
     state.BOT_DEFAULTS["career_start"]["max_consecutive"] == 0)
  ok("state reads it", hasattr(state, "CAREER_START_MAX"))
  ok("and carries the running count", hasattr(state, "CAREERS_STARTED"))

  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  branch = source[source.index('if matches["team_rank"] or matches["game_nav"]'):]
  branch = branch[:branch.index('if matches["to_home"]')]
  # The guard has to sit before the walk, or the run overshoots by one career
  # and spends 30 TP doing it.
  guard = branch.index("CAREERS_STARTED >= state.CAREER_START_MAX")
  ok("the limit is checked before a career is started",
     guard < branch.index("career_start.start()"))
  ok("and 0 means no limit",
     "state.CAREER_START_MAX and" in branch)
  # The count is no longer incremented here: career_start writes the career to
  # the ledger and sets the count from it, so the number the loop compares
  # against the limit is the number of rows on disk and cannot drift from it.
  walk = open(os.path.join("core", "career_start.py"), encoding="utf-8").read()
  ok("the count is set from the ledger, not incremented",
     "state.CAREERS_STARTED = len(started_careers())" in walk)
  ok("and only after a career really started",
     walk.index("career_uuid = uuid.uuid4().hex")
     < walk.index("state.CAREERS_STARTED = len(started_careers())"))

def test_the_log_page_is_told_the_count():
  """The Live Log header reads the same number the limit counts."""
  server = open(os.path.join("server", "main.py"), encoding="utf-8").read()
  payload = server[server.index("def log_data("):]
  payload = payload[:payload.index("return data")]
  for key in ("CAREERS_STARTED", "CAREER_START_MAX", "CAREER_START_ENABLED"):
    ok(f"/logs/data carries {key}", key in payload)
  view = os.path.join("web", "src", "components", "logs", "LogView.tsx")
  if not os.path.exists(view):
    print("skip  no LogView.tsx")
    return
  page = open(view, encoding="utf-8").read()
  ok("the page types the careers field", "careers?:" in page)
  ok("and renders it", "careerLabel" in page)
  # It must not number from the career it was handed: started+1 would read one
  # out for the whole run.
  ok("it shows the count, not a position", "careers.started + 1" not in page)

def test_the_live_log_source_is_in_the_repo():
  """LogView.tsx was ignored by a bare `logs` rule in both .gitignore files,
  which matches a directory of that name at any depth - so the Live Log view's
  only source lived outside the repo while its build output was committed."""
  for path in (".gitignore", os.path.join("web", ".gitignore")):
    rules = [ln.strip() for ln in open(path, encoding="utf-8")]
    ok(f"{path} anchors its logs rule", "logs" not in rules, "bare 'logs' rule")

def test_the_frozen_panel_detector():
  """A client that keeps drawing a full frame it never changes.

  Three occurrences in three days, and `game_panel_blank` caught none of them:
  it looks for a *flat* panel, and these hold real artwork. What separates the
  two states is exact identity - measured on the live game while the bot
  played, consecutive grabs differed by 41,709 to 785,636 pixels and were never
  identical, while a frozen client is byte-identical every time.
  """
  frames = [os.path.join(FIXTURES, "out_of_career", "in_career.png"),
            os.path.join(FIXTURES, "out_of_career", "game_home.png"),
            os.path.join(WALK, "support_formation.png")]
  frames = [f for f in frames if os.path.exists(f)]
  digests = [E.panel_digest(frame(f)) for f in frames]
  ok("different screens give different digests",
     len(set(digests)) == len(digests), f"{len(set(digests))} of {len(digests)}")
  ok("and the same screen gives the same digest",
     E.panel_digest(frame(frames[0])) == digests[0])

  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  ok("the limit is a run of checks, not one frame",
     isinstance(E.FROZEN_PANEL_LIMIT, int) and 2 <= E.FROZEN_PANEL_LIMIT <= 40,
     str(E.FROZEN_PANEL_LIMIT))
  # It has to run before the dispatch, and on every pass: a freeze *in* the
  # lobby keeps matching the Tazuna hint, so the not-in-lobby recovery - where
  # game_panel_blank lives - is never reached at all.
  grab = source.index("screen = ImageGrab.grab()\n\n    # Before anything is read")
  digest = source.index("digest = panel_digest(screen)")
  dispatch = source.index("matches = multi_match_templates(templates, screen=screen)")
  ok("the check runs on every pass, before the dispatch",
     grab < digest < dispatch)
  ok("and it stops the bot rather than tapping on",
     "pixel-identical" in source)

def test_the_freeze_recovery():
  """Closing a frozen client and walking it back into the career.

  The detector only ever stopped the bot; with restart_on_freeze on it closes
  the game, launches it, taps the title and hands back to career_lobby with
  RESUMING_CAREER set - the same hand-off the daily reset and the Session Error
  dialog make, and the thing that stops the reload being read as a finished
  career, or (with career_start on) as a cue to start a new one on top of a
  career that is still running.
  """
  import core.recover as recover
  ok("restart_on_freeze is a bot setting",
     "restart_on_freeze" in state.BOT_DEFAULTS)
  ok("and is off by default - it ends the game process",
     state.BOT_DEFAULTS["restart_on_freeze"] is False)
  ok("state reads it", hasattr(state, "RESTART_ON_FREEZE"))

  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  branch = source[source.index("if frozen_panel >= FROZEN_PANEL_LIMIT:"):]
  branch = branch[:branch.index("    else:")]
  ok("the toggle gates it", "state.RESTART_ON_FREEZE" in branch)
  ok("off, it still stops as it did", 'error("Stopping.' in branch)
  ok("on, it restarts", "recover.restart_client()" in branch)
  ok("and hands the reload to the resume path",
     "RESUMING_CAREER = SEEN_LOBBY" in branch)
  # Without this the next pass counts the stale frame again and trips instantly.
  ok("it clears the frozen counters", "frozen_panel = 0" in branch
     and "last_digest = None" in branch)
  ok("restarts are bounded", "FREEZE_RESTART_LIMIT" in branch)
  ok("the bound is sane",
     isinstance(E.FREEZE_RESTART_LIMIT, int) and 0 < E.FREEZE_RESTART_LIMIT <= 20,
     str(E.FREEZE_RESTART_LIMIT))

  walk = open(os.path.join("core", "recover.py"), encoding="utf-8").read()
  ok("it closes before launching",
     walk.index("window.close(") < walk.index("window.launch_game()"))
  ok("it waits for the window rather than assuming", "_wait_for_window" in walk)
  ok("it taps the title screen", "TITLE_SCREEN_TAP_MOUSE_POS" in walk)
  ok("a close that fails does not become a launch",
     "Not restarting." in walk)
  for fn in ("restart_client", "_wait_for_window"):
    ok(f"{fn} bails when the bot is stopping",
       "_stopping()" in walk[walk.index(f"def {fn}("):])

def test_the_career_ledger():
  """The count lives in a file, one row per career, each with its own id.

  In memory it would reset every time the bot restarted - and restarting the
  bot is exactly what a frozen client forces, so "three careers" would never
  have meant three.
  """
  import tempfile
  progress, card = CS.PROGRESS, state.CAREER_START_BORROW_CARD
  try:
    with tempfile.TemporaryDirectory() as d:
      CS.PROGRESS = os.path.join(d, "career_start_progress.json")
      state.CAREER_START_BORROW_CARD = "Light Hello"
      ok("a fresh ledger counts nothing", CS.started_careers() == [])
      CS.remember_card("Light Hello", career_uuid="aaa")
      CS.remember_card("Light Hello", career_uuid="bbb")
      rows = CS.started_careers()
      ok("each career is a row", len(rows) == 2, str(len(rows)))
      ok("with its own id", {r["uuid"] for r in rows} == {"aaa", "bbb"})
      # The walk records the card on every pass through; only a career counts.
      CS.remember_card("Light Hello")
      ok("a borrow without a career does not count",
         len(CS.started_careers()) == 2, str(len(CS.started_careers())))
      ok("the card survives", CS.remembered_card() == "Light Hello")
      ok("reset clears the count", CS.reset_count() and CS.started_careers() == [])
      ok("and keeps the card, which is not part of it",
         CS.remembered_card() == "Light Hello")
  finally:
    CS.PROGRESS, state.CAREER_START_BORROW_CARD = progress, card

def test_the_count_is_read_back_not_zeroed():
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  ok("the run loads the count from the ledger",
     "len(career_start.started_careers())" in source)
  ok("and no longer zeroes it on start",
     "state.CAREERS_STARTED = 0" not in source)
  server = open(os.path.join("server", "main.py"), encoding="utf-8").read()
  ok("the page can read the count", "/career/count" in server)
  ok("and reset it", "/career/reset" in server)
  # A reset the running bot ignored until its next restart would be useless.
  reset = server[server.index("def career_reset("):]
  ok("reset clears the running bot's count too",
     "state.CAREERS_STARTED = 0" in reset[:600])

def test_how_the_bot_runs_is_not_config():
  """bot.json, not config.json, and migrated rather than reset.

  Config presets under uma_configs/ describe a trainee and are meant to be
  swapped; these describe this machine and this run. Loading a different preset
  must not change whether a frozen game is restarted.
  """
  import shutil
  import tempfile
  template = json.load(open("config.template.json", encoding="utf-8"))
  for key in ("sleep_time_multiplier", "tp_bottle_floor", "reroll_sparks",
              "restart_on_freeze", "career_start"):
    ok(f"{key} has left the config schema", key not in template)
    ok(f"and has a bot default", key in state.BOT_DEFAULTS)
  rules = [ln.strip() for ln in open(".gitignore", encoding="utf-8")]
  ok("bot.json is gitignored", "bot.json" in rules)
  main = open("main.py", encoding="utf-8").read()
  ok("the migration runs before update_config strips the keys",
     main.index("state.migrate_bot_settings()") < main.index("update_config()\n"))

  original, cwd = state.BOT_FILE, os.getcwd()
  try:
    with tempfile.TemporaryDirectory() as d:
      shutil.copy("config.json", os.path.join(d, "config.json"))
      os.chdir(d)
      state.BOT_FILE = "bot.json"
      settled = {"sleep_time_multiplier": 2, "tp_bottle_floor": 7,
                 "reroll_sparks": False, "restart_on_freeze": True,
                 "career_start": {"enabled": True, "borrow_card": "Light Hello",
                                  "max_consecutive": 3}}
      # The bug this exists for: update_config() strips the moved keys from
      # config.json at startup, so a migration reading the *merged* config sees
      # nothing and a settled setup comes back as defaults - which is exactly
      # what happened live. It therefore reads config.json itself, and runs
      # from main.py before update_config().
      json.dump(settled, open("config.json", "w", encoding="utf-8"))
      ok("a settled config is migrated, not defaulted",
         state.migrate_bot_settings() is True)
      ok("and written to the new file", os.path.exists("bot.json"))
      state.load_bot()
      ok("the globals follow it",
         state.CAREER_START_MAX == 3 and state.RESTART_ON_FREEZE is True
         and state.REROLL_SPARKS is False)
      ok("a second call is a no-op once the file exists",
         state.migrate_bot_settings() is False)
      # Saving a partial patch must not wipe the rest.
      state.save_bot({"career_start": {"max_consecutive": 9}})
      ok("a partial save keeps the other career_start fields",
         state.CAREER_START_BORROW_CARD == "Light Hello"
         and state.CAREER_START_MAX == 9)
      ok("and keeps the settings outside it",
         state.TP_BOTTLE_FLOOR == 7 and state.SLEEP_TIME_MULTIPLIER == 2)
      open("bot.json", "w").write("{ not json")
      state.load_bot()
      ok("a corrupt file falls back to defaults",
         state.CAREER_START_MAX == 0 and state.RESTART_ON_FREEZE is False)
  finally:
    os.chdir(cwd)
    state.BOT_FILE = original
    state.load_bot()

def test_the_loop_only_starts_a_career_when_told_to():
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  branch = source[source.index('if matches["team_rank"] or matches["game_nav"]'):]
  branch = branch[:branch.index('if matches["to_home"]')]
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
  test_the_consecutive_limit()
  test_how_the_bot_runs_is_not_config()
  test_the_frozen_panel_detector()
  test_the_freeze_recovery()
  test_the_career_ledger()
  test_the_count_is_read_back_not_zeroed()
  test_the_log_page_is_told_the_count()
  test_the_live_log_source_is_in_the_repo()
  test_the_loop_only_starts_a_career_when_told_to()
  print()
  if failures:
    print(f"{len(failures)} failed: " + ", ".join(failures))
    sys.exit(1)
  print("all ok")
