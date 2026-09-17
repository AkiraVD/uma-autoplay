"""Saved configs, kept in one folder beside the bot.

Load and Save used to go through the browser's own file dialogs, so a preset
landed wherever that machine happened to be pointing. The page is opened from
several devices over the tailnet, so "wherever" differed every time and the
presets scattered. These routes keep every preset in `uma_configs/`, next to
config.json, so the same list shows up whichever device opens the page.

A name arrives from the browser and ends up as a filename, and the page is
reachable over the tailnet, so names are sanitised here rather than trusted:
anything outside [A-Za-z0-9._ -] is replaced, and the resolved path has to sit
directly inside the folder - the same discipline server/main.py's fallback uses
before serving anything out of web/dist.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = ROOT / "uma_configs"

# Everything else becomes "-". Dots are kept so "config.kitasan.json" survives
# as a name, but a leading dot is stripped so nothing can write a dotfile.
UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")
MAX_STEM = 80

def _stem(name: str) -> str:
  cleaned = UNSAFE.sub("-", (name or "").strip())
  if cleaned.lower().endswith(".json"):
    cleaned = cleaned[:-5]
  # A name of only dots/dashes/spaces would resolve to the folder itself.
  return cleaned.strip(". -")[:MAX_STEM]

def path_for(name: str):
  """Absolute path for a preset, or None when the name can't be used.

  Returns None rather than raising so callers answer 400 instead of 500.
  """
  stem = _stem(name)
  if not stem:
    return None
  path = (CONFIGS_DIR / f"{stem}.json").resolve()
  # "..%2F" survives routing; the parent check is what makes that harmless.
  if path.parent != CONFIGS_DIR.resolve():
    return None
  return path

def listing():
  """Every saved preset, newest first, with the fields the page shows."""
  CONFIGS_DIR.mkdir(exist_ok=True)
  rows = []
  for path in CONFIGS_DIR.glob("*.json"):
    try:
      data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
      # A hand-edited or half-written file shouldn't take the whole list down;
      # it is listed as unreadable so it is visible rather than silently gone.
      rows.append({"name": path.stem, "config_name": path.stem, "trainee": "",
                   "scenario": "", "saved_at": int(path.stat().st_mtime),
                   "unreadable": True})
      continue
    if not isinstance(data, dict):
      continue
    rows.append({
      "name": path.stem,
      "config_name": data.get("config_name") or path.stem,
      "trainee": data.get("trainee") or "",
      "scenario": data.get("scenario") or "",
      "saved_at": int(path.stat().st_mtime),
      "unreadable": False,
    })
  rows.sort(key=lambda r: r["saved_at"], reverse=True)
  return rows

def read(path: Path) -> dict:
  return json.loads(path.read_text(encoding="utf-8"))

def write(path: Path, data: dict):
  CONFIGS_DIR.mkdir(exist_ok=True)
  # Written whole, then moved into place, so a preset is never half a file if
  # the write is interrupted while the page is listing the folder.
  tmp = path.with_suffix(".json.tmp")
  tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
  tmp.replace(path)

def delete(path: Path):
  path.unlink()
