"""Lift a career's decisions out of its log into a replayable JSON fixture.

Reading a career back is how the training logic gets judged, but `logs/` is
gitignored and `utils/log.py` keeps only ten 1 MB backups - a career's evidence
is gone after about ten more runs, and a long career rotates *mid-run* so its
own start is already in `log.txt.1`. This writes the decisions into
`tests/fixtures/careers/`, which is tracked, so a change to the scorers can be
replayed against a real career instead of a hand-built board.

  python tools/career_extract.py logs/log.txt.1 logs/log.txt \
      --since 23:57:17 --out tests/fixtures/careers/trackblazer_20260918.json

Files are read in the order given, so pass the rotated backup first. `--since`
takes the timestamp of the run's `[BOT] Starting` line, because one log file
holds several careers.

One record per lobby turn: the board exactly as `check_training` read it, the
stats and caps behind it, the energy, what the bot then did, and the planner's
advisory verdict where one was logged - so the two can be compared without
re-running anything.
"""
import argparse
import ast
import json
import os
import re
import sys

LINE = re.compile(r"^(\d\d:\d\d:\d\d) (\w+) +(.*)$")

# The board line, as core/state.py writes it. Energy is optional because the
# wit line has carried a "(db -21)" tail and early careers had no cost at all.
FACILITY = re.compile(
  r"\[(\w+)\]\s*.\s*Total Supports (\d+), Levels:(\{[^}]*\})\s*,"
  r" Fail: (\d+)%, Gains: (\{[^}]*\})(?:, Energy (-?\d+))?")

# The per-type split, added 2026-09-18: `Split:[spd:max=2, friend:blue=1]`.
# Careers recorded before that have no Split clause, so it is matched
# separately and simply comes back empty for them - the aggregate in `Levels:`
# cannot be split back into types, which is why those careers cannot replay
# rainbow_training. See docs/backtest.md.
SPLIT = re.compile(r"Split:\[([^\]]*)\]")
SPLIT_ENTRY = re.compile(r"(\w+):(\w+)=(\d+)")

# Grand Concert only: the Performance types a scheduled song is still short of,
# and which of them each facility pays. `performance_bonus` is scored off this,
# so a career recorded without it cannot replay that term at all - it comes back
# 0.0 for every facility and the whole turn scores as if nothing were scheduled.
# Careers recorded before 2026-10-12 have no `performance` key for that reason.
PERFORMANCE = re.compile(r"^Performance: short of (\[[^\]]*\])( \(urgent\))?,"
                         r" chips (\{.*\})$")

# training_score's own breakdown, one line per facility. Recorded as an oracle
# rather than as input: a replay that rebuilds the board from `facilities` must
# land on the same `total`, and that is the only way to tell a scorer change
# from a reconstruction mistake. It also carries the one input the board line
# never prints - `total_hints` only reaches the score as a flat +0.5 on `base`,
# so the difference between the logged base and a rebuilt one recovers it.
SCORE = re.compile(r"^(spd|sta|pwr|guts|wit) -> base=([\d.]+), multiplier=([\d.]+),"
                   r" room=([\d.]+), unity=([-\d.]+), gains=([\d.]+)"
                   r"(?:, performance=([\d.]+))?(?:, wit_band=([\d.]+))?"
                   r"(?:, duel=([\d.]+))?, total=([-\d.]+)")

PATTERNS = {
  "year": re.compile(r"^Year: (.+)$"),
  "turn": re.compile(r"^Turn: (.+)$"),
  "criteria": re.compile(r"^Criteria: (.+)$"),
  "energy": re.compile(r"^Remaining energy guestimate = ([\d.]+)$"),
  "stats": re.compile(r"^Current stats: (\{[^}]*\})$"),
  "caps": re.compile(r"^Stat caps on screen: (\{[^}]*\})$"),
  "headroom": re.compile(r"^Stat headroom: (\{[^}]*\})$"),
}

# What the turn actually did. Order matters: the first match wins, so the
# reason lines beat the bare `Training X.` click that follows them.
#
# `do_train` logs `Training {KEY}.`, which is the one signal every path emits -
# Junior goes through focus_max_friendships, which logs no selection at all, so
# without this fallback the whole of Junior year records no decision.
#
# `do_rest` logs *nothing*: it clicks the rest button with no `text=`. So a rest
# is only visible through logic.py's reason lines, or inferred at the end from a
# scored turn that never trained. Never match `Selecting X training.` - that
# fires once per facility while check_training scans, five times a turn.
DECISIONS = [
  ("train", re.compile(r"^Training selected: (\w+) with training weight ([\d.]+)")),
  ("train", re.compile(r"^Summer camp, \d+ turn\(s\) left.*taking (WIT)")),
  ("train", re.compile(r"^.*: resting this late banks energy the career cannot"
                       r" spend, so taking (\w+) instead\.$")),
  ("rest", re.compile(r"^Energy .* is under .*, resting instead of training\.$")),
  ("rest", re.compile(r"^.*nothing clears the \d+% failure bar")),
  ("rest", re.compile(r"^No safe training found")),
  # NOT a rest, though it reads like one: logic.py follows this line with
  # `return "wit"`. Recorded as a rest it made two wit trainings in
  # grandconcert_kitasan_20261012 look like the scorer and the career
  # disagreeing, which is the one thing a backtest must not get wrong.
  ("train", re.compile(r"^All trainings are unsafe, but (WIT) is safe")),
  # A Recreation outing is a third thing a turn can do, and the turn trains
  # nothing - so inferring from "board scored, no training executed" labelled
  # it a rest. `do_something` never sees that choice (should_recreate makes it
  # afterwards), so a replay of the scorer cannot be judged against it either
  # way: it is kept as its own action so it can be excluded rather than scored.
  ("outing", re.compile(r"^Going on a Recreation outing")),
  ("train", re.compile(r"^Training ([A-Z]+)\.$")),
]

# --- the Lessons board ------------------------------------------------------
#
# Every visit logs its board card by card (lessons.describe), the Performance
# totals, and - since 2026-10-13 - the rest of what choose() is handed. Together
# that is the whole input, so a Lessons decision can be replayed the same way a
# training decision is. The card line is describe()'s own format:
#
#   Lesson card 2: technique 'Jazz Dance Basics' [Speed +4 Guts +4] (locked) 8/0/0/8/0
#
# The name comes through `!r`, so it is quoted with whichever quote it does not
# contain. The cost row is POINT_KEYS order (da, pa, vo, vi, co) and is absent
# when the row would not read.
LESSON_CARD = re.compile(
  r"^Lesson card (\d+): (technique|song|\?) (['\"])(.*?)\3"
  r" \[(.*)\] \((learnable|locked)(, scheduled)?\)(?: ([\d/]+))?$")
LESSON_POINTS = re.compile(r"^Performance points (\{[^}]*\}), reserve (\{[^}]*\}),"
                           r" (\d+) technique\(s\)")
LESSON_INPUTS = re.compile(r"^Lessons inputs: energy (-?[\d.]+)/([\d.]+), wit returns"
                           r" ([\d.]+), segment (\d+), songs (\d+) (\{[^}]*\}),"
                           r" page (\d+), spend_all (True|False)")
LESSON_ACTION = re.compile(r"^(Learning|Scheduling) (?:technique |song )?(['\"])(.*?)\2: (.*?)\.$")
LESSON_NONE = re.compile(r"^Lessons: (.*?)\.?$")
POINT_KEYS = ("da", "pa", "vo", "vi", "co")

PLANNER_SCORES = re.compile(r"^planner scores: (.*?) \| best")
PLANNER_WOULD = re.compile(r"^planner would: (\S+) - (.*?) \[goal=(.*?),")


def _dict(text):
  try:
    return ast.literal_eval(text)
  except (ValueError, SyntaxError):
    return None


def _turn_value(text):
  """`Turn:` is a number most turns and the string "Race Day" on others."""
  text = text.strip()
  try:
    return int(text)
  except ValueError:
    return text


def read_lines(paths, since=None, until=None):
  """Every log line of ONE career: from `since` to where that career ends.

  **Stopping matters as much as starting.** `--since` alone ran to the end of
  the file, so a log holding several careers produced a fixture holding several
  careers - 195 turns with Junior passed three times, which still satisfied
  every per-turn check and looked entirely healthy. Two such files were built
  and deleted on 2026-09-19 before this stop existed.

  A career ends at the next `[BOT] Starting` after the anchor. That is used in
  preference to `[BOT] Stopped`, which is not a reliable terminator: the bot can
  be stopped and restarted mid-career (F1, or the config page), and a career
  resumed after a stop is still the same career.
  """
  started = since is None
  for path in paths:
    with open(path, encoding="utf-8", errors="ignore") as handle:
      for raw in handle:
        hit = LINE.match(raw.rstrip("\n"))
        if not hit:
          continue
        stamp, level, message = hit.groups()
        if not started:
          if stamp == since and "[BOT] Starting" in message:
            started = True
          else:
            continue
        elif "[BOT] Starting" in message and stamp != since:
          return                      # the next career begins; this one is done
        if until and stamp >= until:
          return
        yield stamp, level, message


def extract(paths, since=None, until=None):
  """Group the log into one record per turn, keyed off the `Year:` line."""
  turns = []
  current = None
  for stamp, _level, message in read_lines(paths, since, until):
    hit = PATTERNS["year"].match(message)
    if hit:
      # A new Year line opens a turn. The facilities are read *before* it on
      # some paths and after on others, so a turn keeps whatever it has seen
      # since the last one rather than resetting the board here.
      carried = current.pop("_pending", {}) if current else {}
      current = {"time": stamp, "year": hit.group(1).strip(),
                 "facilities": carried}
      turns.append(current)
      continue

    if current is None:
      # Facilities read before the first Year line still belong to it.
      current = {"time": stamp, "year": None, "facilities": {}}
      turns.append(current)

    face = FACILITY.search(message)
    if face:
      key, supports, levels, fail, gains, energy = face.groups()
      record = {
        "supports": int(supports),
        "levels": _dict(levels),
        "failure": int(fail),
        "gains": _dict(gains),
        "energy_cost": int(energy) if energy is not None else None,
      }
      found = SPLIT.search(message)
      if found:
        by_type = {}
        for card_type, level, count in SPLIT_ENTRY.findall(found.group(1)):
          by_type.setdefault(card_type, {})[level] = int(count)
        record["split"] = by_type
      current["facilities"][key.lower()] = record
      continue

    # --- the Lessons board, one record per purchase attempt ------------------
    # The board is re-read after every purchase, so one visit can leave several
    # records. Card 1 opens one; the action line closes it. A board with no
    # action line (the visit was cut short, or the read would not settle) is
    # dropped rather than half-kept.
    hit = LESSON_CARD.match(message)
    if hit:
      slot, kind, _q, name, effects, flags, scheduled, price = hit.groups()
      if int(slot) == 1 or current.get("_board") is None:
        current["_board"] = {"at": stamp, "cards": []}
      cost = None
      if price:
        parts = price.split("/")
        if len(parts) == len(POINT_KEYS):
          cost = {k: int(v) for k, v in zip(POINT_KEYS, parts)}
      current["_board"]["cards"].append({
        "slot": int(slot) - 1,
        "kind": kind if kind != "?" else None,
        "name": name,
        # describe() joins the card's effect lines with "; ", and a single line
        # can still carry two stats ("Speed +4 Guts +4"), so this is the lines
        # back, not the stats.
        "effects": [e for e in effects.split("; ") if e and e != "no effects read"],
        "learnable": flags == "learnable",
        "scheduled": bool(scheduled),
        "cost": cost,
      })
      continue

    hit = LESSON_POINTS.match(message)
    if hit and current.get("_board") is not None:
      current["_board"]["points"] = _dict(hit.group(1))
      current["_board"]["reserve"] = _dict(hit.group(2))
      current["_board"]["to_page"] = int(hit.group(3))
      continue

    hit = LESSON_INPUTS.match(message)
    if hit and current.get("_board") is not None:
      energy = float(hit.group(1))
      current["_board"].update({
        "energy": None if energy < 0 else energy,
        "cap": float(hit.group(2)),
        "wit_return": float(hit.group(3)),
        "segment": int(hit.group(4)),
        "songs": int(hit.group(5)),
        # The per-segment counts, which the total cannot be split back into -
        # hype_songs_needed reads them, so choose() needs them to replay.
        "songs_by_segment": {int(k): v for k, v in (_dict(hit.group(6)) or {}).items()},
        "page": int(hit.group(7)),
        "spend_all": hit.group(8) == "True",
      })
      continue

    hit = LESSON_ACTION.match(message)
    if hit and current.get("_board") is not None:
      board = current.pop("_board")
      board["action"] = "learn" if hit.group(1) == "Learning" else "schedule"
      board["chose"] = hit.group(3)
      board["why"] = hit.group(4)
      current.setdefault("lessons", []).append(board)
      continue

    hit = LESSON_NONE.match(message)
    if hit and current.get("_board") is not None:
      board = current.pop("_board")
      board["action"] = "none"
      board["chose"] = None
      board["why"] = hit.group(1)
      current.setdefault("lessons", []).append(board)
      continue

    hit = SCORE.search(message)
    if hit:
      current.setdefault("scores", {})[hit.group(1)] = {
        "base": float(hit.group(2)), "multiplier": float(hit.group(3)),
        "room": float(hit.group(4)), "unity": float(hit.group(5)),
        "gains": float(hit.group(6)),
        "performance": float(hit.group(7)) if hit.group(7) else 0.0,
        "wit_band": float(hit.group(8)) if hit.group(8) else 0.0,
        "duel": float(hit.group(9)) if hit.group(9) else 0.0,
        "total": float(hit.group(10)),
      }
      continue

    hit = PERFORMANCE.search(message)
    if hit:
      chips = _dict(hit.group(3)) or {}
      current["performance"] = {
        "short": _dict(hit.group(1)) or [],
        "urgent": bool(hit.group(2)),
        "chips": chips,
      }
      continue

    for name, pattern in PATTERNS.items():
      if name == "year":
        continue
      hit = pattern.match(message)
      if hit:
        raw = hit.group(1)
        value = (_dict(raw) if raw.startswith("{")
                 else _turn_value(raw) if name == "turn"
                 else float(raw) if name == "energy" else raw)
        if name == "energy":
          # Keep the FIRST reading of the block and nothing later. A turn logs
          # energy several times: do_something reads it once before deciding,
          # most_support_card reads it again, and the next iteration's pre-turn
          # read lands here too because it comes before the next `Year:` line.
          # Overwriting gave every turn the energy *after* it acted - the rescue
          # turn recorded 44.07, the post-WIT refund, where the decision was
          # actually made at 38.98. The last one is kept separately, since
          # "what did the action do to the tank" is worth having too.
          current["energy_after"] = value
          current.setdefault("energy", value)
        else:
          current[name] = value
        break
    else:
      hit = PLANNER_SCORES.match(message)
      if hit:
        scores = {}
        for part in hit.group(1).split(", "):
          if "=" in part:
            k, v = part.split("=", 1)
            try:
              scores[k] = float(v)
            except ValueError:
              pass
        current.setdefault("planner", {})["scores"] = scores
        continue
      hit = PLANNER_WOULD.match(message)
      if hit:
        current.setdefault("planner", {})
        current["planner"]["verdict"] = hit.group(1)
        current["planner"]["why"] = hit.group(2)
        current["planner"]["goal"] = hit.group(3)
        continue
      for action, pattern in DECISIONS:
        found = pattern.match(message)
        if found and "action" not in current:
          current["action"] = action
          if action == "train" and found.groups():
            current["trained"] = found.group(1).lower()
          current["decided_by"] = message
          break
  return turns


def main():
  ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  ap.add_argument("logs", nargs="+", help="log files, rotated backup first")
  ap.add_argument("--since", help="timestamp of the run's [BOT] Starting line")
  ap.add_argument("--until", help="stop at this timestamp; normally unnecessary,"
                                  " since a career already ends at the next"
                                  " [BOT] Starting")
  ap.add_argument("--out", required=True, help="JSON fixture to write")
  ap.add_argument("--label", default="", help="name for this career")
  a = ap.parse_args()

  turns = extract(a.logs, a.since, a.until)
  # A turn with no board is a race day, a story screen or a partial read; keep
  # it, because "what did it do on the turns it could not score" is exactly the
  # question a backtest asks.
  scored = [t for t in turns if t.get("facilities")]
  # `do_rest` logs nothing at all, so a rest is only ever visible as the absence
  # of a train line. A turn that scored a board and then never trained rested,
  # and that is marked here rather than left as a hole - a backtest comparing a
  # new scorer against this one needs the rests most of all.
  for turn in scored:
    if not turn.get("action"):
      turn["action"] = "rest"
      turn["decided_by"] = "inferred: board scored, no training executed"
  # A visit left half-recorded - the log ended, or the board would not settle -
  # has cards but no action, and scoring a replay against "no decision" would
  # count as a miss. Drop those, and fall back to the turn's own energy reading
  # for logs written before `Lessons inputs:` existed (2026-10-13).
  visits = dropped = 0
  for turn in turns:
    turn.pop("_board", None)
    boards = turn.get("lessons")
    if not boards:
      continue
    keep = [b for b in boards if b.get("action")]
    dropped += len(boards) - len(keep)
    for board in keep:
      if "energy" not in board and turn.get("energy") is not None:
        board["energy"] = turn["energy"]
        board["energy_from"] = "turn"
    if keep:
      turn["lessons"] = keep
      visits += len(keep)
    else:
      turn.pop("lessons")
  payload = {
    "label": a.label or os.path.splitext(os.path.basename(a.out))[0],
    "source": {"logs": a.logs, "since": a.since},
    "turns": turns,
  }
  os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
  with open(a.out, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=False)
  print(f"  {len(turns)} turns ({len(scored)} with a scored board) -> {a.out}")
  acted = [t for t in turns if t.get("action")]
  print(f"  {len(acted)} turns carry a decision, "
        f"{len([t for t in turns if t.get('planner')])} carry a planner verdict")
  if visits or dropped:
    cap = len([b for t in turns for b in t.get("lessons", []) if b.get("cap")])
    print(f"  {visits} Lessons board(s) recorded ({cap} with the energy cap logged)"
          + (f", {dropped} half-recorded and dropped" if dropped else ""))
  return 0


if __name__ == "__main__":
  sys.exit(main())
