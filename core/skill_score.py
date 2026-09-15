"""Decide which skills to buy, by how reliably they will fire in Team Trials.

A career exists to produce an Uma for Team Trials, and Team Trials scores a
skill for **activating**, not for what it does - a gold activation is worth 12
SV and a white one 5, whatever the skill actually grants. Career races are
winnable without skills. So the objective is not "which skill makes this Uma
faster", it is "which skills will fire, per skill point spent".

That makes the shape of the problem: filter to skills that can fire for this
Uma at all, score the rest on how reliably their condition is met, divide by
cost, and fill the budget.

The condition scoring is ported from the public optimizer at
https://daftuyda.moe/optimizer (js/skill-scorer.js and
js/team-trials-optimizer.js), which works the same way. Two things are done
differently here because master.mdb gives us better inputs than a web page has:

- gold/white comes from `skill_data.rarity` (1 white, 2 gold) rather than being
  guessed from "cost >= 170";
- costs are `single_mode_skill_need_point.need_skill_point`, the real career
  price, rather than a scraped table.

Everything here is pure: it takes skill records and returns a decision, so it
is testable without the game running.
"""
import re

from utils.log import debug

# The optimizer's weights. Consistency dominates because an unreliable skill
# scores nothing in Team Trials no matter how cheap it was.
CONSISTENCY_WEIGHT = 0.6
COST_WEIGHT = 0.4

# Skill Value per activation: what Team Trials pays out.
GOLD_SV = 12
WHITE_SV = 5
GOLD_RARITY = 2

# A "perfect" ratio is 12 SV for 120 SP.
IDEAL_SV_PER_SP = 0.1

# A passive ("green") skill has no duration - it is either on for the whole race
# or not at all. Many are gated on the venue, the going or the time of day, none
# of which is known when the skill is bought and none of which Team Trials lets
# you pick. A green like "Fukushima Racecourse ○" pays out only when the draw
# happens to send you there, so it is worth a fraction of a skill that fires on
# every course.
#
# Without this the planner spends the whole budget on them: they are cheap and
# their conditions are trivially satisfiable on paper, so consistency-times-cost
# rates them top. The first clean run bought eleven racecourse greens.
PASSIVE_ABILITY_TIMES = (-1, 0)
VOLATILE_CONDITION = re.compile(
  r"(track_id|ground_condition|weather|season|rotation|post_number|time)\s*(==|!=|>=|<=|>|<)")
GREEN_PASSIVE_PENALTY = 0.2

RUNNING_STYLES = {"front": 1, "pace": 2, "late": 3, "end": 4}
DISTANCE_TYPES = {"sprint": 1, "mile": 2, "medium": 3, "long": 4}
GROUND_TYPES = {"turf": 1, "dirt": 2}

def clamp(value, low, high):
  return max(low, min(high, value))

def condition_groups(skill):
  """The skill's condition blocks, each as one string.

  master.mdb splits a skill into up to two effect blocks, each with its own
  precondition (a gate that had to be true earlier) and condition. The
  optimizer treats the pair as one text, so this does too.
  """
  groups = []
  for cond, pre in (("condition", "precondition"), ("condition_2", "precondition_2")):
    text = " & ".join(p for p in ((skill.get(cond) or "").strip(),
                                  (skill.get(pre) or "").strip()) if p)
    if text:
      groups.append(text.lower())
  return groups

def range_coverage(text, key, max_value):
  """How much of `key`'s range the condition allows, 0..1, or None if unbounded.

  A condition that fires anywhere in the field is worth more than one that
  needs a specific position, and this is what measures the difference.
  """
  low, high, seen = 1, max_value, False
  for pattern, apply in (
      (r"==\s*(-?\d+)", lambda v: (v, v)),
      (r">=\s*(-?\d+)", lambda v: (max(low, v), high)),
      (r">\s*(-?\d+)", lambda v: (max(low, v + 1), high)),
      (r"<=\s*(-?\d+)", lambda v: (low, min(high, v))),
      (r"<\s*(-?\d+)", lambda v: (low, min(high, v - 1)))):
    match = re.search(key + r"\s*" + pattern, text)
    if match:
      low, high = apply(int(match.group(1)))
      seen = True
  if not seen:
    return None
  if high < low:
    return 0.0
  return clamp((high - low + 1) / max_value, 0.0, 1.0)

def comparator_count(text):
  return len(re.findall(r"==|>=|<=|>|<", text))

def timing_score(text):
  """When in the race it can fire. Something that can fire at any time is best."""
  if not text:
    return 0.62
  if re.search(r"always\s*==\s*1", text):
    return 0.98
  if re.search(r"is_lastspurt|is_finalcorner|is_last_straight", text):
    return 0.76 if "_random" in text else 0.88
  if re.search(r"phase_random|phase_[a-z_]*random|corner_random|straight_random"
               r"|distance_rate_after_random", text):
    return 0.62
  if re.search(r"phase\s*==\s*[1234]", text):
    return 0.76
  if "distance_rate" in text:
    coverage = range_coverage(text, "distance_rate", 100)
    return 0.82 if coverage is not None and coverage <= 0.2 else 0.72
  if "corner" in text:
    return 0.75
  return 0.68

def breadth_score(text):
  """How much of the possible race state satisfies it."""
  if not text:
    return 0.65
  parts = [c for c in (range_coverage(text, "order", 18),
                       range_coverage(text, "order_rate", 100),
                       range_coverage(text, "distance_rate", 100)) if c is not None]
  near = re.search(r"near_count\s*>=\s*(\d+)", text)
  if near:
    parts.append(clamp((10 - int(near.group(1)) + 1) / 10, 0.1, 1.0))

  if parts:
    breadth = sum(parts) / len(parts)
  else:
    breadth = 0.96 if re.search(r"always\s*==\s*1", text) else 0.72

  # Having to be in the lead is the narrowest requirement there is.
  if re.search(r"order\s*==\s*1", text):
    breadth = min(breadth, 0.18)
  if re.search(r"order\s*<=\s*5", text):
    breadth = max(breadth, 0.52)

  comparators = comparator_count(text)
  if comparators >= 4:
    breadth -= min(0.2, (comparators - 3) * 0.05)
  return clamp(breadth, 0.05, 1.0)

# Conditions that depend on what other runners do, which nothing can plan for.
SCENARIO_PENALTIES = [
  (r"blocked_side_continuetime|blocked_front_continuetime|blocked_front", 0.22),
  (r"is_surrounded|temptation_count|is_temptation", 0.20),
  (r"is_overtake", 0.18),
  (r"order\s*==\s*1", 0.16),
  (r"change_order_onetime|change_order_up_end_after|change_order_up_middle", 0.14),
  (r"popularity|post_number", 0.12),
  (r"is_move_lane", 0.10),
  (r"is_activate_other_skill_detail|is_activate_any_skill|activate_count_", 0.09),
  (r"near_count\s*>=\s*[34]", 0.09),
]

def scenario_score(text):
  """How much of the condition is outside the trainee's control."""
  if not text:
    return 0.7
  score = 0.95
  for pattern, penalty in SCENARIO_PENALTIES:
    if re.search(pattern, text):
      score -= penalty
  if re.search(r"always\s*==\s*1", text):
    score += 0.04
  return clamp(score, 0.05, 1.0)

def strictness_penalty(text):
  """Extra doubt for conditions that stack requirements."""
  strict = 0
  if re.search(r"order\s*==\s*1", text):
    strict += 2
  if re.search(r"blocked_|is_overtake|change_order_onetime", text):
    strict += 2
  if re.search(r"phase_random|corner_random|straight_random", text):
    strict += 1
  if comparator_count(text) >= 5:
    strict += 1
  return min(0.24, strict * 0.04)

def group_consistency(text):
  return clamp(timing_score(text) * 0.45
               + breadth_score(text) * 0.30
               + scenario_score(text) * 0.25
               - strictness_penalty(text), 0.05, 0.99)

def consistency(skill):
  """How reliably this skill fires, 0..1.

  Groups combine as one minus the chance they all miss, because a skill with
  two condition blocks fires if either is met - adding them would say a skill
  with two unreliable triggers is more reliable than one certain trigger.
  """
  groups = condition_groups(skill)
  if not groups:
    return 0.58

  scores = [group_consistency(text) for text in groups]
  miss = 1.0
  for score in scores:
    miss *= 1 - min(0.97, score * 0.9)
  combined = 1 - miss
  if len(groups) > 1:
    combined += min(0.08, (len(groups) - 1) * 0.03)
  return clamp(combined, 0.05, 0.99)

def cost_efficiency(cost, is_gold):
  """Skill Value per skill point, normalised so 12 SV for 120 SP scores 1.0."""
  if not cost or cost <= 0:
    return 1.0
  score = ((GOLD_SV if is_gold else WHITE_SV) / cost) / IDEAL_SV_PER_SP
  # Cheap skills are worth disproportionately more, because the budget buys
  # several of them and Team Trials counts activations rather than magnitudes.
  if cost <= 120:
    score *= 1.15
  elif cost <= 160:
    score *= 1.05
  if cost >= 360:
    score *= 0.70
  elif cost >= 300:
    score *= 0.80
  return clamp(score, 0.0, 1.0)

def is_volatile_green(skill):
  """True for a passive whose only condition is something nobody controls."""
  if skill.get("ability_time") not in PASSIVE_ABILITY_TIMES:
    return False
  groups = condition_groups(skill)
  return bool(groups) and all(VOLATILE_CONDITION.search(text) for text in groups)

def expected_sv(skill):
  """Expected Team Trials points: how often it fires times what firing pays.

  This, not `score`, is what the planner maximises. `score` divides value by
  cost, and a knapsack already accounts for cost through the budget - using it
  as the objective counts cost twice and degenerates into "buy whatever is
  cheapest", which is exactly what the first version did.
  """
  sv = GOLD_SV if skill.get("rarity") == GOLD_RARITY else WHITE_SV
  return consistency(skill) * sv

def score(skill):
  """Composite 0..1 for one skill record from masterdb.skills().

  Ranking and display only - the planner uses `expected_sv`. Kept because it is
  the number the source optimizer shows, and it is the right thing to sort a
  human-readable list by.
  """
  is_gold = skill.get("rarity") == GOLD_RARITY
  composite = (CONSISTENCY_WEIGHT * consistency(skill)
               + COST_WEIGHT * cost_efficiency(skill.get("cost"), is_gold))
  if is_volatile_green(skill):
    composite -= GREEN_PASSIVE_PENALTY
  return clamp(composite, 0.0, 1.0)

def _named_values(text, key):
  """The values a condition demands for `key`, and the ones it excludes."""
  wanted = {int(v) for v in re.findall(key + r"\s*==\s*(\d+)", text)}
  excluded = {int(v) for v in re.findall(key + r"\s*!=\s*(\d+)", text)}
  return wanted, excluded

def beneficial(skill):
  """False for the debuff skills - the ones whose name ends in a cross.

  These are real, purchasable and cheap (40-50 SP), and they make the trainee
  *worse*: "Fukushima Racecourse x" moderately decreases performance there. A
  scorer that only weighs consistency against cost loves them, because they are
  the cheapest things in the game and their conditions are trivially satisfied -
  the first run of the planner spent an entire 400-point budget on ten of them.

  grade_value carries the sign (-129 against +129 for the same skill's positive
  rank), which is a cleaner test than the name: it catches 47 of 577 purchasable
  skills without depending on how OCR rendered the glyph.
  """
  grade = skill.get("grade_value")
  return grade is None or grade >= 0

def _codes(value, table):
  """Accept "mile", 2, or any collection of either, as a set of codes."""
  if value is None:
    return set()
  values = value if isinstance(value, (list, tuple, set, frozenset)) else [value]
  codes = set()
  for item in values:
    if isinstance(item, int):
      codes.add(item)
    else:
      code = table.get(str(item).strip().lower())
      if code is not None:
        codes.add(code)
  return codes

def applicable(skill, style=None, distance=None, surface=None):
  """False when the skill's condition rules this Uma out entirely.

  A skill gated on `running_style==2` can never fire for a Front runner, so it
  is 180 skill points that do nothing. This is the filter that has to run before
  any scoring, and it is the one the bot has never had - the configured list
  contains exactly that mistake today.

  **Both arguments take a set**, because an Uma runs whatever its aptitudes
  allow: one with Sprint A and Mile A will enter both, so Mile skills are not
  dead weight for it. Filtering on a single distance would throw away half a
  usable list, which is a worse error than keeping a few skills that never fire.

  Unknown or unset aptitudes filter nothing, because guessing would silently
  discard skills that are fine.
  """
  for key, value, table in (("running_style", style, RUNNING_STYLES),
                            ("distance_type", distance, DISTANCE_TYPES),
                            ("ground_type", surface, GROUND_TYPES)):
    codes = _codes(value, table)
    if not codes:
      continue
    for text in condition_groups(skill):
      wanted, excluded = _named_values(text, key)
      # Rules this Uma out only when every aptitude it has is excluded, or the
      # condition names values and none of ours is among them.
      if codes <= excluded:
        return False
      if wanted and not (codes & wanted):
        return False
  return True

def tier_group(skill):
  """What makes two skills alternatives rather than additions.

  A gold skill is an *upgrade* of a white one, and buying it grants the white
  too - so the game lists the gold at its own discounted price PLUS the white's
  price, and the white turns "Obtained" the moment the gold is bought.
  Measured on a live screen: Professor of Curvature listed at 306 with Corner
  Adept at 180; buying Corner Adept for 180 dropped Professor to 126, and
  126 + 180 = 306.

  master.mdb pairs them with `group_id` (`group_rate` is the tier, 1 white and
  2 gold), so the group is the unit of choice. Grouping by name instead - which
  is what this did first - treats Corner Adept and Professor of Curvature as two
  separate buys, budgets 486 for something costing 306, and then cannot click
  the white because the gold already granted it.

  Falls back to the rank-stripped name when there is no group, which is what
  keeps the two ranks of one skill from both being taken.
  """
  group = skill.get("group_id")
  if group:
    return f"group:{group}"
  return re.sub(r"\s+[○◎×]$", "", skill["name"]).strip().lower()

def plan(skills, budget, style=None, distance=None, surface=None,
         exclusive=None, allow_volatile_greens=False):
  """Best affordable set of skills, as a list of records.

  Exact rather than greedy: this is a bounded knapsack and the budget is small,
  so there is no reason to approximate. Skills are grouped so at most one of a
  mutually exclusive family is taken - buying both ranks of one skill is wasted
  points, and `exclusive` defaults to grouping by name with the rank stripped.
  """
  budget = max(0, int(budget or 0))
  if budget <= 0:
    return []

  usable = [s for s in skills
            if s.get("cost") and s["cost"] <= budget
            and beneficial(s) and applicable(s, style, distance, surface)
            and (allow_volatile_greens or not is_volatile_green(s))]
  if not usable:
    return []

  if exclusive is None:
    exclusive = tier_group

  families = {}
  for skill in usable:
    families.setdefault(exclusive(skill), []).append(skill)

  # Scores are floats; the DP works in integers so ties are stable.
  scaled = {id(s): int(round(expected_sv(s) * 10000)) for s in usable}

  best = [0] * (budget + 1)
  taken = [None] * (budget + 1)
  for key, members in sorted(families.items()):
    nxt = list(best)
    nxt_taken = list(taken)
    for spent in range(budget + 1):
      if best[spent] < 0:
        continue
      for member in members:
        after = spent + member["cost"]
        if after > budget:
          continue
        value = best[spent] + scaled[id(member)]
        if value > nxt[after]:
          nxt[after] = value
          nxt_taken[after] = (spent, member, taken[spent])
    best, taken = nxt, nxt_taken

  end = max(range(budget + 1), key=lambda b: (best[b], -b))
  chosen, node = [], taken[end]
  while node:
    spent, member, previous = node
    chosen.append(member)
    node = previous

  chosen.reverse()
  spend = sum(s["cost"] for s in chosen)
  debug(f"Skill plan: {len(chosen)} skills for {spend}/{budget} points, "
        f"{best[end] / 10000:.1f} expected SV.")
  return chosen
