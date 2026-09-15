"""Score an event's choices from the effects the game prints on screen.

The event screen can show a "Choices" panel on the right listing every option
and exactly what it does. That removes the need to recognise the event at all,
which is what the outcome tables in `event_outcomes` exist to do - so this runs
ahead of them and covers scenario events, patched events and anything else the
tables have never seen.

Two ways the panel gets there, and the caller does not have to care which:

- Options > Career > "Always display choice effects" opens it automatically.
- Otherwise the "Effects" button on the event bubble opens it.

The wording matches the data files closely enough that `score_outcome` does the
generic lines. Three phrasings are only ever seen on screen and are handled
here:

    Branch 1 / Branch 2            alternative random results, so averaged
    Previously trained attribute   one stat, name not stated
    Random 2 attribute(s)          N stats, names not stated
"""
import re

from core import outings
from core.event_outcomes import STAT_KEYS, score_outcome, stat_weight
from utils.log import debug, warning

# A branch marker splits one option's result into alternatives the game picks
# between. Summing them would count an outcome that only sometimes happens, and
# on the injury event that meant counting "Become Practice Poor" as certain.
BRANCH_RE = re.compile(r"^branch\s*\d*$")

# "Previously trained attribute -10" and "Random 2 attribute(s) -10" name an
# amount but not which stat, so they are priced at the average of the user's
# stat weights times the number of stats affected.
UNNAMED_RE = re.compile(
  r"^(?:(previously\s+trained)|random\s*(\d+)|all)\s+attribute[a-z()]*\s*([+-])\s*(\d+)")

# Hints read as "<Skill Name> Hint Lvl +1" here, where the data files write
# something ending in "hint". The skill name in front means score_outcome sees
# a subject ending in "lvl" and prices the whole line at one point a level,
# against the 12 a hint level is actually worth. easyocr also reads "Lvl" as
# "Ivl" about half the time, so both spellings are accepted.
HINT_RE = re.compile(r"hint\s*[il]vl\s*([+-])\s*(\d+)")
HINT_POINTS = 12.0

# A cure carries no number, so the generic parser cannot see it at all. Worth
# roughly what the condition it removes was costing.
CURE_RE = re.compile(r"randomly\s+cures\s*(\d+)\s*bad\s+condition")
CURE_POINTS = 25.0

# "Unlock recreation with <name>" hands over a friend card's entire outing
# chain, and carries no number either, so it scored 0 and the option holding it
# lost to whatever raw stats the other one offered. Light Hello's unlock lost to
# a Wit +40 / Skill +40 option in six careers running (panel scores 94 vs 159),
# which is why a whole Grand Concert career took no outings at all.
UNLOCK_RE = re.compile(r"unlock\s+recreation(?:\s+with\s+(.+?))?\s*$")

# Mood and bond on score_outcome's scale, mirrored here the way HINT_POINTS
# already mirrors its hint weight.
MOOD_POINTS = 15.0
BOND_POINTS = 1.2

def unlock_value(card_name):
  """Points for unlocking a friend card's outing chain.

  Priced as the part of the chain that resting cannot give: mood, stats, hint
  levels, bond and cures, summed over every step.

  The chain's energy is deliberately left out, and it is most of the chain's
  raw worth - Light Hello's five steps carry about 200 of it. An outing is only
  ever taken in place of a rest, and should_recreate re-makes that comparison
  every turn with the real numbers, so counting the energy here would pay for
  it a second time and let an unlock outbid anything on the panel. What is left
  is the honest margin: the mood, stats and hints a rest would never have paid.
  """
  total = 0.0
  for step in outings.chain_steps(card_name):
    total += step.get("mood", 0.0) * MOOD_POINTS
    total += step.get("hints", 0.0) * HINT_POINTS
    total += step.get("bond", 0.0) * BOND_POINTS
    total += step.get("random_stats", 0.0) * unknown_stat_weight()
    for key, amount in (step.get("stats") or {}).items():
      total += amount * stat_weight(key)
    if step.get("heals"):
      total += CURE_POINTS
  return total

def unknown_stat_weight():
  """Mean weight across the five stats, for a gain that does not name one."""
  weights = [stat_weight(key) for key in sorted(set(STAT_KEYS.values()))]
  return sum(weights) / len(weights) if weights else 1.0

def clean(line):
  """Undo the OCR damage this panel reliably produces.

  easyocr splits the sign off a number about a third of the time and mangles
  "attribute(s)" into things like "attributels)". Neither is worth a smarter
  reader - the vocabulary is tiny and fixed.
  """
  text = line.strip().lower()
  text = re.sub(r"attribute[l|(][s)]+\)?", "attribute(s)", text)
  # "- 10" and "+ 10" -> "-10" / "+10", so the amount stays attached to its sign.
  text = re.sub(r"([+-])\s+(\d)", r"\1\2", text)
  return text

def score_line(line):
  """Points for one effect line. Returns (score, matched)."""
  text = clean(line)
  if not text:
    return 0.0, True

  hit = UNNAMED_RE.match(text)
  if hit:
    previously, count, sign, amount = hit.groups()
    stats = 1 if previously else (int(count) if count else 5)
    value = int(amount) * (-1 if sign == "-" else 1)
    return stats * value * unknown_stat_weight(), True

  hit = HINT_RE.search(text)
  if hit:
    sign, amount = hit.groups()
    levels = int(amount) * (-1 if sign == "-" else 1)
    return levels * HINT_POINTS, True

  hit = CURE_RE.search(text)
  if hit:
    return int(hit.group(1)) * CURE_POINTS, True

  hit = UNLOCK_RE.search(text)
  if hit:
    return unlock_value(hit.group(1)), True

  score = score_outcome(text)
  # score_outcome returns 0.0 both for "nothing here" and for a line it could
  # not parse, so report the difference rather than hiding a vocabulary gap.
  return score, score != 0.0

def split_branches(lines):
  """Group an option's lines into the alternatives the game chooses between."""
  branches = [[]]
  for line in lines:
    if BRANCH_RE.match(line.strip().lower()):
      if branches[-1]:
        branches.append([])
      continue
    branches[-1].append(line)
  return [b for b in branches if b]

def score_choice(lines):
  """Expected points for one option, averaging over its random branches."""
  branches = split_branches(lines)
  if not branches:
    return 0.0

  totals = []
  for branch in branches:
    total = 0.0
    for line in branch:
      value, matched = score_line(line)
      total += value
      if not matched:
        debug(f"Choices panel: no rule for {line!r}, scored 0.")
    totals.append(total)
  return sum(totals) / len(totals)

def best_choice(choices):
  """Best 1-based option from `read_choice_effects` output, or (0, reason).

  Returns 0 when the panel gave nothing to choose on, so the caller can fall
  back to the outcome tables instead of acting on an empty read.
  """
  if not choices:
    return 0, "no choices panel on screen"
  if len(choices) == 1:
    return 1, "only one option on the panel"

  scored = [(score_choice(lines), i + 1) for i, lines in enumerate(choices)]
  if all(not any(lines) for lines in choices):
    return 0, "panel had no effect lines"

  ranked = sorted(scored, key=lambda s: -s[0])
  detail = ", ".join(f"#{i}={s:.0f}" for s, i in scored)
  return ranked[0][1], detail
