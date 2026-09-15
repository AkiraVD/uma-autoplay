"""tools/health.py's log analysis, against made-up log lines.

Run with `python tests/test_health.py` from the repo root. Only the pure part is
covered: the process, window, display and screen checks need a live desktop.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)

import health as H  # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def stamp(secs):
  secs %= 86400
  return f"{secs // 3600:02d}:{secs // 60 % 60:02d}:{secs % 60:02d}"

def lobby_pass(secs, turn, decision, year="Junior Year Pre-Debut"):
  t = stamp(secs)
  return [f"{t} INFO    Year: {year}", f"{t} INFO    Turn: {turn}",
          f"{t} INFO    Mood: GOOD", f"{t} INFO    {decision}"]

REST = "Energy 14 is under 35, resting instead of training."
START = 10 * 3600

def test_stuck_on_one_turn():
  lines = [f"{stamp(START)} DEBUG   [BOT] Starting..."]
  for i in range(20):
    lines += lobby_pass(START + 10 + i * 40, 6, REST)
  f = H.analyse_log(lines)
  ok("twenty readings of turn 6 are counted", f["passes_on_turn"] == 20, f["passes_on_turn"])
  ok("time on the turn spans first to last reading", f["secs_on_turn"] == 19 * 40, f["secs_on_turn"])
  ok("the repeated decision is reported", f["last_decision"] == REST, f["last_decision"])
  ok("a running bot is not read as stopped", f["stopped"] is False)
  ok("resting gets the confirmation hint", "Rest confirmation" in H.stuck_hint(f["last_decision"]))

def test_progressing_turns():
  lines = [f"{stamp(START)} DEBUG   [BOT] Starting..."]
  lines += lobby_pass(START + 10, 6, "Training SPD.")
  lines += lobby_pass(START + 60, 5, "Training STA.")
  lines += lobby_pass(START + 110, 5, "Training STA.")
  f = H.analyse_log(lines)
  ok("a new turn restarts the count", (f["turn"], f["passes_on_turn"]) == ("5", 2), (f["turn"], f["passes_on_turn"]))
  ok("the latest decision wins", f["last_decision"] == "Training STA.", f["last_decision"])

def test_restart_resets_the_count():
  lines = [f"{stamp(START)} DEBUG   [BOT] Starting..."]
  for i in range(10):
    lines += lobby_pass(START + 10 + i * 40, 6, REST)
  lines.append(f"{stamp(START + 500)} DEBUG   [BOT] Stopped.")
  lines.append(f"{stamp(START + 600)} DEBUG   [BOT] Starting...")
  lines += lobby_pass(START + 610, 6, REST)
  f = H.analyse_log(lines)
  ok("only the latest run counts", f["passes_on_turn"] == 1, f["passes_on_turn"])
  ok("a restarted bot is not stopped", f["stopped"] is False)

def test_stopped_run():
  lines = [f"{stamp(START)} DEBUG   [BOT] Starting..."]
  lines += lobby_pass(START + 10, 6, REST)
  lines.append(f"{stamp(START + 30)} DEBUG   [BOT] Stopped.")
  ok("a stop after the last start is seen", H.analyse_log(lines)["stopped"] is True)

def test_past_midnight():
  late = 23 * 3600 + 59 * 60 + 30
  lines = [f"{stamp(late - 5)} DEBUG   [BOT] Starting..."]
  lines += lobby_pass(late, 6, REST)
  lines += lobby_pass(late + 40, 6, REST)
  f = H.analyse_log(lines)
  ok("the clock keeps counting past midnight", f["secs_on_turn"] == 40, f["secs_on_turn"])

def test_turns_are_per_year():
  lines = [f"{stamp(START)} DEBUG   [BOT] Starting..."]
  lines += lobby_pass(START + 10, 1, "Training SPD.", year="Junior Year Late Dec")
  lines += lobby_pass(START + 60, 1, "Training SPD.", year="Classic Year Early Jan")
  f = H.analyse_log(lines)
  ok("the same turn number in a new year is a new turn", f["passes_on_turn"] == 1, f["passes_on_turn"])

def test_trouble_window():
  lines = [f"{stamp(START)} DEBUG   [BOT] Starting...",
           f"{stamp(START + 10)} WARNING Tutorial has come back 6 times and neither option helped",
           f"{stamp(START + 1500)} ERROR   Something broke",
           f"{stamp(START + 1600)} WARNING Not in the career lobby for 20 checks, trying to back out.",
           f"{stamp(START + 1610)} INFO    Year: Junior Year Pre-Debut"]
  trouble = H.analyse_log(lines)["trouble"]
  ok("old warnings fall out of the window", not any("Tutorial" in t for t in trouble), trouble)
  ok("recent errors and loop warnings are kept", len(trouble) == 2, trouble)

def test_no_log():
  f = H.analyse_log([])
  ok("an empty log has no turn and no trouble", f["turn"] is None and f["trouble"] == [])

for test in [test_stuck_on_one_turn, test_progressing_turns, test_restart_resets_the_count,
             test_stopped_run, test_past_midnight, test_turns_are_per_year, test_trouble_window,
             test_no_log]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
