from utils.tools import sleep
import os
import sys
import threading
import uvicorn
import pyautogui
import utils.hotkey as hotkeys
import utils.window as window
import traceback

from utils.log import info, warning, error, debug

from core.execute import career_lobby
import core.state as state
import core.notify as notify
from server.main import app
import server.main as server_main
from update_config import update_config

# Pause/Break. The listener hears this on the whole desktop through the X RECORD
# extension, without grabbing it, so whatever key this is toggles the bot from
# any window. F1 was the old binding and too easy to hit by accident - plenty of
# programs use it for help. Nothing on this desktop reacts to Pause.
hotkey = "pause"

def focus_umamusume():
  try:
    target_window = window.find(window.GAME_TITLE)
    if not target_window:
      error(f"Couldn't find the {window.GAME_TITLE} window. Start the game from Steam first.")
      return False
    window.activate(target_window)
  except Exception as e:
    error(f"Error focusing window: {e}")
    return False
  return True

def main():
  print("Uma Autoplay!")
  try:
    state.reload_config()
    state.stop_event.clear()
    # Anything the page wrote while the bot was stopped is in the config
    # just loaded, so the loop has nothing left to pick up.
    state.config_dirty.clear()

    if focus_umamusume():
      info(f"Config: {state.CONFIG_NAME}")
      career_lobby()
    else:
      error("Failed to focus Umamusume window")
  except Exception as e:
    error_message = traceback.format_exc()
    error(f"Error in main thread: {error_message}")
  finally:
    debug("[BOT] Stopped.")
    # career_lobby() can return on its own - the lobby-lost guard, or a run
    # that finished. Nothing else cleared this, so is_bot_running stayed True
    # with a dead thread behind it and the next press was read as "stop": the bot
    # needed two presses to start again, and /logs/data reported it running.
    state.is_bot_running = False

def _set_bot_running_locked(want):
  """Start or stop the bot thread. The caller holds state.bot_lock.

  Returns "running", "stopped" or "stopping". "stopping" is a stop whose thread
  has not finished its current step yet; a start is refused until it has.
  """
  # The thread has to actually be alive, not just flagged: belt and braces
  # against a self-stop leaving the flag set, since a press swallowed as a
  # no-op "stop" is indistinguishable from a missed key.
  alive = bool(state.bot_thread and state.bot_thread.is_alive())
  running = state.is_bot_running and alive
  if want and not running:
    if alive:
      # The last stop has not finished. Starting now would put a second bot
      # thread beside the first, both clicking. This used to happen, because a
      # stop dropped the thread reference even while it was still running.
      debug("[BOT] Still stopping, not starting a second bot.")
      return "stopping"
    debug("[BOT] Starting...")
    state.is_bot_running = True
    state.bot_thread = threading.Thread(target=main, daemon=True)
    state.bot_thread.start()
    return "running"
  if running and not want:
    debug("[BOT] Stopping...")
    state.stop_event.set()
    state.is_bot_running = False
    debug("[BOT] Waiting for bot to stop...")
    state.bot_thread.join(timeout=3)
    if state.bot_thread.is_alive():
      # Kept, so a start can see the thread has not finished.
      debug("[BOT] Bot still running, please wait...")
      return "stopping"
    debug("[BOT] Bot stopped completely")
    state.bot_thread = None
    return "stopped"
  return "running" if running else ("stopping" if alive else "stopped")

def set_bot_running(want):
  """Start (True) or stop (False) the bot. The hotkey and the config page's
  Start/Stop button both come here, so they cannot disagree about what is
  running."""
  with state.bot_lock:
    return _set_bot_running_locked(want)

def toggle_bot():
  with state.bot_lock:
    running = state.is_bot_running and bool(state.bot_thread and state.bot_thread.is_alive())
    return _set_bot_running_locked(not running)

def hotkey_listener():
  while True:
    try:
      hotkeys.wait(hotkey)
    except Exception as e:
      error(f"Can't listen for {hotkey}, so it won't start the bot: {e}")
      return
    toggle_bot()
    sleep(0.5)

def start_log_viewer():
  """Bring the phone-friendly log view up alongside the bot.

  It was a second thing to remember to launch, and forgetting it meant no way to
  watch a run from another device - the game owns the whole screen, so an
  overlay is not an option.

  Safe to run in-process: it only reads logs/log.txt, holds no lock and writes
  nothing, and it sits on its own thread and port. Any failure is logged and
  swallowed, because the viewer is a convenience and must not stop a run.
  """
  try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
    import logserver
    url, err = logserver.serve_in_background()
    if url:
      info(f"Log viewer: {url}")
      print(f"[SERVER] Log viewer at {url}")
    else:
      warning(f"Log viewer did not start ({err}). The bot runs without it.")
  except Exception as e:
    warning(f"Log viewer did not start ({e}). The bot runs without it.")

def start_server():
  res = pyautogui.resolution()
  if res.width != 1920 or res.height != 1080:
    error(f"Your resolution is {res.width} x {res.height}. Please set your screen to 1920 x 1080.")
    return
  host = "127.0.0.1"
  port = 8000
  info(f"Press '{hotkey}' to start/stop the bot.")
  print(f"[SERVER] Open http://{host}:{port} to configure the bot.")
  config = uvicorn.Config(app, host=host, port=port, workers=1, log_level="warning")
  server = uvicorn.Server(config)
  server.run()

if __name__ == "__main__":
  # Before update_config(), which deep-merges the template over config.json and
  # drops keys the template no longer has. How the bot runs moved to bot.json,
  # and reading those values across has to happen while they are still there.
  state.migrate_bot_settings()
  update_config()
  # bot.json and telegram.json are not part of the config, so nothing else
  # loads them until reload_config() runs at the first bot start. Load them
  # here so the config page and the Telegram listener are right before that.
  state.load_bot()
  state.load_telegram()
  # Answers /health from the phone. Waits for Telegram to be switched on rather
  # than needing a restart when it is.
  notify.listen()
  start_log_viewer()
  threading.Thread(target=hotkey_listener, daemon=True).start()
  # The config page's Start/Stop button, which works where a key press cannot
  # reach - from another device, or through a tunnel.
  server_main.set_bot_running = set_bot_running
  start_server()
