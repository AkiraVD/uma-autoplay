# core/parked

Code the bot no longer runs, kept because it worked and the measurements behind
it were expensive.

**Nothing here is imported by `main.py` or anything it reaches.** That is the
whole point: a parked module must not cost the hot path a template match or an
import. `tests/test_parked.py` asserts it, so an accidental re-wiring fails a
test rather than quietly coming back.

## What is parked

| File | Was | Why |
|---|---|---|
| `trackblazer_mode.py` | the `TRACKBLAZER` table in `core/scenarios.py` and two `career_lobby()` branches | see below |
| `shop.py` | `core/shop.py` - drives the Climax Store shelf | Trackblazer-only |
| `shop_choice.py` | `core/shop_choice.py` - prices shop items against stat headroom | Trackblazer-only, pure |

**Trackblazer, parked 2026-09-21.** The mode played end to end on 2026-09-18,
holding RANK 1 through all three Twinkle Star Climax rounds. It was parked for
the Climax Store: a scrolling shelf with per-item costs, stock counts and a
coin balance that every turn of the mode has to read, sitting in the facility
row that a race day replaces. Two of the bot's worst loops came from that
corner - the agenda-race badge looping 302 times over 2h22m, and the bot
shopping on its own scheduled-race turn and then reporting "Training button is
not found" because it was standing in the shop.

## What is NOT parked, and must stay that way

`core/trackblazer.py` and `core/epithets.py` are **live**. They are data and
arithmetic - the points, coins and stat tables read out of master.mdb, and the
epithet definitions - and `server/race_plan.py` is built on them, so the config
page's Race Plan tab still works. Its totals are still denominated in
Trackblazer Result Pts; that is a scoring choice, not a live mode.

The cross-mode fixes that came out of the Trackblazer work stayed in
`core/execute.py` on purpose, because they guard traps every mode can hit:

- the **consecutive-races warning** handler, above the generic cancel
- the **scheduled-race notice** handler, same reason
- the **"Enter race?" confirmation** handler
- `game_panel_blank()`, the dead-client check

## Unparking

1. Put `SCENARIO_TABLE` back in `core/scenarios.py` and `"trackblazer"` back in
   `state.SCENARIOS` / `SCENARIO_NAMES`, and drop it from `PARKED_SCENARIOS`.
2. Merge `TEMPLATES` into `core/execute.py`'s templates dict.
3. Call `open_scheduled_race()` and `visit_shop()` from `career_lobby()` at the
   points their docstrings name - the order between them is load-bearing.
4. Put the mode back in `web/src/components/general/GameMode.tsx` and the zod
   enum in `web/src/types/index.ts`, then rebuild `web/dist`.
5. Delete the parked entry from `tests/test_parked.py`.

The measured positions never left `utils/constants.py`
(`TB_CLIMAX_RACE_MOUSE_POS`, `TB_TURN_DIGITS_REGION`, the `SHOP_*` family) and
the layouts are in `docs/screen-map.md`. `docs/TODO.md` has what was still
unfinished when it was parked.
