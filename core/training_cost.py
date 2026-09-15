"""What a training costs in energy, per facility, from the game's own data.

`logic.TRAINING_ENERGY_COST` was a flat 25 for every facility. master.mdb
(`single_mode_training_effect`, `target_type` 10) says:

    Speed -21   Stamina -19   Power -20   Guts -22   Wit **+5**

so the constant overstated every facility by a few points and had the **sign
wrong on Wit**, which hands energy back rather than spending it. Wit is where
that mattered most: WIT_ENERGY_BAND exists to reward wit when the tank is low,
which was a hand-tuned patch sitting on top of a 30-point error underneath.

**What this deliberately does not model: support-card energy reduction.**
"Energy Cost Reduction" is effect type 28 in master.mdb, and the Grand Live
friend card discounts her own trainings, so the real cost on a given turn can
be lower than anything here. Two things block reading it, and neither is worth
guessing around:

- the deck cannot be identified. `state.check_support_card` recognises cards by
  **type icon only**, never by name, so there is nothing to key an effect lookup
  against;
- the game's Log states the true number ("Energy went down by 20."), but
  `outings.confirm_outing` records that a Log block cannot be reliably
  attributed to the action that caused it - it has come back holding the tail
  of a dialogue, and a goal event's "Skill Pts went up by 30" - and that
  "produced confident nonsense". Learning a per-turn decision input from an
  unreliable read is worse than a slightly high constant.

So these are base costs, and they are an underestimate of the discount rather
than a wrong number: the real cost is this or less. Closing the gap properly
needs either card identification on the training screen, or a dependable read
of the energy-bar preview - not a guess.
"""
import os
import sqlite3
from pathlib import Path

from utils.log import debug
import core.masterdb as masterdb

MDB_PATH = Path(masterdb.master_path())

# master.mdb command_id per facility, and the target_type that means energy.
COMMAND = {"spd": 101, "pwr": 102, "guts": 103, "sta": 105, "wit": 106}
ENERGY_TARGET = 10

# Used when master.mdb cannot be found (a non-default install without UMA_MASTER_MDB). Copied from the
# database rather than guessed, so the fallback agrees with the real thing.
FALLBACK = {"spd": -21, "sta": -19, "pwr": -20, "guts": -22, "wit": 5}

# For the one caller that has no facility in hand: the typical stat facility.
DEFAULT_COST = 21

_base = None

def _load_base():
  """{stat: energy change} from master.mdb. Negative is a cost."""
  global _base
  if _base is not None:
    return _base
  _base = dict(FALLBACK)
  if not MDB_PATH.exists():
    debug("training_cost: no master.mdb, using the built-in energy costs.")
    return _base
  try:
    con = sqlite3.connect(f"file:{MDB_PATH.as_posix()}?mode=ro", uri=True)
    for stat, command in COMMAND.items():
      row = con.execute(
        "SELECT effect_value FROM single_mode_training_effect "
        "WHERE command_id=? AND target_type=? ORDER BY sub_id LIMIT 1",
        (command, ENERGY_TARGET)).fetchone()
      if row:
        _base[stat] = row[0]
    con.close()
  except sqlite3.Error as e:
    debug(f"training_cost: master.mdb unreadable ({e}); using the built-in costs.")
  return _base

def change(stat):
  """Energy change for one training. Negative is a cost, positive a return."""
  return _load_base().get(stat, -DEFAULT_COST)

def cost(stat):
  """What a training *spends*, never negative. Wit returns energy, so 0."""
  return max(0, -change(stat))
