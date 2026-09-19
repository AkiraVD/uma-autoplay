"""What to buy off the Trackblazer shop shelf.

**Pure logic.** Rows arrive as dicts, coins as an int, and the answer comes back
as a list of rows to tick. Nothing here reads the screen or clicks, so the whole
thing is testable without a game - the reader and the four-screen purchase live
with the rest of the screen code.

The shape comes from what the shelf actually is, measured on a live career
(docs/screen-map.md):

- **The shelf is a rotating subset.** Seven rows were on offer against 53 items
  in `data/trackblazer_shop.json`, so the catalogue is the universe and the
  shelf is today's stock. Never plan from the catalogue; plan from the rows.
- **Coins expire with the career.** There is nothing to save them for past the
  last shop, so an unspent coin is worth nothing and the tie-break leans toward
  spending rather than hoarding.
- **Row names match the catalogue exactly.** All seven measured rows resolved
  through `trackblazer.item()` with matching costs, so a row is priced and
  understood by name alone.

What it deliberately does not do: decide *when* to visit the shop, or use what
it buys. Buying is one decision and using is another.
"""
import core.trackblazer as trackblazer

# Worth per coin, by what the effect does. These are ranks, not measurements -
# the game gives no exchange rate between a stat point and a mood level - so
# they encode a policy and are meant to be argued with:
#
# - `stat` is the floor to beat, because it is the one effect whose value is
#   unconditional and immediate. A Notepad is 3 points for 10 coins.
# - `facility_level` is rated highest: a facility level raises every future
#   training on it, so it compounds over the turns that remain.
# - `training_bonus` and `no_fail` only pay if a training happens while they
#   last, so they are discounted for being conditional.
# - `cure_condition` is rated on the condition it removes, not on the item.
# - `max_energy` raises the ceiling, which is worth more early than late.
VALUE_PER_COIN = {
  "facility_level": 3.0,
  "stat": 1.0,
  "max_energy": 0.9,
  "energy": 0.8,
  "training_bonus": 0.7,
  "no_fail": 0.6,
  "mood": 0.5,
  "cure_condition": 0.5,
  "bond": 0.4,
  "race_bonus": 0.3,
  "fan_bonus": 0.3,
  "gain_condition": 0.3,
  "shuffle_supports": 0.2,
  "energy_cost_up": -1.0,
}

# A stat point is the unit everything else is priced against.
STAT_POINT = 1.0
# One facility level, in stat points. A level pays out on every training of that
# facility for the rest of the career, so it is deliberately large.
FACILITY_LEVEL = 40.0
# One energy, in stat points.
#
# **Energy is preferred over cheap stat items**, which is a deliberate policy
# call and not a measurement. The derivation gives a range rather than a number:
# a training costs about 21 energy and returns roughly 10-30 stat points, so an
# energy is worth somewhere between 0.5 and 1.4 stat points. This used to sit at
# 0.5, the bottom of that range, which made Vita 20 (0.29/coin) rate below a
# Speed Notepad (0.30/coin) - the bot would have bought notepads over energy.
#
# 1.0 is the boundary value where every energy row clears every cheap stat row:
# Vita 20 reaches 0.57/coin against Scroll's 0.50, and Royal Kale Juice leads
# the shelf at 1.31. Going higher (1.2, 1.5) reorders nothing, it only widens
# the margin, so 1.0 is the smallest number that satisfies the policy and it
# sits mid-range in the derivation rather than at an end of it.
ENERGY_POINT = 1.0
# One mood level, in stat points.
MOOD_LEVEL = 8.0


def _effect_value(effect, headroom=None):
  """What one effect clause is worth, in stat points."""
  kind = effect.get("kind")
  amount = effect.get("amount", 0)

  if kind == "stat":
    stat = effect.get("stat")
    # A stat with no room left is worth nothing, however cheap the item is.
    if headroom is not None and headroom.get(stat, 1) <= 0:
      return 0.0
    return amount * STAT_POINT
  if kind == "facility_level":
    return amount * FACILITY_LEVEL
  if kind in ("energy", "max_energy"):
    return amount * ENERGY_POINT
  if kind == "mood":
    return amount * MOOD_LEVEL          # negative amounts subtract, as they should
  if kind == "energy_cost_up":
    # A drawback clause, not a benefit: it makes the training cost more.
    return -effect.get("percent", 0) * 0.1
  if kind in ("training_bonus", "race_bonus", "fan_bonus"):
    return effect.get("percent", 0) * 0.1 * max(1, effect.get("turns", 1)) * 0.5
  if kind == "no_fail":
    return 6.0 * max(1, effect.get("turns", 1))
  if kind == "cure_condition":
    return 10.0
  if kind == "gain_condition":
    return 6.0
  if kind == "bond":
    return amount * 0.6
  if kind == "shuffle_supports":
    return 3.0
  return 0.0


def value_of(entry, headroom=None):
  """A catalogue entry's worth in stat points, summed over its clauses.

  `headroom` is the per-stat room left (`logic.set_stat_headroom`'s view). A
  stat item for a capped stat is worth nothing, which is the one piece of career
  state a purchase decision genuinely needs.
  """
  if not entry:
    return 0.0
  return sum(_effect_value(e, headroom) for e in (entry.get("effect") or []))


def score_row(row, headroom=None):
  """(value-per-coin, value, entry) for one shelf row, or None if unknown.

  A row is `{"name": ..., "cost": ...}` as read off the shelf. The cost on
  screen wins over the catalogue's, because the shelf is what will be charged.
  """
  entry = trackblazer.item(row.get("name", ""))
  if entry is None:
    return None
  if entry.get("trap"):
    # One item is flagged: Energy Drink MAX EX raises the cap by 8 and restores
    # nothing, where the 30-coin Energy Drink MAX raises it by 4 AND restores 5.
    # The file carries the flag and the note; this is what honours it.
    return None
  cost = row.get("cost", entry.get("cost", 0)) or 0
  if cost <= 0:
    return None
  value = value_of(entry, headroom)
  if value <= 0:
    return None
  return (value / cost, value, entry)


def plan(rows, coins, headroom=None):
  """Which rows to tick, richest value-per-coin first, within `coins`.

  Greedy on value-per-coin rather than exhaustive: the shelf holds about seven
  rows and coins expire unspent, so the cost of a slightly suboptimal basket is
  far below the cost of not buying. Returns the rows in shelf order, so a caller
  ticking them top to bottom does not have to scroll back up.

  Unknown names, trap items and anything worth nothing are skipped, and a row
  is only taken if its own cost still fits what is left.
  """
  scored = []
  for index, row in enumerate(rows or []):
    hit = score_row(row, headroom)
    if hit:
      per_coin, value, entry = hit
      scored.append((per_coin, value, index, row, entry))

  scored.sort(key=lambda s: (-s[0], -s[1], s[2]))
  taken, spent = [], 0
  for per_coin, value, index, row, entry in scored:
    cost = row.get("cost", entry.get("cost", 0)) or 0
    if spent + cost <= coins:
      taken.append((index, row))
      spent += cost

  taken.sort(key=lambda t: t[0])
  return [row for _, row in taken]


def explain(rows, coins, headroom=None):
  """A one-line reason per row, for the log. Same order as `rows`."""
  lines = []
  for row in rows or []:
    name = row.get("name", "?")
    entry = trackblazer.item(name)
    if entry is None:
      lines.append(f"{name}: not in the catalogue, skipped")
      continue
    if entry.get("trap"):
      lines.append(f"{name}: flagged a trap ({entry.get('note', '')[:60]}), skipped")
      continue
    cost = row.get("cost", entry.get("cost", 0)) or 0
    value = value_of(entry, headroom)
    per = (value / cost) if cost else 0
    lines.append(f"{name}: {value:.0f} pts for {cost} coins = {per:.2f}/coin")
  return lines
