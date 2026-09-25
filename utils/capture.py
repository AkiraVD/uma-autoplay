"""Keeping the frames a new reader has to be built from.

Set `UMA_CAPTURE_DIR` to a directory and the bot writes one PNG per interesting
moment into it. Unset - the normal case - every call is a single truthiness
test.

It exists for the same reason `UMA_TURN_DEBUG` does (`core/state.py`): a watcher
that greps the log and then grabs the screen arrives three steps late, because
the bot reads, decides and moves on inside a second. The only place a reader's
real input exists is at the call site that had it.

Two rules that are not obvious from the name:

- **It never takes its own screenshot.** Every call site already holds a frame.
  Grabbing a second one here would put a capture on the hot path for a flag
  that is off almost always.
- **It stops rather than prunes.** `utils/shots.py` keeps the newest N because
  those frames are moments that have already passed. These are the opposite:
  a set somebody is deliberately collecting, where the tenth is worth as much
  as the sixtieth. So there is a per-tag cap and then it stops, because this is
  a flag people leave on - the automated captures reached 1,062 files and about
  a gigabyte before anything limited them.

Nothing here raises. A capture failing must never cost a turn.
"""
import os
import time

from utils.log import info, debug

# The directory to write into, or "" for off. Read once at import, like
# TURN_DEBUG_DIR, so turning it on means restarting the bot.
DIR = os.environ.get("UMA_CAPTURE_DIR") or ""

# Frames per tag before this stops keeping them. Sixty is more than one career
# produces of any single kind, and about 90MB at 1920x1080.
LIMIT = 60

_counts = {}
_stopped = set()


def enabled():
  """Whether anything is being captured. Call sites use this to decide whether
  a frame is even worth grabbing."""
  return bool(DIR)


def keep(screen, tag):
  """Save `screen` as `<DIR>/<tag>_NNN_HHMMSS.png`. Returns the path, or None.

  `screen` is a PIL Image the caller already holds - this never grabs one. The
  counter leads the timestamp so the files sort in the order they were taken
  even when two land in the same second.
  """
  if not DIR or screen is None or tag in _stopped:
    return None
  try:
    count = _counts.get(tag, 0)
    if count >= LIMIT:
      _stopped.add(tag)
      info(f"capture: kept {LIMIT} '{tag}' frames in {DIR}, which is the cap. No more of this kind.")
      return None
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, f"{tag}_{count:03d}_{time.strftime('%H%M%S')}.png")
    screen.save(path)
    _counts[tag] = count + 1
    debug(f"capture: kept {path}")
    return path
  except Exception as e:
    debug(f"capture: could not keep a '{tag}' frame ({e}).")
    return None
