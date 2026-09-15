"""Find, raise, close and launch the game window, per platform.

Windows goes through pygetwindow, as the bot always did. pygetwindow has no
Linux support, so Linux asks the window manager through wmctrl (EWMH). That
covers X11, and on Wayland it still sees XWayland windows - which is what the
game is under Proton.

When no window manager answers, Linux asks the X server directly instead
(xwininfo, xprop, WM_DELETE_WINDOW). That happens on the headless display from
tools/headless/ once its metacity is gone: it exited on its own mid-career once,
and wmctrl, which reads the window manager's client list, then sees nothing.
"""
import os
import re
import shutil
import subprocess
import sys
import time

WINDOWS = sys.platform == "win32"
STEAM_APP_ID = 3224770
GAME_TITLE = "Umamusume"

class Window:
  def __init__(self, handle, title, pid=0, native=None, managed=True):
    self.handle = handle    # X window id on Linux, HWND on Windows
    self.title = title
    self.pid = pid          # 0 when the window does not say
    self.native = native    # the pygetwindow object on Windows
    self.managed = managed  # False: found through X directly, with no window manager

  def __repr__(self):
    return f"Window({self.title!r}, handle={self.handle}, pid={self.pid}, managed={self.managed})"

def _wmctrl(*args):
  if not shutil.which("wmctrl"):
    raise RuntimeError("wmctrl is not installed. Install it with 'sudo apt install wmctrl'.")
  result = subprocess.run(["wmctrl", *args], capture_output=True, encoding="utf-8",
                          errors="replace", timeout=10)
  return result.stdout

def _listed():
  """[Window] for every managed window, from `wmctrl -lp`."""
  windows = []
  for line in _wmctrl("-lp").splitlines():
    # 0x04a00007  0 12345  hostname Title, which may contain spaces or be empty
    parts = line.split(None, 4)
    if len(parts) < 4:
      continue
    pid = int(parts[2]) if parts[2].isdigit() else 0
    windows.append(Window(parts[0], parts[4] if len(parts) == 5 else "", pid))
  return windows

def _x(*args):
  tool = args[0]
  if not shutil.which(tool):
    raise RuntimeError(f"{tool} is not installed. Install it with 'sudo apt install x11-utils'.")
  return subprocess.run(list(args), capture_output=True, encoding="utf-8", errors="replace",
                        timeout=10).stdout

def _x_named_children():
  """[(handle, title)] for the root window's named children, straight from X.

  With no window manager, every application window is a direct child of the
  root. Wine also leaves hidden ones there under names like "Steam" and
  "Default IME", which is why find() checks that a match is actually shown.
  """
  return re.findall(r'^\s+(0x[0-9a-fA-F]+) "(.*?)": \(', _x("xwininfo", "-root", "-children"), re.M)

def _x_viewable(handle):
  return "Map State: IsViewable" in _x("xwininfo", "-id", handle)

def _x_pid(handle):
  m = re.search(r"=\s*(\d+)", _x("xprop", "-id", handle, "_NET_WM_PID"))
  return int(m.group(1)) if m else 0

def _x_close(handle):
  """Ask a window to close with WM_DELETE_WINDOW, the message a window manager's
  close button sends, for a display with no window manager to send it."""
  from Xlib import X, display
  from Xlib.protocol import event
  connection = display.Display()
  try:
    target = connection.create_resource_object("window", int(handle, 16))
    message = event.ClientMessage(
      window=target, client_type=connection.intern_atom("WM_PROTOCOLS"),
      data=(32, [connection.intern_atom("WM_DELETE_WINDOW"), X.CurrentTime, 0, 0, 0]))
    target.send_event(message)
    connection.flush()
  finally:
    connection.close()

def find(title):
  """The window whose title is exactly `title` (ignoring surrounding spaces), or None."""
  if WINDOWS:
    import ctypes
    import pygetwindow as gw
    native = next((w for w in gw.getWindowsWithTitle(title) if w.title.strip() == title), None)
    if not native:
      return None
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(native._hWnd, ctypes.byref(pid))
    return Window(native._hWnd, native.title, pid.value, native)
  try:
    listed = _listed()
  except RuntimeError:
    listed = []
  if listed:
    return next((w for w in listed if w.title.strip() == title), None)
  # Nothing listed means no window manager is answering; ask X itself.
  for handle, name in _x_named_children():
    if name.strip() == title and _x_viewable(handle):
      return Window(handle, name, _x_pid(handle), managed=False)
  return None

def activate(win):
  """Bring the window to the front, restoring it if minimised."""
  if WINDOWS:
    # Windows refuses a plain activate() from a background process, but a
    # minimize/restore cycle comes back on top.
    if not win.native.isMinimized:
      win.native.minimize()
      time.sleep(0.2)
    win.native.restore()
  elif win.managed:
    _wmctrl("-i", "-a", win.handle)
  # An unmanaged window has no window manager to raise it, and needs none: on
  # the headless display the game is the only window shown.
  time.sleep(0.5)

def _alive(win):
  if win.pid:
    try:
      os.kill(win.pid, 0)
    except ProcessLookupError:
      return False
    except PermissionError:
      pass
    return True
  if win.managed:
    return any(w.handle == win.handle for w in _listed())
  return any(handle == win.handle for handle, _ in _x_named_children())

def close(win, timeout=30):
  """Close the window the way its X button does, then wait for the process to
  exit (or, when the window names no process, for the window to go).

  Returns True once it is gone, False if it is still there after `timeout`."""
  if WINDOWS:
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    proc = k32.OpenProcess(0x00100000, False, win.pid)  # SYNCHRONIZE
    win.native.close()
    timed_out = k32.WaitForSingleObject(proc, int(timeout * 1000)) == 0x102  # WAIT_TIMEOUT
    k32.CloseHandle(proc)
    return not timed_out
  if win.managed:
    _wmctrl("-i", "-c", win.handle)
  else:
    _x_close(win.handle)
  deadline = time.time() + timeout
  while time.time() < deadline:
    if not _alive(win):
      return True
    time.sleep(0.5)
  return False

def launch_game():
  """Hand steam://rungameid to Steam, which starts itself if needed.

  Raises OSError when there is nothing to hand it to."""
  url = f"steam://rungameid/{STEAM_APP_ID}"
  if WINDOWS:
    os.startfile(url)
    return
  if shutil.which("steam"):
    command = ["steam", url]
  elif shutil.which("xdg-open"):
    command = ["xdg-open", url]
  else:
    raise OSError("neither steam nor xdg-open is on PATH")
  subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, start_new_session=True)
