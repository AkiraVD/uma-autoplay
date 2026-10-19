import re
import core.state as state
import core.outings as outings
import core.planner as planner
import core.training_cost as training_cost
from core.state import check_current_year, stat_state, stat_caps_state, check_energy_level, check_aptitudes
from utils.log import info, warning, error, debug
import utils.constants as constants

# Get priority stat from config
def get_stat_priority(stat_key: str) -> int:
  return state.PRIORITY_STAT.index(stat_key) if stat_key in state.PRIORITY_STAT else 999

def check_all_elements_are_same(d):
    sections = list(d.values())
    return all(section == sections[0] for section in sections[1:])

# Will do train with the most support card
# Used in the first year (aim for rainbow)
def most_support_card(results):
  # Seperate wit
  wit_data = results.get("wit")

  # Get all training but wit
  non_wit_results = {
    k: v for k, v in results.items()
    if k != "wit" and (int(v["failure"]) <= state.MAX_FAILURE or has_extreme_burst(v))
  }

  # Check if train is bad
  all_others_bad = len(non_wit_results) == 0
  energy_level, max_energy = check_energy_level()
  if energy_level < state.SKIP_TRAINING_ENERGY:
    burst_key = best_extreme_burst(results)
    if burst_key:
      info(f"Energy {energy_level:.0f} is under {state.SKIP_TRAINING_ENERGY}, but {burst_key.upper()} has an Extreme Spirit Burst ready. Training it rather than resting it away.")
      return burst_key
    info(f"Energy {energy_level:.0f} is under {state.SKIP_TRAINING_ENERGY}, resting instead of training.")
    return None

  if all_others_bad and wit_data and int(wit_data["failure"]) <= state.MAX_FAILURE and wit_data["total_supports"] >= 2:
    info("All trainings are unsafe, but WIT is safe and has enough support cards.")
    return "wit"

  filtered_results = {
    k: v for k, v in results.items()
    if int(v["failure"]) <= state.MAX_FAILURE or has_extreme_burst(v)
  }

  if not filtered_results:
    info("No safe training found. All failure chances are too high.")
    return None

  # this is the weight adder used for skewing results of training decisions PRIORITY_EFFECTS_LIST[get_stat_priority(x[0])] * PRIORITY_WEIGHTS_LIST[priority_weight]
  # Best training
  best_training = max(filtered_results.items(), key=training_score)

  best_key, best_data = best_training

  # Everything below this point rests to save the energy for a turn with better
  # odds or a fuller facility. An Extreme Spirit Burst is a guaranteed success
  # paying several times a normal training, and it is gone if the turn goes
  # anywhere else, so no amount of thinness or low energy argues against it.
  if has_extreme_burst(best_data):
    info(f"{best_key.upper()} has an Extreme Spirit Burst ready - guaranteed success, so energy and support count are not reasons to skip it.")
    return best_key

  if best_data["total_supports"] <= 1:
    if int(best_data["failure"]) == 0:
      # WIT must be at least 2 support cards
      if best_key == "wit":
        if energy_level > state.NEVER_REST_ENERGY:
          info(f"Only 1 support and it's WIT but energy is too high for resting to be worth it. Still training.")
          return "wit"
        else:
          info(f"Only 1 support and it's WIT. Skipping.")
          return None
      info(f"Only 1 support but 0% failure. Prioritizing based on priority list: {best_key.upper()}")
      return best_key
    else:
      if energy_level > state.NEVER_REST_ENERGY:
        info(f"Energy is over {state.NEVER_REST_ENERGY}, train anyway.")
        return best_key
      else:
        info("Low value training (only 1 support). Choosing to rest.")
        return None

  info(f"Best training: {best_key.upper()} with {best_data['total_supports']} support cards and {best_data['failure']}% fail chance")
  return best_key

PRIORITY_WEIGHTS_LIST={
  "HEAVY": 0.75,
  "MEDIUM": 0.5,
  "LIGHT": 0.25,
  "NONE": 0
}
TRAINING_KEY_LIST = ["spd", "sta", "pwr", "guts", "wit"]

def training_score(x):
  global PRIORITY_WEIGHTS_LIST
  priority_weight = PRIORITY_WEIGHTS_LIST[state.PRIORITY_WEIGHT]
  base = x[1]["total_supports"]
  for key in TRAINING_KEY_LIST:
    non_max_friends = x[1][key]["friendship_levels"]["blue"] + x[1][key]["friendship_levels"]["green"] + x[1][key]["friendship_levels"]["gray"]
    base += non_max_friends * 0.5
  if x[1]["total_hints"] > 0:
      base += 0.5
  multiplier = 1 + state.PRIORITY_EFFECTS_LIST[get_stat_priority(x[0])] * priority_weight
  room = headroom_factor(x[0])
  total = base * multiplier * room
  unity = unity_bonus(x[1], x[0], state.CURRENT_YEAR, base_score=total)
  total += unity
  gains = gain_score(x[1], x[0])
  total += gains
  performance = performance_bonus(x[1], x[0])
  total += performance
  # This is the path that otherwise ends in a rest, so wit's energy return has
  # to reach it as well or wit could never be picked over resting.
  wit_energy = wit_energy_bonus(x[0], x[1])
  total += wit_energy

  # Debug output
  debug(f"{x[0]} -> base={base}, multiplier={multiplier}, room={room:.2f},"
        f" unity={unity}, gains={gains:.2f}"
        + (f", performance={performance:.2f}" if performance else "")
        + (f", wit_energy={wit_energy:.2f}" if wit_energy else "")
        + f", total={total}, priority={get_stat_priority(x[0])}")

  return (total, -get_stat_priority(x[0]))

def focus_max_friendships(results):
  filtered_results = {
      stat: data for stat, data in results.items()
      if int(data["failure"]) <= state.MAX_FAILURE or has_extreme_burst(data)
  }

  if not filtered_results:
      debug("No trainings under MAX_FAILURE, falling back to most_support_card.")
      return None, 0

  for stat_name in filtered_results:
    data = filtered_results[stat_name]
    # order of importance gray > blue > green, because getting greens to max is easier than blues (gray is very low blue)
    possible_friendship = (
                            data["total_friendship_levels"]["green"]
                            + data["total_friendship_levels"]["blue"] * 1.01
                            + data["total_friendship_levels"]["gray"] * 1.02
                          )

    # hints are worth a little more than half a training
    if data["total_hints"] > 0:
      hint_values = { "gray": 0.612, "blue": 0.606, "green": 0.6 }
      for level, bonus in hint_values.items():
        if data["hints_per_friend_level"].get(level, 0) > 0:
            possible_friendship += bonus
            break

    possible_friendship += unity_bonus(data, stat_name, state.CURRENT_YEAR, base_score=possible_friendship)
    possible_friendship += gain_score(data, stat_name)
    possible_friendship += performance_bonus(data, stat_name)
    debug(f"{stat_name} : gray={data['total_friendship_levels']['gray']}, blue={data['total_friendship_levels']['blue']}, green={data['total_friendship_levels']['green']}, total={possible_friendship:.3f}")
    filtered_results[stat_name]["possible_friendship"] = possible_friendship

  best_key = max(filtered_results, key=lambda k: (filtered_results[k]["possible_friendship"], -get_stat_priority(k)))
  best_score = filtered_results[best_key]["possible_friendship"]
  return best_key, best_score

# Do rainbow training
# A facility already worth roughly one rainbow support. This is the point at
# which a saved burst counts as landing on a "strong" training.
STRONG_TRAINING_SCORE = 2.0

# Ceiling on the whole spirit-gauge bonus, as a fraction of one ready burst.
#
# uma.guide scores a Spirit Burst at 2 points in all three of its turn-scoring
# tables and gives a charging gauge no score at all - the gauge weight in this
# repo comes from UMAT's scenario config, not from the guide. Scaled linearly
# it runs away: in a live run a facility with four charging gauges scored 4.00
# against a ready burst at 2.00, and the bot trained the gauges and left the
# burst unfired. The guides are unambiguous that early bursts are the
# priority - they are the biggest contributor to levelling facilities - so
# charging must never outrank firing.
MAX_GAUGE_FRACTION = 0.75

# Points per weighted stat point. A strong training reads around 50 weighted
# stats, which lands near 2.0 - one rainbow support on this repo's scale.
STAT_GAIN_POINTS = 0.04
# Skill points are useful but are not a stat, so they count for less.
SKILL_PT_WEIGHT = 0.5
# A burst fires on whichever training is taken, so when one is ready the gains
# on screen are the ones that land. Weighting them up rather than adding a flat
# bonus keeps a burst on a big training ahead of a burst on a small one.
BURST_GAIN_MULTIPLIER = 1.5
BURST_EX_GAIN_MULTIPLIER = 2.0

# Cap used when neither the config nor the screen gave one. Same fallback
# filter_by_stat_caps has always used.
DEFAULT_STAT_CAP = 1200

# How many points each stat can still absorb this turn, rebound by
# set_stat_headroom() from do_something(). A stat missing from here is unknown
# rather than capped, and its gains score at full value as they always did.
_stat_headroom = {}
# Current value per stat, set by the same call that sets the headroom.
_stat_current = {}

# The game halves both the gain and the race effect of any stat past this.
# Measured over 1353 training reads from careers 6-10: printed Speed gains
# median 20 below 1200 and 10 at or above it - an exact halving, and it is
# already in the numbers core/gains.py reads off the screen.
STAT_SOFT_CAP = 1200
# So a printed point that lands above the soft cap cost twice the training a
# point below it did. Scoring it at 2x prices the training that earned it
# rather than the number the game chose to print.
SOFT_CAP_GAIN_MULTIPLIER = 2.0

def stat_cap(stat, game_caps=None):
  """Where further training in one stat stops paying.

  The configured cap is a strategy ceiling and the on-screen one is the hard
  limit; whichever is lower wins. A cap that failed to read is -1 and simply
  drops out.
  """
  game_caps = game_caps or {}
  caps = [c for c in (state.STAT_CAPS.get(stat), game_caps.get(stat)) if c and c > 0]
  return min(caps) if caps else DEFAULT_STAT_CAP

def set_stat_headroom(current_stats, game_caps=None):
  """Record how much room each stat has left, for gain_score to spend against.

  A stat whose current value would not read comes back as -1; it is left out
  entirely rather than guessed at, because guessing low would silently write
  off a training that is in fact still worth taking.
  """
  global _stat_headroom, _stat_current
  _stat_headroom = {
    stat: max(0, stat_cap(stat, game_caps) - current)
    for stat, current in (current_stats or {}).items()
    if current is not None and current >= 0
  }
  # Kept alongside the headroom so weighted_stat_points can tell how much of a
  # gain lands above the soft cap. Same -1 rule: an unread stat is left out.
  _stat_current = {
    stat: current
    for stat, current in (current_stats or {}).items()
    if current is not None and current >= 0
  }
  debug(f"Stat headroom: {_stat_headroom}")


def stat_headroom():
  """The per-stat room left, as a copy, for callers outside this module.

  **No live caller as of 2026-09-21.** Its one user was the Trackblazer shop -
  an item for a capped stat has to score zero, because a Speed Scroll is worth
  nothing once Speed has no room - and that went to `core/parked/`. Kept rather
  than deleted because it is the seam the parked shop is re-wired to, and
  because the staleness rule below is the non-obvious part worth preserving.
  Handed out as a copy: a caller has no business editing the scorer's view.

  **It is up to one turn stale.** `set_stat_headroom` runs inside
  `do_something()`, so anything consulting this earlier in the turn - the shop
  visit did - sees the previous turn's reading, and an empty dict on the first
  turn of a career. That is deliberate rather than worth re-reading the stats
  for: caps move by tens of points a turn at most, and `value_of` already
  treats a missing stat as unknown-so-score-in-full rather than as no room.
  """
  return dict(_stat_headroom)

# Room enough for a strong training to land in full. Facilities pay about 40
# to 50 in their own stat at the top end, so past this there is nothing to
# discount.
HEADROOM_FULL = 50.0
# What a facility keeps when its own stat has no room left. Not zero: the
# bond, the hints and the skill points are all still worth having, and they
# are most of why a rainbow is taken late in a career.
HEADROOM_FLOOR = 0.35

def headroom_factor(stat_name):
  """How much of the support-and-rainbow proxy this facility still earns.

  filter_by_stat_caps only drops a stat once it is *fully* capped, so between
  "a few points left" and "capped" a facility kept its whole proxy score. Seen
  live in the Finale: Speed sat at 1304 against a 1316 cap - twelve usable
  points - and its rainbow still scored 11.3, beating a wit facility offering
  113 skill points, which is most of an extra skill at career end.

  gain_score already clips the printed gains to headroom. This does the same
  for the proxy, which is what carries the score when the gains do not read.
  Unknown headroom means no reading, not no room, so it scores in full.
  """
  room = _stat_headroom.get(stat_name)
  if room is None:
    return 1.0
  return HEADROOM_FLOOR + (1.0 - HEADROOM_FLOOR) * min(1.0, room / HEADROOM_FULL)

def soft_cap_value(stat_name, amount):
  """A printed gain in pre-halving units: the part above 1200 counts double.

  The game halves a gain once the stat passes STAT_SOFT_CAP, and the training
  screen prints the halved figure, so the bot reads 10 where it would have read
  20 lower down. Those ten points cost a whole training either way; scoring
  them as ten prices the game's bookkeeping rather than the work.

  Only the portion that actually crosses the cap is doubled - a training that
  takes Speed from 1190 to 1210 is twenty printed points of which ten sat below
  the line, so it scores 10 + 10x2 = 30, not 40.

  An unread current value means no doubling: guessing would inflate a facility
  the bot cannot see.
  """
  current = _stat_current.get(stat_name)
  if current is None or amount <= 0:
    return amount
  below = max(0.0, min(float(amount), STAT_SOFT_CAP - current))
  above = float(amount) - below
  return below + above * SOFT_CAP_GAIN_MULTIPLIER

def weighted_stat_points(stats):
  """Stat gains in score units, clipped to the room left under each cap.

  Shared by the training gains and by an outing's predicted stats so the two
  come out on the same scale and can be compared directly.
  """
  priority_weight = PRIORITY_WEIGHTS_LIST[state.PRIORITY_WEIGHT]
  total = 0.0
  for stat, amount in (stats or {}).items():
    headroom = _stat_headroom.get(stat)
    if headroom is not None:
      # Only the part that fits under the cap actually lands.
      amount = min(amount, headroom)
      if amount <= 0:
        continue
    amount = soft_cap_value(stat, amount)
    multiplier = 1 + state.PRIORITY_EFFECTS_LIST[get_stat_priority(stat)] * priority_weight
    total += amount * multiplier
  return total * STAT_GAIN_POINTS

def gain_score(data, stat_name=""):
  """Score the stat gains the training screen prints for this facility.

  These are the numbers the game will actually award, so they beat the support
  count and rainbow proxies whenever they can be read. Returns 0.0 when the
  reader saw nothing, which leaves the existing scoring untouched.

  Gains are clipped to the headroom left under each stat's cap. A training
  prints its side stats too, so a big number in an already-capped secondary
  used to pull the bot onto a facility whose points had nowhere to go -
  filter_by_stat_caps only ever looked at a training's own stat.
  """
  gains = data.get("gains") or {}
  if not gains:
    return 0.0
  score = weighted_stat_points({k: v for k, v in gains.items() if k != "skill"})
  # Skill points have no cap.
  score += gains.get("skill", 0) * SKILL_PT_WEIGHT * STAT_GAIN_POINTS

  unity = data.get("unity") or {}
  if unity.get("burst_ex"):
    score *= BURST_EX_GAIN_MULTIPLIER
  elif unity.get("burst"):
    score *= BURST_GAIN_MULTIPLIER
  return score

def has_extreme_burst(data):
  """An Extreme Spirit Burst forces the training's failure chance to 0%, so a
  facility carrying one is safe whatever the failure reader saw."""
  return bool((data.get("unity") or {}).get("burst_ex", 0))

def best_extreme_burst(results):
  """The facility carrying an Extreme Spirit Burst, best of several.

  Every rest gate in this module exists for one of two reasons: the failure
  chance is too high, or the turn is worth too little to spend. An Extreme
  burst removes both - it forces the training to 0% failure and pays two to
  three times a normal facility - and it is gone the moment the turn goes to
  anything else, so it overrides those gates rather than being weighed against
  them. Returns None outside Unity Cup, where burst_ex is always 0.
  """
  candidates = {k: v for k, v in results.items() if has_extreme_burst(v)}
  if not candidates:
    return None
  if len(candidates) == 1:
    return next(iter(candidates))
  return max(candidates.items(), key=training_score)[0]

def _save_bursts(year):
  """Junior and Classic are the facility-levelling and recruiting years, so
  bursts get popped on sight. From Senior on they are saved for strong
  trainings. The Finale is the last chance to spend one, so it pops again."""
  return "Senior Year" in year and "Finale" not in year

def unity_bonus(data, stat_name, year="", base_score=None):
  """Extra score for Unity Cup spirit gauges and ready bursts on this facility.

  Zero outside Unity Cup, where the counts are always 0.

  Weights follow uma.guide's turn-scoring tables, which value a Spirit Burst at
  2 points - one rainbow support on this repo's scale - and UMAT's scenario
  config, which puts a charging gauge at half a burst. An Extreme burst is
  worth more again: it zeroes the failure chance, raises the team member's stat
  caps and grants more stats than a normal burst.

  The gauge total is capped at MAX_GAUGE_FRACTION of a burst. "Half a burst"
  was written with one gauge in mind, and a facility can carry four.

  Timing follows uma.guide: pop bursts on sight early, because that is what
  levels facilities and recruits team members, then "save Bursts to improve
  already strong Trainings" once that is done. From Senior Year the burst is
  scaled by base_score, the facility's score before this bonus, so a burst can
  amplify a good training but cannot drag the bot onto an empty one.

  The gauge bonus is dropped during the Finale: charging a gauge only pays off
  through a later burst, and by then there are no turns left to spend it.
  """
  unity = data.get("unity") or {}
  spirit = unity.get("spirit", 0)
  burst = unity.get("burst", 0)
  burst_ex = unity.get("burst_ex", 0)
  if not spirit and not burst and not burst_ex:
    return 0.0

  bonus = 0.0
  if spirit and "Finale" not in year:
    bonus += min(spirit * state.SPIRIT_GAUGE_POINTS,
                 state.SPIRIT_BURST_POINTS * MAX_GAUGE_FRACTION)

  # An empty list means "count bursts everywhere"; otherwise only on the stats
  # the user nominated.
  if not state.BURST_ENABLED_STATS or stat_name in state.BURST_ENABLED_STATS:
    burst_points = burst * state.SPIRIT_BURST_POINTS + burst_ex * state.SPIRIT_BURST_EX_POINTS
    if burst_points and base_score is not None and _save_bursts(year):
      burst_points *= min(1.0, max(0.0, base_score) / STRONG_TRAINING_SCORE)
    bonus += burst_points
  return bonus

def performance_bonus(data, stat_name=""):
  """Grand Concert: extra score for paying the Performance type a scheduled
  song is short of.

  A song only unlocks its bonuses and Hype once its whole cost is paid, and
  the cost is split across two types, so points of a type the song already has
  enough of do nothing for it. The panel's red "N more" badges say which types
  are short; each chip on this facility naming one of them adds
  PERFORMANCE_SHORT_POINTS. A friendship training pays two types, so it can
  collect this twice - on top of already scoring well as a rainbow.

  Zero outside Grand Concert and whenever nothing is scheduled.

  Urgent types are worth PERFORMANCE_URGENT_POINTS instead: a Lessons board of
  locked cards buys nothing at all until one of its types is paid, and in
  Senior H2 every turn without the 18th song is a turn closer to losing the
  gold skill. At the ordinary weight neither ever changed a training choice
  (careers 4 and 5).

  **Tapered by the facility's own headroom**, when the caller says which
  facility this is. The chips are not a stat gain - they land whatever the stat
  does - but this is *added to* terms that are each priority-weighted and
  clipped to the room under the cap, and at the urgent weight it is worth about
  as much as a whole rainbow. So on a facility whose stat has nowhere left to go
  it could buy a training turn on chips alone. Seen in the 2026-10-12 Grand
  Concert career: Guts at 647 against a 650 cap - three points of headroom,
  priority weight zero - scored 0.39 proxy + 0.93 gains + 4.00 urgent chips and
  took the turn from Speed's 14.50, and Guts finished 41 points *past* the cap
  the config set. The taper keeps the nudge where the turn also pays stats and
  withdraws it where the turn would pay nothing else.

  An untapered call (no stat_name) is still the raw weight, which is what the
  Lessons-side tests measure.
  """
  performance = data.get("performance") or {}
  short = set(performance.get("short") or ())
  if not short:
    return 0.0
  weight = state.PERFORMANCE_URGENT_POINTS if performance.get("urgent") else state.PERFORMANCE_SHORT_POINTS
  hits = sum(1 for kind in performance.get("types") or () if kind in short)
  room = headroom_factor(stat_name) if stat_name else 1.0
  return hits * weight * room

# Energy a wit training hands back. Wit is the only facility that returns
# energy instead of spending it, and that return is what the scorers add on
# top of wit's ordinary score - no gate, no band: wit competes on its stat
# gains and supports like every other facility, and the energy it gives back
# is priced as a bonus through energy_value, which is already worth more the
# emptier the tank and nothing at all once the gain would spill.
#
# The return is NOT flat. "Wit Friendship Recovery" on a wit support card adds
# to the base, once per card at MAX bond on the wit facility, and the additions
# STACK. Measured off tests/fixtures/careers - energy before against energy
# after a turn the bot trained wit, read against that board's own wit rainbow
# count:
#
#   0 rainbows  +5.1        1 rainbow  +9.3 / +9.8        2 rainbows  +14.4
#
# which is base 5 + Mihono Bourbon SSR 5 + Agnes Tachyon SR 4 to within the
# energy bar's own pixel resolution. A card below max bond adds nothing, so
# only the "max" level counts here - not the yellow+max the rest of this module
# calls a rainbow. (The web is no use: game8's Friendship Training page says
# outright that its numbers are still being tested.)
#
# This replaced WIT_MIN_RAINBOWS, a hard exclusion, and WIT_ENERGY_BAND, a flat
# bonus between 30 and 70 energy. Both were proxies for the same thing - wit is
# worth taking when the tank needs filling - and both were wrong at the edges:
# the gate needed two of its own rainbows, which the 2026-10-13 career managed
# on exactly one of 43 turns, so wit was excluded all career however good the
# board was; and the band paid the same bonus at 31 energy as at 69.
WIT_RECOVERY_BASE = max(0, training_cost.change("wit"))
WIT_RECOVERY_PER_RAINBOW = 4.75

# Energy at the time do_something ran, and the bar's own cap. Read once per
# turn and published rather than re-read, the same way the stat headroom is.
_energy_level = None
_max_energy = None

# The goal text and turn counter, published by career_lobby before it calls
# do_something. They exist only for the advisory planner: do_something receives
# `results` and nothing else, so the criteria cannot reach it otherwise, and
# reading it again here would cost a second OCR pass on every turn.
_goal_context = {}


def set_goal_context(criteria=None, turn=None):
  """Publish this turn's goal text and turns-left for the advisory planner."""
  global _goal_context
  _goal_context = {"criteria": criteria, "turn": turn}


def goal_criteria():
  """The goal as the last lobby read it, or "".

  Read by the lost-race notification, which fires on a race result screen -
  where the goal is not on screen at all. The last lobby's copy is the right
  one: it is the goal the race that just ended was run for.

  The lobby reads the goal together with the "Entry criteria met!" line printed
  under it, and OCR renders that tail variously as "met!", "metl" or "meti".
  It says nothing about a race already lost, so it is cut here rather than in
  `set_goal_context` - the planner matches on the whole string.
  """
  text = (_goal_context.get("criteria") or "").strip()
  return re.split(r"\s*Entry criteria\b", text, maxsplit=1)[0].strip() or text
def set_energy_level(level, max_energy=None):
  """Publish this turn's energy reading for the scorers.

  max_energy comes along because the Grand Concert widens the bar - the
  2026-10-13 career sat at 97-104 for eighteen turns - and energy_value needs
  the real cap to know how much of a gain would actually land.
  """
  global _energy_level, _max_energy
  _energy_level = level
  _max_energy = max_energy

def wit_energy_gain(data):
  """Energy one wit training would hand back, given this turn's wit board."""
  maxed = data["wit"]["friendship_levels"]["max"] if data.get("wit") else 0
  return WIT_RECOVERY_BASE + maxed * WIT_RECOVERY_PER_RAINBOW

def wit_energy_bonus(stat_name, data):
  """What wit's energy return is worth this turn, in the scorers' own points.

  Zero for every other facility: their energy COST is not priced here either,
  so charging wit for the comparison would be the only accounting on the board.
  Priced through energy_value, so it falls away as the tank fills and is worth
  nothing at all on a full one.
  """
  if stat_name != "wit":
    return 0.0
  return energy_value(wit_energy_gain(data), _energy_level or 0, _max_energy)

def rainbow_training(results):
  global PRIORITY_WEIGHTS_LIST
  priority_weight = PRIORITY_WEIGHTS_LIST[state.PRIORITY_WEIGHT]
  # 2 points for rainbow supports, 1 point for normal supports, stat priority tie breaker
  rainbow_candidates = results
  for stat_name in rainbow_candidates:
    multiplier = 1 + state.PRIORITY_EFFECTS_LIST[get_stat_priority(stat_name)] * priority_weight
    data = rainbow_candidates[stat_name]
    total_rainbow_friends = data[stat_name]["friendship_levels"]["yellow"] + data[stat_name]["friendship_levels"]["max"]
    # Summed over every key. This was assigned inside the loop, so only the last
    # key in TRAINING_KEY_LIST reached the "is any friend still short of max"
    # bonus below.
    non_max_friends = sum(
      data[key]["friendship_levels"]["gray"]
      + data[key]["friendship_levels"]["blue"]
      + data[key]["friendship_levels"]["green"]
      for key in TRAINING_KEY_LIST
    )
    #adding total rainbow friends on top of total supports for two times value nudging the formula towards more rainbows
    rainbow_points = total_rainbow_friends + data["total_supports"]
    if data["total_hints"] > 0:
      rainbow_points += 0.5
    if non_max_friends > 0:
      rainbow_points = rainbow_points + 0.5
    if total_rainbow_friends > 0:
      rainbow_points = rainbow_points + 0.5
    rainbow_points = rainbow_points * multiplier * headroom_factor(stat_name)
    rainbow_points += unity_bonus(data, stat_name, state.CURRENT_YEAR, base_score=rainbow_points)
    rainbow_points += gain_score(data, stat_name)
    rainbow_points += performance_bonus(data, stat_name)
    rainbow_points += wit_energy_bonus(stat_name, data)
    rainbow_candidates[stat_name]["rainbow_points"] = rainbow_points
    rainbow_candidates[stat_name]["total_rainbow_friends"] = total_rainbow_friends

  # Get rainbow training
  rainbow_candidates = {
    stat: data for stat, data in results.items()
    if (int(data["failure"]) <= state.MAX_FAILURE or has_extreme_burst(data))
       and data["rainbow_points"] >= 2
  }

  if not rainbow_candidates:
    info("No training cleared the weight threshold under the failure limit.")
    return None

  # Find support card rainbow in training
  best_rainbow = max(
    rainbow_candidates.items(),
    key=lambda x: (
      x[1]["rainbow_points"],
      -get_stat_priority(x[0])
    )
  )

  best_key, best_data = best_rainbow

  # "Rainbow points" was a misleading name: the number is mostly support count,
  # hints and the measured stat gains, and only partly rainbows. A board with
  # three blue supports and no rainbow at all scores 5.863, where a board with
  # one genuine rainbow scores 4.513 - so the figure was routinely reported as
  # "rainbow points" on facilities holding none. Say what it is, and say how
  # many rainbows actually contributed.
  rainbows = best_data["total_rainbow_friends"]
  info(f"Training selected: {best_key.upper()} with training weight"
       f" {best_data['rainbow_points']:.3f} from {rainbows} rainbow(s),"
       f" {best_data.get('total_supports', 0)} support(s)"
       f" and {best_data['failure']}% fail chance")
  return best_key

def filter_by_stat_caps(results, current_stats, game_caps=None):
  under = {
    stat: data for stat, data in results.items()
    if current_stats.get(stat, 0) < stat_cap(stat, game_caps)
  }
  # URA Finale: same argument, stronger. A capped facility carrying the Duel!
  # badge still pays the hint, the skill points and the stat-cap raise - and a
  # cap raise is worth most exactly where the cap is already the binding
  # constraint. The stat gain is the only part that goes to waste.
  for stat, data in results.items():
    if stat not in under and data.get("duel"):
      info(f"{stat.upper()} is capped, but it carries the Duel! badge, which pays"
           " a hint and a cap raise rather than a stat.")
      under[stat] = data

  # Grand Concert: a capped facility still pays Performance points, and when it
  # is the only one paying a type the board is stuck on, the wasted stat gain
  # is the cheaper loss. Career 6 spent turns unable to take the one Vi chip
  # because it sat on Guts, capped at 400 with 556 trained.
  urgent = set()
  for data in results.values():
    performance = data.get("performance") or {}
    if performance.get("urgent"):
      urgent |= set(performance.get("short") or ())
  if not urgent:
    return under
  covered = {kind for data in under.values()
             for kind in ((data.get("performance") or {}).get("types") or ())}
  missing = urgent - covered
  for stat, data in results.items():
    if stat in under or not missing:
      continue
    pays = set((data.get("performance") or {}).get("types") or ()) & missing
    if pays:
      info(f"{stat.upper()} is capped, but it is the only facility paying"
           f" {', '.join(sorted(pays))}, which the Lessons board is waiting on.")
      under[stat] = data
  return under

def all_values_equal(dictionary):
    values = list(dictionary.values())
    return all(value == values[0] for value in values[1:])

# Decide training
# Recreation is priced from what the next outing will actually give, which
# core.outings predicts from the friend card's event chain. The old flat
# estimate of 20 energy was roughly half the truth - friend outings run 24 to
# 70, median 30 - so the spill guard was letting outings through on a nearly
# full tank.

# Energy is worth a lot when it is scarce, because it buys back the turn that
# would otherwise go to a rest, and close to nothing on a full tank where it
# spills.
#
# The anchor is the rest it avoids, not the training it enables. A rest returns
# about 50 energy and costs one turn, so the price of a point is the value of
# that turn over 50.
#
# This was 0.05, from a turn worth one *average* training - call it 2.5. The
# average is the wrong turn to price. Energy does not buy back an average turn:
# it buys back the best board in the window the tank was empty for. Career 13
# gave away nine own-type Speed rainbow boards, 328 Speed between them, and
# every one of them was reached below 38 energy - including the strongest board
# of the career, worth 25.16, which arrived on 17. A turn worth 4 rather than
# 2.5 prices the bottom of the tank at 0.08, and that is what is set here.
#
# The old note argued the other way: that pricing energy against the training
# it enables (25 energy buys a 2.0 training, so 0.08 a point) double counts,
# because the training spends a turn as well as the energy. That is true of the
# derivation and beside the point of the measurement - the two happen to meet
# at the same number from opposite directions.
#
# This is the lever for everything energy-shaped, not just one rule: it sets
# what a Recreation outing is worth, the wit facility's energy bonus, what a
# Lessons Energy technique has to beat, and the bar in rest_beats_training
# below (at 0.05 that rule fired once in three recorded careers; at 0.08 it
# fires three to five times each). Replaying cannot judge a change to it - a
# recorded career hands the replay its own failure percentages, so banked
# energy buys nothing there - so it moves on live careers only.
ENERGY_POINTS_EMPTY = 0.08
ENERGY_POINTS_FULL = 0.01
# What a full rest returns. Only used to price resting against an outing.
REST_ENERGY_ESTIMATE = 50
# What a training costs. An outing pays energy out and a training pays it in,
# so comparing their stat payouts alone would flatter the training.
#
# This used to be a flat 25 for every facility. It is per-facility now and comes
# from the game's own numbers via core/training_cost - Speed -21, Stamina -19,
# Power -20, Guts -22 and Wit **+5** - so the old constant overstated every
# facility and had the sign wrong on wit, which returns energy. Kept only for
# the one caller that has no facility in hand.
TRAINING_ENERGY_COST = training_cost.DEFAULT_COST
# One mood step, and one mood step while below the configured target - mood
# multiplies every training gain, so it is worth more when it is short.
MOOD_POINTS = 0.35
MOOD_POINTS_BELOW_TARGET = 0.9
# Clearing a negative condition. Only counted when one is actually showing.
CONDITION_CLEAR_POINTS = 3.0
# One hint level. training_score gives 0.5 for a facility carrying any hint.
HINT_POINTS = 0.6
# Friend bond, per point. Small on its own: bond pays off through the chain.
BOND_POINTS = 0.02
# How far ahead an outing has to be before it overrides the training decision.
# Without it the two scores trade places on OCR noise.
OUTING_MARGIN = 0.15
# The same idea for a rest. Larger than OUTING_MARGIN because the two are not
# symmetric: an outing taken on noise still pays stats, bond and mood for the
# turn, where a rest taken on noise buys nothing but energy.
REST_MARGIN = 0.3
# Off switch for the rule below, so tools/career_replay.py can run a recorded
# career with and without it. Nothing in the bot writes this.
REST_ON_WEAK_BOARD = True

# ---- "Too good to pass": trading failure odds for an exceptional board ----
#
# The failure filter is a hard cutoff, so a three-rainbow Speed board printing
# +87 Speed is refused at 32% exactly as a one-support board is. That is the
# wrong comparison. What a risky turn is worth is its expected value,
# (1 - failure) x gains, weighed against the best thing the turn could
# otherwise do.
#
# Career 13, Classic Early Oct, 28 energy: SPD carried 3 own-type rainbows and
# +87 Speed at 52% failure, and the bot trained a 0-support WIT at 12% for +4
# Speed. The gamble was worth 0.48 x 87 = 42 Speed in expectation; the turn
# banked 4.
#
# Why it stays rare, and why the gates sit where they do. Over careers 13 and
# 14 - 625 facility reads - only 7 carry two or more own rainbows above the
# failure bar, and only 2 of those sit under the ceiling, so this is worth
# about one turn a career. Every board the rule has matched so far was Speed.
#
# The gains bar is deck-dependent and belongs to the user for that reason: 45 is
# where an exceptional board starts on the deck careers 13 and 14 ran, and a
# deck with stronger own-type cards prints more for the same three rainbows, so
# a build that regularly clears 100 wants the bar raised to match. Set it off
# what the boards in the log actually print, not off this number.
#
# What is NOT priced: a failed training also drops mood, and can injure, which
# costs turns this comparison cannot see. That is what GAMBLE_EV_MARGIN is for
# - the gamble has to beat the alternative by a margin rather than merely tie -
# and why GAMBLE_CEILING_FAILURE is an absolute refusal rather than another
# term in the sum.
# The four numbers are the user's, under `gamble_board` in config.json and on
# the config page's Training tab, because they are a risk appetite rather than a
# calibration: how good a board has to be, and how bad a failure chance is worth
# accepting, is a judgement the person running the career makes. Read as
# state.GAMBLE_* so a config reload reaches them. This flag is not one of them -
# it is the off switch for tools/career_replay.py's `--alt-flag`, the same as
# REST_ON_WEAK_BOARD, and nothing in the bot writes it. The config's own
# `enabled` is what turns the rule off for a run.
GAMBLE_ON_GREAT_BOARD = True

def energy_points(energy_level, max_energy):
  """Score per point of energy at the current fill level."""
  if not max_energy or max_energy <= 0:
    return ENERGY_POINTS_EMPTY
  fraction = min(1.0, max(0.0, float(energy_level) / max_energy))
  return ENERGY_POINTS_FULL + (ENERGY_POINTS_EMPTY - ENERGY_POINTS_FULL) * (1.0 - fraction)

def energy_value(delta, energy_level, max_energy):
  """Score for gaining (or spending) energy now.

  A gain is clipped to the room left under the cap - energy that spills is
  worth nothing, the same way a stat gain into a capped stat is. A cost is not
  clipped, because it is always paid in full.

  An unreadable cap clips nothing rather than raising: check_energy_level can
  return None for it, and a scorer that throws here does not fall back to a
  worse score - it takes the whole decision down a different branch. That is
  what dropped the replay of the 2026-10-13 career from 97% to 39%.
  """
  if delta >= 0 and max_energy and max_energy > 0:
    delta = min(delta, max(0, max_energy - energy_level))
  return delta * energy_points(energy_level, max_energy)

def mood_value(gain, mood_index, mood_target):
  """Score for a mood gain, clipped to the steps left below GREAT."""
  if gain <= 0:
    return 0.0
  # MOOD_LIST ends with UNKNOWN, so GREAT is the entry before it.
  best = len(constants.MOOD_LIST) - 2
  if 0 <= mood_index <= best:
    gain = min(gain, best - mood_index)
  if gain <= 0:
    return 0.0
  per_step = MOOD_POINTS_BELOW_TARGET if mood_index < mood_target else MOOD_POINTS
  return gain * per_step

def outing_score(effects, energy_level, max_energy, mood_index, mood_target, debuffed):
  """Price a predicted outing on the same scale gain_score uses for training."""
  effects = effects or {}
  score = energy_value(effects.get("energy", 0.0), energy_level, max_energy)
  score += weighted_stat_points(effects.get("stats") or {})
  # A random stat cannot be matched against a cap or a priority, so it is
  # counted flat rather than guessed at.
  score += effects.get("random_stats", 0.0) * STAT_GAIN_POINTS
  score += effects.get("skill", 0.0) * SKILL_PT_WEIGHT * STAT_GAIN_POINTS
  score += mood_value(effects.get("mood", 0.0), mood_index, mood_target)
  score += effects.get("hints", 0.0) * HINT_POINTS
  score += effects.get("bond", 0.0) * BOND_POINTS
  if effects.get("heals") and debuffed:
    score += CONDITION_CLEAR_POINTS
  return score

def rest_score(energy_level, max_energy):
  """What resting is worth, so an outing can be weighed against it."""
  return energy_value(REST_ENERGY_ESTIMATE, energy_level, max_energy)


def rest_beats_training(results, key, year, energy_level, max_energy):
  """Why banking a rest now beats the training just chosen, or None.

  Every other rest the bot takes is reactive: SKIP_TRAINING_ENERGY fires once
  the tank is already empty, so the energy gets bought on whatever turn happens
  to come next rather than on a turn that was worth little. Measured over
  career 13, that cost nine own-type Speed rainbow boards, every one of them
  reached below 38 energy - including the strongest board of the whole career
  (Senior Late Jul, score 25.16, arrived on 17). The turn that emptied the tank
  two turns earlier was a wit training worth 6.91, taken at 33 energy.

  So this is the comparison that was missing: a weak board at mid energy is the
  cheapest rest the career will be offered, and spending it there is what makes
  the next strong board affordable. It is the comparison should_recreate
  already makes for an outing, against the same calibrated energy_value, so it
  introduces no new scale.

  Everything that already argues against resting still wins, because each is
  about a turn that does not come again: a burst, summer camp, the end of the
  career, and the user's own never_rest_energy.
  """
  if not key or not REST_ON_WEAK_BOARD:
    return None
  data = (results or {}).get(key) or {}

  # The config's own ceiling: above it the user has said a rest is never worth
  # a turn, whatever the board looks like.
  if energy_level > state.NEVER_REST_ENERGY:
    return None

  # A guaranteed success paying several times a normal training is not a weak
  # board, whatever the scorers made of the rest of it.
  if has_extreme_burst(data):
    return None

  # Camp turns and the closing turns do not come again, so energy banked on one
  # has nothing left to fund. Both have their own rules further down, and this
  # must not reach around them.
  if camp_turns_left(year) or career_ending(year):
    return None

  # Junior is the bond-building year - do_something hands it to
  # focus_max_friendships, which picks for friendship and not for stats - and
  # training_value only sees the gains the game printed, so it reads every
  # Junior board as weak. It is also the year with nothing to bank for: the
  # boards this rule exists to afford are all Classic and Senior. Replaying
  # career 13 without this, two of its four rests were Junior Pre-Debut.
  if "Junior Year" in (year or ""):
    return None

  value = training_value(results, key)
  if value is None:
    # Unknown is not worthless - an unreadable gains strip must not read as a
    # wasted turn. The same rule should_recreate follows.
    return None

  # abs() on purpose. Live, `energy_cost` is what check_energy_reserved read off
  # the bar's dim tail, and it is positive; the recorded careers in
  # tests/fixtures/careers store the signed figure the log prints (-19). The two
  # conventions disagree, and a sign flip here would turn a training's cost into
  # a bonus on exactly the turns this is meant to judge.
  measured = data.get("energy_cost")
  spend = abs(measured) if measured is not None else training_cost.cost(key)

  # A facility that spends nothing is never the turn to rest. Wit *returns*
  # energy, so it already does what the rest was wanted for, and it trains on
  # top of that - replaying career 13 without this, five of the nine turns the
  # rule took were wit boards paying 10 to 15 of their own stat, given up for
  # energy the wit turn would have handed back anyway. The same argument camp
  # already makes with camp_wit_safe.
  if spend <= 0:
    return None

  alternative = value + energy_value(-spend, energy_level, max_energy)
  banked = rest_score(energy_level, max_energy)
  if banked <= alternative + REST_MARGIN:
    return None
  return (f"the board is worth {alternative:.2f} after its energy cost while a"
          f" rest banks {banked:.2f} at {energy_level:.0f} energy")

def gamble_action(results, energy_level, max_energy):
  """The facility whose board is worth its failure chance, or None.

  Returns (key, note), so the caller can say in the log why a turn was taken at
  a failure chance the config refuses. None leaves the turn to the scorers.

  The energy cost is charged in FULL rather than discounted by the success
  odds, because a failed training spends the energy too. That is what keeps the
  rule off an empty tank, which is exactly where these boards show up: failure
  percentages climb as the bar drains, so the strongest board of a career tends
  to arrive on the turn least able to afford it.
  """
  if not GAMBLE_ON_GREAT_BOARD or not state.GAMBLE_ENABLED:
    return None

  best = None
  for key, data in (results or {}).items():
    # Wit is never the gamble: it costs no energy and hands it back, so it is
    # already the facility a low tank gives the turn to.
    if key == "wit":
      continue
    failure = int(data.get("failure") or 0)
    # At or under the bar there is nothing to override, and an Extreme burst
    # has already forced the failure chance to zero.
    if failure <= state.MAX_FAILURE or has_extreme_burst(data):
      continue
    if failure > state.GAMBLE_CEILING_FAILURE:
      continue
    own = (data.get(key) or {}).get("friendship_levels") or {}
    rainbows = own.get("yellow", 0) + own.get("max", 0)
    if rainbows < state.GAMBLE_MIN_RAINBOWS:
      continue
    # The raw printed stat points, skill excluded, so the gate stays legible
    # against the numbers on the screen. The comparison below uses the
    # weighted, headroom-clipped score instead.
    printed = sum(v for k, v in (data.get("gains") or {}).items()
                  if k != "skill")
    if printed < state.GAMBLE_MIN_GAIN_POINTS:
      continue
    value = training_value(results, key)
    if value is None:
      # Unreadable gains are unknown, not worthless - and a gamble is the last
      # thing to take on a board that could not be read.
      continue
    # A training that cannot be paid for is a stall, not a gamble: the energy
    # is spent whether or not it succeeds. This is what keeps the rule off an
    # empty tank, which is where these boards tend to appear - failure
    # percentages climb as the bar drains.
    spend = _spend_energy(data, key)
    if spend > energy_level:
      continue
    ev = value * (100 - failure) / 100.0 + energy_value(
      -spend, energy_level, max_energy)
    if best is None or ev > best[1]:
      best = (key, ev, failure, rainbows, printed)

  if not best:
    return None
  key, ev, failure, rainbows, printed = best

  # What the turn is otherwise worth: the best board the failure bar allows.
  #
  # A rest is deliberately NOT the comparison. This board is gone next turn and
  # a rest is not, so "bank the energy instead" gives up something the career
  # will not be offered again for something it can have on any turn - the same
  # argument the Extreme burst, the camp turns and the closing turns already
  # make, and the one rest_beats_training is written to stay clear of.
  #
  # Measured, that distinction is the whole rule: pricing career 13's Classic
  # Early Oct board (3 rainbows, +87 Speed, 52%) against a rest rejected it by
  # 0.1 points, because at ENERGY_POINTS_EMPTY 0.08 a rest on a 28/104 tank
  # scores 3.06 - about 24 Speed - against the gamble's 3.72. Taking it was
  # worth 42 Speed in expectation and the turn banked 4, so the comparison
  # that rejected it was the wrong one.
  alternative = 0.0
  alt_label = "nothing else safe"
  for other, data in results.items():
    if other == key:
      continue
    if (int(data.get("failure") or 0) > state.MAX_FAILURE
        and not has_extreme_burst(data)):
      continue
    other_value = training_value(results, other)
    if other_value is None:
      continue
    net = other_value + energy_value(
      -_spend_energy(data, other), energy_level, max_energy)
    if net > alternative:
      alternative, alt_label = net, other.upper()

  if ev <= alternative * state.GAMBLE_EV_MARGIN:
    return None
  return (key, (f"{rainbows} own rainbow(s) and +{printed} printed stat points"
                f" at {failure}% failure is worth {ev:.2f} in expectation,"
                f" against {alternative:.2f} for {alt_label}"))

def _spend_energy(data, key):
  """The energy this facility spends, as a positive number.

  abs() for the same reason rest_beats_training needs it: live, `energy_cost`
  is what check_energy_reserved read off the bar's dim tail and is positive,
  while the recorded careers in tests/fixtures/careers store the signed figure
  the log prints (-19). A sign flip here would turn a cost into a bonus on
  exactly the turns this is meant to judge.
  """
  measured = data.get("energy_cost")
  return abs(measured) if measured is not None else training_cost.cost(key)

def training_value(results, key):
  """Weighted value of one training, from the gains the game printed.

  None means the gains could not be read. Callers must treat that as unknown
  rather than worthless, or an unreadable screen would look like a wasted turn
  and hand every turn to Recreation.
  """
  if not key:
    return None
  data = (results or {}).get(key) or {}
  if not (data.get("gains") or {}):
    return None
  return gain_score(data, key)

def should_recreate(value, resting, energy_level, max_energy, mood_index,
                    mood_target, outing_available, debuffed, burst_ready=False,
                    training_key=None, measured_cost=None, duel_ready=False):
  """Whether a Recreation outing beats training or resting this turn.

  One comparison rather than the ladder of thresholds this used to be: what the
  next outing gives, against what the bot was about to do instead. Knowing the
  chain step is what makes that possible - step 5 carrying a hint level is
  worth several times step 1, and the old code priced them identically.

  Returns a reason string, or None to leave the existing decision alone.
  """
  if not outing_available:
    return None

  # An outing is priced mostly on the energy it hands back, which makes it bid
  # highest exactly when the tank is low - the same turns a burst is most
  # likely to be rested away. The outing keeps until next turn; the burst does
  # not, and it cannot fail, so it is not energy the turn should be spent on.
  if burst_ready:
    debug("An Extreme Spirit Burst is ready, so Recreation does not get this turn.")
    return None

  # Same argument for a duel: the outing keeps until next turn, the badge does
  # not. An outing bids highest exactly when the tank is low, which is when a
  # one-shot opportunity is most likely to be given away.
  if duel_ready:
    debug("A Duel! badge is on the board, so Recreation does not get this turn.")
    return None

  effects, label = outings.next_outing()
  outing = outing_score(effects, energy_level, max_energy, mood_index, mood_target, debuffed)

  if resting:
    alternative = rest_score(energy_level, max_energy)
    what = f"resting ({alternative:.2f})"
  elif value is None:
    # Unknown is not worthless: an unreadable gains strip must not hand the
    # turn to Recreation.
    debug(f"Outing worth {outing:.2f} [{label}], but the training gains would not read.")
    return None
  else:
    # The facility's own cost, not an average: wit returns energy rather than
    # spending it, so charging it 25 made an outing look better than it was on
    # exactly the turns the wit band was trying to rescue.
    #
    # Measured beats the database. The training screen dims the slice of the
    # bar the training will spend, and that figure already includes the deck's
    # Energy Cost Reduction - on one measured turn guts cost 15.7 against a
    # base of 22. The database is the fallback for when the bar would not read.
    spend = training_cost.cost(training_key) if training_key else TRAINING_ENERGY_COST
    if measured_cost is not None:
      spend = measured_cost
    alternative = value + energy_value(-spend, energy_level, max_energy)
    what = f"training ({alternative:.2f} after its energy cost)"

  debug(f"Outing {outing:.2f} [{label}] vs {what}.")
  if outing < alternative + OUTING_MARGIN:
    return None
  return f"{outing:.2f} against {what} - {label}"

# Summer camp is Early Jul to Late Aug of the Classic and Senior years - four
# turns whose trainings are the strongest of the career, with every support on
# every facility. Arriving empty is how they get thrown away: in the Classic
# camp of a live run the bot trained three of the four and rested the fourth on
# energy 30, for want of about five energy it could have banked in June.
#
# Junior has no camp - the event tables carry "Summer Camp (Year 2)" and
# "Summer Camp (Year 3) Ends" and nothing for Year 1 - so June of the Junior
# year is an ordinary month and gets no special treatment.
SUMMER_CAMP_YEARS = ("Classic Year", "Senior Year")
# Energy to arrive at camp with.
SUMMER_PREP_ENERGY = 70
# How far ahead of camp to start banking. Two turns is enough for one rest to
# land and a second to cover a very low tank; looking further just spends good
# training turns on energy that would spill before camp.
SUMMER_PREP_TURNS = 2

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

def turns_until_summer(year_text):
  """Turns from now until the first camp turn, or None when there is none.

  The year string is "<Junior|Classic|Senior> Year <Early|Late> <Mon>", so
  "Junior Year Pre-Debut", "Finale Underway" and Trackblazer's "TS Climax
  Races Underway" have no month to read and fall out as None rather than
  needing their own cases. Returns None from Early Jul
  onwards too: once camp has started there is nothing left to prepare for.
  """
  parts = (year_text or "").split(" ")
  if len(parts) < 4:
    return None
  if f"{parts[0]} {parts[1]}" not in SUMMER_CAMP_YEARS:
    return None
  half, month = parts[2], parts[3]
  if half not in ("Early", "Late") or month not in MONTHS:
    return None
  now = MONTHS.index(month) * 2 + (1 if half == "Late" else 0)
  camp = MONTHS.index("Jul") * 2
  return camp - now if now < camp else None

# What one wit training hands back, for the camp-reachability check. The base
# alone, deliberately: a card's Wit Friendship Recovery only lands if that
# card is at max bond on the wit facility this turn, and this has to hold for
# every turn between here and camp. See WIT_RECOVERY_BASE for the measurement.
WIT_ENERGY_RETURN = WIT_RECOVERY_BASE
# Own rainbows a wit tile needs to be worth a pre-camp banking turn.
PREP_WIT_MIN_RAINBOWS = 1
# Sentinel for "spend this turn resting". Not a training key, so it cannot be
# confused with one.
SUMMER_REST = "rest"

def prep_wit_ready(results):
  """True when the wit facility is worth taking on a banking turn.

  A banking turn is spent to reach camp with a full tank, so the recovery is
  the entire point and one of wit's own rainbows is enough. A wit tile with
  none of them is still a weak training at any energy, so it does not
  qualify - the turn is better spent resting.
  """
  data = results.get("wit")
  if not data:
    return False
  if int(data["failure"]) > state.MAX_FAILURE and not has_extreme_burst(data):
    return False
  own_rainbows = (data["wit"]["friendship_levels"]["yellow"]
                  + data["wit"]["friendship_levels"]["max"])
  return own_rainbows >= PREP_WIT_MIN_RAINBOWS

def summer_prep_action(results, year_text, energy_level):
  """What a pre-camp turn should do, or None to leave the turn alone.

  Returns a training key, or SUMMER_REST. The order is what camp is worth:
  an Extreme burst first, because it is a guaranteed success that does not
  survive the turn; then a wit facility, which banks the turn and trains at
  the same time; then a plain rest, but only when the turns still to come
  could not close the gap without this one.
  """
  turns = turns_until_summer(year_text)
  if turns is None or turns > SUMMER_PREP_TURNS:
    return None
  if energy_level is None or energy_level >= SUMMER_PREP_ENERGY:
    return None

  burst_key = best_extreme_burst(results)
  if burst_key:
    return burst_key

  # Rests the turns after this one can still hold.
  later = REST_ENERGY_ESTIMATE * (turns - 1)
  if (SUMMER_PREP_ENERGY - (energy_level + WIT_ENERGY_RETURN) <= later
      and prep_wit_ready(results)):
    return "wit"
  if energy_level + later < SUMMER_PREP_ENERGY:
    return SUMMER_REST
  return None

CAMP_MONTHS = ("Jul", "Aug")

def camp_turns_left(year_text):
  """Camp turns remaining including this one, or None outside camp.

  Four at Early Jul, one at Late Aug. Used to tell a turn that still has
  turns to protect from the last one, which has nothing left to save for.
  """
  parts = (year_text or "").split(" ")
  if len(parts) < 4:
    return None
  if f"{parts[0]} {parts[1]}" not in SUMMER_CAMP_YEARS:
    return None
  half, month = parts[2], parts[3]
  if month not in CAMP_MONTHS or half not in ("Early", "Late"):
    return None
  now = MONTHS.index(month) * 2 + (1 if half == "Late" else 0)
  end = MONTHS.index("Aug") * 2 + 1
  return end - now + 1

def camp_wit_safe(results):
  """The wit facility exists and can be taken without failing.

  No rainbow bar here, unlike prep_wit_ready. This is only asked when the
  alternative is a rest, and a rest inside camp spends one of the four best
  turns of the career on nothing at all - a thin wit still beats it, and it
  hands energy back on top.
  """
  data = results.get("wit")
  if not data:
    return False
  return int(data["failure"]) <= state.MAX_FAILURE or has_extreme_burst(data)

def camp_action(results, year_text, energy_level):
  """What a camp turn should do, or None to leave it to the normal path.

  Camp is four turns and each is worth far more than any turn outside it, so
  the goal is four trainings rather than three good ones and a rest. Wit is
  what makes that reachable: it is the only facility that hands energy back,
  so a wit turn funds the turns after it instead of costing one.

  This is the preventive half: a tank that a normal training would push under
  the rest gate, moving the rest to next turn instead. The wit has to be worth
  taking on its own terms here, because a real training is still affordable.

  The other half - rescuing a turn that is about to be rested away for any
  reason at all - lives at the end of do_something, where every road to a
  rest meets. It used to live here and keyed on energy, which missed the
  rests that high failure caused rather than an empty tank.
  """
  left = camp_turns_left(year_text)
  if not left or energy_level is None:
    return None

  if (left > 1
      and energy_level - TRAINING_ENERGY_COST < state.SKIP_TRAINING_ENERGY):
    burst_key = best_extreme_burst(results)
    if burst_key:
      return burst_key
    if prep_wit_ready(results):
      return "wit"
  return None

# The year strings the game shows once a career's last races have started. URA,
# Unity and Grand Concert all write "Finale Underway"; Trackblazer writes its
# own.
CAREER_END_PHASES = ("Finale Underway", "TS Climax Races Underway")

def career_ending(year_text):
  """True on the last five training turns of a career.

  The window is found by the year string rather than by the turn counter,
  because the counter cannot do the job at either end of it:

    Senior Year Early Dec      1
    Senior Year Late Dec       2
    <phase> Underway           3, 4, 5 - one training turn before each of the
                               three finale races

  Inside the finale the counter always reads 1: it counts down to the next race
  day, not to the end of the career, so it cannot tell those three turns apart.
  And in Trackblazer's climax it reads -1, which is outside TURNS_LEFT_RANGE and
  means the box was unreadable - a rule keyed on the number would never fire
  there at all.

  Only the Senior December counts. Junior and Classic have Decembers of their
  own, two thirds and one third of a career from the finale, where energy
  banked by a rest still has turns to be spent on.
  """
  text = year_text or ""
  if any(phase in text for phase in CAREER_END_PHASES):
    return True
  return "Senior Year" in text and "Dec" in text

def final_stretch_action(results):
  """The best safe training on a career-ending turn, or None to rest after all.

  A rest banks about REST_ENERGY_ESTIMATE (50) for turns that are about to stop
  existing, while a training spends about DEFAULT_COST (21). With one turn left
  a rest can repay at most a fifth of what it banks, and even five turns out the
  ceiling is around 105 against the 50 banked plus whatever is already in the
  tank. So on these turns anything trainable beats resting, and unlike the camp
  rescue there is no reason to prefer wit: energy handed back has nothing left
  to fund, so the strongest board wins instead.

  Risk is still refused. Only facilities clearing MAX_FAILURE (or carrying an
  Extreme burst, which zeroes the failure chance) qualify, because a failed
  training here costs an injury and the finals with it - worth more than the
  stats of any single turn.
  """
  safe = {key: data for key, data in (results or {}).items()
          if int(data["failure"]) <= state.MAX_FAILURE or has_extreme_burst(data)}
  if not safe:
    return None
  return max(safe.items(), key=training_score)[0]

def gold_push_action(results, energy_level):
  """The safest facility paying a Performance type the 18th song is short of.

  None unless grand_concert.always_buy_gold_skill is on and Senior H2 is still
  short of 18 songs, so nothing changes for anyone not chasing the skill. A
  facility that would fail is never taken, and neither is one on an empty tank:
  a failed training costs more than the points are worth.
  """
  if not state.ALWAYS_BUY_GOLD_SKILL or energy_level < state.SKIP_TRAINING_ENERGY:
    return None
  import core.lessons as lessons
  if not lessons.pushing_for_gold(state.CURRENT_YEAR):
    return None
  paying = {}
  for stat, data in results.items():
    performance = data.get("performance") or {}
    short = set(performance.get("short") or ())
    if not short or int(data["failure"]) > state.MAX_FAILURE:
      continue
    hits = short & set(performance.get("types") or ())
    if hits:
      paying[stat] = len(hits)
  if not paying:
    return None
  # Most of the needed types first, then the user's stat order: this turn is
  # bought for the points, so the stat is only the tie-break.
  return min(paying.items(), key=lambda item: (-item[1], get_stat_priority(item[0])))[0]

def duel_action(results, energy_level):
  """The facility to take for a Happy Meek duel this turn, or None.

  URA Finale only, and only when `ura.chase_duels` is on. A duel pays a stat,
  skill points, a stat-cap raise and - the point of the whole thing - a hint for
  a Racing Spirit skill, all on top of the training's own gains and at no extra
  energy. It is worth more than the difference between two facilities, so it is
  decided ahead of the normal scorers rather than weighted into them.

  Three deliberate rules:

  - **0% failure, not MAX_FAILURE.** A failed training cancels the duel, so a
    risky duel is strictly worse than waiting for a safe one. That is tighter
    than the usual bar, so this opens no new unsafe path.
  - **Stamina first.** The duel offers the trained facility's own stat as
    option 1, so training Stamina is the only way `Contest of stamina!` is
    guaranteed to be on the board.
  - **Never on an empty tank.** A duel pays a normal training's stats; it does
    not pay for the forced rest on the turn after.
  """
  if not state.URA_CHASE_DUELS:
    return None
  if state.UNITY_SEEN or state.GRAND_CONCERT_SEEN:
    return None
  if energy_level < state.SKIP_TRAINING_ENERGY:
    return None
  badged = {key: data for key, data in results.items()
            if data.get("duel") and int(data["failure"]) == 0}
  if not badged:
    return None
  if "sta" in badged:
    return "sta"
  return max(badged.items(), key=training_score)[0]

def do_something(results):
  year = check_current_year()
  current_stats = stat_state()
  info(f"Current stats: {current_stats}")
  # Kept for the end-of-career notification: by the time the career is over the
  # lobby that shows these is gone, and this is the last turn that had them.
  state.LAST_STATS = current_stats
  game_caps = stat_caps_state()
  info(f"Stat caps on screen: {game_caps}")
  # Published before any scorer runs: gain_score reads it to discount gains
  # that would land in a stat with no room left.
  set_stat_headroom(current_stats, game_caps)
  # Published for wit's energy bonus, so rainbow_training and training_score
  # do not each take their own reading.
  energy_level, max_energy = check_energy_level()
  set_energy_level(energy_level, max_energy)

  filtered = filter_by_stat_caps(results, current_stats, game_caps)

  if not filtered:
    info("All stats capped or no valid training.")
    return None

  # ADVISORY ONLY - this decides nothing and changes no behaviour.
  #
  # The race-vs-train planner needs to know how good this turn's best training
  # is, and training_score is the number it would judge. But do_something only
  # reaches that scorer through most_support_card, so in any year that takes
  # the rainbow path it is never computed at all: it appears twice in a whole
  # career log, both times for wit. rainbow_training's own "total=" lines are a
  # different scale and cannot stand in for it.
  #
  # So score all five here and log what the planner would have concluded. That
  # gives real turns to calibrate STRONG_TRAINING_SCORE against before anything
  # is allowed to act on it. Costs no OCR - it is arithmetic over `results`,
  # which has already been read.
  try:
    scored = sorted(((training_score((key, data))[0], key)
                     for key, data in filtered.items()), reverse=True)
    if scored:
      best, best_key = scored[0]
      scores = {k: s for s, k in scored}
      debug("planner scores: " + ", ".join(f"{k}={s:.2f}" for s, k in scored)
            + f" | best {best_key.upper()}={best:.2f}")

      # What core/planner.py would decide, given this turn. Still advisory: the
      # verdict is logged and thrown away, so a career's worth of them can be
      # read back before anything is allowed to act on it.
      #
      # `opportunities` is a crude stand-in. The planner wants it in the goal's
      # own units - races for a count goal, fans for a fan goal - and all this
      # has is turns remaining, which is only an upper bound of one race per
      # turn, and plain wrong units for Result Pts. So the line prints the
      # inputs beside the verdict rather than presenting it as authoritative.
      goal = planner.parse_goal(_goal_context.get("criteria"))
      turns_left = _goal_context.get("turn")
      opportunities = turns_left if isinstance(turns_left, int) and turns_left >= 0 else None
      # Only facilities that could actually be trained reach the planner. A
      # score says nothing about failure, so an unsafe standout would otherwise
      # read as a turn worth protecting: measured 2026-09-18 on Senior Early
      # Dec, SPD scored 9.30 with every facility at 20-23% against a 15% bar,
      # and the real logic rested. The line above keeps all five on purpose -
      # that is calibration data, not an input.
      safe_scores = {key: score for score, key in scored
                     if int(filtered[key]["failure"]) <= state.MAX_FAILURE
                     or has_extreme_burst(filtered[key])}
      action, why = planner.decide(
        goal, opportunities, energy_level, safe_scores,
        skip_training_energy=state.SKIP_TRAINING_ENERGY)
      ratio = planner.training_is_worth_keeping(safe_scores)
      debug(f"planner would: {action or 'defer'} - {why}"
            f" [goal={goal}, opportunities={opportunities}"
            f" (turns-left proxy), energy={energy_level:.0f},"
            f" standout={ratio}]")
  except Exception as e:
    # Advisory only, so it must never be able to break a turn.
    debug(f"planner: advisory failed, ignored ({e}).")

  # A duel is one turn only and pays a hint the career cannot get any other way,
  # so it is decided before the scorers and before anything that can rest.
  duel = duel_action(filtered, energy_level)
  if duel:
    info(f"Taking {duel.upper()}: it carries the Duel! badge at 0% failure"
         + (" and Stamina is the one contest that has to be trained for." if duel == "sta" else "."))
    return duel

  # The run for the 18th song, when the config says the gold skill is wanted.
  # Banking energy is worth more than one turn of Performance points in every
  # other situation, but in Senior H2 a turn that pays a type the last song
  # still needs is a turn that cannot be had again: career 6 rested twice with
  # the needed chip on the board and finished on 17.
  push = gold_push_action(filtered, energy_level)
  if push:
    info(f"Taking {push.upper()}: it pays a Performance type the 18th song still"
         " needs, and grand_concert.always_buy_gold_skill is on.")
    return push

  # Inside camp: keep all four turns training rather than resting one away.
  camp = camp_action(filtered, year, energy_level)
  if camp:
    left = camp_turns_left(year)
    if camp == "wit":
      info(f"Summer camp, {left} turn(s) left and energy is {energy_level:.0f}."
           " Taking WIT: it trains and hands energy back, so the turns after"
           " it do not go to a rest.")
    else:
      info(f"Summer camp, {left} turn(s) left and energy is {energy_level:.0f},"
           f" and {camp.upper()} has an Extreme Spirit Burst ready. Taking it.")
    return camp

  # Bank energy for camp.
  prep = summer_prep_action(filtered, year, energy_level)
  if prep:
    turns = turns_until_summer(year)
    where = (f"Summer camp is {turns} turn(s) away and energy is"
             f" {energy_level:.0f}")
    if prep == SUMMER_REST:
      info(f"{where}. Resting to arrive with at least {SUMMER_PREP_ENERGY}.")
      return None
    if prep == "wit":
      info(f"{where}. Taking WIT, which trains and hands energy back instead"
           " of spending it.")
    else:
      info(f"{where}, but {prep.upper()} has an Extreme Spirit Burst ready."
           " Taking it.")
    return prep

  # A board the failure bar refuses but the odds say to take. After camp and
  # the summer prep, which are about turns whose value is certain, and before
  # the scorers, because it has to reach around both the failure filter and the
  # energy floor inside most_support_card.
  gamble = gamble_action(filtered, energy_level, max_energy)
  if gamble:
    gamble_key, why = gamble
    info(f"Taking {gamble_key.upper()} at a failure chance the"
         f" {state.MAX_FAILURE}% bar refuses: {why}.")
    return gamble_key

  if "Junior Year" in year:
    result, best_score = focus_max_friendships(filtered)

    # If the best option for raising friendship is just one friend, with no hint bonus
    if best_score <= 1.3:
      result = most_support_card(filtered)

  else:
    result = rainbow_training(filtered)
    if result is None:
      info("No training cleared the weight threshold; falling back to most_support_card.")
      result = most_support_card(filtered)

  if result is None:
    burst_key = best_extreme_burst(filtered)
    if burst_key:
      info(f"Resting would throw away the Extreme Spirit Burst on {burst_key.upper()}. Training it instead.")
      return burst_key
    # Whatever sent this turn to a rest - an empty tank, a board where only a
    # thin wit is safe - a rest inside camp spends one of the four best turns
    # of the career on nothing, and a safe wit trains and refills instead.
    left = camp_turns_left(year)
    if left and camp_wit_safe(filtered):
      info(f"Summer camp, {left} turn(s) left: resting would waste a camp turn,"
           " so taking WIT instead.")
      return "wit"

    # The same argument at the other end of the career: these turns do not come
    # again, so a rest banks energy the career will never get to spend.
    if career_ending(year):
      final = final_stretch_action(filtered)
      if final:
        info(f"{year}: resting this late banks energy the career cannot spend,"
             f" so taking {final.upper()} instead.")
        return final
      info(f"{year}: nothing clears the {state.MAX_FAILURE}% failure bar, so"
           " resting rather than risking an injury before the last races.")

  # Last: a training the scorers picked can still be worth less than the energy
  # the turn would bank. Everything above this point is about a turn that must
  # not be rested away, so it is decided after all of them and only ever turns a
  # training into a rest, never the other way round.
  if result is not None:
    why = rest_beats_training(filtered, result, year, energy_level, max_energy)
    if why:
      info(f"Resting instead of {result.upper()}: {why}.")
      return None

  return result

# helper functions
def decide_race_for_goal(year, turn, criteria, keywords):
  criteria_text = criteria or ""
  no_race = False, None
  any_race = False, "any"

  # Stop if Pre-Debut
  if year == "Junior Year Pre-Debut":
    return no_race
  
  # Re-run Maiden race asap
  if "Maiden" in criteria_text:
    return any_race

  # An unreadable turn counter used to fall straight through into racing. With
  # no idea how close the goal deadline is, not racing is the recoverable choice.
  if turn < 0:
    info("Turn count unknown, skipping the goal race check this turn.")
    return no_race

  # Stop if have more than 10 turns
  if turn >= 10:
    return no_race
  
  # Stop if no keywords found in criteria
  # Case-insensitive: the goal text reads "Fans" in game but the keyword is
  # "fan", so the exact-case check never matched and this branch was dead.
  if not any(word.lower() in criteria_text.lower() for word in keywords):
    return no_race
  
  info("Criteria word found. Trying to find races.")

  # Skip racing for fan randomly if already scheduled race within the time frame
  # if "fan" in criteria_text:
  #   schedule_race, schedule_turn = get_nearest_scheduled_race(year)
  #   if schedule_race and schedule_turn < turn:
  #     if schedule_turn == 0:
  #       return True, schedule_race["name"]
  #     info(f'Race {schedule_race["name"]} is in {schedule_turn} turns, skipping race for now.')
  #     return no_race

  # A goal naming a G1 - Oguri's "Progress: 2 G1 wins" and the like - can be
  # met by a particular race rather than whatever the aptitude search lands on.
  # This is the only thing prioritize_g1_race now controls: with it off, a
  # mission takes any race it can run, which is the safer default because
  # naming a race means selecting it by picture, and only G1s have pictures
  # (43 of 212 career races; no G2 or G3 has one).
  #
  # The caller reaches this only on turns the race schedule did not already
  # race, so a scheduled race always wins over a goal race on the same day.
  if state.PRIORITIZE_G1_RACE and "Progress" in criteria_text and any(
      word in criteria_text for word in ["G1", "GI"]):
    race_list = constants.RACE_LOOKUP.get(year, [])
    if not race_list:
      return no_race
    best_race = filter_races_by_aptitude(race_list, state.APTITUDES)
    if best_race:
      return True, best_race["name"]
    return no_race
 
  # if there's no specialized goal, just do any race
  return any_race

def filter_races_by_aptitude(race_list, aptitudes):
  GRADE_SCORE = {"a": 2, "b": 1}

  results = []
  for race in race_list:
    surface_key = f"surface_{race['terrain'].lower()}"
    distance_key = f"distance_{race['distance']['type'].lower()}"

    s = GRADE_SCORE.get(aptitudes.get(surface_key, ""), 0)
    d = GRADE_SCORE.get(aptitudes.get(distance_key, ""), 0)

    if s and d:  # both nonzero (A or B)
      score = s + d
      results.append((score, race["fans"]["gained"], race))

  if not results:
    return None

  # sort best → worst by score, then fans
  results.sort(key=lambda x: (x[0], x[1]), reverse=True)
  return results[0][2]

def get_nearest_scheduled_race(year_text):
  year_parts = year_text.split(" ")
  current_year = f"{year_parts[0]} {year_parts[1]}"
  current_date = f"{year_parts[2]} {year_parts[3]}"
  date_index = constants.DATE_ARRAY.index(current_date)
  total_dates = len(constants.DATE_ARRAY)

  year_order = {
    "Junior Year": 0,
    "Classic Year": 1,
    "Senior Year": 2,
  }

  current_year_order = year_order[current_year]

  print("state.RACE_SCHEDULE", state.RACE_SCHEDULE)

  # Find the first race that happens after current date
  for race in state.RACE_SCHEDULE:
    print("race", race)
    race_year_order = year_order[race["year"]]
    race_index = constants.DATE_ARRAY.index(race["date"])

    if race_year_order < current_year_order:
        continue  # skip past years

    if race_year_order == current_year_order and race_index < date_index:
        continue  # skip earlier races in same year

    # Calculate turn difference
    if race_year_order == current_year_order:
        turns = race_index - date_index
    else:
        turns = (race_year_order - current_year_order) * total_dates - date_index + race_index

    return race, turns

  # No upcoming race found
  return None, None
