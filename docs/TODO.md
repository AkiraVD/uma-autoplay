# TODO

Open work only. Everything resolved has been cut - the write-ups are in git
history (`git log -p docs/TODO.md`) and the measured screen layouts are in
`screen-map.md`.

## Scenarios

- **Unity: choose the team-race opponent.** The bot confirms whatever the game
  preselects. Everything needed is on screen - `Rank 23/28/40`, grades `E/F/G`,
  and a per-discipline circle/triangle/cross row in the confirmation modal.
  Beating a harder team raises team rank, which drives facility levels; losing
  it lowers them.
- **Trackblazer: not started.** Feasible by OCR - UMAT has a full OCR
  implementation - but not a liftable module: they fork the whole bot per
  scenario. The genuinely new parts are the ~54KB shop database, item purchase
  and item use. The scenario adds a coin shop refreshing every 6 turns, Grade
  Points replacing career goals, epithets and race routes, rival VS races, the
  Twinkle Star Climax finale and ~30-40 races. Start with a screen-mapping pass
  like `screen-map.md`.

## master.mdb

`core/masterdb.py` backs trainee data, training costs, skill names, costs and
rarity, and the server's pickers. Two uses are still open:

- `data/races.json` and `data/skills.json` still go stale on patches.
  `text_data` categories 28/29/32 are race names, 47/48 skill names.
- Category 181 (12,758 event names) would canonicalise event-name OCR the way
  skill names are canonicalised now.

## Untested paths, each waiting on a screen that has not appeared

- **`login_bonus`** has never fired live - zero occurrences in any log. It only
  shows after a reload or the daily reset, so it is fixture-verified only.
- **`set_skip_x2()`'s press path.** The button was already x2 when the handler
  first ran, so it read the state and returned without pressing. Its first real
  exercise is the next career start, when the game resets Skip to Off.
- **A skill row at max hint (level 5).** Mid-career buying has been watched
  refusing, never accepting.
- **A three-option event.** Only two-option panels have been seen, across 9 real
  ones. Nothing assumes a count, but the header spacing is unchecked and
  `LAST_EVENT_CHOICE_ICON_TOP` suggests up to five are possible.
- **The Effects-button fallback.** "Always display choice effects" has been On
  throughout, so the panel opens by itself and that path has never run.
- **`unity_begin_showdown`'s settle delay** against a live Team Zenith screen.

## Numbers that are reasoned rather than measured

Worth deriving properly if the behaviour ever looks wrong:

- Outings: `MOOD_POINTS`, `HINT_POINTS`, `CONDITION_CLEAR_POINTS`,
  `BOND_POINTS`, `TRAINING_ENERGY_COST`. Only the energy anchor has a
  derivation behind it, and the readback checks energy alone.
- The wit band's `(30, 70)` edges and its 0.9 per rainbow.
- `MAX_GAUGE_FRACTION = 0.75`. uma.guide gives a charging gauge no weight at
  all, so anything from 0 to just under one burst is defensible.
- `core/skill_score.py`'s weights are the source optimizer's, not measured here.

## Smaller open items

- **A career that ends with chain steps left** has spent outings on a chain it
  never cashed. `outings.steps_remaining()` exists but nothing calls it, and
  turns-left-in-career is not derived anywhere.
- **Only one friend card has ever been seen in a deck.** With two the panel
  lists both and the reader takes the first row.
- **`LOG_PANEL_REGION` assumes the Log tab is selected** in the right-hand
  panel. Left on Sparks or Agenda, the readback quietly finds nothing.
- **The readback checks energy only.** Hints, skill points and condition clears
  are parsed and logged but never judged - locating the right block of a
  scrolling Log proved unreliable.
- **The end-of-career stop message does not say which template matched.** The
  branch is `team_rank or game_nav` and both match on the home screen, so the
  log cannot say which caught it. Naming it would make the next such run
  self-evidencing.
- **Dialogue-only events still reach `select_event`.** `event_choice_1.png`
  matches a scenario event with no choices at all, costing an OCR pass and two
  fuzzy matches per dialogue event. Harmless, and logged at debug.
- **The failure-label OCR fallback** fires on about 7% of reads - 8 of 110 in a
  full career - and degrades safely, since an unreadable failure is treated as
  unsafe. Leave it unless the rate climbs.
- **`disable_singlemode`** is carried through `skill_score` but not used as a
  filter. 354 of 577 purchasable skills set it, which suggests "not buyable in a
  career", but that reading is unverified and filtering on a guess would hide
  skills that really are on offer.
- **Skill costs on screen are not read by the planner.** It takes them from the
  database, which assumes the OCR'd name resolved to the right skill.

## Parked: API / packet mode

UMAT's chain is UMAT -> HTTP localhost -> KUC / uma_viewer -> captured packets
-> CarrotJuicer, and CarrotJuicer hooks the decryption function in
libnative.dll - DLL injection, not passive sniffing. KUC is not publicly
available, the capture tooling targets Android or the DMM client rather than
Steam Global, and injecting into the game process is materially more detectable
than reading pixels and moving the mouse.

Worth revisiting only if Trackblazer's shop inventory, coin balance and grade
points turn out to be genuinely unreadable on screen.
