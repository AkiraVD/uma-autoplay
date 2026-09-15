"""Mouse and keyboard through the X server's XTEST extension, for Linux.

For the game on a display of its own (tools/headless/): XTEST events are
delivered by the X server they are sent to - the one DISPLAY names - and by no
other, so the desktop's cursor and keyboard are never touched. uinput cannot do
that: its virtual device plugs into the machine, and only the desktop's X server
takes input devices.

utils/control.py is what the bot calls. The shapes here match utils/uinput.py,
so control.py drives either one the same way.
"""
import os
import re
import threading
import time

from Xlib import X, XK, display
from Xlib.ext import xtest

BUTTONS = {"left": 1, "middle": 2, "right": 3}
# Names the bot and its tools use, as X keysym names. F-keys and single
# characters are keysyms under their own names.
KEYSYMS = {
  "esc": "Escape", "escape": "Escape", "enter": "Return", "return": "Return",
  "space": "space", "tab": "Tab", "backspace": "BackSpace",
  "up": "Up", "down": "Down", "left": "Left", "right": "Right",
}

_lock = threading.Lock()
_display = None

class XTestError(RuntimeError):
  pass

def _connection():
  """One connection to DISPLAY, shared by the pointer and the keyboard."""
  global _display
  with _lock:
    if _display is None:
      _display = display.Display()
    return _display

def check():
  """None when XTEST on DISPLAY can be used, otherwise why not."""
  name = os.environ.get("DISPLAY")
  try:
    connection = _connection()
  except Exception as e:
    return f"Couldn't connect to display {name!r} ({e})."
  if not connection.has_extension("XTEST"):
    return f"Display {name!r} has no XTEST extension."
  return None

def keycode(name):
  key = name.strip().lower()
  sym = KEYSYMS.get(key) or (key.upper() if re.fullmatch(r"f\d{1,2}", key) else key)
  code = _connection().keysym_to_keycode(XK.string_to_keysym(sym))
  if not code:
    raise XTestError(f"No keycode for {name!r} on display {os.environ.get('DISPLAY')!r}.")
  return code

class Pointer:
  """The display's own pointer, moved and clicked through XTEST."""

  def __init__(self, width, height):
    self.width = width
    self.height = height
    self._connection = _connection()

  def move_to(self, x, y):
    """Move and return the point actually used, clamped to the screen."""
    x = max(0, min(int(x), self.width - 1))
    y = max(0, min(int(y), self.height - 1))
    xtest.fake_input(self._connection, X.MotionNotify, x=x, y=y)
    self._connection.sync()
    return x, y

  def button(self, name, pressed):
    if name not in BUTTONS:
      raise XTestError(f"Unknown button {name!r}; expected one of {', '.join(BUTTONS)}.")
    xtest.fake_input(self._connection, X.ButtonPress if pressed else X.ButtonRelease, BUTTONS[name])
    self._connection.sync()

  def close(self):
    pass

class Keyboard:
  def __init__(self):
    self._connection = _connection()

  def key(self, code, pressed):
    xtest.fake_input(self._connection, X.KeyPress if pressed else X.KeyRelease, code)
    self._connection.sync()

  def tap(self, code, hold=0.02):
    self.key(code, True)
    time.sleep(hold)
    self.key(code, False)

  def close(self):
    pass
