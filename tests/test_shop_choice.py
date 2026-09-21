"""What to buy off the Trackblazer shop shelf: core/parked/shop_choice.py.

PARKED with the mode on 2026-09-21 and still run, so the code core/parked/
keeps cannot rot between now and whenever someone unparks it.

Run with `python tests/test_shop_choice.py` from the repo root. Pure logic - it
reads `data/trackblazer_shop.json` through core/trackblazer.py and nothing else,
so there is no OCR and no stubbing.

The shelf below is the real one, read off a live career on 2026-09-17 and
written up in docs/screen-map.md: seven rows, every cost matching the file. Any
test that invents a shelf instead is testing the scorer against itself.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.parked.shop_choice as C          # noqa: E402
import core.trackblazer as TB         # noqa: E402

failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


# The stock as the game actually showed it, Junior Early Sep.
SHELF = [
  {"name": "Royal Kale Juice", "cost": 70},
  {"name": "Wit Scroll", "cost": 30},
  {"name": "Guts Ankle Weights", "cost": 50},
  {"name": "Guts Manual", "cost": 15},
  {"name": "Speed Notepad", "cost": 10},
  {"name": "Glow Sticks", "cost": 15},
  {"name": "Coaching Megaphone", "cost": 40},
]

ROOM = {"spd": 900, "sta": 900, "pwr": 900, "guts": 900, "wit": 900}


def names(rows):
  return [r["name"] for r in rows]


def test_every_measured_row_is_understood():
  """If a real row does not resolve, the plan is guessing rather than choosing."""
  unknown = [r["name"] for r in SHELF if TB.item(r["name"]) is None]
  ok("all seven live rows resolve in the catalogue", not unknown, unknown)
  mismatched = [(r["name"], r["cost"], TB.item(r["name"])["cost"])
                for r in SHELF if TB.item(r["name"])["cost"] != r["cost"]]
  ok("and the shelf costs match the file", not mismatched, mismatched)


def test_a_capped_stat_makes_its_item_worthless():
  """The one piece of career state a purchase genuinely needs."""
  entry = TB.item("Speed Notepad")
  with_room = C.value_of(entry, ROOM)
  capped = C.value_of(entry, dict(ROOM, spd=0))
  ok("Speed Notepad is worth something with room", with_room > 0, with_room)
  ok("and nothing at all when spd is capped", capped == 0, capped)
  picked = C.plan(SHELF, coins=10, headroom=dict(ROOM, spd=0))
  ok("so it is not bought when spd is capped", "Speed Notepad" not in names(picked), names(picked))


def test_the_trap_item_is_never_bought():
  """Energy Drink MAX EX: +8 max energy and no restore, for 50.

  The cheaper Energy Drink MAX gives +4 AND restores 5 for 30. The catalogue
  carries `trap: true` and seriru's guide says "you must not buy it"; nothing
  in the code read that flag until now.
  """
  trap = TB.item("Energy Drink MAX EX")
  ok("the flag is still on the item", bool(trap and trap.get("trap")), trap and trap.get("trap"))
  shelf = [{"name": "Energy Drink MAX EX", "cost": 50}]
  ok("and it is refused even with coins to spare",
     C.plan(shelf, coins=999, headroom=ROOM) == [], names(C.plan(shelf, 999, ROOM)))
  ok("scoring it returns nothing rather than a number",
     C.score_row({"name": "Energy Drink MAX EX", "cost": 50}, ROOM) is None)


def test_it_spends_what_it_has_and_no_more():
  shelf_total = sum(r["cost"] for r in SHELF)
  for coins in (0, 9, 10, 25, 100):
    picked = C.plan(SHELF, coins=coins, headroom=ROOM)
    spent = sum(r["cost"] for r in picked)
    ok(f"{coins} coins -> spends {spent}, within budget", spent <= coins)
    # The real assertion: a budget under the shelf total must *choose*, not
    # sweep. Asserting only "spent <= coins" passes trivially when the plan
    # happens to buy everything, which is how a vacuous version of this test
    # sat here looking green.
    if coins < shelf_total:
      ok(f"  and at {coins} it leaves something on the shelf",
         len(picked) < len(SHELF), f"took {len(picked)} of {len(SHELF)}")
  ok("nothing is affordable under the cheapest row",
     C.plan(SHELF, coins=9, headroom=ROOM) == [])


def test_energy_is_preferred_over_cheap_stat_items():
  """A deliberate policy call, set by ENERGY_POINT.

  An energy is worth 0.5-1.4 stat points by derivation (a ~21-energy training
  returns 10-30 stat points), and the bottom of that range put Vita 20 below a
  Speed Notepad. Every energy row must now out-rank every cheap stat row.
  """
  def per_coin(name):
    entry = TB.item(name)
    return C.value_of(entry, ROOM) / entry["cost"]

  worst_energy = min(per_coin(n) for n in ("Vita 20", "Vita 40", "Vita 65",
                                           "Royal Kale Juice"))
  best_cheap_stat = max(per_coin(n) for n in ("Speed Notepad", "Speed Manual",
                                              "Speed Scroll"))
  ok("the weakest energy item still beats the best cheap stat item",
     worst_energy > best_cheap_stat, f"{worst_energy:.2f} vs {best_cheap_stat:.2f}")

  ok("Royal Kale Juice leads the measured shelf",
     max(SHELF, key=lambda r: per_coin(r["name"]))["name"] == "Royal Kale Juice",
     max(SHELF, key=lambda r: per_coin(r["name"]))["name"])
  ok("and its Mood -1 is priced in, not ignored",
     C.value_of(TB.item("Royal Kale Juice"), ROOM)
     < 100 * C.ENERGY_POINT, C.value_of(TB.item("Royal Kale Juice"), ROOM))

  picked = C.plan(SHELF, coins=70, headroom=ROOM)
  ok("70 coins buys the Kale rather than a basket of stat items",
     "Royal Kale Juice" in names(picked), names(picked))


def test_the_plan_comes_back_in_shelf_order():
  """The caller ticks rows top to bottom; out-of-order means scrolling back."""
  picked = C.plan(SHELF, coins=1000, headroom=ROOM)
  order = [names(SHELF).index(n) for n in names(picked)]
  ok("picked rows are in shelf order", order == sorted(order), order)


def test_unknown_rows_are_skipped_not_guessed():
  shelf = SHELF + [{"name": "Nonexistent Widget", "cost": 5}]
  picked = C.plan(shelf, coins=1000, headroom=ROOM)
  ok("an unreadable row is never ticked",
     "Nonexistent Widget" not in names(picked), names(picked))
  ok("and explain() says why",
     any("not in the catalogue" in line for line in C.explain(shelf, 1000, ROOM)))


def test_a_drawback_clause_counts_against_the_item():
  """Ankle Weights raises training gains AND the energy cost."""
  weights = TB.item("Guts Ankle Weights")
  kinds = {e.get("kind") for e in (weights.get("effect") or [])}
  ok("the item carries an energy_cost_up clause", "energy_cost_up" in kinds, kinds)
  ok("and energy_cost_up scores negative",
     C._effect_value({"kind": "energy_cost_up", "percent": 20, "turns": 1}) < 0)


for test in [test_every_measured_row_is_understood,
             test_a_capped_stat_makes_its_item_worthless,
             test_the_trap_item_is_never_bought,
             test_it_spends_what_it_has_and_no_more,
             test_energy_is_preferred_over_cheap_stat_items,
             test_the_plan_comes_back_in_shelf_order,
             test_unknown_rows_are_skipped_not_guessed,
             test_a_drawback_clause_counts_against_the_item]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
