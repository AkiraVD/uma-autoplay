"""Block until a global hotkey is pressed, per platform.

Windows uses the keyboard package, as before. On Linux that package reads
/dev/input directly and needs root, so this listens through the X server's
RECORD extension instead (the way pynput does). RECORD sees every key press on
the display whichever window has focus - the fullscreen game included - without
grabbing the key away from anything and without root. On Wayland it only sees
presses while an XWayland window, such as the game under Proton, has focus.

UMA_HOTKEY_DISPLAY names the X display to listen on (default: DISPLAY). When the
game plays on a display of its own (run_background.sh), the bot's DISPLAY is that
display, which has no keyboard, so this stays pointed at the desktop's.
"""
import os
import sys
import threading

_events = {}
_lock = threading.Lock()

def wait(key):
  """Block until `key` ("pause") is pressed. Presses before the call are ignored.

  Raises RuntimeError on Linux when the X server cannot be listened to."""
  if sys.platform == "win32":
    import keyboard
    keyboard.wait(key)
    return
  event = _listen(key)
  event.clear()
  event.wait()

def _listen(key):
  with _lock:
    if key not in _events:
      event = threading.Event()
      _start_record(key, event)
      _events[key] = event
    return _events[key]

def _keycode(local, XK, key):
  """The keycode for a key name, trying the spellings X keysyms actually use.

  Keysym names are case-sensitive and not uniform: "F1" is upper case, "Pause"
  is capitalised, "Scroll_Lock" is capitalised per word. `key.upper()` alone
  happened to resolve "f1" and returned 0 for every other spelling, which then
  read as "no keycode for this key on this keyboard" - a wrong-spelling bug
  wearing a missing-key error message.
  """
  tried = []
  for name in (key, key.upper(), key.capitalize(),
               "_".join(part.capitalize() for part in key.split("_"))):
    if name in tried:
      continue
    tried.append(name)
    keysym = XK.string_to_keysym(name)
    if keysym:
      keycode = local.keysym_to_keycode(keysym)
      if keycode:
        return keycode
  return 0

def _start_record(key, event):
  """Open a RECORD context for key presses and pump it on a daemon thread.

  Setup happens here, on the caller's thread, so a missing display or extension
  raises to the caller instead of silently killing the listener."""
  try:
    from Xlib import X, XK, display
    from Xlib.ext import record
    from Xlib.protocol import rq
  except ImportError as e:
    raise RuntimeError(f"python-xlib is needed for the hotkey on Linux ({e}).")

  name = os.environ.get("UMA_HOTKEY_DISPLAY") or None
  try:
    local = display.Display(name)
    keycode = _keycode(local, XK, key)
    local.close()
    recorder = display.Display(name)
  except Exception as e:
    shown = name or os.environ.get("DISPLAY")
    raise RuntimeError(f"Couldn't connect to X display {shown!r} for the hotkey ({e}).")
  if not keycode:
    raise RuntimeError(f"No keycode for hotkey {key!r} on this keyboard.")
  if not recorder.has_extension("RECORD"):
    raise RuntimeError("The X server has no RECORD extension, so the hotkey can't be heard.")

  context = recorder.record_create_context(0, [record.AllClients], [{
    "core_requests": (0, 0), "core_replies": (0, 0),
    "ext_requests": (0, 0, 0, 0), "ext_replies": (0, 0, 0, 0),
    "delivered_events": (0, 0), "device_events": (X.KeyPress, X.KeyPress),
    "errors": (0, 0), "client_started": False, "client_died": False,
  }])

  def on_reply(reply):
    if reply.category != record.FromServer or reply.client_swapped:
      return
    data = reply.data
    if not data or data[0] < 2:
      return
    while len(data):
      ev, data = rq.EventField(None).parse_binary_value(data, recorder.display, None, None)
      if ev.type == X.KeyPress and ev.detail == keycode:
        event.set()

  threading.Thread(target=recorder.record_enable_context, args=(context, on_reply),
                   daemon=True, name=f"hotkey-{key}").start()
