"""Character and support card pictures for the config page's event pickers.

The game's own pictures sit in encrypted asset bundles, so these come from
GameTora, keyed by the same ids master.mdb uses. Each is fetched once and kept
under cache/images, so the page makes no outside request after the first view
and keeps working offline.
"""
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from utils.log import warning

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache" / "images"

SOURCES = {
  "chara": "https://gametora.com/images/umamusume/characters/icons/chr_icon_{id}.png",
  "support": "https://gametora.com/images/umamusume/supports/support_card_s_{id}.png",
  # Per *card*, not per character: the Trainee picker's whole job is telling
  # [Dot-o'-Lantern] Meisho Doto from [Turbulent Blue], and those share a chara
  # id. So this one's item_id is "<chara_id>_<card_id>" - chr_icon_<card_id>
  # is a 404, only the chara id has an icon.
  "trainee": "https://gametora.com/images/umamusume/characters/thumb/chara_stand_{id}.png",
}

# item_id reaches the filesystem as a filename, so it is digits and underscores
# or it is nothing.
ID_PATTERN = re.compile(r"^\d{1,10}(_\d{1,10})?$")

# Ids GameTora didn't have, so a missing picture isn't asked for again on every view.
_missing = set()


def image_path(kind, item_id):
  """Local file for a picture, fetched on first use. None if there isn't one."""
  if kind not in SOURCES or not ID_PATTERN.match(str(item_id)):
    return None
  path = CACHE_DIR / kind / f"{item_id}.png"
  if path.exists():
    return path
  if (kind, item_id) in _missing:
    return None

  request = urllib.request.Request(SOURCES[kind].format(id=item_id), headers={"User-Agent": "Mozilla/5.0"})
  try:
    with urllib.request.urlopen(request, timeout=10) as response:
      if response.headers.get_content_type() != "image/png":
        raise ValueError(f"not a PNG: {response.headers.get_content_type()}")
      data = response.read()
  except urllib.error.HTTPError as e:
    if e.code == 404:
      _missing.add((kind, item_id))
    else:
      warning(f"IMG-FETCH-HTTP: {kind} {item_id}: HTTP {e.code}")
    return None
  except (urllib.error.URLError, TimeoutError, ValueError) as e:
    # Offline or refused: try again next time rather than remembering it as missing.
    warning(f"IMG-FETCH-NET: {kind} {item_id}: {e}")
    return None

  path.parent.mkdir(parents=True, exist_ok=True)
  # Written aside and renamed, so a half-written file is never served.
  tmp = path.with_suffix(f".{os.getpid()}.tmp")
  tmp.write_bytes(data)
  os.replace(tmp, path)
  return path
