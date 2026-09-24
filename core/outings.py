"""Predict what the next Recreation outing will actually give.

Friend-type supports - Tazuna, Riko Kashimoto, Aoi Kiryuin, Light Hello, Sasami
Anshinzawa - pay out through outings rather than through the training
facilities, and they do it as a fixed chain: step 1, then step 2, one step per
outing taken. The chain does not advance with the calendar, so there is nothing
to schedule. What the bot was missing is only which step comes next, which is
why every outing used to price the same when step 5 is worth several times
step 1:

    step 1   energy 30, mood +1, a few stats
    step 2   energy 29, and clears a negative condition
    step 4   energy 28, skill +14, and clears a negative condition
    step 5   energy 25, skill +14, and a hint level or three

`data/events/support_card.json` already carries the chains. A chain event is
prefixed with one chevron per step, so "Memories of Cinema" carrying three
chevrons is step 3.

Which card is in the deck is not known until one of its branching steps names
itself, so the depth is counted (one per outing taken) and the prediction is
averaged across the friend chains until a name pins it down. The averages differ
sharply by depth, which is the part that actually drives the decision.
"""
import json
import os
import re

from rapidfuzz import fuzz, process

from utils.log import debug, info, warning

EVENT_DATA = os.path.join("data", "events", "support_card.json")

# The chevron the data source prefixes chain events with, one per step.
CHEVRON = "❯"

# Friend-type support cards, by the character part of their slug. There is no
# type field in the data file and no numeric signature that separates them: a
# training card's chain can hand out as much Energy as a friend card's, so
# Manhattan Cafe's chain and Sasami's are indistinguishable by their contents.
# The game has five friend characters; add to this list if a sixth ships, and
# until then an unknown one simply falls back to the averaged prediction.
FRIEND_CARDS = (
  "tazuna-hayakawa",
  "aoi-kiryuin",
  "riko-kashimoto",
  "light-hello",
  "sasami-anshinzawa",
)

# Name match floor. Higher than core.event_outcomes uses for its own lookups,
# because a wrong match here moves the tracked chain position rather than just
# costing one event choice.
MATCH_THRESHOLD = 0.85

STAT_WORDS = {
  "speed": "spd", "stamina": "sta", "power": "pwr",
  "guts": "guts", "wit": "wit", "wisdom": "wit",
}

STAT_KEYS = ("spd", "sta", "pwr", "guts", "wit")

# There is deliberately no "plain recreation" profile here. The Recreation
# badge disappears once a friend card's chain is spent, and should_recreate is
# gated on the badge, so this module is never asked to price an outing that has
# no chain step behind it. A depth past the end of the chain therefore means the
# tracked position is wrong, not that the chain is finished - see next_outing.

_chains = None
_by_name = None
_by_depth = None
# Outings taken this career, and the card identified if one ever named itself.
_depth = 0
_card = None
# True once the Recreation panel has been read. A measured position beats a
# counted one: an outing that was started and then backed out of still moves
# the counter, and the panel is the only thing that says otherwise.
_measured = False
# (effects, label) of the outing just taken, waiting to be checked against
# what the game's Log says actually happened.
_pending = None


def _blank():
  return {"energy": 0.0, "mood": 0.0, "stats": {}, "random_stats": 0.0,
          "skill": 0.0, "bond": 0.0, "hints": 0.0, "heals": False, "range": {}}


def _amount(sign, first, second):
  """'+12' -> 12.0, '+5/+10' -> 7.5. The slash form is a variable outcome."""
  value = (int(first) + int(second)) / 2.0 if second else float(first)
  return -value if sign == "-" else value


def parse_effects(text):
  """Turn one outcome's text into the effects it grants.

  Random outcomes ("Randomly either ... or ...") are averaged over their
  variants rather than summed: the source lists every branch, and a branch that
  only sometimes happens is only sometimes worth its number.
  """
  variants, current = [], []
  for line in (text or "").replace("\r", "\n").split("\n"):
    line = line.strip()
    if not line or line.lower().startswith("randomly either"):
      continue
    if line.lower() == "or":
      if current:
        variants.append(current)
        current = []
      continue
    current.append(line)
  if current:
    variants.append(current)
  if not variants:
    return _blank()

  totals = []
  for lines in variants:
    eff = _blank()
    for line in lines:
      lowered = line.lower()
      if "negative status" in lowered:
        eff["heals"] = True
      # "2 random stats +10" is two different stats at +10 each.
      random_stat = re.match(r"(\d+)\s+random\s+stats?\s*\+\s*(\d+)", lowered)
      if random_stat:
        eff["random_stats"] += int(random_stat.group(1)) * int(random_stat.group(2))
        continue
      for m in re.finditer(r"([a-z' ]+?)\s*([+-])\s*(\d+)(?:\s*/\s*\+?(\d+))?", lowered):
        subject = m.group(1).strip()
        amount = _amount(m.group(2), m.group(3), m.group(4))
        if subject == "maximum energy":
          # Raises the ceiling rather than filling it, so it is not energy.
          continue
        if subject == "energy":
          eff["energy"] += amount
        elif subject == "mood":
          eff["mood"] += amount
        elif subject in STAT_WORDS:
          key = STAT_WORDS[subject]
          eff["stats"][key] = eff["stats"].get(key, 0.0) + amount
        elif subject == "all stats":
          for key in STAT_KEYS:
            eff["stats"][key] = eff["stats"].get(key, 0.0) + amount
        elif "skill point" in subject:
          eff["skill"] += amount
        elif subject.endswith("bond"):
          eff["bond"] += amount
        elif subject.endswith("hint"):
          eff["hints"] += amount
    totals.append(eff)

  return average(totals)


def average(effects_list):
  """Mean of several effect dicts, plus the spread it was taken over.

  `heals` is a flag, so it is OR'd rather than averaged. The spread matters as
  much as the mean: a step with a random roll gives one of its variants, not
  their average, so a readback that disagrees with the mean is only worth
  reporting when it falls outside the range as well.
  """
  out = _blank()
  if not effects_list:
    return out
  n = float(len(effects_list))
  spread = {}
  for eff in effects_list:
    for key in ("energy", "mood", "skill", "bond", "hints", "random_stats"):
      value = eff.get(key, 0.0)
      out[key] += value / n
      # An input that already carries a range contributes its whole range, so
      # averaging across cards keeps each card's own roll inside the result.
      lo, hi = (eff.get("range") or {}).get(key, (value, value))
      known = spread.get(key)
      spread[key] = (lo, hi) if known is None else (min(known[0], lo), max(known[1], hi))
    out["heals"] = out["heals"] or bool(eff.get("heals"))
    for stat, value in (eff.get("stats") or {}).items():
      out["stats"][stat] = out["stats"].get(stat, 0.0) + value / n
  out["range"] = spread
  return out


def _rough(eff):
  """Order one event's options against each other. Not the training scale."""
  return (eff["energy"] + eff["skill"] + eff["random_stats"]
          + sum(eff["stats"].values()) + eff["hints"] * 20.0 + eff["mood"] * 5.0
          + (25.0 if eff["heals"] else 0.0))


def _best_option(options):
  """Effects of the option the bot would actually take.

  Branching chain steps are answered by core.events, which picks the highest
  scoring option, so the prediction has to assume the same pick rather than
  whichever one the data file happens to list first.
  """
  parsed = [parse_effects(text) for text in options.values()]
  return max(parsed, key=_rough) if parsed else None


def _character(slug):
  """'30021-tazuna-hayakawa' -> 'tazuna-hayakawa', or None if not a friend."""
  for name in FRIEND_CARDS:
    if slug.endswith(name):
      return name
  return None


def load_chains(force=False):
  """{character: {depth: effects}} for each friend card's outing chain."""
  global _chains, _by_name, _by_depth
  if _chains is not None and not force:
    return _chains

  _chains, _by_name, _by_depth = {}, {}, {}
  try:
    with open(EVENT_DATA, "r", encoding="utf-8") as f:
      data = json.load(f)
  except (OSError, ValueError) as e:
    debug(f"No outing chain data ({e}); outings price as plain recreation.")
    return _chains

  pattern = re.compile(r"^\((" + CHEVRON + r"+)\)\s*(.+)$")
  raw = {}
  for entry in data:
    character = _character(entry.get("CardSlug") or "")
    if not character:
      continue
    match = pattern.match(entry.get("EventName") or "")
    if not match:
      continue
    depth = len(match.group(1))
    # Keyed by card, not just by character. The same character ships at several
    # rarities with the same chain but different numbers - Riko's step 5 gives
    # Energy +24 on one card and +30 on the other - and merging their option
    # dicts silently kept whichever the data file listed last. The readback
    # against the game's Log is what caught that.
    step = raw.setdefault(character, {}).setdefault(depth, {"name": match.group(2).strip(),
                                                            "cards": {}})
    step["cards"].setdefault(entry.get("CardSlug") or "", {}).update(
      entry.get("EventOptions") or {})

  for character, steps in raw.items():
    built = {}
    for depth, step in steps.items():
      per_card = [e for e in (_best_option(o) for o in step["cards"].values()) if e]
      if not per_card:
        continue
      # The panel names the character but not which card it is, so the estimate
      # spans every version: the mean to score against, the spread to judge a
      # readback by.
      effects = per_card[0] if len(per_card) == 1 else average(per_card)
      effects["name"] = step["name"]
      effects["depth"] = depth
      built[depth] = effects
      _by_name[step["name"]] = (character, depth)
    if built:
      _chains[character] = built

  longest = max((max(v) for v in _chains.values()), default=0)
  for depth in range(1, longest + 1):
    steps = [v[depth] for v in _chains.values() if depth in v]
    if steps:
      _by_depth[depth] = average(steps)

  debug(f"Loaded {len(_chains)} friend outing chains covering {len(_by_name)} events.")
  return _chains


def display_name(character):
  """'riko-kashimoto' -> 'Riko Kashimoto', as the Recreation panel prints it."""
  return character.replace("-", " ").title()

def reset():
  """Forget the tracked position. Called when a career starts."""
  global _depth, _card, _measured, _pending
  _depth, _card, _measured, _pending = 0, None, False, None

def measured():
  """Whether the position came off the Recreation panel rather than a count."""
  return _measured

def _match_card(card_name):
  """The chain owner an OCR'd panel name refers to, or None.

  Loose, because the name is OCR'd, but above MATCH_THRESHOLD: a wrong match
  moves the tracked position rather than costing one event choice.
  """
  if not card_name:
    return None
  hit = process.extractOne(card_name, [display_name(c) for c in _chains],
                           scorer=fuzz.token_sort_ratio)
  if hit and hit[1] / 100.0 >= MATCH_THRESHOLD:
    return next(c for c in _chains if display_name(c) == hit[0])
  return None


def set_complete(card_name):
  """Record that the panel says the chain is spent - every step is done.

  "Event Complete!" is not a step count, so it cannot come through
  set_position: the chevrons are gone by then and that reads as zero steps
  done, which is the wrong end of the chain.
  """
  global _card, _depth, _measured
  load_chains()
  character = _match_card(card_name)
  steps = len(_chains[character]) if character in _chains else (max(_by_depth) if _by_depth else 0)
  if character is not None:
    _card = character
  if not _measured or _depth != steps:
    info(f"Recreation panel: {character or 'the friend chain'} is complete"
         f" at {steps} steps; counter said {_depth}.")
  _depth, _measured = steps, True
  return _card, steps


def set_position(card_name, filled):
  """Record the chain position read off the Recreation panel.

  The panel states both facts outright - which friend card is in the deck,
  and how many of its Event Progress chevrons are filled - so this overrides
  both the counter and anything inferred from an event name. `card_name` is
  OCR'd, so it is matched loosely; a name that matches nothing is ignored
  rather than guessed at.
  """
  global _card, _depth, _measured
  load_chains()
  if filled is None or filled < 0:
    return None
  character = _match_card(card_name)
  if character is None:
    if _card is not None:
      # A name that will not match means the frame was not the chooser - the
      # confirmation dialog covers the row, and its chevron count reads zero.
      # Overwriting a known position with that would walk the chain backwards.
      debug(f"Ignoring a Recreation read: card name {card_name!r} does not match"
            f" the tracked {_card}.")
      return None
    # Nothing tracked yet, so the step count alone is still worth having: depth
    # drives the decision and the prediction falls back to the friend average.
    debug(f"Recreation panel: {filled} steps done, card name {card_name!r} unrecognised.")
    _depth, _measured = filled, True
    return None
  if filled != _depth or character != _card or not _measured:
    info(f"Recreation panel: {character} at step {filled}"
         + (f" of {len(_chains[character])}" if character in _chains else "")
         + (f"; counter said {_depth}." if filled != _depth else "."))
  _card, _depth, _measured = character, filled, True
  return _card, filled


def advance():
  """Count an outing, for when the Recreation panel could not be read.

  Less trustworthy than set_position: an outing that was opened and then
  abandoned still lands here, and the count cannot say which card it was.
  """
  global _depth
  _depth += 1
  debug(f"Outing taken; chain depth now {_depth}"
        + (f" on {_card}." if _card else " (card not identified yet)."))


def note_event(event_name):
  """Pin the chain position exactly if this event names a known chain step.

  Only branching steps put choices on screen, so most steps go past without a
  readable name and the counter carries the position. When one is readable it
  overrides the counter, which is also how a restart mid-career resyncs.
  """
  global _depth, _card
  load_chains()
  if not event_name or not _by_name:
    return None
  hit = process.extractOne(event_name, _by_name.keys(), scorer=fuzz.token_sort_ratio)
  if not hit or hit[1] / 100.0 < MATCH_THRESHOLD:
    return None
  character, depth = _by_name[hit[0]]
  if character != _card or depth != _depth:
    info(f"Outing chain: {character} at step {depth} of {len(_chains[character])}"
         f" ({hit[0]!r}); counter said {_depth}.")
  _card, _depth = character, depth
  return character, depth


def chain_steps(card_name=None):
  """Every step of one friend's chain, for pricing the chain as a whole.

  `card_name` comes off the Choices panel through OCR, so it is matched as
  loosely as set_position matches it. An unrecognised name falls back to the
  average across the five friends rather than to nothing: the unlock is worth
  having whoever is in the deck, and the averages are what next_outing would
  price it at anyway.
  """
  load_chains()
  if card_name:
    hit = process.extractOne(card_name, [display_name(c) for c in _chains],
                             scorer=fuzz.token_sort_ratio)
    if hit and hit[1] / 100.0 >= MATCH_THRESHOLD:
      character = next(c for c in _chains if display_name(c) == hit[0])
      return [_chains[character][depth] for depth in sorted(_chains[character])]
  return [_by_depth[depth] for depth in sorted(_by_depth)]


def steps_remaining():
  """Steps left in the chain, or None while the card is unidentified."""
  load_chains()
  if _card and _card in _chains:
    return max(0, len(_chains[_card]) - _depth)
  return None


def next_outing():
  """(effects, label) for the outing the bot would take now.

  Only meaningful while the Recreation badge is up, which is the caller's job to
  check. The badge goes away when the chain is spent, so being asked at all
  means a step is on offer.

  That makes a depth past the end of the chain a tracking error rather than a
  finished chain - a mis-read panel, or a counted outing that was abandoned. The
  answer is to clamp to the last step we know about and say so, not to price the
  outing as a karaoke session: under-valuing it would quietly stop the bot
  taking outings at all, and the badge is telling us one is there.
  """
  load_chains()
  depth = _depth + 1

  if _card and _card in _chains:
    chain = _chains[_card]
    step = chain.get(depth)
    if step:
      return step, f"{_card} step {depth}/{len(chain)}"
    last = max(chain)
    warning(f"Outing offered but {_card} is tracked at step {_depth} of {len(chain)};"
            f" the position is wrong. Pricing it as step {last}.")
    return chain[last], f"{_card} position uncertain, priced as step {last}"

  step = _by_depth.get(depth)
  if step:
    return dict(step, stats=dict(step["stats"])), f"step {depth}, averaged over friend cards"
  last = max(_by_depth) if _by_depth else None
  if last is None:
    return _blank(), "no chain data"
  warning(f"Outing offered but the chain is tracked at step {_depth}, past every"
          f" known chain. Pricing it as step {last}.")
  fallback = _by_depth[last]
  return dict(fallback, stats=dict(fallback["stats"])), f"position uncertain, priced as step {last}"

# How the Log phrases an outcome. Nothing here is guessed: every pattern below
# is anchored on wording seen in a real entry, and a line that matches none of
# them is ignored rather than parsed loosely. OCR mangles the punctuation
# ("level(s)" reads as "levells)", "Gale!" as "Galel"), so the patterns anchor
# on the words around the number and never on the trailing character.
LOG_PATTERNS = [
  ("energy",  r"energy\s+recovered\s+by\s+(\d+)",                        1),
  ("energy",  r"energy\s+(?:dropped|decreased|went\s+down)\s+by\s+(\d+)", -1),
  ("skill",   r"(?:gained|earned)\s+(\d+)\s+skill\s+p",                  1),
  ("skill",   r"skill\s+p\w*\s+went\s+up\s+by\s+(\d+)",               1),
  ("hints",   r"gained\s+(\d+)\s+hint\s+level",                          1),
  ("bond",    r"friendship\s+with\s+.*?\s+went\s+up\s+by\s+(\d+)",    1),
]
STAT_UP = r"(speed|stamina|power|guts|wit|wisdom)\s+went\s+(up|down)\s+by\s+(\d+)"

def parse_log_effects(lines):
  """Effects the Log says actually happened, in the same shape as a prediction.

  Only the newest run of outcome lines is used. The Log keeps a scrollback, so
  taking every effect line on screen would add up several turns of results.
  """
  hits = []
  for index, line in enumerate(lines or []):
    text = (line or "").lower()
    eff = _blank()
    matched = False

    eff["seen"] = set()

    stat = re.search(STAT_UP, text)
    if stat:
      key = STAT_WORDS[stat.group(1)]
      amount = float(stat.group(3)) * (1 if stat.group(2) == "up" else -1)
      eff["stats"][key] = amount
      matched = True

    for field, pattern, sign in LOG_PATTERNS:
      found = re.search(pattern, text)
      if found:
        eff[field] += float(found.group(1)) * sign
        eff["seen"].add(field)
        matched = True

    if "mood" in text:
      # "Mood remains Great" is a real outcome line and means no change, so it
      # counts as part of the block even though it adds nothing.
      if re.search(r"went\s+up|improved|rose", text):
        eff["mood"] += 1.0
        eff["seen"].add("mood")
      elif re.search(r"went\s+down|dropped|worsened", text):
        eff["mood"] -= 1.0
        eff["seen"].add("mood")
      matched = matched or bool(re.search(r"remains|went|improved|rose|dropped", text))

    if re.search(r"recovered\s+from|was\s+healed|no\s+longer", text):
      eff["heals"] = True
      matched = True

    # A maxed friendship is the bond line for a card already at the ceiling.
    if re.search(r"friendship\s+with\s+.*?\s+is\s+maxed", text):
      matched = True

    if matched:
      hits.append((index, eff))

  if not hits:
    return None

  # Keep only the last run. A gap of one line is tolerated because the OCR
  # splits a wrapped sentence ("...is maxed" / "out") across two boxes.
  block = [hits[-1]]
  for index, eff in reversed(hits[:-1]):
    if block[0][0] - index <= 2:
      block.insert(0, (index, eff))
    else:
      break

  total = _blank()
  # Which fields the Log actually spoke about. A field it never mentioned is
  # unknown, not zero - the Log prints an "Energy recovered by" line only
  # when energy moved, and treating its absence as a real zero reported a
  # correct prediction as wrong on the first live outing.
  total["seen"] = set()
  for _, eff in block:
    for key in ("energy", "mood", "skill", "bond", "hints", "random_stats"):
      total[key] += eff[key]
      if eff.get("seen") and key in eff["seen"]:
        total["seen"].add(key)
    total["heals"] = total["heals"] or eff["heals"]
    if eff["heals"]:
      total["seen"].add("heals")
    for stat, amount in eff["stats"].items():
      total["stats"][stat] = total["stats"].get(stat, 0.0) + amount
  return total

def expect_readback(effects, label, energy_before=None, energy_headroom=None):
  """Remember what an outing was predicted to give, for confirm_outing.

  `energy_before` is the energy bar reading taken just before going out.
  The bar is a pixel measurement the bot already makes every turn, and it
  is far more dependable than finding the right block of the Log, so it is
  what the energy prediction is actually judged against.

  `energy_headroom` is how much the bar could still rise. Energy that would
  spill past the cap is never seen, so an outing at 77 that grants 24 shows
  as +23 and one at 90 granting 30 shows as +10 - neither is a bad
  prediction, and without this the second would be reported as one.
  """
  global _pending
  _pending = (effects, label, energy_before, energy_headroom)

def pending_readback():
  return _pending is not None

def confirm_outing(lines, energy_after=None):
  """Check the Log against what the last outing was predicted to give.

  This does not change any decision - the turn is already spent - but it is the
  only evidence that the chain data, the tracked position and the scoring
  constants describe the game rather than a plausible story about it. Mismatches
  are logged loudly because a silent one means every later prediction is wrong
  in the same way.
  """
  global _pending
  if _pending is None:
    return None
  predicted, label, energy_before, energy_headroom = _pending
  _pending = None

  # Parsed for the record only. Picking "the newest block" of the Log is not
  # dependable: it has come back with the tail of a dialogue once and with a
  # goal-selection event ("Skill Pts went up by 30") another time, neither of
  # them the outing. Comparing against that produced confident nonsense, so the
  # Log is now written to the log and nothing more.
  parsed = parse_log_effects(lines)
  debug(f"Log said: {parsed}")

  # Energy is the one field with a trustworthy measurement behind it - the bar
  # is counted in pixels, not read as text - and it is also what separates one
  # chain step from another, so it is the whole comparison.
  actual = _blank()
  usable = (energy_before is not None and energy_after is not None
            and energy_before >= 0 and energy_after >= 0)
  if not usable:
    # The Recreation panel covers the energy bar, so the reading taken as the
    # outing starts can come back as -1. Treating that as a number turned a
    # 30-energy step into a claimed 66.
    debug(f"No usable energy reading to check {label} against.")
    return None
  actual["energy"] = float(energy_after) - float(energy_before)
  seen = {"energy"}

  spread = predicted.get("range") or {}
  parts = []
  want = predicted.get("energy", 0.0)
  lo, hi = spread.get("energy", (want, want))
  if energy_headroom is not None and energy_headroom >= 0:
    # Only what fits under the cap can show on the bar.
    lo, hi = min(lo, energy_headroom), min(hi, energy_headroom)
  got = actual["energy"]
  # The bar is a pixel estimate, so allow it a little slack.
  if not (lo - 3.0 <= got <= hi + 3.0):
    span = f"{lo:.0f}" if lo == hi else f"{lo:.0f}-{hi:.0f}"
    parts.append(f"energy should have been {span}, the bar moved {got:.0f}")

  # Mood is deliberately left out. It caps at GREAT, and a run sits there most
  # of the time, so "predicted +1, log says it stayed put" is the normal case
  # rather than a fault.

  if parts:
    warning(f"Outing readback for {label}: " + "; ".join(parts) + ".")
  else:
    info(f"Outing readback for {label} is consistent with the prediction.")
  return actual
