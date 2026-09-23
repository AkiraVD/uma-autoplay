import pyautogui
import utils.control as control
from utils.tools import sleep, get_secs, drag_scroll, click_and_hold
from PIL import ImageGrab, ImageStat

pyautogui.useImageNotFoundException(False)
# The corner fail-safe aborts the whole run with FailSafeException if the mouse
# is ever parked in a screen corner - including when a person nudges it while
# the bot is mid-move. Pause already stops the bot, so this only cost us a career.
pyautogui.FAILSAFE = False

import hashlib
import os
import re
import time
from rapidfuzz import fuzz
import core.state as state
import core.scenarios as scenarios
from core.state import check_support_card, check_unity_icons, check_failure, check_turn, check_mood, check_current_year, check_criteria, check_skill_pts, check_energy_level, check_energy_reserved, get_race_type, check_status_effects, check_aptitudes, check_credit, check_outing_available, check_recreation_panel, read_log_lines
from core.logic import do_something, decide_race_for_goal, training_value, should_recreate, has_extreme_burst, set_goal_context

from utils.log import info, warning, error, debug
import utils.constants as constants

from core.recognizer import is_btn_active, multi_match_templates, match_template
from core.skill import buy_skill
from core.gains import check_stat_gains
from core.events import event_choice, get_event_name
import core.outings as outings
import core.training_cost as training_cost
import core.trainee as trainee
import core.lessons as lessons
import core.sparks as sparks
import core.career_start as career_start
import core.recover as recover

templates = {
  "event": "assets/icons/event_choice_1.png",
  "inspiration": "assets/buttons/inspiration_btn.png",
  "next": "assets/buttons/next_btn.png",
  "next2": "assets/buttons/next2_btn.png",
  # The race preview - "View Results" beside "Race" - is the screen the loop
  # sits on after choosing a race, and it had no handler at all: it caused a
  # 2h23m hang once and wedged career 7 twice in one night. Nothing existing
  # comes close to it (race_btn 0.35, next_btn 0.39), so it needs its own
  # template. Cut from the live frame; scores 1.000/0.999/0.996 on three
  # captures from three sessions against a best negative of 0.351 over nine
  # other screens, so 0.8 has enormous margin.
  # "This will put you at N consecutive races." - raised when the race list is
  # opened on a third race in a row. It pairs OK with a Cancel that cancel_btn
  # matches, so without a branch of its own the generic handler at :1360
  # dismisses it silently and whatever opened it simply opens it again: 302
  # times over 2h22m on 2026-09-20. Cut left of the count so the 2-race wording
  # matches the same asset. sep: best negative 0.426.
  # Kept when Trackblazer was parked (2026-09-21), and the asset path is the
  # only Trackblazer left in it: the warning is raised by the *game*, in any
  # mode, whenever the race list is opened on a third race in a row. What it
  # guards is generic - a dialog whose Cancel the handler below takes silently.
  "consecutive_races": "assets/trackblazer/consecutive_races_warning.png",
  # "You have a scheduled race. Proceed to the Races screen?" - raised on
  # entering a career whose agenda has a race this turn. This note previously
  # claimed no such window existed, on the strength of one turn-change lobby
  # that showed only the Races badge; both are real, and they appear at
  # different moments. It pairs Race with a Close that cancel_btn matches, so
  # like every other dialog in this chain it needs its own branch above the
  # generic handler. sep: best negative 0.547 (the consecutive-races warning,
  # which shares the green header). Measured 2026-09-20.
  # Kept for the same reason as consecutive_races above: parked mode, generic
  # trap. Its Close matches cancel_btn, so without a branch of its own the
  # generic handler dismisses it while logging nothing.
  "scheduled_race_notice": "assets/trackblazer/scheduled_race_available.png",
  "race_preview": "assets/buttons/race_preview_btn.png",
  # "Race Details ... Enter race?" - the confirmation the race list raises on
  # the Race button, and the last screen before a race actually starts.
  # race_day() and race_select() drive it blind, by pressing race_btn.png twice
  # in a row, so it never needed a handler until a bot was started while the
  # race list was already up: race_preview_btn scores 0.848 on this dialog's
  # narrower Race button, just under the 0.85 multi_match threshold, so the
  # frame fell through to the generic cancel - which passes no text and logs
  # nothing - and the list opened it again. Silent, and forever (2026-09-21,
  # the Japanese Derby of a Grand Concert career).
  # The template is the dialog's "Enter race?" line, so it must not be clicked
  # at its own centre; the Race button is found separately. 1.000 on two
  # captures four days apart against a best negative of 0.631 over 23 frames.
  "race_confirm": "assets/ui/enter_race_confirm.png",
  # And the screen the preview leads to: the fullscreen runner lineup, whose
  # "Race!" is a different button again (the preview's scores 0.33 on it).
  # Note this screen is fullscreen 1920x1080, not the portrait panel the rest
  # of the regions assume, which is part of why nothing matched here.
  # One positive frame only so far, against nine negatives at 0.22-0.33.
  "race_lineup": "assets/buttons/race_lineup_btn.png",
  # "Race Playback" - Landscape or Portrait, with "Do not show again." - opens
  # over the preview after Race. Its Cancel matches cancel_btn.png at 0.997, so
  # the generic handler dismissed it and the bot pressed Race again every ~17s
  # for 10 minutes (2026-09-15). Cut from the dialog's title: 1.000 on four
  # captures against a best negative of 0.704 (finish_confirm) over 21 frames,
  # most of them other green-titled dialogs.
  "race_playback": "assets/ui/race_playback.png",
  "cancel": "assets/buttons/cancel_btn.png",
  "tazuna": "assets/ui/tazuna_hint.png",
  "infirmary": "assets/buttons/infirmary_btn.png",
  "retry": "assets/buttons/retry_btn.png",
  # The "Try Again" dialog after a lost race - a different button from
  # retry_btn, which scores only 0.53 against it. That gap is why
  # max_race_retries could never fire: career 11 lost the Kikuka Sho with 782
  # Alarm Clocks in hand, one of them free that day, and ended there instead
  # of retrying. Cut from that frame; 1.000 on it against a best negative of
  # 0.486 (the "Start Career!" button, the nearest other green pill) over
  # thirteen frames. Only one positive so far - watch it.
  "try_again": "assets/buttons/try_again_btn.png",
  "claw_credit": "assets/buttons/claw_credit.png",
  "claw_result": "assets/buttons/claw_result.png",
  # Unity Cup team-race day replaces the lobby with a "Team Showdown" screen
  # that has no Tazuna hint, so the normal lobby check never fires there.
  "unity_race": "assets/buttons/unity_cup_race_btn.png",
  # The opponent picker is its own screen with only Back at the bottom, so the
  # lobby recovery used to back out of it and bounce straight back to the
  # Team Showdown screen - a loop.
  "unity_select_opponent": "assets/buttons/select_opponent_btn.png",
  "unity_begin_showdown": "assets/buttons/begin_showdown_btn.png",
  # The matchup screen offers "Watch Main Race" or "See All Race Results";
  # the latter skips the race animation and goes straight to the outcome.
  "unity_race_results": "assets/buttons/see_all_race_results_btn.png",
  # The Finals against Team Zenith gets its own VS screen with a circular Race!
  # disc instead of the usual Begin Showdown modal.
  "unity_zenith_race": "assets/buttons/zenith_race_btn.png",
  # Last screen of a run. It has no Tazuna hint and no Back or Close button,
  # so the lobby recovery below can only tap at it forever.
  "career_complete": "assets/buttons/complete_career_btn.png",
  # "Finish this Career playthrough?" - the confirmation behind Complete
  # Career. Like the Unity showdown modal it pairs Cancel with the accept
  # button, which is why the accept branches run before the generic
  # cancel handler rather than after it.
  "career_finish": "assets/buttons/finish_btn.png",
  # Clicking Recreation with a friend support in the deck opens a chooser
  # rather than going straight out: one row per friend card, then the trainee,
  # whose row is plain recreation. It was never handled, and its Cancel button
  # matches cancel_btn.png at 0.982, so every outing this bot has ever decided
  # to take was cancelled one poll later.
  "recreation_panel": "assets/ui/recreation_panel.png",
  "event_progress": "assets/ui/event_progress.png",
  # "Go on a fun outing? This will take up the entire turn." opens on top of
  # the chooser and reuses its green Recreation header, so recreation_panel
  # still matches (0.995) while event_progress is covered (0.638). The OK
  # button is what tells the two apart, and its Cancel is a 0.997 match, so
  # this has to be settled inside the panel branch.
  "ok": "assets/buttons/ok_btn.png",
  # A one-time dialog at the start of every career asking whether to shorten
  # events. Its four radio buttons match event_choice_1.png at 0.973, so
  # select_event() kept picking the top one and never pressed Confirm, and
  # the dialog has no title that OCRs so the repeat guard could not see it
  # either. Career 3 sat here until the supervisor gave up.
  "quick_mode": "assets/ui/quick_mode_settings.png",
  # Spark Selection, the screen after a career completes. Cut from the
  # "Reroll Sparks" button because that button exists nowhere else - which
  # is also why the branch must never click it: a reroll costs 30 TP.
  "sparks": "assets/ui/sparks_select.png",
  # "Career Complete - To Home / Edit Team", the last screen of a career.
  "to_home": "assets/buttons/to_home_btn.png",
  # The gold TEAM RANK badge, which the game shows on its own screens and
  # never inside a career. Seeing it means the career is over and this loop is
  # looking at something it has no business driving.
  "team_rank": "assets/ui/team_rank.png",
  # The game's own bottom navigation - Enhance / Story / Home / Race / Scout -
  # cut from the Scout tile, the one of the five whose art carries no event
  # badge. It is on every screen the game shows outside a career (home,
  # Scenario Select, trainee select) and on none inside one, so it means the
  # same thing as the team rank badge while also catching the screens that
  # carry no badge. Scores 0.930-1.000 on the five out-of-career frames against
  # a best negative of 0.693 (continue_career) over 87 fixture frames.
  #
  # It earns its place because DIALOG_ADVANCE_ALT_MOUSE_POS (756, 980) lands on
  # the Scout tile, which is the gacha. Any unreadable screen carrying this bar
  # had the blind tap opening Scout every other cycle and then backing out of
  # it again - which is what "it keeps going to the gacha menu after a career"
  # was. Stopping here means the tap never happens on those screens at all.
  "game_nav": "assets/ui/game_nav_scout.png",
  # The same bar, read off the Race tile. game_nav is cut from the Scout tile
  # in its inactive state, so it goes blind on the Scout screen itself - which
  # is precisely where DIALOG_ADVANCE_ALT_MOUSE_POS parks the bot. Only one tab
  # is ever active, so a second tile is always in its normal state and one of
  # the two always matches. Race was measured against enhance and story: it
  # scores 0.693 on the worst negative where story reaches 0.844, against a
  # 0.85 threshold. See docs/screen-map.md.
  "game_nav_alt": "assets/ui/game_nav_race.png",
  # The login bonus, which both the daily reset and the end of a career land
  # on. Nothing in this dict matched it, so it was the one screen in the
  # post-career walk that fell through to the blind taps. Its banner is
  # unmistakable: 1.000 against a best negative of 0.252 over the same 87
  # frames. Deliberately not keyed on skip_btn.png - that is the race skip,
  # which race_prep() uses inside a career.
  "login_bonus": "assets/ui/login_bonus.png",
  # The daily reset (22:00 local, career 4) drops a "Date Changed - It's a new
  # day!" dialog over the lobby; its OK reloads the game to the login bonus and
  # the home screen, with the career still there behind "Continue Career".
  "date_changed": "assets/ui/date_changed.png",
  "continue_career": "assets/ui/continue_career.png",
  # "Session Error - Returning to Title screen due to inactivity.", raised after
  # the game has sat idle for hours. Its single "Title Screen" button leaves the
  # generic dismisser nothing to take, so before this the loop fell through to
  # blind taps that land on empty dialog body - a stall, not a loop, so the one
  # repeating log line that gives a wedge away was absent too. Cut from the
  # message line, so it must not be clicked at its own centre.
  "session_error": "assets/ui/session_error.png",
  # Grand Concert. The concert screen replaces the lobby after each half-year's
  # last turn and has no Tazuna hint and no Back, so the lobby recovery used to
  # be all that saw it - and its alternate blind tap, DIALOG_ADVANCE_ALT, lands
  # on the Concert button. "Ready to start the concert?" pairs Start with a
  # Cancel that cancel_btn.png would take. "To Lessons" is on the Schedule
  # Notification that says a reserved song has become affordable.
  "gc_concert": "assets/grand_concert/concert_btn.png",
  "gc_concert_start": "assets/grand_concert/concert_start_btn.png",
  "gc_to_lessons": "assets/grand_concert/to_lessons_btn.png",
  # "Bonuses Updated! Concert bonuses updated!" (Close / Confirm), over the
  # first lobby after a concert. Nothing generic handles it, so it used to sit
  # there ~30s until the lobby recovery found its Close.
  "gc_bonuses_updated": "assets/grand_concert/bonuses_updated.png",
  # The last concert, after Senior Late Dec. Its button says "Grand Concert"
  # in lettering the concert_btn crop does not match, and after Start comes an
  # "ON STAGE!" disc over a screen whose only other button is Back - which the
  # lobby recovery would press, backing out of the finale.
  "gc_grand_concert": "assets/grand_concert/grand_concert_btn.png",
  "gc_on_stage": "assets/grand_concert/on_stage_btn.png",
}

# The turn whose scheduled race has already been opened. A list rather than a
# bare name so the loop can rebind it without a `global`, matching how the shop
# keeps `_visited`. Without this the branch fired on every pass of the loop:
# 302 clicks over 2h22m on one turn, because a failed click leaves the lobby
# unchanged and the badge still matching.
_scheduled_race_turn = [None]

def playback_box_ticked(screen):
  """True when the Race Playback dialog's "Do not show again." box is ticked.

  The tick is grey when off and green when on, like the Grand Concert's skip
  box (core/lessons.py::cutscene_unticked): 146 green pixels ticked, 0 not."""
  left, top, right, bottom = constants.RACE_PLAYBACK_CHECKBOX_BBOX
  box = screen.crop((left + 10, top + 10, right - 10, bottom - 10)).convert("RGB")
  green = sum(1 for r, g, b in box.getdata() if g > 150 and r < 170 and b < 110)
  return green >= 20

def deliberate_click(img, region=None, confidence=0.8, minSearch=2, text="",
                     settle=0.35, hold=0.2):
  """Click the way this game's client actually accepts, for buttons that ignore
  an ordinary one.

  The spark screen at the end of a career swallowed sixteen consecutive normal
  clicks. It was not a targeting problem: the window had focus and
  confirm_btn located dead on the button at (686, 995) every time. Moving
  there, pausing, then holding the button down went through on the first try.
  Same lesson as the skill list, which ignores a quick flick and needs a drag
  held at both ends.

  Both the pause and the hold are kept. Only one spark screen was available to
  test on and the working click changed both at once, so which of the two is
  load-bearing is not known - guessing and keeping the wrong half would put the
  stall straight back.

  Returns True if the button was found and clicked.
  """
  if state.stop_event.is_set() or not state.is_bot_running:
    return False
  if region:
    btn = pyautogui.locateCenterOnScreen(img, confidence=confidence,
                                         minSearchTime=minSearch, region=region)
  else:
    btn = pyautogui.locateCenterOnScreen(img, confidence=confidence,
                                         minSearchTime=minSearch)
  if not btn:
    return False
  if text:
    debug(text)
  control.moveTo(btn, duration=0.3)
  time.sleep(settle)
  control.mouseDown()
  time.sleep(hold)
  control.mouseUp()
  return True

def click(img: str = None, confidence: float = 0.8, minSearch:float = 2, click: int = 1, text: str = "", boxes = None, region=None):
  if state.stop_event.is_set():
    return False
  if not state.is_bot_running:
    return False

  if boxes:
    if isinstance(boxes, list):
      if len(boxes) == 0:
        return False
      box = boxes[0]
    else :
      box = boxes

    if text:
      debug(text)
    x, y, w, h = box
    center = (x + w // 2, y + h // 2)
    control.moveTo(center[0], center[1], duration=0.225)
    control.click(clicks=click, interval=0.15)
    return True

  if img is None:
    return False

  if region:
    btn = pyautogui.locateCenterOnScreen(img, confidence=confidence, minSearchTime=minSearch, region=region)
  else:
    btn = pyautogui.locateCenterOnScreen(img, confidence=confidence, minSearchTime=minSearch)
  if btn:
    if text:
      debug(text)
    control.moveTo(btn, duration=0.225)
    control.click(clicks=click, interval=0.15)
    return True

  return False

TRAINING_KEYS = ["spd", "sta", "pwr", "guts", "wit"]

def training_pos(key):
  return getattr(constants, f"{key.upper()}_TRAIN_MOUSE_POS")

def select_training(key):
  """Select a facility by position and confirm it took, using the banner.

  Only safe when `key` is not the facility that is already selected: clicking
  the selected one starts the training instead of selecting it.
  """
  x, y = training_pos(key)
  click(boxes=(x, y, 1, 1), text=f"Selecting {key.upper()} training.")
  sleep(0.3)
  selected, _ = state.check_selected_training()
  return selected == key

def go_to_training():
  # Must be scoped to the button area: the template is a short, generic strip and
  # a full-screen search happily matches unrelated desktop UI outside the game.
  return click("assets/buttons/training_btn.png", region=constants.SCREEN_BOTTOM_REGION)

def wait_for_training_screen(attempts=10):
  """Poll until the training banner names a facility. Returns the key or None."""
  for _ in range(attempts):
    if state.stop_event.is_set():
      return None
    selected, _ = state.check_selected_training()
    if selected:
      return selected
    sleep(0.3)
  return None

def peek_for_extreme_burst():
  """Training results when an Extreme Spirit Burst is ready, else None.

  Only called on a debuffed turn, which is rare, so the extra scan costs little
  over a career. The results are handed back so the turn does not pay for a
  second one. check_training leaves the lobby up again either way.
  """
  if not go_to_training():
    debug("Training button is not found, so the burst peek is skipped.")
    return None
  sleep(0.5)
  results = check_training()
  if any(has_extreme_burst(data) for data in results.values()):
    return results
  return None

def check_training():
  if state.stop_event.is_set():
    return {}

  results = {}

  # failcheck enum "train","no_train","check_all"
  failcheck="check_all"
  margin=5

  # The five facilities never move, so they are clicked by position rather than
  # located by icon template: an event badge (a "Duel!" starburst) can sit on an
  # icon and break the match, which used to drop that training for the turn.
  # One facility is always selected on arrival and which one is not
  # deterministic, so read it instead of assuming.
  # The lobby -> training transition is animated, and the lobby's "Debut" pill
  # sits where the banner does, so poll for the banner instead of trusting a
  # fixed sleep.
  current = wait_for_training_screen()
  if current is None:
    warning("Couldn't read the training banner, skipping the training check.")
    click(img="assets/buttons/back_btn.png")
    return {}

  # Grand Concert: every facility's Performance chip is on screen at once and
  # does not change with the selection, so one read covers all five.
  performance = state.check_performance() if state.GRAND_CONCERT_SEEN else None
  # A Lessons board of locked techniques has no badge to say what it needs.
  if performance is not None:
    blocked = lessons.blocked_types()
    performance["short"] = sorted(set(performance["short"]) | set(blocked))
    # A stuck board and the run for the 18th song are both worth more than the
    # gentle nudge a scheduled song gets.
    performance["urgent"] = bool(blocked) or lessons.pushing_for_gold(state.CURRENT_YEAR)
  if performance and performance["short"]:
    debug(f"Performance: short of {performance['short']}{' (urgent)' if performance['urgent'] else ''},"
          f" chips {performance['chips']}")

  for key in TRAINING_KEYS:
    if state.stop_event.is_set():
      return {}

    if key != current:
      if not select_training(key):
        warning(f"{key.upper()} training didn't get selected, not considering it this turn.")
        # The click may still have moved the selection, so resync before the next one.
        current, _ = state.check_selected_training()
        continue
      current = key

    support_card_results = check_support_card()
    # Unity Cup only; zeros in every other scenario, so this is safe to always read.
    support_card_results["unity"] = check_unity_icons()
    # The screen prints the actual stat gains for this facility. They beat the
    # support-count proxies when readable; an empty dict means fall back.
    support_card_results["gains"] = check_stat_gains()
    # Read while this facility is the selected one: the bar's dim tail is that
    # facility's real cost, discounts included.
    support_card_results["energy_cost"] = check_energy_reserved()
    support_card_results["performance"] = ({"types": performance["chips"].get(key, []),
                                            "short": performance["short"],
                                            "urgent": performance.get("urgent", False)} if performance else {})

    if key != "wit":
      if failcheck == "check_all":
        failure_chance = check_failure()
        if failure_chance < 0:
          # Unreadable. Mark only this training unsafe: letting -1 fall through
          # to the comparisons below made it look safer than MAX_FAILURE, which
          # then short-circuited every remaining training to 0% risk.
          warning(f"Couldn't read {key.upper()} failure chance, treating it as unsafe.")
          failure_chance = state.MAX_FAILURE + margin + 1
        elif failure_chance > (state.MAX_FAILURE + margin):
          info("Failure rate too high skip to check wit")
          failcheck="no_train"
          failure_chance = state.MAX_FAILURE + margin
        elif failure_chance < (state.MAX_FAILURE - margin):
          info("Failure rate is low enough, skipping the rest of failure checks.")
          failcheck="train"
          failure_chance = 0
      elif failcheck == "no_train":
        failure_chance = state.MAX_FAILURE + margin
      elif failcheck == "train":
        failure_chance = 0
    else:
      if failcheck == "train":
        failure_chance = 0
      else:
        failure_chance = check_failure()
        if failure_chance < 0:
          warning("Couldn't read WIT failure chance, treating it as unsafe.")
          failure_chance = state.MAX_FAILURE + margin + 1

    support_card_results["failure"] = failure_chance
    results[key] = support_card_results

    unity = support_card_results["unity"]
    unity_note = f", Spirit: {unity['spirit']}, Burst: {unity['burst']}, Extreme: {unity['burst_ex']}" if (unity["spirit"] or unity["burst"] or unity["burst_ex"]) else ""
    gains_note = f", Gains: {support_card_results['gains']}" if support_card_results["gains"] else ""
    measured = support_card_results.get("energy_cost")
    base = training_cost.cost(key)
    # Printed whenever it differs from the database, because a difference is a
    # support card's Energy Cost Reduction showing up - the only place the bot
    # can see one at all.
    energy_note = ("" if measured is None else
                   f", Energy -{measured:.0f}" + (f" (db -{base})" if abs(measured - base) >= 2 else ""))
    # `Levels:` is the aggregate over all six card types, and a sum cannot be
    # split back into its parts - so on its own it cannot say how many of this
    # facility's cards are its OWN type, which is what a rainbow is. Reading a
    # career back afterwards therefore could not replay rainbow_training or
    # training_score at all (see docs/backtest.md). So print the per-type split
    # too, flat and only where it is non-zero: nested braces would be unreadable
    # five times a turn, and `spd:max=2` parses without them.
    split = ", ".join(
      f"{card_type}:{level}={count}"
      for card_type, bucket in support_card_results.items()
      if isinstance(bucket, dict) and "friendship_levels" in bucket
      for level, count in bucket["friendship_levels"].items()
      if count)
    split_note = f", Split:[{split}]" if split else ""
    debug(f"[{key.upper()}] → Total Supports {support_card_results['total_supports']}, Levels:{support_card_results['total_friendship_levels']} , Fail: {failure_chance}%{unity_note}{gains_note}{energy_note}{split_note}")
    sleep(0.1)

  click(img="assets/buttons/back_btn.png")
  return results

def do_train(train):
  if state.stop_event.is_set():
    return

  selected = wait_for_training_screen()
  if selected is None:
    warning("Couldn't read the training banner, not training.")
    return

  if selected != train:
    if not select_training(train):
      warning(f"Couldn't select {train.upper()} training, not training.")
      return

  # The facility is selected, so this second click is the one that commits it.
  x, y = training_pos(train)
  click(boxes=(x, y, 1, 1), text=f"Training {train.upper()}.")

def do_rest(energy_level):
  if state.stop_event.is_set():
    return
  if state.NEVER_REST_ENERGY > 0 and energy_level > state.NEVER_REST_ENERGY:
    info(f"Wanted to rest when energy was above {state.NEVER_REST_ENERGY}, retrying from beginning.")
    return
  rest_btn = pyautogui.locateOnScreen("assets/buttons/rest_btn.png", confidence=0.8, region=constants.SCREEN_BOTTOM_REGION)
  rest_summber_btn = pyautogui.locateOnScreen("assets/buttons/rest_summer_btn.png", confidence=0.8, region=constants.SCREEN_BOTTOM_REGION)

  if rest_btn:
    click(boxes=rest_btn)
  elif rest_summber_btn:
    click(boxes=rest_summber_btn)

def do_recreation():
  if state.stop_event.is_set():
    return
  recreation_btn = pyautogui.locateOnScreen("assets/buttons/recreation_btn.png", confidence=0.8, region=constants.SCREEN_BOTTOM_REGION)
  recreation_summer_btn = pyautogui.locateOnScreen("assets/buttons/rest_summer_btn.png", confidence=0.8, region=constants.SCREEN_BOTTOM_REGION)

  if recreation_btn:
    click(boxes=recreation_btn)
  elif recreation_summer_btn:
    click(boxes=recreation_summer_btn)

def save_screen(tag):
  """Keep a full screenshot of a screen we could not name, for later template
  work. A run must never die for want of a debugging aid, so nothing here
  raises."""
  try:
    os.makedirs("shots", exist_ok=True)
    path = os.path.join("shots", f"{tag}_{time.strftime('%H%M%S')}.png")
    ImageGrab.grab().save(path)
    info(f"Saved {path} for later.")
  except Exception as e:
    debug(f"Couldn't save a screenshot of {tag} ({e}).")

def do_race(prioritize_g1 = False, img = None):
  if state.stop_event.is_set():
    return False
  # Grand Concert squeezes a fourth button into the lobby's bottom row, and the
  # smaller Races button scores 0.799 against races_btn.png - a hair under the
  # threshold, so it was never found and no optional race was ever run there.
  if not (state.GRAND_CONCERT_SEEN
          and click(img="assets/grand_concert/races_btn.png", confidence=0.89,
                    minSearch=get_secs(3), region=constants.SCREEN_BOTTOM_REGION)):
    click(img="assets/buttons/races_btn.png", minSearch=get_secs(10))

  consecutive_cancel_btn = pyautogui.locateCenterOnScreen("assets/buttons/cancel_btn.png", minSearchTime=get_secs(0.7), confidence=0.8)
  if state.CANCEL_CONSECUTIVE_RACE and consecutive_cancel_btn:
    click(img="assets/buttons/cancel_btn.png", text="[INFO] Already raced 3+ times consecutively. Cancelling race and doing training.")
    return False
  elif not state.CANCEL_CONSECUTIVE_RACE and consecutive_cancel_btn:
    click(img="assets/buttons/ok_btn.png", minSearch=get_secs(0.7))

  sleep(0.7)
  found = race_select(prioritize_g1=prioritize_g1, img=img)
  if not found:
    if img is not None:
      info(f"{img} not found.")
    else:
      info("Race not found.")
    return False

  race_prep()
  sleep(1)
  after_race()
  return True

_repeated_event = {"name": None, "count": 0}
# Repeats before trying to break out of a menu that reopens, and before giving
# up on the event handler entirely so the rest of the dispatch gets a turn.
# Without the second one an unrecognised choice screen spins here forever,
# which is exactly what the Quick Mode dialog did.
REPEAT_LAST_OPTION = 3
REPEAT_GIVE_UP = 6
_career_end = {"skills_done": False, "any_skill_done": False}
# The story Skip setting resets to Off with every new career, and nothing set
# it, so the intro was tapped line by line at ~9 s each and read as a stall.
_career_start = {"skip_set": False}

SKIP_STATES = {"off": "assets/buttons/skip_off.png",
               "x1": "assets/buttons/skip_x1.png",
               "x2": "assets/buttons/skip_x2.png"}

def set_skip_x2(max_presses=3):
  """Cycle the story Skip button to x2. Returns True once it reads x2.

  The button cycles Off -> x1 -> x2. The state is read between presses rather
  than counted from a known start: each state matches its own template at
  1.000 with the nearest other at 0.832 (measured live 2026-09-17), and a
  single missed press would otherwise leave the career on x1 throughout.
  """
  for _ in range(max_presses):
    if state.stop_event.is_set() or not state.is_bot_running:
      return False
    found = None
    for name, path in SKIP_STATES.items():
      if match_template(path, region=constants.SKIP_BUTTON_BBOX):
        found = name
        break
    if found == "x2":
      return True
    if found is None:
      debug("Story Skip button not on screen; leaving it alone.")
      return False
    x, y = constants.SKIP_BUTTON_MOUSE_POS
    click(boxes=(x, y, 1, 1), text=f"Story Skip reads {found}; pressing for x2.")
    sleep(1)
  return False
# Consecutive Recreation frames showing neither the confirmation nor a friend
# row. Almost always the panel mid-animation rather than a friend-less deck.
_recreation = {"waits": 0}

CHOICE_VERTICAL_GAP = 112

def option_count(icon_top):
  """How many options this event offers, from where its first one sits.

  The list is bottom-anchored (constants.LAST_EVENT_CHOICE_ICON_TOP), so the
  first option moves up one row per extra option. Measured across the logs:
  736 = 1 option, 624 = 2, 513 = 3, 290 = 5.
  """
  span = constants.LAST_EVENT_CHOICE_ICON_TOP - icon_top
  return max(1, round(span / CHOICE_VERTICAL_GAP) + 1)

def choice_point(icon, chosen):
  """Where to click for option `chosen` (1-based): (x, y, count, chosen).

  A configured choice can exceed the options actually on screen. "Closer
  Together" opens with a one-option prompt before its five lyric lines, and
  grand_concert.lyrics_option = 2 then clicked 112px below that single option,
  hit nothing, and left the event to re-prompt - eight times across the logs.
  Clamping keeps the click on the list.
  """
  count = option_count(icon[1])
  picked = max(1, min(chosen, count))
  return icon[0], icon[1] + (picked - 1) * CHOICE_VERTICAL_GAP, count, picked

def select_event():
  event_choices_icon = pyautogui.locateOnScreen("assets/icons/event_choice_1.png", confidence=0.9, minSearchTime=0.2, region=constants.GAME_SCREEN_REGION)

  if not event_choices_icon:
    return False

  if not state.USE_OPTIMAL_EVENT_CHOICE:
    click(boxes=event_choices_icon, text="Event found, selecting top choice.")
    return True

  event_name = get_event_name()
  # Branching chain steps are the only ones that name themselves on screen.
  # When one does it pins the outing chain exactly, which also resyncs the
  # counter after a restart mid-career.
  outings.note_event(event_name)

  # An info menu reopens after every answer, so always taking the top choice
  # loops forever - the Unity Cup tutorial does exactly this. Its way out is the
  # last option ("That's all, thank you."), and because the choice list is
  # bottom-anchored the last option is always at the same y.
  # Counted even when the name will not read. An empty name is falsy, so this
  # used to reset the counter every iteration and the escape below could
  # never fire - any choice-shaped screen the OCR cannot name spun forever.
  key = event_name or "<unnamed>"
  if key == _repeated_event["name"]:
    _repeated_event["count"] += 1
  else:
    _repeated_event["name"], _repeated_event["count"] = key, 1

  # A scenario's Tutorial opens with "Yes, I'd like to know more." on top, and
  # that leads into a question menu the repeat guard below then has to fight
  # its way out of. Its last option ("No, I think I'm okay.") skips it outright.
  # Seen in Grand Concert on turn 5.
  if event_name and fuzz.ratio(event_name.strip().lower(), "tutorial") >= 85:
    click(boxes=(event_choices_icon[0], constants.LAST_EVENT_CHOICE_ICON_TOP,
                 event_choices_icon[2], event_choices_icon[3]),
          text="Skipping the scenario tutorial.")
    return True

  if _repeated_event["count"] >= REPEAT_GIVE_UP:
    warning(f"{key} has come back {_repeated_event['count']} times and neither"
            " the last nor the first option helped; leaving it to the rest"
            " of the loop.")
    _repeated_event["count"] = 0
    return False

  if _repeated_event["count"] >= REPEAT_LAST_OPTION:
    # A reopening menu is left by its terminal option, which is the last one
    # ("That's all, thank you."). But that option raises a confirmation, and a
    # confirmation's affirmative is the FIRST option - so taking the last one
    # every time answers "Are you sure?" with "No" and lands straight back in
    # the menu. The Unity Cup tutorial did exactly this until the give-up
    # counter fired, then started the same cycle over.
    #
    # Alternating covers both screens without having to tell them apart: the
    # odd attempt leaves the menu, the even one confirms it.
    last = _repeated_event["count"] % 2 == 1
    y = constants.LAST_EVENT_CHOICE_ICON_TOP if last else event_choices_icon[1]
    which = "last" if last else "first"
    warning(f"{key} has come back {_repeated_event['count']} times, taking the"
            f" {which} option to break out.")
    click(boxes=(event_choices_icon[0], y, event_choices_icon[2], event_choices_icon[3]),
          text=f"Selecting {which} option to exit a repeating menu.")
    return True

  chosen = event_choice(event_name)
  if chosen == 0:
    click(boxes=event_choices_icon, text="Event found, selecting top choice.")
    return True

  x, y, count, picked = choice_point(event_choices_icon, chosen)
  if picked != chosen:
    debug(f"Option {chosen} was asked for, but this prompt shows {count}; taking {picked}.")
  debug(f"Event choices coordinates: {event_choices_icon} ({count} option(s))")
  debug(f"Clicking: {x}, {y}")
  click(boxes=(x, y, 1, 1), text=f"Selecting optimal choice: {event_name}")
  # The Acupuncturist used to get a forced top-choice click right after this,
  # one second after the scored pick, before the screen had changed. Its
  # follow-up screen has no Effects panel and already falls back to the top
  # option, which ends the event (2026-09-15, scored #2 kept, stats confirmed).
  return True

def game_panel_blank(screen):
  """True when the game's own panel is one flat colour - a client that has
  stopped drawing. See the note on BLANK_PANEL_STD."""
  l, t, w, h = constants.GAME_SCREEN_REGION
  panel = screen.crop((l, t, l + w, t + h)).convert("L")
  return ImageStat.Stat(panel).stddev[0] < BLANK_PANEL_STD

def panel_digest(screen):
  """A fingerprint of the game panel, for spotting a client that has frozen.

  Not a similarity score - an exact digest. Measured on the live game while the
  bot played (2026-09-23), consecutive grabs three seconds apart differed by
  41,709 to 785,636 pixels and were *never* identical; a frozen client is
  byte-identical every time. The two states do not overlap, so there is no
  threshold to tune and none to get wrong."""
  l, t, w, h = constants.GAME_SCREEN_REGION
  panel = screen.crop((l, t, l + w, t + h)).convert("RGB")
  return hashlib.md5(panel.tobytes()).hexdigest()

def race_day():
  if state.stop_event.is_set():
    return
  # A race day replaces the usual lobby with a layout whose big race button does
  # not match race_day_btn.png (~0.47 on URA's), so without this the bot sits in
  # the lobby and never starts the finale. Which button, and where it sits, is
  # the mode's business - see core/scenarios.py.
  mode = scenarios.current()
  if not click(img="assets/buttons/race_day_btn.png", minSearch=get_secs(10), region=constants.SCREEN_BOTTOM_REGION):
    if not click(img=mode["race_day_asset"], minSearch=get_secs(3),
                 region=constants.SCREEN_BOTTOM_REGION,
                 text=f"{mode['name']} race day."):
      # URA's button is heavily animated, so its template match is marginal and
      # this fallback is what usually runs. It does not move, so click where it
      # lives. Every mode left in core/scenarios.py ends in the URA Finale and
      # shares that button, so this position is the one that carries the finale.
      x, y = mode["race_day_pos"]
      click(boxes=(x, y, 1, 1), text=f"{mode['name']} race day (by position).")

  click(img="assets/buttons/ok_btn.png")
  sleep(0.5)

  #move mouse off the race button so that image can be matched
#  control.moveTo(x=400, y=400)

  for i in range(2):
    if state.stop_event.is_set():
      return
    click(img="assets/buttons/race_btn.png", minSearch=get_secs(2))
    sleep(0.5)

  race_prep()
  sleep(1)
  after_race()

def race_select(prioritize_g1 = False, img = None):
  if state.stop_event.is_set():
    return False
  control.moveTo(constants.SCROLLING_SELECTION_MOUSE_POS)

  sleep(0.3)

  if prioritize_g1:
    info(f"Looking for {img}.")
    for i in range(2):
      if state.stop_event.is_set():
        return False
      if click(img=f"assets/races/{img}.png", minSearch=get_secs(0.7), text=f"{img} found.", region=constants.RACE_LIST_BOX_REGION):
        for i in range(2):
          if state.stop_event.is_set():
            return False
          click(img="assets/buttons/race_btn.png", minSearch=get_secs(2))
          sleep(0.5)
        return True
      drag_scroll(constants.RACE_SCROLL_BOTTOM_MOUSE_POS, -270)

    return False
  else:
    info("Looking for race.")
    for i in range(4):
      if state.stop_event.is_set():
        return False
      match_aptitude = pyautogui.locateOnScreen("assets/ui/match_track.png", confidence=0.8, minSearchTime=get_secs(0.7))

      if match_aptitude:
        # locked avg brightness = 163
        # unlocked avg brightness = 230
        if not is_btn_active(match_aptitude, treshold=200):
          info("Race found, but it's locked.")
          return False
        info("Race found.")
        click(boxes=match_aptitude)

        for i in range(2):
          if state.stop_event.is_set():
            return False
          click(img="assets/buttons/race_btn.png", minSearch=get_secs(2))
          sleep(0.5)
        return True
      drag_scroll(constants.RACE_SCROLL_BOTTOM_MOUSE_POS, -270)

    return False

RACE_LOAD_TEMPLATES = {
  "confirm": "assets/buttons/race_exclamation_btn.png",
  "skip": "assets/buttons/skip_btn.png",
  "skip_big": "assets/buttons/skip_btn_big.png",
  "results": "assets/buttons/next_btn.png",
}
RACE_LOAD_TIMEOUT = 180

def wait_for_race_load(timeout=RACE_LOAD_TIMEOUT):
  """Wait out the loading screen that follows entering a race.

  The game downloads race assets the first time a venue comes up ("Downloading
  67.41% / Now Loading..." over the whole window) and that can run well past any
  fixed sleep. The old code slept 10s, gave up looking for the Race! button and
  left the career parked on the pre-race screen with nothing to click.

  Returns "results" when the race has already finished, "confirm" when a Race!
  or skip button is up, or None on timeout or stop.
  """
  deadline = time.time() + timeout
  while time.time() < deadline:
    if state.stop_event.is_set():
      return None
    found = multi_match_templates(RACE_LOAD_TEMPLATES)
    if found["results"]:
      return "results"
    if found["confirm"] or found["skip"] or found["skip_big"]:
      return "confirm"
    sleep(1)
  warning(f"Race screen still had not loaded after {timeout}s.")
  return None

def race_prep():
  global PREFERRED_POSITION_SET

  if state.stop_event.is_set():
    return

  if state.POSITION_SELECTION_ENABLED:
    # these two are mutually exclusive, so we only use preferred position if positions by race is not enabled.
    if state.ENABLE_POSITIONS_BY_RACE:
      click(img="assets/buttons/info_btn.png", minSearch=get_secs(5), region=constants.SCREEN_TOP_REGION)
      sleep(0.5)
      #find race text, get part inside parentheses using regex, strip whitespaces and make it lowercase for our usage
      race_info_text = get_race_type()
      match_race_type = re.search(r"\(([^)]+)\)", race_info_text)
      race_type = match_race_type.group(1).strip().lower() if match_race_type else None
      click(img="assets/buttons/close_btn.png", minSearch=get_secs(2), region=constants.SCREEN_BOTTOM_REGION)

      if race_type != None:
        position_for_race = state.POSITIONS_BY_RACE[race_type]
        info(f"Selecting position {position_for_race} based on race type {race_type}")
        click(img="assets/buttons/change_btn.png", minSearch=get_secs(4), region=constants.SCREEN_MIDDLE_REGION)
        click(img=f"assets/buttons/positions/{position_for_race}_position_btn.png", minSearch=get_secs(2), region=constants.SCREEN_MIDDLE_REGION)
        click(img="assets/buttons/confirm_btn.png", minSearch=get_secs(2), region=constants.SCREEN_MIDDLE_REGION)
    elif not PREFERRED_POSITION_SET:
      click(img="assets/buttons/change_btn.png", minSearch=get_secs(6), region=constants.SCREEN_MIDDLE_REGION)
      click(img=f"assets/buttons/positions/{state.PREFERRED_POSITION}_position_btn.png", minSearch=get_secs(2), region=constants.SCREEN_MIDDLE_REGION)
      click(img="assets/buttons/confirm_btn.png", minSearch=get_secs(2), region=constants.SCREEN_MIDDLE_REGION)
      PREFERRED_POSITION_SET = True

  view_result_btn = pyautogui.locateCenterOnScreen("assets/buttons/view_results.png", confidence=0.8, minSearchTime=get_secs(10), region=constants.SCREEN_BOTTOM_REGION)
  click("assets/buttons/view_results.png", click=3)
  sleep(0.5)
  control.click()
  sleep(0.1)
  control.moveTo(constants.SCROLLING_SELECTION_MOUSE_POS)
  for i in range(2):
    if state.stop_event.is_set():
      return
    control.tripleClick(interval=0.2)
    sleep(0.5)
  control.click()
  next_button = pyautogui.locateCenterOnScreen("assets/buttons/next_btn.png", confidence=0.9, minSearchTime=get_secs(12), region=constants.SCREEN_BOTTOM_REGION)
  if not next_button:
    # The post-race results screen uses the shorter Next button: next_btn.png
    # scores ~0.42 against it while next2_btn.png scores ~1.00.
    next_button = pyautogui.locateCenterOnScreen("assets/buttons/next2_btn.png", confidence=0.9, minSearchTime=get_secs(2), region=constants.SCREEN_BOTTOM_REGION)
  if not next_button:
    info(f"Wouldn't be able to move onto the after race since there's no next button.")
    # Career 5 lost the Tenno Sho (Spring) goal here and the screen that
    # replaced Next - the one offering Try Again for an Alarm Clock - was never
    # captured, so there is no template for it. Keep a shot of whatever this is.
    save_screen("after_race_no_next")
    if click("assets/buttons/race_btn.png", confidence=0.8, minSearch=get_secs(10), region=constants.SCREEN_BOTTOM_REGION):
      info("Went into the race, waiting for it to load.")
      loaded = wait_for_race_load()
      if loaded == "results":
        # The race ran itself while we waited for the download, so there is
        # no Race! button to confirm and nothing left to skip.
        info("Race already finished while loading.")
        return
      if not click("assets/buttons/race_exclamation_btn.png", confidence=0.8, minSearch=get_secs(10)):
        info("Couldn't find \"Race!\" button, looking for alternative version.")
        click("assets/buttons/race_exclamation_btn_portrait.png", confidence=0.8, minSearch=get_secs(10))
      sleep(0.5)
      skip_btn = pyautogui.locateOnScreen("assets/buttons/skip_btn.png", confidence=0.8, minSearchTime=get_secs(2), region=constants.SCREEN_BOTTOM_REGION)
      skip_btn_big = pyautogui.locateOnScreen("assets/buttons/skip_btn_big.png", confidence=0.8, minSearchTime=get_secs(2), region=constants.SKIP_BTN_BIG_REGION_LANDSCAPE)
      if not skip_btn_big and not skip_btn:
        warning("Coulnd't find skip buttons at first search.")
        skip_btn = pyautogui.locateOnScreen("assets/buttons/skip_btn.png", confidence=0.8, minSearchTime=get_secs(10), region=constants.SCREEN_BOTTOM_REGION)
        skip_btn_big = pyautogui.locateOnScreen("assets/buttons/skip_btn_big.png", confidence=0.8, minSearchTime=get_secs(10), region=constants.SKIP_BTN_BIG_REGION_LANDSCAPE)
      if skip_btn:
        click(boxes=skip_btn, click=3)
      if skip_btn_big:
        click(boxes=skip_btn_big, click=3)
      sleep(3)
      if skip_btn:
        click(boxes=skip_btn, click=3)
      if skip_btn_big:
        click(boxes=skip_btn_big, click=3)
      sleep(0.5)
      if skip_btn:
        click(boxes=skip_btn, click=3)
      if skip_btn_big:
        click(boxes=skip_btn_big, click=3)
      sleep(3)
      skip_btn = pyautogui.locateOnScreen("assets/buttons/skip_btn.png", confidence=0.8, minSearchTime=get_secs(5), region=constants.SCREEN_BOTTOM_REGION)
      click(boxes=skip_btn, click=3)
      #since we didn't get the trophy before, if we get it we close the trophy
      close_btn = pyautogui.locateOnScreen("assets/buttons/close_btn.png", confidence=0.8, minSearchTime=get_secs(5))
      click(boxes=close_btn, click=3)
      info("Finished race skipping job.")

def after_race():
  if state.stop_event.is_set():
    return
  click(img="assets/buttons/next_btn.png", minSearch=get_secs(5))
  sleep(0.3)
  control.click()
  click(img="assets/buttons/next2_btn.png", minSearch=get_secs(5))

# The Tazuna hint only shows in the career lobby, which makes it the cheapest
# "are we home?" test there is on this screen.
def in_lobby():
  try:
    return bool(match_template("assets/ui/tazuna_hint.png"))
  except Exception as e:
    debug(f"Lobby check failed: {e}")
    return False

def back_to_lobby(attempts=4):
  """Click Back until the career lobby is showing again.

  Returns False when it could not get there, so the caller can re-observe
  instead of acting on a screen it assumed rather than saw.
  """
  for i in range(attempts):
    if state.stop_event.is_set():
      return False
    if in_lobby():
      return True
    click(img="assets/buttons/back_btn.png", minSearch=get_secs(1.5),
          text=f"Not back in the lobby yet, backing out ({i + 1}/{attempts}).")
    sleep(1.0)
  return in_lobby()

def auto_buy_skill():
  """True when the lobby is showing again afterwards, so the turn can go on.

  The exit used to be six unverified clicks. When Confirm, Learn or Close did
  not appear inside their (very short) search windows the bot was left standing
  in the skill screen, and the caller carried straight on into race_day(),
  whose templates match nothing there - which is how a Senior race day became
  "URA Finale race day (by position)", a blind click, and a stopped bot with
  the race still unrun. Every step now says whether it landed.
  """
  if state.stop_event.is_set():
    return False
  if check_skill_pts() < state.SKILL_PTS_CHECK:
    return True

  if not click(img="assets/buttons/skills_btn.png"):
    warning("Couldn't open the skill screen, leaving the skill spend for later.")
    return in_lobby()
  info("Buying skills")
  sleep(0.5)

  if buy_skill():
    for name, path, region, search in (
      ("Confirm", "assets/buttons/confirm_btn.png", constants.SCREEN_BOTTOM_REGION, 3),
      ("Learn", "assets/buttons/learn_btn.png", constants.SCREEN_BOTTOM_REGION, 3),
      ("Close", "assets/buttons/close_btn.png", constants.SCREEN_MIDDLE_REGION, 3),
    ):
      if not click(img=path, minSearch=get_secs(search), region=region):
        warning(f"{name} did not appear after buying skills.")
      sleep(0.5)
  else:
    info("No matching skills found. Going back.")

  if back_to_lobby():
    return True
  warning("Still not in the career lobby after buying skills; re-reading the"
          " screen rather than racing from one that was never confirmed.")
  return False

PREFERRED_POSITION_SET = False
# How many consecutive non-lobby checks to tolerate before giving up. At roughly
# nine seconds a check this is about 35 minutes, which clears the longest
# legitimate runs (a race and its results, a concert, the career-start
# Inspiration screen) by a wide margin. The Doto career that prompted it sat on
# the race preview screen for 960 checks - 2h23m - because do_race bailed out
# and left the game on a screen career_lobby has no branch for; backing out
# never found a button, so it alternated dialogue taps until a person noticed.
LOBBY_LOST_LIMIT = 240
# The game client can stop drawing while the career carries on server-side. On
# 2026-09-21, ~7.5h into one client's uptime, the portrait panel went flat white
# the moment the Japanese Derby started and never came back: Xorg :1 was healthy
# (no errors in its log, screenshots still updating), the window was up, and the
# race itself ran - the Continue Career dialog after a restart showed the goal
# still in progress and the results screen had Maruzensky 2nd. Nothing on a
# dead panel matches any template, so the loop fell into the blind-tap branch
# and stayed there for twelve minutes until a person looked.
#
# It is trivial to see: the panel is a single flat fill. Measured on the dead
# frames, greyscale std over GAME_SCREEN_REGION was 0.8 against 51.8 on the
# live frame one click later, so 3.0 has enormous margin. A real screen always
# carries text or art; the only flat frames the game draws are transition
# flashes, well under a second, which is why this needs a run of checks rather
# than one.
BLANK_PANEL_STD = 3.0
BLANK_PANEL_LIMIT = 18
# The other way a client stops drawing, and the one that actually happens: the
# panel keeps a full, detailed frame and simply never changes. Three times in
# three days - 2026-09-21 as the Japanese Derby started, 2026-09-23 inside a
# support card event, and again that afternoon inside a story event - and
# BLANK_PANEL_STD cannot see any of them, because a real frame has a real
# stddev. Each one cost ~35 minutes of blind tapping before LOBBY_LOST_LIMIT
# stopped the bot, and then the night.
#
# Ten consecutive identical panels, roughly 90s. A live client cannot produce
# even one: measured while the bot played, grabs three seconds apart differed
# by 41,709 to 785,636 pixels and were never identical. Ten is for the screen
# nobody has captured yet, not for the ones that have been.
FROZEN_PANEL_LIMIT = 10
# Automatic restarts allowed in one run, when restart_on_freeze is on. A
# restart costs about two minutes (30s for the close the frozen client ignores,
# ~30s for the window, two settles), so five is roughly half an hour of trying
# before a person is needed. Generous because an overnight run has legitimately
# needed two or three; bounded because a game that launches and freezes at once
# would otherwise loop on it all night.
FREEZE_RESTART_LIMIT = 5
# Attempts at walking back in from a Session Error before giving up. The branch
# ends in `continue` without touching not_in_lobby, so nothing else bounds it -
# and an unbounded press-and-retry on one dialog is this bot's oldest failure
# shape (302 clicks over 2h22m on the agenda-race badge). Three is enough for a
# slow reload to finish and few enough that a dialog the press cannot clear is
# handed straight back to a person.
SESSION_ERROR_LIMIT = 3
# Alarm Clocks spent on retries this career (see the Retry handler below).
RACE_RETRIES = 0
# A lobby has been seen since the bot started, so a home screen now means the
# game went back there under us (the daily reset) rather than a finished career.
SEEN_LOBBY = False
RESUMING_CAREER = False
def career_lobby():
  # Program start
  global PREFERRED_POSITION_SET, RACE_RETRIES, SEEN_LOBBY, RESUMING_CAREER
  PREFERRED_POSITION_SET = False
  SEEN_LOBBY = False
  RESUMING_CAREER = False
  not_in_lobby = 0
  blank_panel = 0
  session_errors = 0
  frozen_panel = 0
  last_digest = None
  freeze_restarts = 0
  # Not zero: the count lives in logs/career_start_progress.json so it survives
  # the restart that follows a frozen client, which is what ends most runs.
  # The config page's Reset is what clears it.
  state.CAREERS_STARTED = len(career_start.started_careers())
  if state.CAREERS_STARTED:
    info(f"{state.CAREERS_STARTED} career(s) counted since the last reset"
         + (f", limit {state.CAREER_START_MAX}." if state.CAREER_START_MAX
            else "."))
  # Set once the back-out probes have found no button to press, so the dialogue
  # tap can run every cycle rather than every fifth. Cleared whenever a button
  # is found or the lobby comes back, so each new unknown screen is probed
  # afresh before we start tapping at it.
  dialogue_tap = False
  outings.reset()
  lessons.resume()
  # Say who we are training and flag a config that disagrees with her. Advisory
  # only: an unusual style may well be deliberate, but a skill_run_style the
  # trainee has no aptitude for is points that can never pay out.
  trainee.check(state.TRAINEE, position=state.PREFERRED_POSITION,
                run_style=getattr(state, "SKILL_RUN_STYLE", None),
                distances=getattr(state, "SKILL_DISTANCE", None))
  while state.is_bot_running and not state.stop_event.is_set():
    screen = ImageGrab.grab()

    # Before anything is read off this frame: is the client still drawing it?
    # Checked on every pass rather than only when the lobby is lost, because a
    # freeze *in* the lobby is the worse case - the Tazuna hint keeps matching
    # on the stale frame, so the loop would train against a board that never
    # changes and never reach the not-in-lobby recovery at all.
    digest = panel_digest(screen)
    if digest == last_digest:
      frozen_panel += 1
      if frozen_panel >= FROZEN_PANEL_LIMIT:
        warning(f"The game panel has been pixel-identical for {frozen_panel}"
                " checks: the client has stopped drawing.")
        if not state.RESTART_ON_FREEZE:
          error("Stopping. The career is saved - close and relaunch the game,"
                " then Continue Career. Turn on restart_on_freeze to have the"
                " bot do that itself.")
          return
        if freeze_restarts >= FREEZE_RESTART_LIMIT:
          error(f"Already restarted the game {freeze_restarts} times this run"
                " and it froze again. Stopping rather than restarting on a"
                " loop; something is wrong beyond one bad frame.")
          return
        freeze_restarts += 1
        info(f"Restarting the game (attempt {freeze_restarts} of"
             f" {FREEZE_RESTART_LIMIT}).")
        if not recover.restart_client():
          return
        # The career is still there, behind the home screen's Career button.
        # This is the same hand-off the daily reset and the Session Error
        # dialog make, and it is what stops the reload being read as a
        # finished career - or, with career_start on, as a cue to start a new
        # one on top of a career that is still in progress.
        RESUMING_CAREER = SEEN_LOBBY
        frozen_panel = 0
        last_digest = None
        not_in_lobby = 0
        continue
    else:
      frozen_panel = 0
      last_digest = digest

    matches = multi_match_templates(templates, screen=screen)

    # Before select_event: its radio buttons look exactly like event choices,
    # so the event handler would take one and leave Confirm unpressed.
    if matches["quick_mode"]:
      # "Shorten all events" is the second of the four radios. It is also the
      # game's default, but a default is not a guarantee across accounts or
      # patches, so pick it rather than assume it. Clicking a radio only moves
      # the pending choice - Confirm is what commits, so this is safe to press
      # even when it is already selected.
      x, y = constants.QUICK_MODE_SHORTEN_ALL_MOUSE_POS
      click(boxes=(x, y, 1, 1), text="Quick Mode: selecting 'Shorten all events'.")
      sleep(0.6)
      if not click(img="assets/buttons/confirm_btn.png", minSearch=get_secs(2),
                   region=constants.GAME_SCREEN_REGION,
                   text="Confirming Quick Mode settings."):
        cx, cy = constants.QUICK_MODE_CONFIRM_MOUSE_POS
        click(boxes=(cx, cy, 1, 1),
              text="Confirming Quick Mode at the measured position.")
      sleep(2)
      continue

    if select_event():
      continue
    # Screen-specific branches come first, generic ones last. Every handler in
    # the generic block - next, next2, cancel, retry - matches on more screens
    # than one, so any of them sitting above a specific branch eats that
    # screen's real action. Three separate loops came from exactly that: the
    # Team Zenith finals and the Complete Career confirmation (cancel
    # dismissing a modal the screen behind immediately re-opened) and a
    # repeating event menu. New screens belong here, not below the generics.
    if click(boxes=matches["career_finish"], text="Finishing the career."):
      sleep(4)
      continue
    if matches["unity_race"] and not matches["unity_begin_showdown"]:
      # This button toggles the confirmation modal, so clicking it when the modal
      # is already open closes it again. Only press it when the modal is absent,
      # then let the next iteration handle the modal itself.
      click(boxes=matches["unity_race"], text="Unity Cup team race day.")
      sleep(1.2)
      # Preseason rounds open a Begin Showdown modal; the Finals opens a Team
      # Zenith VS screen with a Race! disc instead. Wait for whichever appears.
      if not click(img="assets/buttons/begin_showdown_btn.png", minSearch=get_secs(4),
                   region=constants.GAME_SCREEN_REGION, text="Beginning Unity Cup showdown."):
        if click(img="assets/buttons/zenith_race_btn.png", minSearch=get_secs(4),
                 region=constants.GAME_SCREEN_REGION, text="Racing Team Zenith."):
          sleep(4)
      continue
    if click(boxes=matches["unity_begin_showdown"], text="Beginning Unity Cup showdown."):
      sleep(4)
      continue
    if click(boxes=matches["unity_zenith_race"], text="Racing Team Zenith."):
      sleep(4)
      continue
    if click(boxes=matches["unity_race_results"], text="Skipping to Unity Cup race results."):
      continue
    # Checked after Begin Showdown: the confirmation modal only dims this button
    # rather than hiding it, so it still matches and would otherwise be clicked
    # forever behind the modal. Confirms whichever opponent the game preselects;
    # beating a harder team raises team rank, which drives facility levels.
    if click(boxes=matches["unity_select_opponent"], text="Confirming Unity Cup opponent."):
      sleep(1.0)
      click(img="assets/buttons/begin_showdown_btn.png", minSearch=get_secs(6),
            region=constants.GAME_SCREEN_REGION, text="Beginning Unity Cup showdown.")
      continue
    # Grand Concert's concert turn. The notification and the Start dialog both
    # sit over the concert screen and dim it (concert_btn falls to 0.65), so
    # the order here only matters for reading the log.
    if matches["gc_to_lessons"]:
      state.saw_scenario("grand_concert", "Schedule Notification with To Lessons")
      # The year in hand was read in the last lobby, which for the notification
      # after a concert is the half-year that just ended: career 4 booked a
      # Senior H2 song to Senior H1 that way. Re-read it off the screen behind
      # the dialog, and keep the old one if that read comes back empty.
      fresh = check_current_year()
      if re.search(r"Junior|Classic|Senior|Finale", fresh or ""):
        state.CURRENT_YEAR = fresh
      lessons.to_lessons(matches["gc_to_lessons"][0], year=state.CURRENT_YEAR,
                         turn=state.CURRENT_TURN)
      continue
    if matches["gc_concert_start"]:
      # The Grand Concert's confirmation also offers to skip its cutscene.
      if lessons.cutscene_unticked(screen):
        x, y = constants.SKIP_CUTSCENE_MOUSE_POS
        click(boxes=(x, y, 1, 1), text="Ticking 'Skip the Grand Concert cutscene'.")
        sleep(0.8)
        continue
      click(boxes=matches["gc_concert_start"], text="Ready to start the concert: Start.")
      sleep(3)
      continue
    if click(boxes=matches["gc_on_stage"], text="Grand Concert: On Stage!"):
      sleep(3)
      continue
    if matches["gc_concert"] or matches["gc_grand_concert"]:
      state.saw_scenario("grand_concert", "Concert screen")
      lessons.concert((matches["gc_concert"] or matches["gc_grand_concert"])[0], year=state.CURRENT_YEAR,
                      grand=bool(matches["gc_grand_concert"]))
      sleep(1.5)
      continue
    if matches["gc_bonuses_updated"]:
      # Informational. Confirm only opens the list of active bonuses.
      click(img="assets/buttons/close_btn.png", minSearch=get_secs(1), region=constants.GAME_SCREEN_REGION,
            text="Concert bonuses updated, closing the notice.")
      sleep(1)
      continue

    # Before the generic cancel handler, which matches this panel's Cancel
    # button at 0.982 and would dismiss the outing instead of taking it.
    if matches["recreation_panel"]:
      # Picking a row raises "Go on a fun outing?" over the chooser. It keeps
      # the same header, so the only reliable tell is its OK button.
      if click(boxes=matches["ok"], text="Confirming the outing."):
        _recreation["waits"] = 0
        sleep(2)
        continue

      if matches["event_progress"]:
        _recreation["waits"] = 0
        # A friend row is on offer. It gives everything plain recreation does
        # and advances the card's chain as well, so it is never the worse pick.
        panel = check_recreation_panel()
        if panel and panel["filled"] is not None:
          outings.set_position(panel["card"], panel["filled"])
        # Record what this step is predicted to give first: the Log will say
        # what it actually gave, and that comparison is the only evidence the
        # chain data and the tracked position describe the real game.
        # Energy is checked by the bar rather than the Log, so take a reading
        # before going out, along with the room it has left to rise. The panel
        # sits over the energy bar, so the read can fail and come back as -1;
        # pass nothing rather than a number that is not one.
        before, ceiling = check_energy_level()
        if before is None or before < 0 or ceiling is None or ceiling < 0:
          outings.expect_readback(*outings.next_outing())
        else:
          outings.expect_readback(*outings.next_outing(), energy_before=before,
                                  energy_headroom=max(0, ceiling - before))
        box = matches["event_progress"][0]
        y = box[1] + box[3] // 2 - constants.RECREATION_FRIEND_ROW_ABOVE_PROGRESS
        click(boxes=(constants.RECREATION_ROW_X, y, 1, 1),
              text="Going out with the friend support.")
        if not (panel and panel["filled"] is not None):
          # The position could not be read, so fall back to counting.
          outings.advance()
        sleep(2)
        continue

      # Neither the confirmation nor a friend row. Usually a frame caught
      # mid-animation, so give it a couple of polls to settle before assuming
      # there is genuinely no friend outing and taking the trainee row - which
      # spends the turn on plain recreation and cannot be taken back.
      _recreation["waits"] += 1
      if _recreation["waits"] < 3:
        sleep(0.5)
        continue
      _recreation["waits"] = 0
      x, y = constants.RECREATION_TRAINEE_ROW_MOUSE_POS
      click(boxes=(x, y, 1, 1), text="No friend outing on offer, plain recreation.")
      sleep(2)
      continue

    if matches["claw_credit"]:

      # This will pick the nearest plushie to avoid getting stuck
      # adjust the timer for your preference. duration in milliseconds
      credits = check_credit()
      if credits == "CREDIT 3":
        click_and_hold(img="assets/buttons/claw_btn.png", text="Claw 1 found.", duration_ms=1588)
        sleep(5)
        continue
      if credits == "CREDIT 2":
        click_and_hold(img="assets/buttons/claw_btn.png", text="Claw 2 found.", duration_ms=900)
        sleep(5)
        continue
      if credits == "CREDIT 1":
        click_and_hold(img="assets/buttons/claw_btn.png", text="Claw 3 found.", duration_ms=588)
        sleep(5)
        continue
    if matches["claw_result"]:
      click(img="assets/buttons/ok_2_btn.png", minSearch=get_secs(0.7))
      continue

    # Spark Selection, once the career is over. Confirm keeps the sparks as
    # rolled. Reroll sits immediately to its left and costs 30 TP, so this
    # finds Confirm by template rather than clicking a remembered position -
    # a few pixels of drift there would spend real currency.
    if matches["sparks"]:
      # core.sparks reads the set, applies the reroll rule and keeps the better
      # of the two. Every press in there is a deliberate_click: this screen
      # drops ordinary clicks and the career hangs here forever otherwise.
      sparks.handle()
      sleep(3)
      continue

    # "Session Error - Returning to Title screen due to inactivity." Raised by
    # any long idle gap: after the game sat on dialogs for ~2.5h (2026-09-20),
    # and after it sat at the home screen for ~3h between careers, where the
    # very first press raised it (2026-09-21). That second one is the gap
    # between one career finishing and the next starting.
    #
    # It goes above the whole out-of-career block, and above the home-screen
    # stop in particular, because the dialog can be raised *at* the home screen
    # with the nav bar still drawn behind it. Read there as a finished career,
    # it would stop the bot on a career that is perfectly alive.
    if matches["session_error"]:
      session_errors += 1
      if session_errors > SESSION_ERROR_LIMIT:
        error(f"The Session Error dialog is still up after {SESSION_ERROR_LIMIT}"
              " attempts to walk back in. Stopping rather than pressing at it."
              " The career is saved - restart the game and resume it.")
        return
      warning("Session Error: the game went back to its title screen after an"
              " idle spell. Pressing Title Screen and walking back in.")
      x, y = constants.SESSION_ERROR_BUTTON_MOUSE_POS
      click(boxes=(x, y, 1, 1), text="Returning to the title screen.")
      # The reload is the longest wait in this loop, so give F1 somewhere to
      # land in the middle of it rather than holding the thread for 22s.
      sleep(10)
      if state.stop_event.is_set():
        return
      # The one fixed tap of the startup walk. If the press above missed and the
      # dialog is still up, this lands outside GAME_SCREEN_REGION and presses
      # nothing, and the branch runs again next pass.
      tx, ty = constants.TITLE_SCREEN_TAP_MOUSE_POS
      click(boxes=(tx, ty, 1, 1), text="Tapping the title screen to start.")
      # From here the reload lands on exactly the screens the date-changed path
      # already walks - the login bonus, then Home - and RESUMING_CAREER is what
      # taps Career there instead of reading Home as a finished career.
      RESUMING_CAREER = SEEN_LOBBY
      sleep(12)
      continue

    # The career is over and the game has dropped back to its own screens.
    #
    # There is nothing here for a career loop to do, and staying costs real
    # time: on career 4 it tapped at the character art for 52 minutes and on
    # career 5 for 21, both times until the supervisor's stall timer gave up.
    # The taps are harmless - DIALOG_ADVANCE_MOUSE_POS lands on artwork, well
    # clear of the menu buttons - but the run is finished and should say so.
    #
    # Checked before to_home so a frame showing both is read as 'already out'.
    # The daily reset, mid-career: OK reloads the game, and the career is
    # waiting behind the home screen's Career button.
    if matches["date_changed"]:
      click(boxes=matches["date_changed"], text="Date changed; the game will reload.")
      sleep(1)
      click(img="assets/buttons/ok_btn.png", minSearch=get_secs(5),
            region=constants.GAME_SCREEN_REGION, text="Confirming the new day.")
      RESUMING_CAREER = SEEN_LOBBY
      sleep(8)
      continue

    # "Continue Career - Resume": after a reload the career is still there.
    if matches["continue_career"]:
      click(img="assets/buttons/resume_btn.png", minSearch=get_secs(5),
            region=constants.GAME_SCREEN_REGION, text="Resuming the career.")
      RESUMING_CAREER = False
      sleep(6)
      continue

    # The login bonus, on the way back from a career or through a date change.
    # It matched nothing before, so it was advanced by blind taps. Its Skip is
    # found by template within this branch rather than from the dispatch dict,
    # so the race skip that race_prep() drives is left alone.
    if matches["login_bonus"]:
      if not click(img="assets/buttons/skip_btn.png", minSearch=get_secs(2),
                   region=constants.SCREEN_BOTTOM_REGION,
                   text="Login bonus; skipping it."):
        x, y = constants.LOGIN_BONUS_SKIP_MOUSE_POS
        click(boxes=(x, y, 1, 1),
              text="Login bonus; skipping it at the measured position.")
      sleep(2)
      continue

    # Either the team rank badge or the game's own navigation bar means we are
    # outside a career. The bar is checked too because the badge is missing from
    # some of the screens the game walks through after one, and those are
    # exactly where the blind tap was pressing Scout.
    if matches["team_rank"] or matches["game_nav"] or matches["game_nav_alt"]:
      # A career that was running a moment ago is not over: the reload after a
      # date change lands here, and the career is behind the Career button.
      if RESUMING_CAREER:
        info("Home screen mid-career after the reload; tapping Career to resume.")
        control.click(constants.CAREER_BUTTON_MOUSE_POS)
        sleep(4)
        continue
      # The career is over. Before this the loop simply stopped here, and that
      # is what ended a night's run: on 2026-09-19 it finished at 17:55 and
      # stopped at the home screen three times inside ten minutes. With
      # career_start on, walk the setup screens and begin the next one.
      if state.CAREER_START_ENABLED:
        # The cap is counted in careers *started here*, not careers played: one
        # already in progress when the bot started is nobody's doing but the
        # person's, and counting it would make "run 3" mean two.
        if state.CAREER_START_MAX and state.CAREERS_STARTED >= state.CAREER_START_MAX:
          info(f"Started {state.CAREERS_STARTED} career(s) since the last"
               " reset, the configured limit. Stopping at the home screen."
               " Reset the count on the config page to run more.")
          return
        if career_start.start():
          limit = (f" of {state.CAREER_START_MAX}" if state.CAREER_START_MAX
                   else "")
          info(f"Career {state.CAREERS_STARTED}{limit} started by the bot.")
          SEEN_LOBBY = False
          RESUMING_CAREER = False
          state.apply_scenario(new_career=True)
          # The intro story is career_lobby's to drive from here, the same as
          # a career a person started by hand.
          sleep(4)
          continue
        error("Could not start the next career; stopping. The reason is above.")
        return
      info("The game is on its own screens, so the career is over."
           " Stopping the bot rather than tapping at a screen it cannot drive."
           " Set career_start.enabled to have it start the next one.")
      return

    # "Career Complete - To Home / Edit Team": the last click of a career.
    if click(boxes=matches["to_home"], text="Leaving the finished career."):
      sleep(3)
      continue

    # Skill points are destroyed the moment the career completes, so spend
    # them before clicking through. auto_buy_skill cannot be reused here:
    # its skills_btn template does not match this screen and check_skill_pts
    # reads a region the career-complete layout does not use.
    if matches["career_complete"]:
      # Grand Concert puts a third button on this screen, which moves Skills.
      # Read off the screen rather than trusted from memory: a bot started here
      # has never seen the lobby, and the URA Skills position is the gap beside
      # Complete Career. Its Lessons button is left alone - the board behind it
      # is dimmed and nothing can be bought after the Grand Concert, which is
      # why that visit spends everything.
      if not state.GRAND_CONCERT_SEEN and lessons.lessons_available(screen):
        state.saw_scenario("grand_concert", "Lessons button on the Career Complete screen")
      if not _career_end["skills_done"] or not _career_end["any_skill_done"]:
        # First pass buys from the configured list. The second takes anything
        # affordable, because points left over when the career completes are
        # destroyed - any skill beats losing them.
        match_any = _career_end["skills_done"]
        _career_end["skills_done"] = True
        if match_any:
          _career_end["any_skill_done"] = True
        x, y = (constants.GC_CAREER_COMPLETE_SKILLS_MOUSE_POS if state.GRAND_CONCERT_SEEN
                else constants.CAREER_COMPLETE_SKILLS_MOUSE_POS)
        click(boxes=(x, y, 1, 1), text="Spending leftover skill points before completing.")
        sleep(1.5)
        if buy_skill(match_any=match_any):
          cx, cy = constants.CAREER_COMPLETE_CONFIRM_MOUSE_POS
          click(boxes=(cx, cy, 1, 1), text="Confirming end-of-career skill purchases.")
          sleep(1.5)
          click(img="assets/buttons/learn_btn.png", minSearch=get_secs(2), region=constants.SCREEN_BOTTOM_REGION)
          sleep(1.5)
          click(img="assets/buttons/close_btn.png", minSearch=get_secs(2), region=constants.SCREEN_MIDDLE_REGION)
          sleep(1.0)
        else:
          info("No matching skills left to buy at career end.")
        click(img="assets/buttons/back_btn.png", minSearch=get_secs(2), region=constants.SCREEN_BOTTOM_REGION)
        sleep(1.5)
        continue
      click(boxes=matches["career_complete"], text="Career complete.")
      # The next career starts its friend card chain from step 1.
      outings.reset()
      # And with the story Skip back at Off, so it has to be set again.
      _career_start["skip_set"] = False
      # And may be a different game mode: "auto" has to see it again, and a
      # fixed mode is set afresh.
      state.apply_scenario(new_career=True)
      lessons.reset()
      RACE_RETRIES = 0
      sleep(4)
      continue

    # Generic handlers. They only see a frame every specific branch above has
    # declined, which is what keeps them from stealing a known screen's action.
    if click(boxes=matches["inspiration"], text="Inspiration found."):
      continue
    # Logged so a screen whose Next takes several presses shows up as a run of
    # these rather than as silence: after Grand Concert's 2nd concert the
    # GREAT SUCCESS and schedule screens each sat for 15-20s with next_btn
    # matching at 0.93+, and nothing said why.
    # Retry goes before Next, but only when the button is actually on screen:
    # a lost goal race ends the career, and career 5 clicked Next past the
    # offer without ever trying again. Each press spends an Alarm Clock, so it
    # is capped per career and can be turned off.
    retry_offer = matches["retry"] or matches["try_again"]
    if retry_offer and state.MAX_RACE_RETRIES > 0:
      if RACE_RETRIES < state.MAX_RACE_RETRIES:
        RACE_RETRIES += 1
        if click(boxes=retry_offer,
                 text=f"Retry offered; taking it ({RACE_RETRIES} of {state.MAX_RACE_RETRIES} this career, costs an Alarm Clock)."):
          continue
      else:
        info(f"Retry offered, but {RACE_RETRIES} retries already used this career; carrying on.")
    # Before Next: this screen carries no Next at all, and leaving it to the
    # blind-tap fallback is what wedged the run. Its "View Results" sits beside
    # Race, so tapping about is a coin flip on opening the results panel.
    # The Race Playback dialog sits over the preview, whose Race button still
    # matches underneath, and its Cancel is taken by the generic handler below.
    # Tick "Do not show again." first, so it never returns, then OK.
    if matches["race_playback"]:
      if not playback_box_ticked(screen):
        x, y = constants.RACE_PLAYBACK_CHECKBOX_MOUSE_POS
        click(boxes=(x, y, 1, 1), text="Race Playback dialog: ticking 'Do not show again'.")
        sleep(1)
        continue
      x, y = constants.RACE_PLAYBACK_OK_MOUSE_POS
      click(boxes=(x, y, 1, 1), text="Race Playback dialog: OK.")
      sleep(2)
      continue
    if matches["race_confirm"]:
      # race_btn.png lands on this dialog's Race at 0.923 on both captures, so
      # look for it rather than trusting the position; the constant is the
      # backstop for a frame caught mid-animation.
      if not click(img="assets/buttons/race_btn.png", confidence=0.9, minSearch=get_secs(2),
                   region=constants.GAME_SCREEN_REGION,
                   text="Race Details dialog: entering the race."):
        x, y = constants.RACE_CONFIRM_RACE_MOUSE_POS
        click(boxes=(x, y, 1, 1),
              text="Race Details dialog: entering the race (by position).")
      sleep(1.5)
      continue
    if click(boxes=matches["race_preview"], text="Race preview; starting the race."):
      continue
    if click(boxes=matches["race_lineup"], text="Runner lineup; confirming the race."):
      continue
    if click(boxes=matches["next"], text="Next."):
      continue
    if click(boxes=matches["next2"], text="Next (alt)."):
      continue
    # Above the generic cancel, and that placement is the whole point. This
    # Warning pairs OK with a Cancel that cancel_btn matches at high
    # confidence, so left to the handler below it is dismissed silently -
    # `click(boxes=matches["cancel"])` passes no text and logs nothing - and
    # whatever opened the race list simply opens it again. That is how the
    # scheduled-race branch looped 302 times over 2h22m on 2026-09-20.
    #
    # OK is pressed only when this turn's race was SCHEDULED. Accepting a third
    # consecutive race costs mood and health, which the game says outright, so
    # the bot takes that cost only where the agenda asked for the race; any
    # other route falls through to the generic cancel and skips it, which is
    # the safe direction to be wrong in.
    # "You have a scheduled race. Proceed to the Races screen?" - raised on
    # entering a career mid-agenda. Above the generic cancel for the usual
    # reason: its Close matches cancel_btn, so the handler below would dismiss
    # it silently and land back on a lobby still carrying the Races badge.
    # Taking it also marks the turn, so the consecutive-races warning that
    # follows knows this race was scheduled.
    if matches["scheduled_race_notice"]:
      _scheduled_race_turn[0] = turn
      # The template is the dialog's message text, so it must NOT be clicked at
      # its own centre - that presses the dialog body and nothing happens, the
      # same dead-click that looped the badge branch 302 times. Race sits at a
      # fixed point on this dialog.
      x, y = constants.SCHEDULED_RACE_NOTICE_RACE_MOUSE_POS
      click(boxes=(x, y, 1, 1),
            text="Scheduled race notice: proceeding to the Races screen.")
      sleep(1.5)
      continue

    if matches["consecutive_races"]:
      if _scheduled_race_turn[0] == turn:
        x, y = constants.CONSECUTIVE_RACES_OK_MOUSE_POS
        click(boxes=(x, y, 1, 1),
              text="Consecutive-races warning on a scheduled race: accepting.")
        sleep(1.5)
        continue
      info("Consecutive-races warning, but this race was not scheduled; declining.")

    if click(boxes=matches["cancel"]):
      continue
    if click(boxes=matches["retry"]):
      continue

    if not matches["tazuna"]:
      #info("Should be in career lobby.")
      print(".", end="")
      not_in_lobby += 1
      # This branch used to only print a dot to stdout and spin. Nothing reached
      # the log, so a wedged bot looked identical to a quiet one, and there was
      # no way back: left on a screen the loop does not recognise (the skill
      # list, for one) it would poll here forever. Back out periodically.
      # Backing out works on a panel the loop merely does not *want*; it cannot
      # work on a screen the loop cannot read at all, and there every tap is
      # blind. Stopping makes the wedge visible and leaves the game where a
      # person can see what it is, which is strictly better than tapping on.
      # Before any tapping: a dead client cannot be tapped back to life, and
      # every blind tap on one is a click the game will replay if it ever does
      # redraw. Counted rather than tripped on one frame, because a transition
      # flash is also flat.
      if game_panel_blank(screen):
        blank_panel += 1
        if blank_panel >= BLANK_PANEL_LIMIT:
          error(f"The game panel has been one flat colour for {blank_panel}"
                " checks: the client has stopped drawing. Stopping. The career"
                " is saved - restart the game and resume it from the home"
                " screen.")
          return
      else:
        blank_panel = 0
      if not_in_lobby >= LOBBY_LOST_LIMIT:
        error(f"Not in the career lobby for {not_in_lobby} checks and backing"
              " out has not recovered it. Stopping rather than going on"
              " tapping at a screen this loop cannot read.")
        return
      # Tapping used to be gated behind the same "every 5th check" as the
      # back-out probes, so a scenario dialogue advanced one beat per five
      # cycles - measured at ~43s each. That is invisible when a person clicks
      # through the prologue and starts the bot at the lobby, which is how careers
      # 1-6 were started; the first career this bot opened by itself spent ~70
      # minutes getting from Start Career to the lobby, 86 taps for 14 turns.
      # The expensive part is the two template searches, so keep those on the
      # 5-cycle beat and tap on every cycle once they have told us there is no
      # button to press. Same blind taps, same positions, five times the pace.
      tapping = dialogue_tap
      if not_in_lobby % 5 == 0:
        if not_in_lobby % 20 == 0:
          warning(f"Not in the career lobby for {not_in_lobby} checks, trying to back out.")
        if click(img="assets/buttons/close_btn.png", minSearch=get_secs(1), region=constants.GAME_SCREEN_REGION,
                 text="Closing a panel to get back to the lobby."):
          dialogue_tap = False
          continue
        if click(img="assets/buttons/back_btn.png", minSearch=get_secs(1), region=constants.SCREEN_BOTTOM_REGION):
          dialogue_tap = False
          continue
        # Neither button here, so this is most likely a scenario dialogue that
        # only advances on a tap.
        dialogue_tap = True
        tapping = True
      if tapping:
        # Alternate between two points. One tap position is not enough: the
        # artwork tap advances most scenario dialogue but does nothing at all
        # on the career-start Inspiration screen, which wedged a run for seven
        # minutes. Alternating costs one extra cycle on the screens that were
        # already working and unsticks the ones that were not.
        alt = (not_in_lobby // 3) % 2 == 0
        x, y = (constants.DIALOG_ADVANCE_ALT_MOUSE_POS if alt
                else constants.DIALOG_ADVANCE_MOUSE_POS)
        click(boxes=(x, y, 1, 1),
              text=f"No back button, tapping {'lower' if alt else 'centre'} to advance dialogue.")
      continue

    not_in_lobby = 0
    dialogue_tap = False
    session_errors = 0
    # Past here the lobby is on screen, so a later home screen means the game
    # left the career on its own (the daily reset), not that the career ended.
    SEEN_LOBBY = True
    RESUMING_CAREER = False
    # Back in the lobby, so any run of repeating event screens is over. This is
    # the reset for the repeat counter rather than "no choices on screen", which
    # would clear it between an info menu's answer and its next menu.
    _repeated_event["name"], _repeated_event["count"] = None, 0
    # Same reset point for the end-of-career skill spend, so a second career
    # in the same process still gets one attempt.
    _career_end["skills_done"] = False
    _career_end["any_skill_done"] = False
    # Set the story Skip to x2 once per career. The lobby is the safe place for
    # it: the button is there at a fixed position on every lobby frame, while
    # a global handler would be pressing it on race and story screens that
    # drive it themselves.
    if not _career_start["skip_set"]:
      _career_start["skip_set"] = set_skip_x2()
    energy_level, max_energy = check_energy_level()
    # An outing has played out by the time the lobby comes back, so this is
    # where it gets checked against what was predicted. Runs after the energy
    # reading because the bar is what the energy prediction is judged on.
    # Gated on there being something to check: reading the Log is an OCR pass.
    if outings.pending_readback():
      outings.confirm_outing(read_log_lines(), energy_after=energy_level)

    skipped_infirmary=False
    # Set when the infirmary was passed over for a ready Extreme burst. The
    # visit is not cancelled, only deferred to the end of the turn, so a turn
    # that ends in a rest after all still spends itself clearing the debuff.
    infirmary_deferred=None
    peeked_training=None
    if matches["infirmary"] and is_btn_active(matches["infirmary"][0]):
      # infirmary always gives 20 energy, it's better to spend energy before going to the infirmary 99% of the time.
      if max(0, (max_energy - energy_level)) >= state.SKIP_INFIRMARY_UNLESS_MISSING_ENERGY:
        # A debuff costs a few percent of failure and some mood. An Extreme
        # Spirit Burst forces the training to 0% failure and pays several times
        # a normal one, and it is gone as soon as the turn goes elsewhere - so
        # look at the facilities before handing the turn to the infirmary.
        peeked_training = peek_for_extreme_burst() if state.UNITY_SEEN else None
        if peeked_training is None:
          click(boxes=matches["infirmary"][0], text="Character debuffed, going to infirmary.")
          continue
        infirmary_deferred = matches["infirmary"][0]
        info("An Extreme Spirit Burst is ready, so training through the debuff and leaving the infirmary for later.")
      else:
        info("Skipping infirmary because of high energy.")
        skipped_infirmary=True

    mood = check_mood()
    mood_index = constants.MOOD_LIST.index(mood)
    minimum_mood = constants.MOOD_LIST.index(state.MINIMUM_MOOD)
    minimum_mood_junior_year = constants.MOOD_LIST.index(state.MINIMUM_MOOD_JUNIOR_YEAR)
    turn = check_turn()
    year = check_current_year()
    state.CURRENT_YEAR = year
    state.CURRENT_TURN = turn
    criteria = check_criteria()
    year_parts = year.split(" ")

    print("\n=======================================================================================\n")
    info(f"Year: {year}")
    info(f"Mood: {mood}")
    info(f"Turn: {turn}")
    info(f"Criteria: {criteria}")
    print("\n=======================================================================================\n")

    # Grand Concert. Lessons cost no turn, so they are settled before the turn
    # is planned - an Energy technique can turn a rest into a training, and
    # every Song learned before a concert fills its Hype gauge. The "!" on the
    # button is the game saying something on the board is learnable.
    if not state.GRAND_CONCERT_SEEN and lessons.lessons_available(screen):
      state.saw_scenario("grand_concert", "Lessons button in the lobby")
    lessons_button = lessons.ready(screen) if state.GRAND_CONCERT_SEEN else None
    if lessons_button and lessons.should_visit(year, turn):
      if lessons.visit(energy_level, year, turn, button=lessons_button):
        continue

    # If the calendar says race day, race. Every mode's finale comes through
    # here too. A separate branch used to handle `year == "Finale Season"`, but
    # that string is not one the game produces - check_current_year reports
    # "Finale Underway", and Trackblazer "TS Climax Races Underway" - so it
    # never executed once in any career, in any mode. It was removed rather
    # than repaired: it was a weaker copy of race_day() with no confirm-dialog
    # click and no position fallback, and race_day() has driven every finale
    # all along, which is why that function carries the URA-specific asset.
    if turn == "Race Day":
      info("Race Day.")
      if (state.IS_AUTO_BUY_SKILL and year_parts[0] != "Junior"
          and not auto_buy_skill()):
        continue
      race_day()
      continue

    # Mood check
    if year_parts[0] == "Junior":
      mood_check = minimum_mood_junior_year
    else:
      mood_check = minimum_mood
    if mood_index < mood_check:
      if skipped_infirmary:
        info("Since we skipped infirmary due to energy, check full stats for statuses.")
        if click(img="assets/buttons/full_stats.png", minSearch=get_secs(1)):
          sleep(0.5)
          conditions, total_severity = check_status_effects()
          click(img="assets/buttons/close_btn.png", minSearch=get_secs(1))
          if total_severity > 1:
            info("Severe condition found, visiting infirmary even though we will waste some energy.")
            click(boxes=matches["infirmary"][0])
            continue
        else:
          warning("Coulnd't find full stats button.")
      else:
        info("Mood is low, trying recreation to increase mood")
        do_recreation()
        continue

    # The race schedule is consulted every turn, whatever prioritize_g1_race
    # says. That flag used to gate this whole block, which made it the on/off
    # switch for the schedule rather than anything to do with G1s; it now only
    # affects goal races, and only on turns this block did not already race.
    #
    # do_race's first argument is passed straight to race_select, where it
    # means "find the race by its picture" rather than "prefer a G1" - so a
    # scheduled race always passes True, or the name would be ignored and the
    # aptitude search would pick something else.
    if "Pre-Debut" not in year and len(year_parts) > 3 and year_parts[3] not in ["Jul", "Aug"]:
      race_done = False
      for race_list in state.RACE_SCHEDULE:
        if state.stop_event.is_set():
          break
        if len(race_list):
          if race_list['year'] in year and race_list['date'] in year:
            debug(f"Race now, {race_list['name']}, {race_list['year']} {race_list['date']}")
            if do_race(True, img=race_list['name']):
              race_done = True
              break
            else:
              click(img="assets/buttons/back_btn.png", minSearch=get_secs(1), text=f"{race_list['name']} race not found. Proceeding to training.")
              sleep(0.5)
      if race_done:
        continue

    # Check if we need to race for goal
    if not "Achieved" in criteria:
      if state.APTITUDES == {}:
        sleep(0.1)
        if click(img="assets/buttons/full_stats.png", minSearch=get_secs(1)):
          sleep(0.5)
          check_aptitudes()
          click(img="assets/buttons/close_btn.png", minSearch=get_secs(1))
      keywords = ("fan", "Maiden", "Progress")

      prioritize_g1, race_name = decide_race_for_goal(year, turn, criteria, keywords)
      info(f"prioritize_g1: {prioritize_g1}, race_name: {race_name}")
      if race_name:
        if race_name == "any":
          race_found = do_race(prioritize_g1, img=None)
        else:
          race_found = do_race(prioritize_g1, img=race_name)
        if race_found:
          continue
        else:
          # If there is no race matching to aptitude, go back and do training instead
          click(img="assets/buttons/back_btn.png", minSearch=get_secs(1), text="Proceeding to training.")
          sleep(0.5)

    # Check training button
    if peeked_training is not None:
      # Already scanned when the infirmary was deferred; the screen has not
      # changed since, so scanning again would only cost the turn more time.
      results_training = peeked_training
    else:
      if not go_to_training():
        debug("Training button is not found.")
        continue

      # Last, do training
      sleep(0.5)
      results_training = check_training()

    # Published for the advisory planner, the way the headroom and energy
    # readings are: do_something() only receives `results`, so the goal text
    # and the turn counter cannot reach it any other way. Advisory only - the
    # planner logs a verdict and nothing acts on it yet.
    set_goal_context(criteria, turn)
    best_training = do_something(results_training)
    # A friend-type support pays out through outings, not the training
    # facilities, and the outing also clears conditions and returns energy.
    # So it is weighed against both training and resting, not just mood.
    outing_reason = should_recreate(
      training_value(results_training, best_training),
      best_training is None,
      energy_level, max_energy, mood_index, mood_check,
      check_outing_available(), skipped_infirmary,
      burst_ready=any(has_extreme_burst(d) for d in results_training.values()),
      training_key=best_training,
      measured_cost=(results_training.get(best_training) or {}).get("energy_cost")
                    if best_training else None)
    if outing_reason:
      info(f"Going on a Recreation outing: {outing_reason}.")
      do_recreation()
    elif best_training:
      go_to_training()
      sleep(0.5)
      do_train(best_training)
    elif infirmary_deferred:
      click(boxes=infirmary_deferred,
            text="Nothing worth training after all, going to the infirmary as planned.")
    else:
      do_rest(energy_level)
    sleep(1)
