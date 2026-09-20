"""Saved race lists: a planned schedule, kept so the config can load it.

The Race Plan tab is self-contained - aptitudes, targets and pinned turns are
entered there, not read from config.json - so a plan has to be *saved* before
anything else can use it. These routes keep every list in `uma_race_lists/`,
beside config.json and uma_configs/, for the same reason presets live there:
the page is opened from several devices over the tailnet, and a browser
download would land somewhere different each time.

A list stores two things. The `races` are exactly the shape
`config.race_schedule` takes (`name`, `year`, `date`), so the Races section can
load one straight in. The `settings` are the planner inputs that produced it,
so the tab can reopen a saved plan and carry on rather than rebuilding it from
memory.

Name sanitising is server/configs.py's `safe_stem`, imported rather than
copied: it is the check that stops "..%2F" reaching the filesystem, and two
copies of that would eventually disagree.

Everything arriving from the browser is filtered to known keys before it is
written. The page is reachable over the tailnet, so a list is treated as
untrusted input, not as something the UI is trusted to have shaped correctly.
"""
import json
from pathlib import Path

from server.configs import safe_stem

ROOT = Path(__file__).resolve().parent.parent
LISTS_DIR = ROOT / "uma_race_lists"

# One race as config.race_schedule wants it. Anything else the planner attached
# (grade, racetrack, distance) is kept for display but never required.
RACE_KEYS = ("name", "year", "date", "grade", "racetrack", "terrain", "has_image")
MAX_RACES = 200


def path_for(name: str):
  """Absolute path for a saved list, or None when the name can't be used.

  Returns None rather than raising so callers answer 400 instead of 500.
  """
  stem = safe_stem(name)
  if not stem:
    return None
  path = (LISTS_DIR / f"{stem}.json").resolve()
  # "..%2F" survives routing; the parent check is what makes that harmless.
  if path.parent != LISTS_DIR.resolve():
    return None
  return path


def normalise(data):
  """Keep only what a race list is allowed to hold.

  A race without a name, year and date cannot be scheduled, so it is dropped
  rather than saved as a row that would fail silently later. `settings` is
  stored opaquely - it is the tab's own state and only the tab reads it - but
  it has to be an object, so a list or a string cannot smuggle itself in.
  """
  if not isinstance(data, dict):
    return None
  races = []
  for entry in (data.get("races") or [])[:MAX_RACES]:
    if not isinstance(entry, dict):
      continue
    if not all(entry.get(k) for k in ("name", "year", "date")):
      continue
    races.append({k: entry[k] for k in RACE_KEYS if k in entry})
  settings = data.get("settings")
  return {
    "title": str(data.get("title") or "")[:120],
    "races": races,
    "settings": settings if isinstance(settings, dict) else {},
    "epithets": [str(e)[:80] for e in (data.get("epithets") or [])[:80]
                 if isinstance(e, str)],
  }


def listing():
  """Every saved list, newest first, with the fields the page shows."""
  LISTS_DIR.mkdir(exist_ok=True)
  rows = []
  for path in LISTS_DIR.glob("*.json"):
    try:
      data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
      # A hand-edited or half-written file shouldn't take the whole list down;
      # it is listed as unreadable so it is visible rather than silently gone.
      rows.append({"name": path.stem, "title": path.stem, "races": 0,
                   "runnable": 0, "epithets": 0,
                   "saved_at": int(path.stat().st_mtime), "unreadable": True})
      continue
    if not isinstance(data, dict):
      continue
    races = data.get("races") or []
    rows.append({
      "name": path.stem,
      "title": data.get("title") or path.stem,
      "races": len(races),
      "runnable": sum(1 for r in races if isinstance(r, dict) and r.get("has_image")),
      "epithets": len(data.get("epithets") or []),
      "saved_at": int(path.stat().st_mtime),
      "unreadable": False,
    })
  rows.sort(key=lambda r: r["saved_at"], reverse=True)
  return rows


def read(path: Path) -> dict:
  return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data: dict):
  LISTS_DIR.mkdir(exist_ok=True)
  # Written whole, then moved into place, so a list is never half a file if the
  # write is interrupted while the page is listing the folder.
  tmp = path.with_suffix(".json.tmp")
  tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
  tmp.replace(path)


def delete(path: Path):
  path.unlink()
