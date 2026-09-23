"""Health check for a running career: is the bot up, and is it getting anywhere?

Read-only. It never clicks, types or changes a setting, so it is safe to run
while the bot plays. It answers what otherwise takes a screenshot, a log tail
and a handful of shell commands:

  - is exactly one bot process running, and is the bot toggled on (Pause)?
  - is the log still moving, and is the turn counter still moving?
  - has the bot itself complained recently (loops, give-ups, tracebacks)?
  - is the X display answering, and is the game window there and in front?
  - what is on screen right now (saved as a screenshot to look at)?

The window, focus and screen checks follow the display the running bot plays on
(its own DISPLAY), so a game on the headless display from tools/headless/ is
checked there rather than on the desktop.

  python tools/health.py            # report, screenshot saved under shots/
  python tools/health.py --display :1  # check that display, whatever the bot uses
  python tools/health.py --no-shot  # skip the screenshot and screen probes
  python tools/health.py --json     # machine-readable

Ends with HEALTH-OK, HEALTH-WARN or HEALTH-FAIL (exit code 0, 1 or 2).

The turn check is the reason this exists. A stuck bot usually keeps logging: on
2026-09-15 it chose to rest on turn 6 over twenty times in a row, because the
Rest confirmation it opened was closed again by the generic Cancel handler. The
log grew the whole time, so a watcher looking for silence saw nothing wrong.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, REPO)
sys.path.insert(0, TOOLS)

import shots  # noqa: E402
from logserver import tail  # noqa: E402

LOG = os.path.join(REPO, "logs", "log.txt")
SHOTS = os.path.join(REPO, "shots")
SERVER = "http://127.0.0.1:8000/logs/data"

# A lobby pass takes about 40s and a normal turn reads the lobby once or twice,
# so four readings of one turn is already odd and eight is a loop. Races,
# concerts and skill buying stretch a turn in time, not in lobby readings.
SAME_TURN_WARN = 4
SAME_TURN_FAIL = 8
LOG_SILENT_FAIL = 180
TROUBLE_WINDOW = 600
X_BACKLOG_FAIL = 5
SCREEN_MATCH = 0.85

OK, WARN, FAIL = "ok", "warn", "fail"
RANK = {OK: 0, WARN: 1, FAIL: 2}
MARK = {OK: " ok ", WARN: "warn", FAIL: "FAIL"}
VERDICT = {OK: "HEALTH-OK", WARN: "HEALTH-WARN", FAIL: "HEALTH-FAIL"}

# utils/log.py writes 'HH:MM:SS LEVEL   message'.
LINE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}) +(\w+) +(.*)$")
# The bot's own ways of saying it is going round in circles or has given up.
TROUBLE = re.compile(
  r"has come back \d+ times|Not in the career lobby for|Traceback|Couldn't|"
  r"Stopping rather than|still had not loaded", re.I)
# What the bot decided to do with a turn, so a loop can say what it keeps trying.
DECISION = re.compile(
  r"resting instead of training|^Training [A-Z]+\.$|^Going on a Recreation outing|"
  r"^Going out with the friend support|^Race Day\.|Nothing worth training", re.I)

# Screen elements worth naming, each a template the bot itself uses.
PROBES = [
  ("career lobby", "assets/ui/tazuna_hint.png"),
  ("event choice", "assets/icons/event_choice_1.png"),
  ("dialog with Cancel", "assets/buttons/cancel_btn.png"),
  ("dialog with OK", "assets/buttons/ok_btn.png"),
  ("Next button", "assets/buttons/next_btn.png"),
  ("race skip button", "assets/buttons/skip_btn.png"),
  ("Back button", "assets/buttons/back_btn.png"),
  ("career complete", "assets/buttons/complete_career_btn.png"),
]


def parse(lines):
  """[(secs, level, message)], on a clock that keeps counting past midnight."""
  out, last, day = [], None, 0
  for raw in lines:
    m = LINE.match(raw)
    if not m:
      continue
    secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + day
    if last is not None and secs < last - 3600:
      day += 86400
      secs += 86400
    last = secs
    out.append((secs, m.group(4), m.group(5)))
  return out


def analyse_log(lines):
  """Progress facts for the latest bot run. Pure, so tests can feed it text."""
  entries = parse(lines)
  start = 0
  for i, (_, _, msg) in enumerate(entries):
    if msg.startswith("[BOT] Starting"):
      start = i
  run = entries[start:]
  facts = {"year": None, "turn": None, "passes_on_turn": 0, "secs_on_turn": 0,
           "last_decision": None, "stopped": False, "trouble": []}
  if not run:
    return facts

  year, key, first_on_key = None, None, None
  for secs, _, msg in run:
    if msg.startswith("Year: "):
      year = msg[len("Year: "):]
    elif msg.startswith("Turn: "):
      # Keyed on the year too: the turn counter counts down afresh each year.
      k = (year, msg[len("Turn: "):])
      if k != key:
        key, first_on_key, facts["passes_on_turn"] = k, secs, 0
      facts["passes_on_turn"] += 1
    if DECISION.search(msg):
      facts["last_decision"] = msg
    if msg.startswith("[BOT] Stopped"):
      facts["stopped"] = True

  if key:
    facts["year"], facts["turn"] = key
    facts["secs_on_turn"] = run[-1][0] - first_on_key
  newest = run[-1][0]
  facts["trouble"] = [f"{level} {msg}" for secs, level, msg in run
                      if newest - secs <= TROUBLE_WINDOW
                      and (level == "ERROR" or TROUBLE.search(msg))][-6:]
  return facts


def stuck_hint(decision):
  if decision and "resting instead of training" in decision:
    return ("Resting keeps failing. If a Rest confirmation opens, the generic Cancel"
            " handler closes it again: turn off confirmation pop-ups in the game's"
            " Options, or tick 'Do not show again' on that dialog.")
  return ("The bot keeps repeating something the game is not taking. Look at the"
          " screenshot for a dialog or screen it does not handle.")


def duration(secs):
  return f"{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"{secs}s"


def check(status, code, what, detail="", hint="", **extra):
  return dict(status=status, code=code, what=what, detail=detail, hint=hint, **extra)


def bot_processes():
  """PIDs of python processes running this repo's main.py, or None off Linux."""
  if not os.path.isdir("/proc"):
    return None
  pids = []
  for name in os.listdir("/proc"):
    if not name.isdigit():
      continue
    try:
      with open(f"/proc/{name}/cmdline", "rb") as f:
        argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
      cwd = os.readlink(f"/proc/{name}/cwd")
    except OSError:
      continue
    if (len(argv) >= 2 and "python" in os.path.basename(argv[0])
        and os.path.basename(argv[-1]) == "main.py"
        and os.path.realpath(cwd) == os.path.realpath(REPO)):
      pids.append(int(name))
  return pids


def process_display(pid):
  """DISPLAY from a process's environment, or None."""
  try:
    with open(f"/proc/{pid}/environ", "rb") as f:
      for item in f.read().split(b"\0"):
        if item.startswith(b"DISPLAY="):
          return item[len(b"DISPLAY="):].decode(errors="replace")
  except OSError:
    pass
  return None


def server_status():
  """The config server's view: {"state": "running"|"stopped", ...} or {"error": ...}."""
  try:
    with urllib.request.urlopen(SERVER, timeout=3) as r:
      return json.load(r).get("status") or {"error": "no status in reply"}
  except Exception as e:
    return {"error": str(e)}


def x_backlog():
  """Connections waiting on the X server's listen sockets. A frozen Xorg stops
  accepting them, so this climbs while everything else just hangs."""
  try:
    out = subprocess.run(["ss", "-xl"], capture_output=True, text=True, timeout=5).stdout
  except (OSError, subprocess.SubprocessError):
    return None
  queues = [int(parts[2]) for parts in (line.split() for line in out.splitlines()
            if ".X11-unix/X" in line) if len(parts) > 2 and parts[2].isdigit()]
  return max(queues) if queues else None


def active_window():
  """The focused window's id, "timeout" if X did not answer, None if unknown."""
  try:
    r = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"], capture_output=True,
                       text=True, timeout=5)
  except subprocess.TimeoutExpired:
    return "timeout"
  except OSError:
    return None
  m = re.search(r"0x[0-9a-fA-F]+", r.stdout)
  return int(m.group(0), 16) if m else None


def screen_report():
  """Save a screenshot and name the known elements on it."""
  import cv2
  import numpy as np
  from PIL import ImageGrab
  img = ImageGrab.grab()
  os.makedirs(SHOTS, exist_ok=True)
  path = os.path.join(SHOTS, time.strftime("health_%H%M%S.png"))
  img.save(path)
  # Every check writes one of these, including every /health from a phone.
  shots.prune(SHOTS, "health_")
  screen = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
  seen = []
  for label, rel in PROBES:
    tpl = cv2.imread(os.path.join(REPO, rel))
    if tpl is None:
      continue
    if cv2.minMaxLoc(cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED))[1] >= SCREEN_MATCH:
      seen.append(label)
  return path, seen


def run_checks(shot=True, display=None):
  checks = []
  linux = sys.platform.startswith("linux")

  pids = bot_processes()
  status = server_status()
  bot_display = process_display(pids[0]) if pids and len(pids) == 1 else None
  if display is None:
    display = bot_display
  if display:
    # Everything below that talks to X - window, focus, screenshot - is about
    # the display the bot plays on, which is not the desktop's when the game
    # has a display of its own.
    os.environ["DISPLAY"] = display
  if pids is None:
    checks.append(check(OK, "BOT", "bot process", "not checked off Linux"))
  elif not pids:
    checks.append(check(FAIL, "BOT-E01", "bot process", "no main.py running from this repo",
                        "Start it with ./run_auto_uma.sh, then press Pause."))
  elif len(pids) > 1:
    checks.append(check(FAIL, "BOT-E02", "bot process", f"{len(pids)} bots running, pids {pids}",
                        "Two bots fight over the mouse. Stop all but one."))
  else:
    checks.append(check(OK, "BOT", "bot process", f"pid {pids[0]}, playing on display {bot_display or '?'}"))

  toggled_on = None
  if "state" in status:
    toggled_on = status["state"] == "running"
    if toggled_on:
      checks.append(check(OK, "BOT", "bot toggle", "on (Pause)"))
    else:
      checks.append(check(WARN, "BOT-W01", "bot toggle", "off (Pause)",
                          "The bot is idle. Press Pause, or Start bot on the config page."))
  elif pids:
    checks.append(check(WARN, "SRV-W01", "config server", f"no answer on :8000 ({status['error']})"))

  facts = analyse_log(tail(LOG))
  active = bool(pids) and toggled_on is not False and not facts["stopped"]
  try:
    silent = int(time.time() - os.path.getmtime(LOG))
  except OSError:
    silent = None
  if silent is None:
    checks.append(check(WARN, "LOG-W01", "log", "logs/log.txt not found"))
  elif active and silent >= LOG_SILENT_FAIL:
    checks.append(check(FAIL, "LOG-E01", "log", f"no new line for {duration(silent)} while the bot is on",
                        "The bot is hung. Look at the screenshot; check the display line first."))
  else:
    checks.append(check(OK, "LOG", "log", f"last line {duration(silent)} ago"))

  if facts["turn"] is None:
    checks.append(check(OK, "TURN", "turn progress", "no turn read yet this run"))
  else:
    passes = facts["passes_on_turn"]
    detail = (f"{facts['year'] or '?'}, turn {facts['turn']}: read {passes}x"
              f" over {duration(facts['secs_on_turn'])}")
    lines = [f"last decision: {facts['last_decision']}"] if facts["last_decision"] else []
    if not active:
      checks.append(check(OK, "TURN", "turn progress", detail + " (bot not running)"))
    elif passes >= SAME_TURN_FAIL:
      checks.append(check(FAIL, "TURN-E01", "turn progress", detail + " without the turn changing",
                          stuck_hint(facts["last_decision"]), lines=lines))
    elif passes >= SAME_TURN_WARN:
      checks.append(check(WARN, "TURN-W01", "turn progress", detail,
                          stuck_hint(facts["last_decision"]), lines=lines))
    else:
      checks.append(check(OK, "TURN", "turn progress", detail))

  if facts["trouble"]:
    checks.append(check(WARN, "TRBL-W01", "bot warnings",
                        f"{len(facts['trouble'])} in the last {TROUBLE_WINDOW // 60} min",
                        lines=facts["trouble"]))

  display_ok = True
  focused = None
  if linux:
    backlog = x_backlog()
    focused = active_window()
    if focused == "timeout" or (backlog or 0) > X_BACKLOG_FAIL:
      display_ok = False
      checks.append(check(FAIL, "DISP-E01", "display",
                          f"X server {os.environ.get('DISPLAY', '?')} not answering (backlog {backlog})",
                          "The Xorg freeze: only restarting X or rebooting clears it."))
    else:
      checks.append(check(OK, "DISP", "display", f"{os.environ.get('DISPLAY', '?')} answering (backlog {backlog})"))

  if display_ok:
    try:
      import utils.window as window
      win = window.find(window.GAME_TITLE)
      error = None
    except Exception as e:
      win, error = None, e
    if error is not None:
      checks.append(check(WARN, "WIN-W02", "game window", f"couldn't look for it ({error})"))
    elif not win:
      checks.append(check(FAIL, "WIN-E01", "game window", f"no 'Umamusume' window on {os.environ.get('DISPLAY', '?')}",
                          "The game is closed or crashed. Open it with tools/umatool.py launch."))
    # Without a window manager nobody updates the active window, so the front-window
    # check would only compare against a stale value.
    elif getattr(win, "managed", True) and isinstance(focused, int) \
        and int(str(win.handle), 16 if str(win.handle).startswith("0x") else 10) != focused:
      checks.append(check(WARN, "WIN-W01", "game window", "open but not the front window",
                          "Clicks land on whatever window is on top."))
    elif not getattr(win, "managed", True):
      checks.append(check(OK, "WIN", "game window",
                          f"open (no window manager on {os.environ.get('DISPLAY', '?')}; found through X directly)"))
    else:
      checks.append(check(OK, "WIN", "game window", "open and in front" if isinstance(focused, int) else "open"))

  if shot and display_ok:
    try:
      path, seen = screen_report()
      checks.append(check(OK, "SCR", "screen", ", ".join(seen) or "no known element matched", shot=path))
    except Exception as e:
      checks.append(check(WARN, "SCR-W01", "screen", f"screenshot failed ({e})"))

  verdict = max((c["status"] for c in checks), key=RANK.get)
  return verdict, checks, facts


def report(verdict, checks):
  print(f"uma-auto health  {time.strftime('%H:%M:%S')}")
  for c in checks:
    print(f"[{MARK[c['status']]}] {c['code']:9} {c['what']}: {c['detail']}")
    for line in c.get("lines", []):
      print(f"{'':17}{line}")
    if c.get("shot"):
      print(f"{'':17}screenshot: {c['shot']}")
    if c["hint"] and c["status"] != OK:
      print(f"{'':17}-> {c['hint']}")
  print(VERDICT[verdict])


def main():
  p = argparse.ArgumentParser(prog="health", description=__doc__,
                              formatter_class=argparse.RawDescriptionHelpFormatter)
  p.add_argument("--no-shot", action="store_true", help="skip the screenshot and screen probes")
  p.add_argument("--json", action="store_true", help="print JSON instead of the report")
  p.add_argument("--display", help="X display to check (default: the one the running bot plays on)")
  a = p.parse_args()
  verdict, checks, facts = run_checks(shot=not a.no_shot, display=a.display)
  if a.json:
    print(json.dumps({"verdict": VERDICT[verdict], "checks": checks, "facts": facts}, indent=2))
  else:
    report(verdict, checks)
  sys.exit(RANK[verdict])


if __name__ == "__main__":
  main()
