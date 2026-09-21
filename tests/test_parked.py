"""core/parked/ must stay out of the bot's import graph.

Run with `python tests/test_parked.py` from the repo root.

A parked module that creeps back into an import is the failure this guards: it
would cost the hot path a template match or an import for a mode nobody can
select, and it would do so silently. So rather than reasoning about it, this
imports the bot the way main.py does and then asks sys.modules what came along.

It also checks the parked code still *works*, because core/parked/README.md
promises that unparking is a re-wiring job. Code kept but never run rots; code
kept and still under test does not. The behaviour of the parked modules is
covered by tests/test_shop_choice.py and tests/test_shop_read.py - this only
pins the seam between parked and live.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def test_the_bot_does_not_import_parked_code():
  import core.execute  # noqa: F401  - the whole bot hangs off this
  import core.state     # noqa: F401
  import core.scenarios  # noqa: F401
  leaked = sorted(m for m in sys.modules if m.startswith("core.parked"))
  ok("importing the bot pulls in nothing from core/parked", not leaked, leaked)

def test_no_source_file_outside_parked_imports_it():
  """Cheaper than the import check and catches a lazy `import` inside a branch,
  which sys.modules would miss until that branch actually ran."""
  offenders = []
  for base in ("core", "server", "tools", "utils"):
    for dirpath, _, names in os.walk(base):
      if "parked" in dirpath.split(os.sep) or "__pycache__" in dirpath:
        continue
      for name in names:
        if not name.endswith(".py"):
          continue
        path = os.path.join(dirpath, name)
        with open(path, encoding="utf-8") as fh:
          for lineno, line in enumerate(fh, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
              continue
            if "core.parked" in stripped:
              offenders.append(f"{path}:{lineno}")
  ok("no live module references core.parked", not offenders, offenders)

def test_main_py_too():
  with open("main.py", encoding="utf-8") as fh:
    src = fh.read()
  ok("main.py does not mention parked code", "parked" not in src)

def test_the_parked_trackblazer_mode_still_loads():
  import core.parked.trackblazer_mode as tb
  ok("its scenario table survived", tb.SCENARIO_TABLE["key"] == "trackblazer")
  ok("with its measured race-day position",
     tb.SCENARIO_TABLE["race_day_pos"] == (537, 908), tb.SCENARIO_TABLE["race_day_pos"])
  ok("and both templates", set(tb.TEMPLATES) == {"scheduled_race", "tb_shop"},
     sorted(tb.TEMPLATES))
  for key, path in tb.TEMPLATES.items():
    ok(f"{key}'s asset is still on disk", os.path.isfile(path), path)
  ok("and the two loop branches are still callable",
     callable(tb.open_scheduled_race) and callable(tb.visit_shop))

def test_the_live_scoring_tables_are_not_parked():
  """core/trackblazer.py and core/epithets.py back the Race Plan tab, so they
  are deliberately NOT in core/parked/. Parking them would break the page."""
  import core.trackblazer  # noqa: F401
  import core.epithets     # noqa: F401
  import server.race_plan as race_plan
  ok("race_plan still scores a grade", race_plan.trackblazer.points_for("G1", 1) > 0)
  for path in ("core/trackblazer.py", "core/epithets.py"):
    ok(f"{path} is still live", os.path.isfile(path), path)

if __name__ == "__main__":
  # Order matters for the first test: it must run before anything else has had
  # a chance to import a parked module into sys.modules.
  test_the_bot_does_not_import_parked_code()
  test_no_source_file_outside_parked_imports_it()
  test_main_py_too()
  test_the_parked_trackblazer_mode_still_loads()
  test_the_live_scoring_tables_are_not_parked()
  if failures:
    print(f"\n{len(failures)} FAILED: {failures}")
    sys.exit(1)
  print("\nall ok")
