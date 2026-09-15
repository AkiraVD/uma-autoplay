from rapidfuzz import fuzz, process

from utils.log import debug, info, warning

import json
import os
import re

import core.state as state

# Event outcomes are not readable from the screen - the event screen's "Effects"
# button does not reveal them - so a choice has to be scored against a lookup
# table of known outcomes. Files use the shape:
#   uma_data.json     : [ {UmaName, UmaEvents: [ {EventName, EventOptions} ]} ]
#   support_card.json : [ {EventName, EventOptions, CardSlug} ]
# where EventOptions maps an option label to its outcome text.
EVENT_DATA_DIR = "data/events"

# Option labels in the order they appear on screen. "Bottom Option" is resolved
# last because its index depends on how many options the event actually has.
ORDERED_LABELS = ["Top Option", "Middle Option", "Bottom Option"]

_OUTCOMES = None

STAT_KEYS = {
  "speed": "spd", "stamina": "sta", "power": "pwr",
  "guts": "guts", "wit": "wit", "wisdom": "wit",
}

# Named conditions, worth more or less than any stats attached to them.
GOOD_CONDITIONS = {
  "practice perfect": 40, "charming": 30, "fast learner": 30,
  "hot topic": 15, "shining brightly": 20,
}
BAD_CONDITIONS = {
  "practice poor": -60, "slacker": -50, "slow metabolism": -40,
  "gatekept": -30, "migraine": -30, "night owl": -25,
  "event chain ended": -35, "skin outbreak": -20, "under the weather": -40,
}

def load_outcomes(force=False):
  """Load and index the outcome tables. Returns {event_name: {label: text}}."""
  global _OUTCOMES
  if _OUTCOMES is not None and not force:
    return _OUTCOMES

  table = {}
  if not os.path.isdir(EVENT_DATA_DIR):
    debug(f"No {EVENT_DATA_DIR} directory, event outcome scoring is disabled.")
    _OUTCOMES = table
    return table

  for fname in sorted(os.listdir(EVENT_DATA_DIR)):
    if not fname.endswith(".json"):
      continue
    path = os.path.join(EVENT_DATA_DIR, fname)
    try:
      with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    except (OSError, ValueError) as e:
      warning(f"Couldn't read event outcomes from {path}: {e}")
      continue

    for record in data if isinstance(data, list) else []:
      # A per-uma record nests its events; a support-card record is one event.
      events = record.get("UmaEvents") if "UmaEvents" in record else [record]
      for event in events or []:
        name = event.get("EventName")
        options = event.get("EventOptions")
        if not name or not options:
          continue
        # Each option is a separate record sharing the EventName, so merge them.
        # First text wins per label, so a same-named event on a different uma or
        # support card cannot clobber one already loaded.
        entry = table.setdefault(name, {})
        for label, text in options.items():
          entry.setdefault(label, text)

  info(f"Loaded {len(table)} event outcomes from {EVENT_DATA_DIR}.")
  _OUTCOMES = table
  return table

def stat_weight(stat_key):
  """Weight a stat gain by where the user ranked it, so +10 in the top priority
  stat beats +10 in one they do not care about."""
  try:
    index = state.PRIORITY_STAT.index(stat_key)
  except (AttributeError, ValueError):
    return 1.0
  return 1.0 + (len(state.PRIORITY_STAT) - index) * 0.15

def score_outcome(text):
  """Score one option's outcome text. Higher is better."""
  if not text:
    return 0.0

  lowered = text.lower().replace("\r", "\n")
  score = 0.0

  # Conditions are named states rather than numbers, so match them separately.
  for name, value in GOOD_CONDITIONS.items():
    if name in lowered:
      score += value
  for name, value in BAD_CONDITIONS.items():
    if name in lowered:
      score += value

  for line in lowered.split("\n"):
    line = line.strip()
    if not line:
      continue
    # A random outcome is only sometimes what the text says it is.
    weight = 0.5 if line.startswith("(random)") else 1.0

    for match in re.finditer(r"([a-z' ]+?)\s*([+-])\s*(\d+)", line):
      subject = match.group(1).strip()
      amount = int(match.group(3))
      if match.group(2) == "-":
        amount = -amount

      if subject in STAT_KEYS:
        score += amount * stat_weight(STAT_KEYS[subject]) * weight
      elif subject.endswith("bond"):
        score += amount * 1.2 * weight
      elif subject.endswith("hint"):
        score += amount * 12.0 * weight
      elif "skill point" in subject:
        score += amount * 1.5 * weight
      elif subject == "energy":
        score += amount * 2.0 * weight
      elif subject == "mood":
        score += amount * 15.0 * weight
      elif "stat" in subject:
        score += amount * 4.0 * weight
      else:
        score += amount * weight

  return score

def option_index(label, labels_present):
  """Map an option label to the 1-based position it occupies on screen."""
  match = re.match(r"option\s*(\d+)", label.strip().lower())
  if match:
    return int(match.group(1))
  if not label.strip():
    return 1
  ordered = [l for l in ORDERED_LABELS if l in labels_present]
  if label in ordered:
    return ordered.index(label) + 1
  return 1

def match_event(event_name, threshold=0.75):
  """Fuzzy-match an OCR'd event name against the outcome table."""
  outcomes = load_outcomes()
  if not event_name or not outcomes:
    return None, 0.0
  # token_sort_ratio to match events.py, so a reordered read like
  # "Diligent Effort A" still lands on "A Diligent Effort".
  hit = process.extractOne(event_name, outcomes.keys(), scorer=fuzz.token_sort_ratio)
  if not hit:
    return None, 0.0
  name, score = hit[0], hit[1] / 100
  return (name, score) if score >= threshold else (None, score)

def best_option(event_name):
  """Best 1-based choice for `event_name`, or (0, reason) when unknown."""
  outcomes = load_outcomes()
  matched, similarity = match_event(event_name)
  if not matched:
    return 0, f"no outcome table entry (best {similarity * 100:.0f}%)"
  options = outcomes.get(matched)
  if not options:
    return 0, "not in outcome table"

  # A blank label is not a selectable option - it is the descriptive summary the
  # source attaches to events whose result is conditional rather than chosen.
  options = {k: v for k, v in options.items() if k.strip()}
  if len(options) <= 1:
    return 1, f"{matched!r}: single outcome"

  scored = []
  for label, text in options.items():
    scored.append((score_outcome(text), option_index(label, list(options.keys())), label))
  scored.sort(key=lambda s: -s[0])

  detail = ", ".join(f"{s[2]}={s[0]:.0f}" for s in scored)
  return scored[0][1], f"{matched!r} ({similarity * 100:.0f}%): {detail}"
