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
  performance = performance_bonus(x[1])
  total += performance
  # This is the path that otherwise ends in a rest, so the wit band has to
  # reach it as well or wit could never be picked over resting.
  own_rainbows = (x[1][x[0]]["friendship_levels"]["yellow"]
                  + x[1][x[0]]["friendship_levels"]["max"])
  wit_band = wit_band_bonus(x[0], own_rainbows)
  total += wit_band

  # Debug output
  debug(f"{x[0]} -> base={base}, multiplier={multiplier}, room={room:.2f},"
        f" unity={unity}, gains={gains:.2f}"
        + (f", performance={performance:.2f}" if performance else "")
        + (f", wit_band={wit_band:.2f}" if wit_band else "")
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
    possible_friendship += performance_bonus(data)
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

def performance_bonus(data):
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
  """
  performance = data.get("performance") or {}
  short = set(performance.get("short") or ())
  if not short:
    return 0.0
  weight = state.PERFORMANCE_URGENT_POINTS if performance.get("urgent") else state.PERFORMANCE_SHORT_POINTS
  hits = sum(1 for kind in performance.get("types") or () if kind in short)
  return hits * weight

# Rainbows a wit facility needs before it is worth taking. Wit trains slowly
# and is otherwise picked up for energy and skill points, so it has to earn
# the turn with its own rainbows rather than with borrowed ones - only
# wit-type cards at max bond on the wit facility count, which is what
# total_rainbow_friends measures.
WIT_MIN_RAINBOWS = 3

# Wit is the only training that hands energy back instead of spending it, so
# in the middle of the tank it is really buying the next turn: it keeps enough
# energy to take a good training at 0% failure when one shows up. That makes
# the honest comparison "wit or rest", not "wit or a real training".
#
# Below the band there is too little left for wit to get back to a safe level
# and resting is the right answer; above it the energy wit returns would spill
# and wit is just a weak training again.
WIT_ENERGY_BAND = (30, 70)
# Per wit rainbow, inside the band. Wit's case here rests on its own rainbows:
# a wit tile with none is a weak training whatever the energy is, so this
# scales rather than being a flat bonus.
WIT_BAND_POINTS_PER_RAINBOW = 0.9
# Inside the band wit needs fewer of its own rainbows to be worth considering,
# because it is being weighed against resting rather than against a good
# training. Without this the band could never fire: WIT_MIN_RAINBOWS keeps wit
# out of the running entirely below 3.
WIT_BAND_MIN_RAINBOWS = 1

# Energy at the time do_something ran, for the wit band. Read once per turn
# and published rather than re-read, the same way the stat headroom is.
_energy_level = None

# The goal text and turn counter, published by career_lobby before it calls
# do_something. They exist only for the advisory planner: do_something receives
# `results` and nothing else, so the criteria cannot reach it otherwise, and
# reading it again here would cost a second OCR pass on every turn.
_goal_context = {}


def set_goal_context(criteria=None, turn=None):
  """Publish this turn's goal text and turns-left for the advisory planner."""
  global _goal_context
  _goal_context = {"criteria": criteria, "turn": turn}
# Whether the last turn was inside the band, so entering and leaving it is
# logged once instead of on every turn - energy sits in the band most of the
# time, which made an every-turn line pure noise.
_in_wit_band = None

def set_energy_level(level):
  global _energy_level
  _energy_level = level

def in_wit_energy_band(energy_level=None):
  level = _energy_level if energy_level is None else energy_level
  if level is None or level < 0:
    return False
  low, high = WIT_ENERGY_BAND
  return low <= level <= high

def wit_min_rainbows():
  """How many of its own rainbows wit needs to be a candidate this turn."""
  return WIT_BAND_MIN_RAINBOWS if in_wit_energy_band() else WIT_MIN_RAINBOWS

def wit_band_bonus(stat_name, rainbows):
  """Extra weight for wit while energy sits where wit actually pays.

  Added on top of the usual score rather than replacing it, so the stat gains
  and support counts still decide between wit and a genuinely good training -
  this only has to win against resting.
  """
  if stat_name != "wit" or not rainbows:
    return 0.0
  if not in_wit_energy_band():
    return 0.0
  return rainbows * WIT_BAND_POINTS_PER_RAINBOW

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
    rainbow_points += performance_bonus(data)
    rainbow_points += wit_band_bonus(stat_name, total_rainbow_friends)
    rainbow_candidates[stat_name]["rainbow_points"] = rainbow_points
    rainbow_candidates[stat_name]["total_rainbow_friends"] = total_rainbow_friends

  # Get rainbow training
  rainbow_candidates = {
    stat: data for stat, data in results.items()
    if (int(data["failure"]) <= state.MAX_FAILURE or has_extreme_burst(data))
       and data["rainbow_points"] >= 2
       and not (stat == "wit" and data["total_rainbow_friends"] < wit_min_rainbows())
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
# about 50 energy and costs one turn, and a turn is worth about one average
# training - call it 2.5 - so energy is worth about 0.05 a point at the bottom
# of the tank. Pricing it against the training instead (25 energy buys a 2.0
# training, so 0.08 a point) double counts: the training spends a turn as well
# as the energy, and turns are the scarcer resource for most of a career.
ENERGY_POINTS_EMPTY = 0.05
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
  """
  if delta >= 0:
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
                    training_key=None, measured_cost=None):
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

# What one wit training hands back. Wit is the only facility that returns
# energy instead of spending it, which is what lets it stand in for a rest.
# Deliberately conservative: it only has to be enough to show that taking wit
# does not put camp out of reach.
WIT_ENERGY_RETURN = 5
# Sentinel for "spend this turn resting". Not a training key, so it cannot be
# confused with one.
SUMMER_REST = "rest"

def prep_wit_ready(results):
  """True when the wit facility is worth taking on a banking turn.

  Held to WIT_BAND_MIN_RAINBOWS rather than the strict bar, and deliberately
  so: the strict bar exists because below the energy band wit cannot recover
  the tank on its own, and on a banking turn that recovery is the entire
  point. A wit tile with none of its own rainbows is still a weak training at
  any energy, so it does not qualify - the turn is better spent resting.
  """
  data = results.get("wit")
  if not data:
    return False
  if int(data["failure"]) > state.MAX_FAILURE and not has_extreme_burst(data):
    return False
  own_rainbows = (data["wit"]["friendship_levels"]["yellow"]
                  + data["wit"]["friendship_levels"]["max"])
  return own_rainbows >= WIT_BAND_MIN_RAINBOWS

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

def do_something(results):
  year = check_current_year()
  current_stats = stat_state()
  info(f"Current stats: {current_stats}")
  game_caps = stat_caps_state()
  info(f"Stat caps on screen: {game_caps}")
  # Published before any scorer runs: gain_score reads it to discount gains
  # that would land in a stat with no room left.
  set_stat_headroom(current_stats, game_caps)
  # Published for the wit energy band, so rainbow_training and training_score
  # do not each take their own reading.
  global _in_wit_band
  energy_level, _ = check_energy_level()
  set_energy_level(energy_level)
  banded = in_wit_energy_band()
  if banded != _in_wit_band:
    if banded:
      info(f"Energy {energy_level:.0f} entered the wit band {WIT_ENERGY_BAND};"
           " wit rainbows count for more until it leaves.")
    else:
      info(f"Energy {energy_level:.0f} left the wit band {WIT_ENERGY_BAND}.")
    _in_wit_band = banded

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
      action, why = planner.decide(
        goal, opportunities, energy_level, scores,
        skip_training_energy=state.SKIP_TRAINING_ENERGY)
      ratio = planner.training_is_worth_keeping(scores)
      debug(f"planner would: {action or 'defer'} - {why}"
            f" [goal={goal}, opportunities={opportunities}"
            f" (turns-left proxy), energy={energy_level:.0f},"
            f" standout={ratio}]")
  except Exception as e:
    # Advisory only, so it must never be able to break a turn.
    debug(f"planner: advisory failed, ignored ({e}).")

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
