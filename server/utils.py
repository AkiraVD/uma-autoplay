import hashlib
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

def load_config() -> dict:
  if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
      return json.load(f)
  return {}

def config_version() -> str:
  """What a page must send back to prove its edit is based on the current file.

  The page posts the whole document, so a tab left open on an hour-old config
  silently reverts every setting changed since - which is how a Maruzensky
  config came back over a Mihono Bourbon one on 2026-09-24. A write carries the
  version it read, and one based on anything else is refused rather than
  applied.

  The fingerprint is of the contents, not the timestamp: two writes a few
  milliseconds apart share an mtime even on ext4, and that is exactly the gap
  a second page writes into.
  """
  try:
    return hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()[:16]
  except OSError:
    return "0"

def save_config(data: dict):
  # Written to a temporary file and moved into place: the page applies every
  # edit as it is made, so a write can land at the moment core/state.py reads
  # the file, and half a config.json is worse than an old one.
  tmp = CONFIG_PATH.with_suffix(".json.tmp")
  with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
  tmp.replace(CONFIG_PATH)