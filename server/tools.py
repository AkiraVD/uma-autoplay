"""Run umatool and the health check from the config page's Tools tab.

Only the commands in COMMANDS can run, with their arguments built and checked
here and never passed to a shell - the config page is reachable over the tailnet.
One job at a time: two tools clicking the game at once would fight like two bots.
Commands that click the game, or close it, are refused while the bot is running.

Jobs run on a thread and the page polls status(), because a launch can take
minutes. The child inherits this process's environment, so with the bot started
by run_background.sh every command works on the game's display (:1).
"""
import io
import os
import re
import subprocess
import sys
import threading
import time
import uuid

import core.state as state

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "shots")
UMATOOL = "tools/umatool.py"

# blocked: refused while the bot is running. needs_at: takes an X,Y point.
COMMANDS = {
  "health": {"label": "Health check", "argv": ["tools/health.py"], "timeout": 120},
  "shot": {"label": "Screenshot", "argv": [UMATOOL, "shot"], "timeout": 60},
  "where": {"label": "Where am I", "argv": [UMATOOL, "where"], "timeout": 120},
  "launch": {"label": "Launch game", "argv": [UMATOOL, "launch"], "timeout": 240},
  "close": {"label": "Close game", "argv": [UMATOOL, "close"], "timeout": 60, "blocked": True},
  "advance": {"label": "Advance to lobby", "argv": [UMATOOL, "advance"], "timeout": 200, "blocked": True},
  "skiprace": {"label": "Skip race", "argv": [UMATOOL, "skiprace"], "timeout": 200, "blocked": True},
  "click": {"label": "Click at X,Y", "argv": [UMATOOL, "click"], "timeout": 60, "blocked": True,
            "needs_at": True},
  "scan": {"label": "Facility scan", "argv": [UMATOOL, "scan"], "timeout": 120, "blocked": True},
}

MAX_LINES = 400
AT = re.compile(r"^\s*(\d{1,4})\s*,\s*(\d{1,4})\s*$")
# umatool and health print the PNG they saved; the page shows the last one.
SHOT = re.compile(r"shots/([\w.-]+\.png)")

_lock = threading.Lock()
_job = None  # the running job, or the last one to finish

def _snapshot(job):
  return dict(job, lines=list(job["lines"])) if job else None

def status():
  with _lock:
    job = _snapshot(_job)
  return {"bot_running": bool(state.is_bot_running), "job": job}

def screen_jpeg(quality=85):
  """The game screen right now, as (JPEG bytes, (width, height)).

  Grabbed in this process, which shares the bot's DISPLAY, so under
  run_background.sh it is the game's display. Kept full size, so a pixel in the
  image is a pixel on the game screen: the Tools tab reads click points off it.
  JPEG rather than PNG keeps a 1920x1080 frame small enough to refresh over the
  tailnet. Read-only, so it is allowed while the bot runs.
  """
  from PIL import ImageGrab
  img = ImageGrab.grab().convert("RGB")
  buf = io.BytesIO()
  img.save(buf, "JPEG", quality=quality)
  return buf.getvalue(), img.size

def start(name, at=None):
  """Start a command. Returns (job, None), or (None, (http_status, message))."""
  global _job
  spec = COMMANDS.get(name)
  if spec is None:
    return None, (404, f"TOOL-E01 unknown command {name!r}.")
  if spec.get("blocked") and state.is_bot_running:
    return None, (409, f"TOOL-E02 {spec['label']} touches the game. Stop the bot with F1 first.")

  argv = [sys.executable, *spec["argv"]]
  if name == "shot":
    argv += ["--out", os.path.join("shots", time.strftime("tool_shot_%H%M%S.png"))]
  if spec.get("needs_at"):
    m = AT.match(at or "")
    if not m:
      return None, (400, "TOOL-E03 give the point as X,Y, for example 960,540.")
    x, y = int(m.group(1)), int(m.group(2))
    if not (0 <= x < 1920 and 0 <= y < 1080):
      return None, (400, f"TOOL-E04 {x},{y} is outside the 1920x1080 screen.")
    argv.append(f"{x},{y}")

  with _lock:
    if _job and _job["state"] == "running":
      return None, (409, f"TOOL-E05 {COMMANDS[_job['name']]['label']} is still running.")
    _job = {"id": uuid.uuid4().hex[:12], "name": name, "label": spec["label"],
            "argv": argv[1:], "state": "running", "started": time.time(), "ended": None,
            "exit_code": None, "lines": [], "image": None}
    job = _job
    snapshot = _snapshot(job)
  threading.Thread(target=_run, args=(job, argv, spec["timeout"]), daemon=True,
                   name=f"tool-{name}").start()
  return snapshot, None

def _append(job, line):
  with _lock:
    job["lines"].append(line)
    del job["lines"][:-MAX_LINES]
    m = SHOT.search(line)
    if m and os.path.isfile(os.path.join(SHOTS, m.group(1))):
      job["image"] = m.group(1)

def _finish(job, result, code=None):
  with _lock:
    job["state"] = result
    job["exit_code"] = code
    job["ended"] = time.time()

def _run(job, argv, timeout):
  try:
    proc = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1,
                            env=dict(os.environ, PYTHONUNBUFFERED="1"))
  except OSError as e:
    _append(job, f"TOOL-E06 couldn't start {argv[1]}: {e}")
    _finish(job, "failed")
    return

  expired = threading.Event()
  def kill():
    expired.set()
    proc.kill()
  timer = threading.Timer(timeout, kill)
  timer.start()
  try:
    for line in proc.stdout:
      _append(job, line.rstrip("\n"))
    code = proc.wait()
  finally:
    timer.cancel()

  if expired.is_set():
    _append(job, f"TOOL-E07 stopped after {timeout}s.")
    _finish(job, "timed out", code)
  else:
    # A non-zero exit is not always a failure: health exits 1 or 2 for WARN or
    # FAIL. The page shows the code rather than guessing.
    _finish(job, "done", code)
