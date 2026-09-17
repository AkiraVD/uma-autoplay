"""Decide whether a turn is better spent racing or training.

**Pure logic.** Nothing here reads the screen, clicks, or imports core.state -
every input arrives as an argument, so the whole thing is testable without a
game. The caller owns perception; this owns the decision.

The shape comes from ten turns of advisory logging on real careers, not from
intuition, and three of those measurements overturned the obvious design:

1. **Energy decides more turns than score does.** Three of seven turns were
   settled by energy alone: the bot rested with the highest training score in
   the whole sample sitting on the board, because energy was 33 against a
   threshold of 35. A rule that says "train" on a turn the bot then rests is
   worse than no rule, so doability is checked first.

2. **An absolute score bar never says "race".** STRONG_TRAINING_SCORE is 2.0
   and the best facility cleared it on 7 turns out of 7 - scores ran 0.78 to
   8.42, so the bar sits near the floor. What separates a turn worth keeping
   from a cheap one is how far the best option stands above the rest: the
   best/median ratio ranged 1.18 (everything bunched, nothing to protect) to
   3.79 (one standout). Hence RATIO_WORTH_KEEPING rather than a score floor.

3. **The score must come from whichever scorer actually chose.** Junior uses
   focus_max_friendships, later years rainbow_training, and training_score
   named the same facility as the real chooser only once in four tries. So
   scores are passed in; this module never picks a scorer.

The racing half is a deadline/slack rule. Count what the goal still needs and
how many chances remain before it expires; race when there is no slack left,
and otherwise only when the turn is cheap.
"""
import re

# How far the best facility must stand above the median before a turn is worth
# protecting from a race. 1.5 sits between the flattest board measured (1.18)
# and the next one up (1.43); it is a starting point from ten turns, not a
# settled constant, and wants revisiting with a fuller sample.
RATIO_WORTH_KEEPING = 1.5

# Goal shapes, with the OCR damage they actually arrive with. "Achieved" comes
# through as "Achievedl", "MAX" as "MMAX", "After" as "After'" or "Aftert",
# "1st" as "Ist" - all observed in real logs, so the patterns are loose on the
# tail and strict on the numbers.
_ACHIEVED = re.compile(r"achieved", re.I)
_FANS_TO_GO = re.compile(r"([\d,]+)\s*fan\(s\)\s*to\s*go", re.I)
_RESULT_PTS = re.compile(r"([\d,]+)\s*Result\s*Pts.*?After.?\s*([\d,]+)\s*pts", re.I)
_PLACE_IN = re.compile(r"place\s+\w+\s+in\s", re.I)


def _int(text):
  return int(str(text).replace(",", "").strip())


def parse_goal(criteria):
  """What the goal still needs, as (kind, remaining), or None.

  Returns None when there is nothing to plan for: an achieved goal, a forced
  "Place 1st in <race>" objective (the game puts you in that race itself, so
  there is no decision to make), or text this does not recognise. None means
  "leave the turn to the existing logic", never "do nothing".

  The two measurable kinds report their progress in opposite directions, which
  is the trap here:

      "Earn 5000 fans Progress 3,828 fan(s) to go"   -> remaining IS 3828
      "300 Result Pts Progress After 88 pts"         -> remaining is 300 - 88

  The leading number on the fans line is not trustworthy - one real log reads
  "Earn 3000 fans ... 4,434 fan(s) to go", where the remainder exceeds the
  stated target - so the "to go" figure is taken and the target ignored.
  """
  text = (criteria or "").strip()
  if not text:
    return None
  if _ACHIEVED.search(text):
    return None
  if _PLACE_IN.search(text):
    return None

  hit = _FANS_TO_GO.search(text)
  if hit:
    return ("fans", _int(hit.group(1)))

  hit = _RESULT_PTS.search(text)
  if hit:
    target, done = _int(hit.group(1)), _int(hit.group(2))
    return ("points", max(0, target - done))

  return None


def slack(needed, opportunities):
  """Spare chances: how many race opportunities can be skipped and still make it.

  Negative means the goal cannot be met even by racing everything left, which
  is not a reason to stop racing - it is the reason to race every remaining
  turn, so callers treat <= 0 the same way.
  """
  return opportunities - needed


def training_is_worth_keeping(scores, ratio=RATIO_WORTH_KEEPING):
  """True when one facility stands clearly above the rest this turn.

  `scores` maps facility -> score from whichever scorer the caller used. The
  test is relative on purpose: an absolute floor was measured to pass on every
  single turn, so it could never release a turn for racing.

  One option is always "clearly best" by definition, and an all-zero board is
  not worth protecting.
  """
  values = sorted((v for v in (scores or {}).values() if v is not None), reverse=True)
  if not values:
    return False
  if len(values) == 1:
    return values[0] > 0
  mid = values[len(values) // 2]
  if mid <= 0:
    return values[0] > 0
  return (values[0] / mid) >= ratio


def decide(goal, opportunities, energy, scores,
           skip_training_energy, never_rest_energy=None,
           ratio=RATIO_WORTH_KEEPING):
  """(action, reason) for this turn: "race", "train" or None.

  None means "no opinion - use the existing logic", which is what an
  unrecognised goal or a missing reading gets. The order is the measured one:
  doability, then deadline pressure, then whether the turn is worth keeping.

  `energy` below `skip_training_energy` means the bot cannot train and would
  otherwise rest. Racing costs a turn either way and pays points, coins and
  fans, so a race beats a rest whenever there is any energy at all to race on.
  """
  if energy is None:
    return None, "energy unknown"

  can_train = energy >= skip_training_energy

  if not can_train:
    if energy > 0:
      return "race", (f"energy {energy:.0f} is under {skip_training_energy}, so this turn"
                      " cannot train - racing beats resting while there is energy to race on")
    return None, f"energy {energy:.0f} leaves nothing to race on either"

  if goal is None:
    return None, "no measurable goal this turn"

  kind, remaining = goal
  if remaining <= 0:
    return None, f"{kind} goal already met"

  if opportunities is None:
    # No count in the goal's units, so deadline pressure cannot be judged. Fall
    # through to the board rather than guessing: a wrong slack reading is worse
    # than none, because it always errs toward "race".
    if training_is_worth_keeping(scores, ratio):
      return "train", "no race count available, but this board has a standout"
    return None, "no race count in the goal's units"

  # Opportunities must be in the goal's own units: races for a count goal, but
  # points or fans for those. Turns-left is NOT a substitute - 212 points
  # against 9 turns gives slack -203, so every turn reads as "no time left" and
  # the board never gets a say. Refuse the comparison instead of letting a unit
  # mismatch masquerade as urgency.
  if kind in ("points", "fans") and opportunities < remaining / 10:
    if training_is_worth_keeping(scores, ratio):
      return "train", (f"{opportunities} is not a credible {kind} count for"
                       f" {remaining} needed, so judging on the board: standout")
    return None, (f"{opportunities} is not a credible {kind} count for"
                  f" {remaining} needed - units look mismatched")

  spare = slack(remaining, opportunities)
  if spare <= 0:
    return "race", (f"{remaining} {kind} still needed with only {opportunities} chance(s)"
                    f" left - no turn to spare")

  if training_is_worth_keeping(scores, ratio):
    return "train", (f"{spare} spare chance(s) and this board has a standout,"
                     " so the turn is worth keeping")

  return "race", (f"{spare} spare chance(s) and no standout training,"
                  " so the turn is cheap to spend racing")
