"""Bringing the game back after the client stops drawing.

The client freezes every few hours - three times in three days when this was
written, always during a scene transition (a race starting, a support card
event, a story event). It keeps a full frame on screen and never changes it,
`core/execute.py::panel_digest` is what notices, and until now a person had to
close the game, relaunch it, tap the title screen and press Continue Career.

That walk is what this does. Nothing in it is new: `utils/window.py` already
closes and launches the game for `tools/umatool.py`, and the title tap is the
one fixed point of the startup walk. What it adds is doing them in order,
unattended, and then handing back to `career_lobby()` with `RESUMING_CAREER`
set - so the career is resumed through Continue Career rather than read as a
finished one, exactly the way the daily reset and the Session Error dialog are.

Behind `restart_on_freeze` in the config, off by default: it ends the game
process, and doing that to a client that is merely slow rather than frozen
would cost whatever was on screen.
"""
import time

import core.state as state
import utils.constants as constants
import utils.window as window
from utils.log import info, error
from utils.tools import sleep

# A frozen client ignores WM_DELETE_WINDOW - measured 2026-09-23, it sat through
# the full 30s twice - and utils.window.close then signals it. That wait is the
# floor on how long a restart takes, so it is not worth shortening.
CLOSE_TIMEOUT = 30
# The window has appeared 28-32s after the steam:// hand-off on this machine,
# with Steam already running. Generous, because the alternative to waiting is
# giving up on a game that was about to arrive.
LAUNCH_TIMEOUT = 180
# Let the title screen finish drawing before tapping it, then let the tap land.
SETTLE = 15
TITLE_SETTLE = 15

def _stopping():
  return state.stop_event.is_set() or not state.is_bot_running

def _wait_for_window(timeout):
  t0 = time.time()
  while time.time() - t0 < timeout:
    if _stopping():
      return None
    win = window.find(window.GAME_TITLE)
    if win:
      return win
    sleep(2)
  return None

def restart_client():
  """Close the frozen game, start it again and tap past the title screen.

  True once the game is up and the title tap has been made - the caller
  re-observes from there, so whatever the reload lands on (login bonus, home
  screen, Continue Career) is handled by the branches that already handle it.
  False means a person is needed, and the log says at which step.
  """
  win = window.find(window.GAME_TITLE)
  if win:
    info("Closing the frozen game client.")
    # close() asks politely, waits, then sends SIGTERM and SIGKILL. A frozen
    # client always needs the signals; a merely busy one may not.
    result = window.close(win, timeout=CLOSE_TIMEOUT)
    if result is None:
      error("The game window would not close and its process would not end."
            " Not restarting.")
      return False
    info(f"Game {result}.")
  else:
    # Already gone - it crashed rather than froze, which is the same problem
    # from here on.
    info("No game window to close; launching.")
  if _stopping():
    return False

  try:
    window.launch_game()
  except OSError as e:
    error(f"Could not hand the steam:// URL to anything: {e}")
    return False
  info("Launching the game.")
  win = _wait_for_window(LAUNCH_TIMEOUT)
  if not win:
    if _stopping():
      return False
    error(f"No game window {LAUNCH_TIMEOUT}s after launching. Not restarting.")
    return False
  sleep(SETTLE)
  if _stopping():
    return False

  # The one fixed coordinate of the startup walk, and only ever pressed here,
  # where the game has just started and the title screen is what it shows.
  from core.execute import click
  x, y = constants.TITLE_SCREEN_TAP_MOUSE_POS
  click(boxes=(x, y, 1, 1), text="Tapping the title screen to start.")
  sleep(TITLE_SETTLE)
  info("Game restarted; resuming the career from the home screen.")
  return True
