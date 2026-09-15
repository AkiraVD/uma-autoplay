"""Virtual mouse and keyboard on /dev/uinput, for Linux.

Adapted from ui-control (uictl/uinput.py). Events are written at the kernel
evdev layer, below X11 or Wayland, so every application - the game under Proton
included - receives them as it would from a real device. Needs write access to
/dev/uinput; a desktop login gets that through systemd's uaccess ACL, so no root.

utils/control.py is what the bot calls. This is only the device plumbing.
"""
import fcntl
import os
import struct
import time

UINPUT_PATH = "/dev/uinput"

def _ioc(direction, nr, size):
  return (direction << 30) | (size << 16) | (ord("U") << 8) | nr

UI_DEV_CREATE = _ioc(0, 1, 0)
UI_DEV_DESTROY = _ioc(0, 2, 0)
UI_DEV_SETUP = _ioc(1, 3, 92)       # struct uinput_setup
UI_ABS_SETUP = _ioc(1, 4, 28)       # struct uinput_abs_setup
UI_SET_EVBIT = _ioc(1, 100, 4)
UI_SET_KEYBIT = _ioc(1, 101, 4)
UI_SET_RELBIT = _ioc(1, 102, 4)
UI_SET_ABSBIT = _ioc(1, 103, 4)

# linux/input-event-codes.h
EV_SYN, EV_KEY, EV_REL, EV_ABS = 0x00, 0x01, 0x02, 0x03
SYN_REPORT = 0
REL_HWHEEL, REL_WHEEL = 0x06, 0x08
ABS_X, ABS_Y = 0x00, 0x01
BUTTONS = {"left": 0x110, "right": 0x111, "middle": 0x112, "back": 0x113, "forward": 0x114}

# Kernel keycodes. They are interpreted through the active keyboard layout,
# which only matters for letters on a non-US layout.
KEYS = {
  "esc": 1, "backspace": 14, "tab": 15, "enter": 28, "space": 57,
  "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64, "f7": 65,
  "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
  "up": 103, "left": 105, "right": 106, "down": 108,
}
for _row, _first in (("1234567890", 2), ("qwertyuiop", 16), ("asdfghjkl", 30), ("zxcvbnm", 44)):
  KEYS.update({ch: _first + i for i, ch in enumerate(_row)})
ALIASES = {"escape": "esc", "return": "enter"}

_EVENT = struct.Struct("llHHi")   # struct input_event on 64-bit

class UInputError(RuntimeError):
  pass

def check():
  """None when /dev/uinput can be used, otherwise why not and how to fix it."""
  if not os.path.exists(UINPUT_PATH):
    return "/dev/uinput does not exist. Load the module with 'sudo modprobe uinput'."
  if not os.access(UINPUT_PATH, os.W_OK):
    return ("/dev/uinput is not writable. A desktop login normally gets it by ACL; otherwise run "
            "'sudo usermod -aG input $USER', add the udev rule "
            "KERNEL==\"uinput\", GROUP=\"input\", MODE=\"0660\" and log in again.")
  return None

def keycode(name):
  key = name.strip().lower()
  key = ALIASES.get(key, key)
  if key not in KEYS:
    raise UInputError(f"No keycode for {name!r}. Add it to KEYS in utils/uinput.py.")
  return KEYS[key]

class _Device:
  """One virtual evdev device."""

  def __init__(self, name):
    problem = check()
    if problem:
      raise UInputError(problem)
    self._fd = os.open(UINPUT_PATH, os.O_WRONLY | os.O_NONBLOCK)
    self.name = name

  def _enable(self, request, value):
    fcntl.ioctl(self._fd, request, value)

  def _setup_abs(self, code, minimum, maximum):
    # struct uinput_abs_setup { __u16 code; struct input_absinfo absinfo; }
    blob = struct.pack("Hxx6i", code, 0, minimum, maximum, 0, 0, 0)
    fcntl.ioctl(self._fd, UI_ABS_SETUP, blob)

  def create(self):
    # struct uinput_setup { input_id id; char name[80]; __u32 ff_effects_max; }
    setup = struct.pack("HHHH80sI", 0x03, 0x1234, 0x5678, 1, self.name.encode()[:79], 0)
    fcntl.ioctl(self._fd, UI_DEV_SETUP, setup)
    fcntl.ioctl(self._fd, UI_DEV_CREATE)
    # The display server has to open the new device before it sees anything;
    # events sent sooner are lost.
    time.sleep(0.25)

  def emit(self, etype, code, value):
    os.write(self._fd, _EVENT.pack(0, 0, etype, code, value))

  def sync(self):
    self.emit(EV_SYN, SYN_REPORT, 0)

  def close(self):
    if self._fd is None:
      return
    try:
      fcntl.ioctl(self._fd, UI_DEV_DESTROY)
    except OSError:
      pass
    os.close(self._fd)
    self._fd = None

class Pointer(_Device):
  """Absolute pointer spanning the whole desktop.

  ABS_X/ABS_Y plus mouse buttons and no touch codes is the shape libinput
  classifies as an absolute pointer (what a VM's USB tablet advertises), so the
  cursor lands on the coordinates given rather than moving relative to itself.
  """

  def __init__(self, width, height, name="uma-auto virtual pointer"):
    super().__init__(name)
    self.width = width
    self.height = height
    self._enable(UI_SET_EVBIT, EV_KEY)
    for code in BUTTONS.values():
      self._enable(UI_SET_KEYBIT, code)
    self._enable(UI_SET_EVBIT, EV_ABS)
    self._enable(UI_SET_ABSBIT, ABS_X)
    self._enable(UI_SET_ABSBIT, ABS_Y)
    self._enable(UI_SET_EVBIT, EV_REL)
    for code in (REL_WHEEL, REL_HWHEEL):
      self._enable(UI_SET_RELBIT, code)
    self._setup_abs(ABS_X, 0, max(width - 1, 1))
    self._setup_abs(ABS_Y, 0, max(height - 1, 1))
    self.create()

  def move_to(self, x, y):
    """Move and return the point actually used, clamped to the desktop."""
    x = max(0, min(int(x), self.width - 1))
    y = max(0, min(int(y), self.height - 1))
    self.emit(EV_ABS, ABS_X, x)
    self.emit(EV_ABS, ABS_Y, y)
    self.sync()
    return x, y

  def button(self, name, pressed):
    if name not in BUTTONS:
      raise UInputError(f"Unknown button {name!r}; expected one of {', '.join(BUTTONS)}.")
    self.emit(EV_KEY, BUTTONS[name], 1 if pressed else 0)
    self.sync()

class Keyboard(_Device):
  def __init__(self, name="uma-auto virtual keyboard"):
    super().__init__(name)
    self._enable(UI_SET_EVBIT, EV_KEY)
    for code in range(1, 249):
      self._enable(UI_SET_KEYBIT, code)
    self.create()

  def key(self, code, pressed):
    self.emit(EV_KEY, code, 1 if pressed else 0)
    self.sync()

  def tap(self, code, hold=0.02):
    self.key(code, True)
    time.sleep(hold)
    self.key(code, False)
