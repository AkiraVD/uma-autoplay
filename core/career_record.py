"""The career's race record, taken from the game's own count.

`reroll_sparks = "undefeated"` spends 30 TP on one question - did she win every
race this career - and nothing the bot already reads answers it. Two attempts
have now failed, and both failed for the same reason, which is worth keeping:
**a screen was assumed rather than looked at.**

`core/placement.py` counted saturated gold pixels in the moment after each race
and came back 0 of 19 on a career the game records as 17 of 19. It sampled a
screen the banner is not on yet, and the counts it did collect put wins and
losses on top of each other - career 18 lost Kikuka Sho at 1,101 px and Saudi
Arabia Royal Cup at 2,382 px while winning Hanshin 2200m at 972 px and Tenno
Sho (Spring) at 3,558 px. No threshold separates those.

Then the Complete Career screen's **Details** button, on the strength of the
Veteran Roster's Umamusume Details dialog carrying a Career Info tab that
states

    Career Record    Races: 19    Wins: 17

outright. Careers 19 and 20 both went on that. The dialog career end opens has
the same title and is not the same dialog: two tabs, Conditions and Skills, no
Career Info, no record (shots/career_record_no_tab_064155.png). Career 19 read
nothing because a remembered tab coordinate missed; career 20 read nothing
because the tab is not there at all.

What is left untried is the sidebar's **Log**, which is a career-mode panel -
dead on the home screen - and the only thing on that screen still plausibly
holding the race results. So this now *probes* it: one tap, one OCR pass, and a
frame kept either way, so the next career end hands back a picture of the panel
whether or not the record reads off it. The sidebar only ever redraws the right
half of the screen, so the Complete Career button the caller presses next is
not at risk; on_career_end() is re-checked afterwards to prove it.

Anything that does not read comes back None, and the caller treats that as
"not undefeated". A career wrongly called beaten keeps its 30 TP, which is the
right way round to be wrong - and is what has happened on every career so far.
"""
import core.notify as notify
import core.veteran as veteran
import utils.constants as constants
from core.ocr import read_boxes
from core.recognizer import match_template
from utils.log import debug, info, warning


def on_career_end():
  """True when the Complete Career screen's Details button is on screen."""
  return bool(match_template(constants.CAREER_END_DETAILS_TEMPLATE,
                             threshold=constants.CAREER_END_DETAILS_MATCH))


def keep_frame(tag, screen=None):
  """Keep a frame of whatever went wrong. Never raises: this is a debugging
  aid and a career must not end over one."""
  try:
    notify.save_frame(screen or veteran.grab(), f"career_record_{tag}_")
  except Exception as exc:                                 # noqa: BLE001
    debug(f"Could not save a {tag} frame: {exc}")


def read_side_panel():
  """(whole screen, everything the right-hand panel says).

  The whole screen comes back, not the crop, because the frame kept on a
  failure is the only thing the next attempt gets to be built on and the left
  half says which screen this was.
  """
  screen = veteran.grab()
  panel = veteran.crop(screen, constants.CAREER_END_SIDE_PANEL_REGION)
  return screen, " ".join(text for text, _confidence, _box in read_boxes(panel))


def restore_sidebar():
  """Put the sidebar back on Career Profile and prove the screen survived.

  The caller's very next act is to press Complete Career, so the one thing
  that matters is that the left half is still the Complete Career screen.
  """
  veteran.tap(constants.CAREER_END_SIDEBAR_PROFILE_MOUSE_POS, settle=1.2)
  if on_career_end():
    return True
  warning("The Complete Career screen did not survive opening the Log panel.")
  keep_frame("lost_screen")
  return False


def read():
  """(races, wins) as the game counts them, or None if anything did not read."""
  if not on_career_end():
    debug("No Details button on screen; not reading the career's race record.")
    return None

  veteran.tap(constants.CAREER_END_SIDEBAR_LOG_MOUSE_POS, settle=2.0)
  try:
    screen, joined = read_side_panel()
    stated = veteran.RACE_RECORD.search(joined)
    if not stated:
      # Not a failure to be fixed by retrying: it means the Log panel is not
      # what was hoped, or did not open. Keep the picture - it is the only way
      # the next attempt gets to be built on a measurement rather than a guess.
      warning(f"No 'Races: n Wins: n' on the Log panel; it reads {joined[:200]!r}.")
      keep_frame("log_panel", screen)
      return None
    races, wins = int(stated.group(1)), int(stated.group(2))
    info(f"Career race record: {wins} of {races} won.")
    return races, wins
  finally:
    restore_sidebar()
