"""Screen-debugging CLI for this bot.

Everything here is something that got hand-written several times while chasing
the Unity Cup icons: grab a lossless screenshot, ask what screen we are on,
score a template, find a coloured blob, cut a template candidate and measure
whether it actually separates from the negatives.

Read-only by default. The only subcommands that touch the game are `launch`
(starts it, never clicks), `close`, `click`, `advance`, `skiprace` and `scan`,
and `scan` refuses to click the already-selected facility because on the
training screen that executes the training instead of selecting it.

Run from the repo root:

  python tools/umatool.py launch
  python tools/umatool.py close
  python tools/umatool.py where
  python tools/umatool.py unity
  python tools/umatool.py shot --crop 800,145,950,715 --zoom 3
  python tools/umatool.py score assets/icons/unity_burst_ready.png --region 808,150,878,710
  python tools/umatool.py hue 265,330 --region 795,145,960,720
  python tools/umatool.py cut shots/foo.png 924,168 12 --out assets/icons/x.png
  python tools/umatool.py sep assets/icons/x.png --pos a.png --neg b.png --neg c.png
  python tools/umatool.py watch assets/buttons/next_btn.png --timeout 180
  python tools/umatool.py scan
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageGrab

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import shots  # noqa: E402
import utils.window as window  # noqa: E402

SHOTS = os.path.join(REPO, "shots")


def _grab(path=None):
  """Lossless capture. PNG always - JPEG artefacts ruin cut templates."""
  img = ImageGrab.grab()
  if path:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.save(path)
  return img


def _load(path):
  return Image.open(path).convert("RGB") if path else _grab()


def _bgr(img, region=None):
  arr = np.array(img.convert("RGB"))
  if region:
    l, t, r, b = region
    arr = arr[t:b, l:r]
  return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _rect(s):
  return tuple(int(v) for v in s.split(","))


def _dedupe(res, threshold, gap=25):
  ys, xs = np.where(res >= threshold)
  kept = []
  for x, y in sorted(zip(xs, ys), key=lambda p: -res[p[1], p[0]]):
    if not any(abs(x - kx) < gap and abs(y - ky) < gap for kx, ky in kept):
      kept.append((x, y))
  return kept


# --------------------------------------------------------------------------

def cmd_shot(a):
  path = a.out or os.path.join(SHOTS, time.strftime("shot_%H%M%S.png"))
  img = _grab(path)
  if a.crop:
    l, t, r, b = _rect(a.crop)
    img = img.crop((l, t, r, b))
    if a.zoom > 1:
      img = img.resize((img.width * a.zoom, img.height * a.zoom), Image.LANCZOS)
    path = path.replace(".png", "_crop.png")
    img.save(path)
  print(path, img.size)


def cmd_where(a):
  """Name the current screen instead of guessing from a full screenshot."""
  img = _load(a.image)
  probes = [
    ("lobby (tazuna)",  "assets/ui/tazuna_hint.png",            None),
    ("training btn",    "assets/buttons/training_btn.png",      (150, 780, 960, 1000)),
    ("back btn",        "assets/buttons/back_btn.png",          (150, 980, 330, 1080)),
    ("race btn",        "assets/buttons/race_btn.png",          None),
    ("race! confirm",   "assets/buttons/race_exclamation_btn.png", None),
    ("skip",            "assets/buttons/skip_btn.png",          None),
    ("next",            "assets/buttons/next_btn.png",          (150, 900, 960, 1080)),
    ("view results",    "assets/buttons/view_results.png",      None),
    ("complete career", "assets/buttons/complete_career_btn.png", None),
    ("unity race",      "assets/buttons/unity_cup_race_btn.png", None),
    ("begin showdown",  "assets/buttons/begin_showdown_btn.png", None),
    ("zenith race",     "assets/buttons/zenith_race_btn.png",   None),
  ]
  for label, path, region in probes:
    tpl = cv2.imread(os.path.join(REPO, path))
    if tpl is None:
      continue
    scr = _bgr(img, region)
    if tpl.shape[0] > scr.shape[0] or tpl.shape[1] > scr.shape[1]:
      continue
    res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
    mx = res.max()
    if mx >= a.min:
      _, _, _, loc = cv2.minMaxLoc(res)
      h, w = tpl.shape[:2]
      ox, oy = (region[0], region[1]) if region else (0, 0)
      print(f"  {label:18} {mx:.3f} at ({loc[0] + ox + w // 2},{loc[1] + oy + h // 2})")
  if a.image is None:
    import core.state as state
    print("  selected training:", state.check_selected_training())


def cmd_score(a):
  img = _load(a.image)
  region = _rect(a.region) if a.region else None
  scr = _bgr(img, region)
  for path in a.templates:
    tpl = cv2.imread(path)
    if tpl is None:
      print(f"  {path}: MISSING")
      continue
    if tpl.shape[0] > scr.shape[0] or tpl.shape[1] > scr.shape[1]:
      print(f"  {path}: template larger than search region")
      continue
    res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
    h, w = tpl.shape[:2]
    ox, oy = (region[0], region[1]) if region else (0, 0)
    hits = _dedupe(res, a.min)
    print(f"  {os.path.basename(path):34} best={res.max():.3f} n={len(hits)}")
    for x, y in hits[:a.limit]:
      print(f"      {res[y, x]:.3f} at ({x + ox + w // 2},{y + oy + h // 2})")


def cmd_hue(a):
  """Find coloured blobs. The Unity flames are only separable by hue."""
  img = _load(a.image)
  region = _rect(a.region) if a.region else (0, 0, img.width, img.height)
  lo, hi = (int(v) for v in a.range.split(","))
  arr = np.array(img)[region[1]:region[3], region[0]:region[2]]
  hsv = cv2.cvtColor(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
  hue = hsv[:, :, 0].astype(int) * 2
  mask = (((hue >= lo) & (hue <= hi)) & (hsv[:, :, 1] > a.sat) & (hsv[:, :, 2] > a.val)).astype(np.uint8)
  n, _, stats, cent = cv2.connectedComponentsWithStats(mask, connectivity=8)
  found = []
  for i in range(1, n):
    area = stats[i, cv2.CC_STAT_AREA]
    if area < a.area:
      continue
    found.append((area, int(cent[i][0]) + region[0], int(cent[i][1]) + region[1],
                  stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]))
  found.sort(reverse=True)
  print(f"  hue {lo}-{hi}deg: {mask.sum()} px, {len(found)} blobs >= {a.area}")
  for area, x, y, w, h in found[:a.limit]:
    print(f"      area={area:5d} at ({x},{y}) {w}x{h}")


def cmd_unity(a):
  import core.state as state
  import utils.constants as constants
  print("  check_unity_icons():", state.check_unity_icons())
  spec = (
    ("spirit",   "assets/icons/unity_spirit_gauge.png",  constants.SPIRIT_GAUGE_BBOX, state.SPIRIT_GAUGE_CONFIDENCE),
    ("burst",    "assets/icons/unity_burst_ready.png",   constants.SPIRIT_GAUGE_BBOX, state.BURST_READY_CONFIDENCE),
    ("burst_ex", "assets/icons/unity_burst_extreme.png", constants.UNITY_RAIL_BBOX,   state.BURST_EXTREME_CONFIDENCE),
  )
  img = _load(a.image)
  for key, path, bb, conf in spec:
    tpl = cv2.imread(os.path.join(REPO, path))
    if tpl is None:
      print(f"  {key:9} template missing: {path}")
      continue
    res = cv2.matchTemplate(_bgr(img, bb), tpl, cv2.TM_CCOEFF_NORMED)
    hits = _dedupe(res, conf)
    h, w = tpl.shape[:2]
    where = [(x + bb[0] + w // 2, y + bb[1] + h // 2) for x, y in hits]
    print(f"  {key:9} conf={conf} best={res.max():.3f} n={len(hits)} at {where}")


def cmd_cut(a):
  """Cut a centred square. Sizes are half-widths, matching the sweeps."""
  img = _load(a.image)
  cx, cy = (int(v) for v in a.centre.split(","))
  out = a.out or os.path.join(SHOTS, f"cut_{cx}_{cy}_{a.half}.png")
  os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
  img.crop((cx - a.half, cy - a.half, cx + a.half, cy + a.half)).save(out)
  print(out, Image.open(out).size)


def cmd_sep(a):
  """Does this template actually separate positives from negatives?

  A template that scores 1.000 on the frame it was cut from proves nothing.
  This reports the worst positive and the best negative, which is the only
  number that decides a usable threshold.
  """
  tpl = cv2.imread(a.template)
  if tpl is None:
    print("template missing:", a.template)
    return
  region = _rect(a.region) if a.region else None

  def best(path):
    scr = _bgr(Image.open(path).convert("RGB"), region)
    if tpl.shape[0] > scr.shape[0] or tpl.shape[1] > scr.shape[1]:
      return float("nan")
    return float(cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED).max())

  pos = [(p, best(p)) for p in a.pos]
  neg = [(p, best(p)) for p in a.neg]
  for p, s in pos:
    print(f"  POS {os.path.basename(p):40} {s:.3f}")
  for p, s in neg:
    print(f"  NEG {os.path.basename(p):40} {s:.3f}")
  if pos and neg:
    worst_pos, best_neg = min(s for _, s in pos), max(s for _, s in neg)
    print(f"\n  worst positive {worst_pos:.3f} | best negative {best_neg:.3f} "
          f"| margin {worst_pos - best_neg:+.3f}")
    if worst_pos > best_neg:
      print(f"  suggested threshold {(worst_pos + best_neg) / 2:.2f}")
    else:
      print("  NOT SEPARABLE - recut, usually tighter to exclude a translucent glow")


def cmd_watch(a):
  """Poll until a template shows up. Race loads can outlast any fixed sleep."""
  tpls = {p: cv2.imread(p) for p in a.templates}
  tpls = {k: v for k, v in tpls.items() if v is not None}
  t0 = time.time()
  while time.time() - t0 < a.timeout:
    img = _grab()
    scr = _bgr(img)
    for path, tpl in tpls.items():
      res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
      _, mx, _, loc = cv2.minMaxLoc(res)
      if mx >= a.min:
        h, w = tpl.shape[:2]
        out = os.path.join(SHOTS, time.strftime("watch_%H%M%S.png"))
        _grab(out)
        print(f"t+{time.time() - t0:.0f}s {os.path.basename(path)} {mx:.3f} "
              f"at ({loc[0] + w // 2},{loc[1] + h // 2}) -> {out}")
        return
    time.sleep(a.interval)
  print(f"nothing matched in {a.timeout}s")


LAUNCH_CODES = """\
  LAUNCH-OK       launched; window is up, capture saved
  LAUNCH-RUNNING  window already existed; brought it to front, capture saved
  LAUNCH-E01      could not hand the steam:// URL to Steam (Steam missing?)
  LAUNCH-E02      no "Umamusume" window within --timeout seconds"""
CLOSE_CODES = """\
  CLOSE-OK    window closed, process exited (ended with a signal if the game ignored the close)
  CLOSE-NONE  no game window was open
  CLOSE-E01   process still alive after --timeout seconds and SIGTERM/SIGKILL"""


def _game_window():
  return window.find(window.GAME_TITLE)


def cmd_close(a):
  """Close the game the way the window's X does. It asks no confirmation."""
  win = _game_window()
  if not win:
    print(f"CLOSE-NONE\n{CLOSE_CODES}")
    return
  how = window.close(win, a.timeout)
  if not how:
    print(f"CLOSE-E01 pid {win.pid} after {a.timeout:.0f}s\n{CLOSE_CODES}")
    # Non-zero, so the Tools tab's "exit 1" shows the close failed.
    raise SystemExit(1)
  if how == "terminated":
    print(f"CLOSE-OK (the game ignored the close request for {a.timeout:.0f}s; ended pid {win.pid})")
  else:
    print("CLOSE-OK")


def cmd_launch(a):
  """Start the Steam client of the game, or bring an existing window back.

  Never clicks: what comes up (title screen, maintenance notice, update
  download, login bonus) varies, so the caller reads the capture and decides.
  """
  win = _game_window()
  code = "LAUNCH-RUNNING"
  if win:
    window.activate(win)
  else:
    try:
      window.launch_game()
    except OSError as e:
      print(f"LAUNCH-E01 {e}\n{LAUNCH_CODES}")
      return
    t0 = time.time()
    while not win and time.time() - t0 < a.timeout:
      time.sleep(2)
      win = _game_window()
    if not win:
      print(f"LAUNCH-E02 after {a.timeout:.0f}s\n{LAUNCH_CODES}")
      return
    print(f"window up after {time.time() - t0:.0f}s, settling {a.settle:.0f}s")
    time.sleep(a.settle)
    code = "LAUNCH-OK"
  out = os.path.join(SHOTS, time.strftime("launch_%H%M%S.png"))
  img = _grab(out)
  print(f"{code} -> {out} {img.size}")


def cmd_skiprace(a):
  """Click through a race to its results screen.

  The skip button does not skip the whole race - it jumps to the next segment,
  so it has to be pressed repeatedly. It also moves between the small and big
  variants, so re-locate it every pass rather than reusing a position.
  """
  import utils.control as control
  skips = ["assets/buttons/skip_btn.png", "assets/buttons/skip_btn_big.png"]
  dones = ["assets/buttons/next_btn.png", "assets/buttons/next2_btn.png"]
  t0 = time.time()
  clicks = 0
  while time.time() - t0 < a.timeout:
    scr = _bgr(_grab())
    for path in dones:
      tpl = cv2.imread(path)
      if tpl is None:
        continue
      res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
      _, mx, _, loc = cv2.minMaxLoc(res)
      if mx >= 0.90:
        h, w = tpl.shape[:2]
        out = os.path.join(SHOTS, time.strftime("results_%H%M%S.png"))
        _grab(out)
        print(f"results reached after {clicks} skip clicks, "
              f"{os.path.basename(path)} {mx:.2f} at ({loc[0] + w // 2},{loc[1] + h // 2}) -> {out}")
        return
    hit = None
    for path in skips:
      tpl = cv2.imread(path)
      if tpl is None:
        continue
      res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
      _, mx, _, loc = cv2.minMaxLoc(res)
      if mx >= 0.88:
        h, w = tpl.shape[:2]
        hit = (loc[0] + w // 2, loc[1] + h // 2, os.path.basename(path), mx)
        break
    if hit:
      x, y, name, mx = hit
      control.moveTo(960, 540)
      time.sleep(0.1)
      control.click(x, y)
      clicks += 1
      print(f"  skip #{clicks}: {name} {mx:.2f} at ({x},{y})")
    time.sleep(a.interval)
  print(f"gave up after {a.timeout}s and {clicks} skip clicks")


ADVANCE_CODES = """\
  ADVANCE-OK   career lobby reached
  ADVANCE-E01  not in the lobby after --timeout seconds
  ADVANCE-E02  no career in progress (Career opened the career setup); start one yourself
  ADVANCE-E03  still on the home screen after tapping Career 3 times"""

# Inspiration is a full-screen "GO!" disc with no Next and no dialogue tap
# target, so tapping the dialogue position there does nothing at all.
ADVANCE_BUTTONS = ["assets/buttons/next_btn.png", "assets/buttons/next2_btn.png",
                   "assets/buttons/inspiration_btn.png",
                   "assets/buttons/close_btn.png", "assets/buttons/ok_btn.png",
                   "assets/buttons/ok_2_btn.png"]


def _best(scr, path):
  """Best score of one template on a BGR frame, and the centre of that hit."""
  tpl = cv2.imread(os.path.join(REPO, path))
  if tpl is None:
    return 0.0, None
  res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
  _, mx, _, loc = cv2.minMaxLoc(res)
  h, w = tpl.shape[:2]
  return mx, (loc[0] + w // 2, loc[1] + h // 2)


def advance_decision(scr):
  """What `advance` does with one BGR frame: (action, point, detail).

  action is "lobby" (done), "resume" (Continue Career's Resume), "career" (the
  home screen's Career button), "setup" (stop: no career in progress),
  "button" (Next, OK, Close, Inspiration) or "tap" (dialogue).

  Started from the title screen, the old loop only knew the career lobby, so it
  tapped the character art on the home screen until its timeout (2026-09-15).
  Scores measured that day: the team rank badge is 0.94-1.00 on the home
  screen and also 0.95 on the career setup screens, which alone have a Back
  button (0.98 there, 0.59 on the home screen). The lobby hint scores 0.80 on
  the Date Changed dialog, hence 0.85 rather than 0.80 for the lobby.
  """
  import utils.constants as constants
  mx, _ = _best(scr, "assets/ui/tazuna_hint.png")
  if mx >= 0.85:
    return "lobby", None, f"tazuna {mx:.2f}"
  mx, _ = _best(scr, "assets/ui/continue_career.png")
  if mx >= 0.90:
    rmx, point = _best(scr, "assets/buttons/resume_btn.png")
    if rmx >= 0.90:
      return "resume", point, f"continue_career {mx:.2f}, resume_btn {rmx:.2f}"
  mx, _ = _best(scr, "assets/ui/team_rank.png")
  if mx >= 0.85:
    bmx, _ = _best(scr, "assets/buttons/back_btn.png")
    if bmx >= 0.90:
      return "setup", None, f"team_rank {mx:.2f}, back_btn {bmx:.2f}"
    return "career", constants.CAREER_BUTTON_MOUSE_POS, f"team_rank {mx:.2f}"
  for path in ADVANCE_BUTTONS:
    bmx, point = _best(scr, path)
    if bmx >= 0.90:
      return "button", point, f"{os.path.basename(path)} {bmx:.2f}"
  return "tap", (553, 400), "no button"


def cmd_advance(a):
  """Click through to the career lobby, from the title screen, the home screen,
  or any dialogue/results screen inside a career.

  Each frame goes through advance_decision(). Buttons are re-located every pass
  because they move between screens, and a screen with no button at all is
  advanced with a tap, which is how the scenario dialogues progress.
  """
  import utils.control as control
  labels = {"resume": "Continue Career: Resume", "career": "home screen: Career",
            "button": "button", "tap": "no button, tapped to advance dialogue"}
  t0 = time.time()
  steps = 0
  career_taps = 0
  while time.time() - t0 < a.timeout:
    action, point, detail = advance_decision(_bgr(_grab()))
    if action == "lobby":
      out = os.path.join(SHOTS, time.strftime("lobby_%H%M%S.png"))
      _grab(out)
      print(f"ADVANCE-OK after {steps} clicks ({detail}) -> {out}")
      return
    if action == "setup":
      print(f"ADVANCE-E02 ({detail})\n{ADVANCE_CODES}")
      raise SystemExit(1)
    if action == "career":
      if career_taps >= 3:
        print(f"ADVANCE-E03 ({detail})\n{ADVANCE_CODES}")
        raise SystemExit(1)
      career_taps += 1
    # Glide onto the target, then press: a pointer that jumped straight there
    # did not register on the race preview (2026-09-15).
    control.moveTo(*point, duration=0.225)
    control.click()
    print(f"  {steps + 1}: {labels[action]} ({detail}) at {point}")
    steps += 1
    time.sleep(max(a.interval, 4) if action in ("resume", "career") else a.interval)
  print(f"ADVANCE-E01 after {a.timeout:.0f}s and {steps} clicks\n{ADVANCE_CODES}")
  raise SystemExit(1)


def cmd_click(a):
  import utils.control as control
  x, y = (int(v) for v in a.at.split(","))
  control.moveTo(960, 540)
  time.sleep(0.15)
  control.click(x, y)
  time.sleep(a.after)
  out = os.path.join(SHOTS, time.strftime("click_%H%M%S.png"))
  _grab(out)
  # One of these per press adds up fast during a debugging session.
  shots.prune(SHOTS, "click_")
  print(f"clicked ({x},{y}) -> {out}")


def cmd_type(a):
  """Type text into whatever field is already focused, then capture.

  The headless display has no keyboard a person can reach, so a text field on
  :1 could only ever be filled from here. Focusing is Click at X,Y's job; this
  only sends the keys. Typed one character at a time through utils.control,
  which resolves each to an X keysym, so this is printable ASCII only and a
  character that will not resolve is reported rather than silently dropped.
  """
  import utils.control as control
  bad = [c for c in a.text if not (32 <= ord(c) <= 126)]
  if bad:
    print(f"TYPE-E01 cannot type {bad!r}: printable ASCII only.")
    raise SystemExit(1)
  control.press(list(a.text), interval=a.interval)
  time.sleep(a.after)
  out = os.path.join(SHOTS, time.strftime("type_%H%M%S.png"))
  _grab(out)
  print(f"typed {len(a.text)} character(s) -> {out}")


def cmd_scan(a):
  """Visit every facility and report the Unity icons on each.

  Never clicks the selected facility: that executes the training.
  """
  import core.state as state
  import utils.control as control
  pos = {"spd": (337, 886), "sta": (445, 886), "pwr": (552, 886),
         "guts": (660, 886), "wit": (767, 886)}
  current, lvl = state.check_selected_training()
  if current is None:
    print("not on the training screen")
    return
  print(f"selected on entry: {current.upper()} Lvl {lvl}")
  stamp = time.strftime("%H%M%S")
  os.makedirs(SHOTS, exist_ok=True)
  rows = []
  for key in [k for k in pos if k != current] + [current]:
    if key != current:
      control.moveTo(960, 540)
      time.sleep(0.15)
      control.click(*pos[key])
      time.sleep(1.5)
      current = key
    path = os.path.join(SHOTS, f"{stamp}_{key}.png")
    _grab(path)
    rows.append((key, state.check_unity_icons(), path))
  print(f"\n{'facility':9} {'spirit':>7} {'burst':>7} {'burst_ex':>9}")
  for key, c, _ in rows:
    print(f"{key.upper():9} {c['spirit']:>7} {c['burst']:>7} {c['burst_ex']:>9}")
  print(f"\nPNGs: {os.path.join(SHOTS, stamp)}_*.png")


def main():
  p = argparse.ArgumentParser(prog="umatool", description=__doc__,
                              formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = p.add_subparsers(dest="cmd", required=True)

  s = sub.add_parser("shot", help="lossless screenshot, optionally cropped/zoomed")
  s.add_argument("--out")
  s.add_argument("--crop", help="L,T,R,B")
  s.add_argument("--zoom", type=int, default=1)
  s.set_defaults(func=cmd_shot)

  s = sub.add_parser("where", help="identify the current screen")
  s.add_argument("--image", help="score a saved png instead of the live screen")
  s.add_argument("--min", type=float, default=0.80)
  s.set_defaults(func=cmd_where)

  s = sub.add_parser("score", help="template match with positions")
  s.add_argument("templates", nargs="+")
  s.add_argument("--image")
  s.add_argument("--region", help="L,T,R,B")
  s.add_argument("--min", type=float, default=0.60)
  s.add_argument("--limit", type=int, default=8)
  s.set_defaults(func=cmd_score)

  s = sub.add_parser("hue", help="find coloured blobs (flames are hue-separable)")
  s.add_argument("range", help="LO,HI in degrees")
  s.add_argument("--image")
  s.add_argument("--region", help="L,T,R,B")
  s.add_argument("--sat", type=int, default=90)
  s.add_argument("--val", type=int, default=90)
  s.add_argument("--area", type=int, default=80)
  s.add_argument("--limit", type=int, default=8)
  s.set_defaults(func=cmd_hue)

  s = sub.add_parser("unity", help="unity icon counts plus per-template scores")
  s.add_argument("--image")
  s.set_defaults(func=cmd_unity)

  s = sub.add_parser("cut", help="cut a centred square template")
  s.add_argument("image")
  s.add_argument("centre", help="X,Y")
  s.add_argument("half", type=int)
  s.add_argument("--out")
  s.set_defaults(func=cmd_cut)

  s = sub.add_parser("sep", help="measure positive/negative separation")
  s.add_argument("template")
  s.add_argument("--pos", nargs="+", required=True)
  s.add_argument("--neg", nargs="+", required=True)
  s.add_argument("--region", help="L,T,R,B")
  s.set_defaults(func=cmd_sep)

  s = sub.add_parser("watch", help="poll until a template appears")
  s.add_argument("templates", nargs="+")
  s.add_argument("--timeout", type=float, default=180)
  s.add_argument("--interval", type=float, default=3)
  s.add_argument("--min", type=float, default=0.88)
  s.set_defaults(func=cmd_watch)

  s = sub.add_parser("click", help="click a point, then capture")
  s.add_argument("at", help="X,Y")
  s.add_argument("--after", type=float, default=2.0)
  s.set_defaults(func=cmd_click)

  s = sub.add_parser("type", help="type text into the focused field, then capture")
  s.add_argument("text", help="the text to type (printable ASCII)")
  s.add_argument("--interval", type=float, default=0.06, help="seconds between keys")
  s.add_argument("--after", type=float, default=1.0)
  s.set_defaults(func=cmd_type)

  s = sub.add_parser("launch", help="start the game via Steam (or bring its window to front), then capture")
  s.add_argument("--timeout", type=float, default=180)
  s.add_argument("--settle", type=float, default=15, help="seconds to let splash screens pass")
  s.set_defaults(func=cmd_launch)

  s = sub.add_parser("close", help="close the game window and wait for the process to exit")
  s.add_argument("--timeout", type=float, default=30)
  s.set_defaults(func=cmd_close)

  s = sub.add_parser("skiprace", help="click skip repeatedly until the results screen")
  s.add_argument("--timeout", type=float, default=180)
  s.add_argument("--interval", type=float, default=1.5)
  s.set_defaults(func=cmd_skiprace)

  s = sub.add_parser("advance", help="click through screens until the lobby")
  s.add_argument("--timeout", type=float, default=180)
  s.add_argument("--interval", type=float, default=1.8)
  s.set_defaults(func=cmd_advance)

  s = sub.add_parser("scan", help="visit every facility, report unity icons")
  s.set_defaults(func=cmd_scan)

  a = p.parse_args()
  os.chdir(REPO)
  a.func(a)


if __name__ == "__main__":
  main()
