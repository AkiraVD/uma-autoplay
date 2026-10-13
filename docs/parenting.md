# Making a parent

Notes from community sources (2026-10-05), with what each one means for this
bot. Everything here is datamined or crowd-measured, not official: the odds are
the numbers three or four independent sites agree on, and where they disagree
both figures are given. Nothing in this file has been verified against our own
careers - `logs/` would be the place to check the blue-spark rates if a run of
parent careers ever accumulates.

The one hard change to know about: **Global took the 2nd-anniversary balance
patch on 2026-07-01**, which reworked affinity and halved the soft cap penalty
above 1200. Any guide written before July 2026 has the old affinity rules.

## 1. What a career hands you

The Spark Selection screen (`core/sparks.py`) always lists exactly one blue
(stat), one pink (aptitude) and one green (unique), plus however many white
(skill/race) sparks the career rolled. Each carries 1-3 stars. You get the set
whether the career was won or lost.

**Blue - one stat, picked uniformly at random from the five.** The star count
then comes from that stat's final value:

| final stat | 1★ | 2★ | 3★ |
|---|---|---|---|
| under 600 | 90% | 10% | 0% |
| 600-1100 | 45-50% | 44-50% | 5-6% |
| over 1100 | 20% | 70% | 10% |

Because the stat is chosen first, a career's chance at *any* 3★ blue is about
1.2% per stat at 600+ and 2% per stat over 1100. Pushing one stat to 1100 and
the rest over 600 is how a run is made eligible at all; a run with one stat at
1600 and the other four under 600 has a 2% chance of a 3★ blue and an 80%
chance the spark is for a stat you did not train.

What the spark is worth to the child: **1★ = +5, 2★ = +12, 3★ = +21** at career
start, and 1-28 when it procs at an inspiration event.

**Pink - chosen at random among every aptitude the uma holds at A or higher.**
This is the counter-intuitive one: *more* A aptitudes make a specific pink less
likely. If you are farming a Long pink, do not let Mile and Medium sit at A.

**Green - only generated if the trainee is at star unlock level 3 or above.** A
1★ or 2★ character cannot produce a unique-skill spark at all, however the
career goes.

**White - one roll per learned skill, per distinct G1 win, plus one for the
scenario final.** Generation chance per item:

| source | chance |
|---|---|
| normal skill | 20% |
| ◎ (double-circle) skill | 25% |
| gold skill | 40% |
| distinct G1 win | ~20% (no credit for winning the same race twice) |
| scenario final (URA Finale, Unity, TS Climax) | ~20% |

Each of those is raised by **+2.5% per family member who already carries that
same white spark**, up to 35% (40% for ◎) when all six relatives have it. That
is the whole mechanic behind "looping": a lineage built around the same handful
of skills reproduces them far more reliably than a fresh one.

There is no cap on white sparks. The count is simply how many skills you
learned and how many distinct G1s you won.

**Star count for white and green sparks comes from the career's final rank, not
from the skill.** Below SS: 45% / 50% / 5%. SS and above: 20% / 70% / 10%
(one source splits the top further, UE+ at 17.5% / 70% / 12.5%). Reaching SS is
the single biggest lever on white-spark quality, and rank is computed from
stats and skills only - aptitude, titles and race results do not feed it.

**Reroll.** 30 TP, once per selection, and the original set stays on offer, so
it is free value. The bot's rule (`core/sparks.py`) already keeps a 3★ blue,
otherwise rerolls and takes the better set.

## 2. What the child actually inherits

Sparks proc three times: at career start (parents, guaranteed-ish) and at the
two **inspiration events** in Early April of Classic and Senior year
(grandparents get their chance here too).

Base per-spark inheritance odds, before affinity:

| spark | 1★ | 2★ | 3★ |
|---|---|---|---|
| blue (stat) | 70% | 80% | 90% |
| pink (aptitude) | 1% | 3% | 5% |
| green (unique) | 5% | 10% | 15% |
| white, race | 1% | 2% | 3% |
| white, other | 3% | 6% | 9% |

Grandparent rates are halved (blue may be the exception). The modifier is
`odds = base × (1 + affinity / 100)`, where affinity is the *individual* score
with that relative - so one weak link drags its own sparks down even if the
displayed overall symbol is ◎.

Note how low pink and white are. A 3★ pink from a single parent is a 5% roll;
the 25-40% "chance of S aptitude" quoted in breeding guides is the whole
lineage rolling together across both inspiration events. Stacking the same
spark on several relatives is the only thing that makes those types reliable.

**Aptitude maths.** Pink stars from parents *and* grandparents are summed per
aptitude. The first grade costs 1 star, every grade after it costs 3 (so E→A is
1+3+3 = 7 stars), at most four grades at career start, and A→S only happens
through an inspiration proc. 10 stars is the cap considered at initialisation.

## 3. Affinity, after the July 2026 patch

- **+3 per G1 race both sides won.** G2 and G3 wins no longer count. Titles
  (Triple Crown, Triple Tiara and friends) no longer count. Base compatibility
  between characters was raised across the board to compensate.
- Winning the same G1 twice pays once.
- Scored between the trainee and each parent, and between the trainee and each
  grandparent; relatives also score against each other. An uma has 0 affinity
  with herself.
- Thresholds: **△ ≤50, ○ 51-150, ◎ >150**, and the scale is linear - 149→150 is
  worth exactly what 150→151 is, so ◎ is a convenience target, not a cliff.
- Lineage depth stops at grandparents.

Practical read: the affinity you can *build* comes almost entirely from running
the same G1s across the whole family. Base character affinity (real-life
lineage, same-surface racers) decides how much work that is, and gametora's
compatibility table is where to look it up before committing a run.

## 4. So: the parent career

1. **Decide what the parent is for first.** A parent is a delivery vehicle for
   one blue stat, one aptitude, one unique and a fixed set of whites. Pick the
   blue to be the stat the *child's* deck will not train.
2. **Target stat over 1100, every other stat over 600.** Under 600 a stat
   cannot roll 3★ at all, and the roll ignores what you trained.
3. **Keep exactly one distance/style aptitude at A+** if the pink matters.
4. **3★ character only**, if you want the green.
5. **Buy as many sparking skills as the points allow** - count, not quality
   (see below).
6. **Win as many distinct G1s as the schedule fits**, and the *same* ones across
   the lineage. The Tiara and Crown routes reach 24 G1s. Each shared one is +3.
7. **Finish at SS rank** for the better white/green star table. Rank is stats +
   skills, so 4-6 is where it comes from.
8. **Always reroll** unless the set already has what you came for.
9. **Build the lineage, not the uma.** Run the same deck and the same race plan
   for several generations: every relative already holding a white spark raises
   its generation chance on the next run, and grandparent sparks still proc.

Scenario, per the community guides: Trackblazer is the premier final-parent
scenario (no mandatory races, so the whole calendar is free for G1 overlap, and
it reaches SS consistently); Unity is the best loop *starter* because its five
scenario skills are inheritable; URA is the fastest at 13-20 minutes a career
but the hardest to get SS out of. Grand Concert lands between them on SP.

## 5. What this means for this bot

- **`skill.buy_mode = "parent"` is aimed at the right thing.** Maximising the
  count of inheritable skills is correct, and the `inheritable` filter happens
  to select mostly ◎ ranks, which share one generation chance (25%), so a flat
  value of 1 per skill is a fair objective *inside that set*. Two refinements
  the research suggests: a plain single-rank white rolls 20% against a ◎'s 25%,
  so `one_spark` could return 0.20/0.25 instead of 1.0 and break ties the right
  way; and the docstring's "a gold pays the same single white spark" is not
  quite true - a gold rolls 40%, i.e. 1.6x a ◎ for 3-4x the points. The
  conclusion (drop the golds) survives, the stated reason does not.
- **Stat caps decide blue eligibility, and `guts: 600` sits exactly on the
  line.** For a parent run, raise every cap to at least ~650 and put the
  intended blue stat over 1100. The current `[Down the Line] Mejiro Ryan` URA
  preset (spd 1600 / sta 1000 / pwr 1100 / guts 600 / wit 1200) would roll an
  off-stat blue 4 times in 5, and only speed is over 1100.
- **The 1200 soft cap is half as harsh since 2026-07-01** (excess counts at 1/2,
  not 1/8), which makes training past 1200 worth more than the older guides
  assume - for race performance *and* for rank, hence white-spark stars.
- **`ura.keep_sparks` is the right hook for a targeted parent run**: name the
  white spark the loop is built around and the bot keeps that set without
  rerolling it away.
- **`prioritize_g1_race` plus a race plan of distinct G1s is the affinity
  lever.** Nothing in the planner scores affinity today; the race plan is
  chosen for the career, not for the lineage. A parent run wants *breadth* of
  distinct G1s, and repeats of a G1 already won are worth zero affinity.
- Trackblazer being the recommended final-parent scenario is awkward: it is
  parked in `core/parked/` (2026-09-21). URA remains the practical choice here,
  with Unity for the scenario skills.
- Epithets (`core/epithets.py`) are unaffected by any of this - they are
  Trackblazer's own stat rewards, not the affinity "title bonus" the patch
  removed.

## Sources

- game8, *Legacy and Sparks Guide* and *How to Get 3 Star Sparks*
- uma.guide, *Sparks & Inheritance* and *Parenting in Umamusume*
- umareference.com, *Affinity*, *Chance of Inheriting Sparks*, *3 Star Spark
  Chance*, *Raising Aptitude*, *Parents to Try Making*
- eog.gg, *Parenting & Affinity*
- game8 / gametora, *July 2026 Balance Adjustments*
- Steam community discussions for the blue-spark odds cross-check

## 6. Worked example: Rudolf on Unity

`uma_configs/emperors-path-symboli-rudolf-unity-parent.json`, built from the
rules above. The reasoning, so it can be argued with:

- **[Emperor's Path] Symboli Rudolf** is a 3★ trainee (so a green spark is
  possible at all) with turf A, medium A, long A, pace A, late A, and growth
  **sta +20% / guts +10%**. Stamina is the stat she gets cheapest, and stamina
  is the blue a speed-trained child most wants, so the run is aimed at a
  **3★ Stamina blue**.
- Her pink is uncontrollable: she holds five aptitudes at A (turf, medium,
  long, pace, late) and the pink is drawn at random from exactly that set, so
  any given pink is a 1-in-5. All five are wanted in a turf mid/long lineage,
  which is the best that can be said for it.
- `stat_caps` are the shape of the run, not a ceiling nobody reaches: sta 1500
  and spd 1400 to put two stats over 1100 (2% each), pwr/wit 1000 and guts 900
  to clear 600 (1.2% each). That is ~7.6% per roll, about 16% a career once the
  reroll is counted. Guts at weight 0.6 may still land under 600; that costs
  1.2% and is not worth distorting the run for.
- **Ten distinct G1s**, all turf Medium or Long, none filly-only, none
  `ambiguous`, and - checked against master.mdb - every one of them pays a race
  Spark: Hopeful Stakes, Satsuki Sho, Derby, Takarazuka Kinen, Kikuka Sho,
  Japan Cup, Arima Kinen, Osaka Hai, Tenno Sho Spring, Tenno Sho Autumn. The
  Senior repeats of Takarazuka / Japan Cup / Arima are deliberately **not**
  scheduled: a second win of the same G1 pays no affinity and no second spark,
  and the turns are worth more as training.
- **`skill.buy_mode: "parent"`** with `skill_pts_check` raised to 800, so the
  knapsack runs on a real budget rather than buying three skills at a time.
- `ura.force_buy_skills` names the skills the count-maximiser would skip but
  that are worth their points here. Every one of them is `inheritable`, so none
  is a spark wasted: **It's On!** and the **Burning Spirit** family are
  inheritable *golds* (40% generation, against 25% for a ◎), and the
  Burning Spirit tier is the reason the unity burst weights are raised above
  their defaults - 13+ bursts pays a **Burning Spirit**, 9 or fewer pays an
  **Ignited Spirit**, and Ignited Spirit is `inheritable = False`. Nine bursts
  and thirteen bursts are the difference between a gold spark and nothing.
  `Pace Chaser Corners/Straightaways ◎` are there to win the ten races, and
  `Racing Spirit: *` is what the duels exist for.
- `keep_sparks` is left **empty** on purpose. It outranks the 3★-blue rule and
  skips the reroll, which is the wrong trade on a run whose whole point is the
  3★ blue. Fill it in only once the lineage is built around a named white.

Two machine-level things the preset cannot set, because they live in `bot.json`:

- **`reroll_sparks` is currently `false`.** Turn it on for parent farming. The
  original set stays on offer, so 30 TP is the only cost and it roughly doubles
  the career's chance at a 3★.
- `career_start.borrow_card` should be the support card carrying the white
  skills the loop is built around, not `Tazuna`, once there is a loop.

### An unrelated thing this turned up

**Queen Elizabeth II Cup is filly-only** (`single_mode_program.filly_only_flag`),
and so are Oka Sho, Japanese Oaks, Shuka Sho and Victoria Mile - unconditionally,
every program row. `chara_data.sex` is 2 for a filly-based trainee (Daiwa
Scarlet, Vodka) and 1 for the rest. **Mejiro Ryan is 1**, so the two
`Queen Elizabeth II Cup` entries in the Mejiro Ryan preset can never be
entered. Nothing in the bot checks the flag, so a schedule can quietly name a
race the trainee is not allowed to run.

## 7. Which uma makes a good parent

A parent is judged on four separate things - the blue it hands over, the pink,
the green, and the affinity it carries - and they point at different
characters. **Only one of the four is a question about *which uma*: the green.**
Any uma can be trained to hand over a 3★ stamina blue; only Maruzensky can hand
over `Red Shift`. So when the community calls a uma a good parent, it is
talking about her green, and that section is the one to read first - the other
three are properties of the *career*, not of the character.

There is still no single "best parent", because the green has to fit the
child's running style. The numbers below are computed from master.mdb
(`core/trainee.py`'s `catalog()`, which reads each **trainee** at its highest
rarity, plus `skill_data`'s effect table and the `succession_relation*`
tables), so they track patches. The judgement calls
about which unique skills are worth inheriting are community opinion, and are
marked as such.

**"Trainee", throughout, means the uma you raise, never a support card.** They
are separate tables - `card_data` holds the 109 trainees, `support_card_data`
the 259 support cards - and nothing in this section is about a support card.
One trainee has several *variants*, each its own `card_data` row with its own
star rating, aptitudes, growth and unique skill: `[Peak Joy] Tokai Teio` and
`[Beyond the Horizon] Tokai Teio` are two trainees for this purpose.

### Pink: the fewest A+ aptitudes wins

The aptitude spark is drawn uniformly from **every** aptitude the trainee holds
at A or above - surface, distance and style together - so a trainee with three
is a 1-in-3 for the pink you want and one with six is a 1-in-6. Across the 107
trainee variants with aptitude data: **22 hold three, 54 hold four, 27 hold
five, 4 hold six.**

The 22 three-aptitude trainees, by the distance they farm:

| distance | trainees |
|---|---|
| **Long** | **[Creeping Shadow] Manhattan Cafe** (turf/long/late, **sta +30%**) - the only one |
| Mile | [Formula R] and [Hot☆Summer Night] Maruzensky (turf/mile/front); [Shooting Star Revue] and [Succès Étoilé] Fuji Kiseki (turf/mile/pace) |
| Medium | [Peak Joy] (spd +20) and [Beyond the Horizon] Tokai Teio; [MB-19890425] (sta +20) and [CODE: ICING] Mihono Bourbon; [Crystalline] Mejiro Ardan (wit +20); [Dream Deliverer] / [Get to Winning!] Winning Ticket; [Jokester ☆ Vibes] Tosen Jordan; [Princess of Pink] Kawakami Princess; [Starry Nocturne] Admire Vega; [Tach-nology] Agnes Tachyon |
| Sprint | [Cheerleader in Noble White] / [King of Emeralds] King Halo; [Fille Éclair] / [Ma Chérie of the New Moon] Curren Chan; [Buono ☆ Alla Moda] Hishi Akebono; [Bestest Prize ♪] Haru Urara (dirt) |

**[Creeping Shadow] Manhattan Cafe is the standout parent in the game.** It is
the only three-aptitude Long trainee, and its +30% stamina is tied for the
highest growth rate on any trainee - so the same career farms the scarcest pink
at 1-in-3 *and* is the cheapest route to a 1100+ stamina blue. The other two
+30% trainees
([Bubblegum☆Memories] Taiki Shuttle, pwr; [unsigned] Air Shakur, wit) carry
four and five aptitudes.

**Dirt pinks are the scarce ones.** Only ten trainees hold dirt at A+ at all,
and the only three-aptitude one, [Bestest Prize ♪] Haru Urara, is a **1★
trainee** - no green spark until she is star-unlocked to 3★. The practical dirt parents are
Smart Falcon ([Twilight Triumph], [LOVE☆4EVER], dirt/mile/medium/front) and
[New Year ♪ New Urara!] Haru Urara at four.

The worst pink farmers, for completeness: both Tamamo Cross variants and both
Agnes Digital variants hold six.

### Blue: growth rate decides which stat is cheap

The blue is drawn uniformly from the five stats and starred off that stat's
final value, so the parent you want for a given blue is the one whose growth
bonus gets that stat past 1100 soonest:

| stat | best growth |
|---|---|
| spd | +20%: [Flare] Aston Machan, [Gilded Shrine to Glory] Kitasan Black, [Sapphire Sojourn] Mejiro Dober, [Twilight Triumph] Smart Falcon |
| sta | **+30%: [Creeping Shadow] Manhattan Cafe**; then +20%: Matikanetannhauser, [Turbulent Blue] Meisho Doto, [Rising☆Fortune] Matikanefukukitaru |
| pwr | **+30%: [Bubblegum☆Memories] Taiki Shuttle**; then +20%: Yaeno Muteki, [King of Emeralds] King Halo, [Poinsettia Ribbon] Nice Nature |
| guts | +20%: [Bestest Prize ♪] Haru Urara, [Nevertheless] Narita Taishin, [Authentic / 1928] Gold City, [Princess of Pink] Kawakami Princess |
| wit | **+30%: [unsigned] Air Shakur**; then +20%: Copano Rickey, [Crystalline] Mejiro Ardan, [Off the Line] Mejiro Dober |

### Green: the one that is actually meant by "a good parent"

When the community calls a uma a good parent, this is the dimension they mean.
The blue and the pink can be farmed off whoever is convenient; the **green is
the character**, and it is the only spark whose value depends on *who* ran the
career rather than how.

Three mechanics first:

- **A 3★+ uma is guaranteed a green at career end.** Below star unlock level 3
  there is none at all. That is her own star rating, the one star pieces raise -
  nothing to do with the support cards in the deck.
- **The unique is per variant, not per character.** [Peak Joy] Tokai Teio
  carries `Sky-High Teio Step`, [Beyond the Horizon] Tokai Teio carries
  `Certain Victory`; base King Halo carries `Call Me King` (evolving to
  `Prideful King`), [Cheerleader in Noble White] King Halo carries
  `Louder! Tracen Cheer!`. Which variant you raise decides which green exists.
- **The inherited copy is granted, not bought, and it is weaker.** No skill of
  rarity 3, 4 or 5 has a row in `single_mode_skill_need_point` - the 583 priced
  skills are 436 rarity-1 and 147 rarity-2 - and Global's master.mdb has no
  separate "inherited" skill ids, so the green hands the child the parent's own
  unique at reduced strength. The community figure for the reduction is roughly
  a step down the magnitude ladder (0.35 velocity arriving as 0.15); that number
  is **not** in this build's data, so treat it as a shape rather than a value.
  Whether the parent's unique *level* raises the spark's star count is disputed:
  one source says it does, another says the star count cannot be influenced.

**What makes a green good**, from master.mdb's own effect table
(`ability_type` 31 and 22 are acceleration, 27 and 21 velocity, 9 recovery;
`float_ability_value` the magnitude, `float_ability_time` the duration in
ten-thousandths of a second):

1. **Acceleration beats velocity.** Acceleration wins the positioning fight at
   the start of the last spurt; velocity raises a top speed the child is often
   already near.
2. **The trigger has to be one the child will meet.** Not one well-regarded
   unique is gated on `running_style`, `distance_type` or `ground_type` - they
   are gated on `order` and `order_rate`, which is the same restriction wearing
   different clothes. A green that needs `order==1` is worthless on a Late
   Surger.
3. **Magnitude × duration**, after the step-down.

Every green with 0.30 acceleration or more, all from 3★ variants:

| green | from | accel | for | velocity | trigger | suits |
|---|---|---|---|---|---|---|
| `Sunny Breeze` | [Fluttertail Spirit] Yamanin Zephyr | 0.30 | **4.8s** | - | later half of the final corner, within 50% of the leader; the fallback group drops even the `order==2` | **any style** |
| `Shooting Star` | [Special Dreamer] Special Week | **0.45** | 3.0s | - | second half, front half of the field, *having just lost a place* | any front-half |
| `Flowery☆Maneuver` | [Sunlight Bouquet] Mayano Top Gun | 0.40 | 3.0s | 0.35 | final corner after losing a place; two groups cover `order_rate<=40` **and** `50-80` | front **and** back |
| `Louder! Tracen Cheer!` | [Cheerleader in Noble White] King Halo | 0.40 | 2.4s | - | final corner exit - **no position gate at all** | **any style** |
| `Red Shift/LP1211-M` | [Formula R] Maruzensky | 0.40 | 2.4s | - | final corner, `order<=5` and front half | front / pace |
| `Shooting for Victory!` | [Wild Frontier] Taiki Shuttle | 0.40 | 2.4s | - | late final corner, `order>=3`, front 40% | pace / late |
| `Budding Blossom` | [Layered Petals] Nishino Flower | 0.40 | 2.4s | - | final corner, `order>=3`, front 40% | pace / late |
| `Condor's Fury` | [Kukulkan Warrior] El Condor Pasa | 0.40 | 2.4s | - | final corner, overtaking, `order>=4` within 75% | late / end |
| `Moving Past, and Beyond` | [Off the Line] Mejiro Dober | 0.40 | 2.4s | - | second-half corner, `order_rate 50-70` | late |
| `Angling and Scheming` | [Reeling in the Big One] Seiun Sky | 0.40 | 2.4s | - | on a corner, **`order==1`** | front only |
| `Victory Cheer!` | [Gilded Shrine to Glory] Kitasan Black | 0.30 | 3.0s | 0.50 | last phase on a straight, `order<=2` | front |
| `Festive Miracle` | [Ashen Miracle] Oguri Cap | 0.30 | 2.4s | 0.25 | needs three recovery skills already learned | medium / long |

Below that sits a **velocity-only heavy tier** - 0.80 total velocity across two
effect slots, no acceleration at all - worth taking only when the child's
acceleration is already covered: `The Duty of Dignity Calls` (Mejiro McQueen),
`∴win Q.E.D.` (Biwa Hayahide), `Shadow Break` (Narita Brian),
`Schwarzes Schwert` (Eishin Flash), `Eternal Encompassing Shine`
(Satono Diamond), `Shooting Star of Dioskouroi` (Admire Vega), `G00 1st. F∞;`
(Mihono Bourbon), `Barcarole of Blessings` (T.M. Opera O), `I'm Possible!`
(Seeking the Pearl), `Laugh at the Odds` (Nakayama Festa).

The style-agnostic velocity greens are worth knowing separately, because their
trigger is the same bare `is_finalcorner==1&corner==0` that makes
`Louder! Tracen Cheer!` universal, at 0.45 velocity for 3.0s and no position
requirement: `Sky-High Teio Step` and `Certain Victory` (the two Tokai Teio
variants), and `Prideful King` (evolved base King Halo). Symboli Rudolf's
`Behold Thine Emperor's Divine Might` is also 0.45 velocity but wants three
places gained first, and Oguri Cap's `Triumphant Pulse` is 0.45 velocity in a
200m window with `order 2-5`.

**Where this disagrees with the guides.** The community crowns Maruzensky's
`Red Shift/LP1211-M` as the best inheritable unique. The data agrees it is
excellent and says *why* - 0.40 pure acceleration, naming no style, distance or
surface - but two others look at least as good on the same terms and are never
mentioned: `Louder! Tracen Cheer!` has the same 0.40 acceleration with **no
position gate**, and `Sunny Breeze` carries 0.30 for twice the duration behind
a trigger that barely restricts anything. Magnitude × duration is a composite
of mine, not a figure the game states, and the inherited step-down is
unverified in this build - so treat the ordering inside a tier as soft and the
tier itself as solid.

Two warnings:

- **`skill_score.consistency()` must not be used to pick a green.** It scores
  how *often* a condition is met and knows nothing about acceleration being
  worth more than velocity, so it rates `The Duty of Dignity Calls` 0.97 and
  `Red Shift` 0.71 - exactly backwards for this purpose.
- A green is only worth chasing on a uma you hold at **3★**. Everything above
  is moot for a 1★ or 2★ copy until star pieces fix it.

### Affinity: the whole system is in master.mdb

`succession_relation` (1,616 groups, each worth **1, 2, 7 or 8** points),
`succession_relation_member` (3,212 memberships) and
`succession_relation_rank`, which states the thresholds the guides quote:
**rank 1 = 0-50, rank 2 = 51-150, rank 3 = 151+**. That is the game's own
answer on △ / ○ / ◎.

Summing group points over the 2,278 pairs of the 68 playable characters, a
single child↔parent link is a **median 19 and a maximum 43**. So base lore
affinity alone cannot reach ◎ for anybody: the displayed total is a sum of
several lineage links - and for a grandparent the group has to contain all
three of child, parent and grandparent, which is much rarer - plus **+3 per
shared G1**. The race plan is the controllable term, which is the whole reason
section 4 schedules ten distinct G1s.

Broadest base affinity, mean over the other 67 characters:

| | mean | | mean |
|---|---|---|---|
| Agnes Digital | 23.2 | Symboli Rudolf | 22.2 |
| T.M. Opera O | 23.0 | Super Creek | 22.1 |
| Mejiro McQueen | 22.7 | Gold Ship | 22.0 |
| Narita Brian | 22.6 | Rice Shower | 21.9 |
| Biwa Hayahide | 22.5 | Oguri Cap | 21.8 |
| Special Week | 22.4 | | |

and the floor: Haru Urara 9.4, Aston Machan 12.5, Copano Rickey 13.9,
Sakura Bakushin O 14.4, Maruzensky 14.6. Strongest individual pairs:
Tamamo Cross + Inari One and Smart Falcon + Copano Rickey at 43,
T.M. Opera O + Symboli Rudolf and T.M. Opera O + Biwa Hayahide at 40,
Vodka + Daiwa Scarlet and Symboli Rudolf + Rice Shower at 39.

Note that a *narrow* base affinity is not a verdict on a parent - Maruzensky
sits near the bottom of that table and still has the unique everyone wants to
inherit. It only means the lineage has to buy its ◎ with shared G1 wins.

### So who to farm

- **If the green is what you are farming** - and it usually is - pick by the
  child's running style off the table above, and prefer the three that fit any
  style: [Cheerleader in Noble White] King Halo, [Fluttertail Spirit] Yamanin
  Zephyr, or either Tokai Teio for the velocity version. [Formula R]
  Maruzensky is the community's pick and is not a mistake.
- **For the blue and the pink instead:** [Creeping Shadow] Manhattan Cafe. Long
  pink at 1-in-3, +30% stamina, turf/long/late so her race plan is the
  medium-long G1 core every other turf parent shares. But **her green is weak**
  - `Chasing After You` is 0.20 velocity and nothing else - so she is a
  stat-and-aptitude parent, not a skill one.
- **To glue a lineage together:** Symboli Rudolf, T.M. Opera O, Mejiro McQueen,
  Biwa Hayahide, Special Week - top of the base-affinity table and all turf
  medium/long, so they share the same G1 schedule and stack affinity on each
  other as well as on the child.
- **Avoid as parents, unless you want exactly their green:** both Tamamo Cross
  and both Agnes Digital variants (six A+ aptitudes, so the pink is a 1-in-6),
  and anything still at 1★ or 2★ if the green matters.
