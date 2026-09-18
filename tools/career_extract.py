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
  ("rest", re.compile(r"^All trainings are unsafe")),
  ("train", re.compile(r"^Training ([A-Z]+)\.$")),
]

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


def read_lines(paths, since=None):
  """Every log line from the files, in order, from `since` onward."""
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
        yield stamp, level, message


def extract(paths, since=None):
  """Group the log into one record per turn, keyed off the `Year:` line."""
  turns = []
  current = None
  for stamp, _level, message in read_lines(paths, since):
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
  ap.add_argument("--out", required=True, help="JSON fixture to write")
  ap.add_argument("--label", default="", help="name for this career")
  a = ap.parse_args()

  turns = extract(a.logs, a.since)
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
  return 0


if __name__ == "__main__":
  sys.exit(main())
