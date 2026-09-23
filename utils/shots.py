"""Keeping shots/ from growing without bound.

The automated captures are written constantly - `umatool click` saves one on
every press, and `health` one on every check, including every `/health` sent
from a phone. Left alone they reached 1,062 files and about a gigabyte, which
is what prompted this.

They are also the *least* valuable frames in there: each one is a moment that
has already passed, and what anybody actually looks at is the last few. The
hand-named investigation frames under shots/gl/ are the opposite - they are
referenced by name from docs/screen-map.md and were the source of two templates
this week - so nothing here ever touches a subdirectory or a name that does not
end in the timestamp these tools write.
"""
import os
import re

# The newest this many of each prefix survive. Thirty is about 35MB a prefix and
# comfortably more than one debugging session looks back through: today's
# longest burst was twenty clicks.
KEEP = 30

# `type_174924.png` and nothing else. Anchored at both ends on purpose: a
# `click_notes.png` somebody saved by hand is not one of these, and neither is
# anything in a subdirectory.
STAMPED = r"^%s\d{6}\.png$"

def prune(directory, prefix, keep=KEEP):
  """Delete all but the newest `keep` `<prefix>NNNNNN.png` in `directory`.

  Returns how many were removed. Never raises: this runs after a capture has
  already been saved, and failing to tidy up must not fail the capture, the
  health check, or the click that prompted it.
  """
  try:
    pattern = re.compile(STAMPED % re.escape(prefix))
    found = []
    with os.scandir(directory) as entries:
      for entry in entries:
        if entry.is_file() and pattern.match(entry.name):
          found.append((entry.stat().st_mtime, entry.path))
    if len(found) <= keep:
      return 0
    found.sort(reverse=True)
    removed = 0
    for _, path in found[keep:]:
      try:
        os.remove(path)
        removed += 1
      except OSError:
        pass
    return removed
  except Exception:
    return 0
