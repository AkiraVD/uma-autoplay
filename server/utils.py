import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

def load_config() -> dict:
  if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
      return json.load(f)
  return {}

def save_config(data: dict):
  # Written to a temporary file and moved into place: the page applies every
  # edit as it is made, so a write can land at the moment core/state.py reads
  # the file, and half a config.json is worse than an old one.
  tmp = CONFIG_PATH.with_suffix(".json.tmp")
  with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
  tmp.replace(CONFIG_PATH)