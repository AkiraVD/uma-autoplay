"""Mouse and keyboard output for the bot, with pyautogui's call shapes.

Every press the bot makes goes through here. The names and arguments are
pyautogui's - moveTo, click, mouseDown, mouseUp, moveRel, tripleClick, press -
so call sites read as they always did. So does the timing: a move with a
duration steps the way pyautogui steps it, and each call ends with pyautogui's
0.1s PAUSE. That matters, because the drag distances in core/menu_scan.py and
many settles were measured against pyautogui's motion.

Three backends:
- "uinput", the Linux default: a virtual absolute pointer and keyboard on
  /dev/uinput (utils/uinput.py, adapted from ui-control). The events enter below
  the display server, so the game sees a real device on X11 and Wayland alike.
- "xtest": when DISPLAY is not the desktop's display - the game on a display of
  its own (tools/headless/) - through XTEST (utils/xtest.py). uinput would click
  the desktop there; XTEST reaches only the display it is sent to.
- "pyautogui": on Windows, or on Linux when neither of the above can be used.
UMA_INPUT=uinput|xtest|pyautogui forces one. UMA_SEAT_DISPLAY names the
desktop's display (default ":0").

Finding things on screen (locateOnScreen and friends) stays on pyautogui; this
module only sends input.
"""
import atexit
import os
import re
import sys
import threading
import time

import pyautogui

import utils.uinput as uinput
from utils.log import info, warning

# pyautogui's defaults, kept so timings tuned against it still hold.
PAUSE = 0.1
MINIMUM_DURATION = 0.1
MINIMUM_SLEEP = 0.05
# How long a button or key is held. pyautogui sends down and up back to back;
# ui-control found 20ms reliable for a virtual device.
HOLD = 0.02

_lock = threading.Lock()
_backend = None
_pointer = None
_keyboard = None
_pos = None

def backend():
  """"uinput", "xtest" or "pyautogui", decided on first use."""
  global _backend
  with _lock:
    if _backend is None:
      _backend = _choose()
      info(f"Input backend: {_backend} (display {os.environ.get('DISPLAY') or 'unset'}).")
    return _backend

def _server(name):
  """The X server part of a display name: ":1.0" and ":1" are the same server."""
  return re.sub(r"\.\d+$", "", (name or "").strip())

def _devices(name=None):
  """The device module behind a backend. utils/xtest.py is imported only when
  used, since python-xlib is not installed on Windows."""
  if (name or backend()) == "xtest":
    import utils.xtest as xtest
    return xtest
  return uinput

def _choose():
  forced = os.environ.get("UMA_INPUT", "").strip().lower()
  if forced == "pyautogui" or (not forced and not sys.platform.startswith("linux")):
    return "pyautogui"
  # uinput plugs a device into the machine, and only the desktop's X server takes
  # it. On any other display - the game's own, from tools/headless/ - it would
  # click the desktop instead, so that display gets XTEST.
  desktop = _server(os.environ.get("UMA_SEAT_DISPLAY", ":0"))
  current = _server(os.environ.get("DISPLAY"))
  if forced == "xtest" or (not forced and current and current != desktop):
    problem = _devices("xtest").check()
    if problem is None:
      return "xtest"
    if forced == "xtest":
      raise RuntimeError(problem)
    warning(f"Falling back to pyautogui for input: {problem}")
    return "pyautogui"
  problem = uinput.check()
  if problem is None:
    return "uinput"
  if forced == "uinput":
    raise uinput.UInputError(problem)
  warning(f"Falling back to pyautogui for input: {problem}")
  return "pyautogui"

def _get_pointer():
  global _pointer, _pos
  dev = _devices()
  with _lock:
    if _pointer is None:
      try:
        width, height = pyautogui.size()
      except Exception:
        width, height = 1920, 1080
      _pointer = dev.Pointer(width, height)
      try:
        _pos = tuple(pyautogui.position())
      except Exception:
        _pos = (width // 2, height // 2)
    return _pointer

def _get_keyboard():
  global _keyboard
  dev = _devices()
  with _lock:
    if _keyboard is None:
      _keyboard = dev.Keyboard()
    return _keyboard

def close():
  global _pointer, _keyboard
  for device in (_pointer, _keyboard):
    if device is not None:
      device.close()
  _pointer = _keyboard = None

atexit.register(close)

def position():
  if backend() == "pyautogui":
    return tuple(pyautogui.position())
  _get_pointer()
  return _pos

def _xy(x, y):
  """pyautogui's argument forms: x and y, a point or a (left, top, width, height)
  box as x, or None for wherever the pointer is."""
  if x is not None and y is None and hasattr(x, "__len__"):
    if len(x) == 4:
      x, y = x[0] + x[2] / 2, x[1] + x[3] / 2
    else:
      x, y = x[0], x[1]
  cx, cy = position()
  return (cx if x is None else int(round(x)), cy if y is None else int(round(y)))

def _glide(x, y, duration):
  """pyautogui's _mouseMoveDrag stepping, over the uinput or XTEST pointer."""
  global _pos
  pointer = _get_pointer()
  sx, sy = _pos
  steps = [(x, y)]
  sleep_amount = 0
  if duration > MINIMUM_DURATION and (x, y) != (sx, sy):
    count = max(abs(x - sx), abs(y - sy))
    sleep_amount = duration / count
    if sleep_amount < MINIMUM_SLEEP:
      count = int(duration / MINIMUM_SLEEP)
      sleep_amount = duration / count
    steps = [(sx + (x - sx) * n / count, sy + (y - sy) * n / count) for n in range(count)]
    steps.append((x, y))
  for px, py in steps:
    if len(steps) > 1:
      time.sleep(sleep_amount)
    _pos = pointer.move_to(round(px), round(py))

def moveTo(x=None, y=None, duration=0.0):
  if backend() == "pyautogui":
    return pyautogui.moveTo(x, y, duration=duration)
  _glide(*_xy(x, y), duration)
  time.sleep(PAUSE)

def moveRel(xOffset=0, yOffset=0, duration=0.0):
  if backend() == "pyautogui":
    return pyautogui.moveRel(xOffset, yOffset, duration=duration)
  cx, cy = position()
  moveTo(cx + xOffset, cy + yOffset, duration=duration)

def _button(pressed, x, y, button, duration):
  if x is not None or y is not None:
    _glide(*_xy(x, y), duration)
  _get_pointer().button(button, pressed)
  time.sleep(PAUSE)

def mouseDown(x=None, y=None, button="left", duration=0.0):
  if backend() == "pyautogui":
    return pyautogui.mouseDown(x, y, button=button, duration=duration)
  _button(True, x, y, button, duration)

def mouseUp(x=None, y=None, button="left", duration=0.0):
  if backend() == "pyautogui":
    return pyautogui.mouseUp(x, y, button=button, duration=duration)
  _button(False, x, y, button, duration)

def click(x=None, y=None, clicks=1, interval=0.0, button="left", duration=0.0):
  if backend() == "pyautogui":
    return pyautogui.click(x, y, clicks=clicks, interval=interval, button=button, duration=duration)
  pointer = _get_pointer()
  if x is not None or y is not None:
    _glide(*_xy(x, y), duration)
  for _ in range(clicks):
    pointer.button(button, True)
    time.sleep(HOLD)
    pointer.button(button, False)
    time.sleep(interval)
  time.sleep(PAUSE)

def tripleClick(x=None, y=None, interval=0.0, button="left", duration=0.0):
  click(x, y, clicks=3, interval=interval, button=button, duration=duration)

def press(keys, presses=1, interval=0.0):
  if backend() == "pyautogui":
    return pyautogui.press(keys, presses=presses, interval=interval)
  keyboard = _get_keyboard()
  names = [keys] if isinstance(keys, str) else list(keys)
  for _ in range(presses):
    for name in names:
      keyboard.tap(_devices().keycode(name), HOLD)
      time.sleep(interval)
  time.sleep(PAUSE)
