"""Grand Concert Lessons, against captured frames.

Run with `python tests/test_lessons.py` from the repo root. It builds an easyocr
Reader, because the card names and effects are OCR'd, so it is slow to start.

Fixtures in tests/fixtures/grand_concert/ (Mihono Bourbon, Junior Pre-Debut):
  lobby_locked.png          turn 1 lobby, Lessons still a locked "?"
  lobby_lessons_ready.png   turn 5 lobby, Lessons with the "!" badge
  lobby_song_scheduled.png  the same lobby after a song was scheduled, no "!"
  lessons_techniques.png    board: Power +5 (learnable), a hint (locked: Da 15
                            against 10 held), Skill Pts +5 (learnable)
  lessons_songs_locked.png  board: three songs, none learnable, the third
                            ("Here Comes Our Time") scheduled
  lesson_confirm.png, lesson_schedule.png, technique_learned.png,
  scheduling_complete.png   the dialogs and overlays that sit over the board
  training.png              the training screen, which must not read as Lessons
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.state as S          # noqa: E402
import core.lessons as L        # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "grand_concert")

def fixture(name):
  return Image.open(os.path.join(FIXTURES, name))

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def configure():
  S.SONG_PRIORITY = ["Run for Our Dream!", "Grow Up and Shine!", "Run n' Run!",
                     "Here Comes Our Time", "Believe in Miracles!"]
  S.SONG_PLAN = [4, 8, 12, 16, 18]
  S.HOLD_FOR_TOP_SONGS = 2
  S.ENERGY_TECHNIQUE_BELOW = 50
  S.PRIORITY_STAT = ["spd", "wit", "sta", "pwr", "guts"]
  S.PRIORITY_EFFECTS_LIST = {0: 1.3, 1: 1.1, 2: 0.95, 3: 0.4, 4: 0}
  L.reset()

def test_lobby_signals():
  ok("Lessons button found on the unlocked lobby", L.lessons_available(fixture("lobby_lessons_ready.png")))
  ok("and on the scheduled lobby", L.lessons_available(fixture("lobby_song_scheduled.png")))
  ok("but not before it unlocks", not L.lessons_available(fixture("lobby_locked.png")))
  tap = L.ready(fixture("lobby_lessons_ready.png"))
  ok("the ! badge reads as ready, tapped where the button is", tap and abs(tap[0] - 622) <= 4 and abs(tap[1] - 955) <= 4, tap)
  tap = L.ready(fixture("lobby_summer_camp.png"))
  ok("and at summer camp, where the button moves left", tap and abs(tap[0] - 552) <= 4 and abs(tap[1] - 955) <= 4, tap)
  tap = L.ready(fixture("lobby_finale_race_day.png"))
  ok("and on a Finale race day, where it sits beside the Race button", tap and abs(tap[0] - 753) <= 4 and abs(tap[1] - 915) <= 4, tap)
  ok("no ! badge, not ready", not L.ready(fixture("lobby_song_scheduled.png")))
  ok("locked button, not ready", not L.ready(fixture("lobby_locked.png")))
  ok("a Unity lobby is not Grand Concert",
     not L.lessons_available(Image.open(os.path.join("tests", "fixtures", "out_of_career", "in_career.png"))))

def test_screen_detection():
  ok("the technique board is the Lessons screen", L.on_lessons_screen(fixture("lessons_techniques.png")))
  ok("so is the song board", L.on_lessons_screen(fixture("lessons_songs_locked.png")))
  ok("and the career-end board, whose Concert Info has become Songs Learned",
     L.on_lessons_screen(fixture("lessons_career_end.png")))
  for name in ("lesson_confirm.png", "lesson_schedule.png", "technique_learned.png",
               "scheduling_complete.png", "training.png", "lobby_song_scheduled.png"):
    ok(f"{name} is not", not L.on_lessons_screen(fixture(name)))

def test_dialog_titles():
  """Learn and Schedule share a button, so the titles are what keep them apart.

  The second "Confirm" (learning over a scheduled song) sits on top of the
  first dialog. The first live visit read the Confirmation title behind it and
  cancelled five purchases in a row.
  """
  import utils.constants as C
  title = lambda name, region: L._read_text(fixture(name), region).lower()
  ok("technique Learn dialog", "confirm" in title("lesson_confirm.png", C.LESSON_DIALOG_TITLE_REGION))
  ok("song Learn dialog", "confirm" in title("song_confirm.png", C.LESSON_DIALOG_TITLE_REGION))
  ok("Schedule dialog", "schedule" in title("lesson_schedule.png", C.LESSON_DIALOG_TITLE_REGION)
     and "confirm" not in title("lesson_schedule.png", C.LESSON_DIALOG_TITLE_REGION))
  ok("the unschedule Confirm is seen", "confirm" in title("unschedule_confirm.png", C.LESSON_CONFIRM_TITLE_REGION),
     title("unschedule_confirm.png", C.LESSON_CONFIRM_TITLE_REGION))
  for name in ("song_confirm.png", "lesson_confirm.png", "lesson_schedule.png", "song_learned.png",
               "lessons_techniques.png"):
    ok(f"and not on {name}", "confirm" not in title(name, C.LESSON_CONFIRM_TITLE_REGION),
       title(name, C.LESSON_CONFIRM_TITLE_REGION))
  ok("Scheduling Complete", "scheduling" in title("scheduling_complete.png", C.LESSON_SCHEDULING_TITLE_REGION),
     title("scheduling_complete.png", C.LESSON_SCHEDULING_TITLE_REGION))
  for name in ("lesson_schedule.png", "unschedule_confirm.png", "song_learned.png", "lessons_songs_locked.png"):
    ok(f"and not on {name}", "scheduling" not in title(name, C.LESSON_SCHEDULING_TITLE_REGION))

def test_technique_board():
  cards = L.read_board(fixture("lessons_techniques.png"))
  for card in cards:
    print("     ", L.describe(card))
  ok("all three are techniques", [c["kind"] for c in cards] == ["technique"] * 3)
  ok("learnable flags", [c["learnable"] for c in cards] == [True, False, True])
  ok("names", "Vocal Training" in cards[0]["name"] and "Idol" in cards[2]["name"])
  ok("Power +5 parses", L.parse_effects(cards[0]["effects"]) == {"pwr": 5}, cards[0]["effects"])
  ok("the hint parses", "hint" in L.parse_effects(cards[1]["effects"]), cards[1]["effects"])
  ok("Skill Pts +5 parses", L.parse_effects(cards[2]["effects"]) == {"skill_pts": 5}, cards[2]["effects"])
  action, card, why = L.choose(cards, energy=80, year="Junior Year Pre-Debut")
  # Power weighs 0.4 here, so 5 skill points (4.5) beat 5 Power (2.0).
  ok("skill points over a low-weight stat", action == "learn" and card["slot"] == 2, f"{action} {card and card['name']} ({why})")
  S.PRIORITY_STAT = ["pwr", "spd", "wit", "sta", "guts"]
  action, card, why = L.choose(cards, energy=80, year="Junior Year Pre-Debut")
  ok("but Power when it is the top stat", action == "learn" and card["slot"] == 0, f"{action} {card and card['name']} ({why})")
  configure()

def test_board_settled():
  """Every captured board reads as settled; the mid-refresh read seen live does not."""
  for name in ("lessons_techniques.png", "lessons_songs_locked.png", "lessons_three_learnable.png",
               "lessons_song_learnable.png"):
    ok(f"{name} is settled", L.board_settled(L.read_board(fixture(name))))
  garbled = [{"slot": 0, "kind": None, "name": "I I n no n", "effects": ["Cpeed", "Nlone"]},
             {"slot": 1, "kind": "song", "name": "2", "effects": []},
             {"slot": 2, "kind": None, "name": "", "effects": []}]
  ok("the live mid-refresh read is not", not L.board_settled(garbled))

def test_career_end_board():
  """Drawn dimmed, because nothing can be bought after the Grand Concert. The
  bot no longer opens it, but the reader should still not misread it."""
  cards = L.read_board(fixture("lessons_career_end.png"))
  for card in cards:
    print("     ", L.describe(card))
  ok("the dimmed headers still read as techniques", [c["kind"] for c in cards] == ["technique"] * 3)
  ok("and all three are locked", not any(c["learnable"] for c in cards))

def test_song_board():
  cards = L.read_board(fixture("lessons_songs_locked.png"))
  for card in cards:
    print("     ", L.describe(card))
  ok("all three are songs", [c["kind"] for c in cards] == ["song"] * 3)
  ok("none learnable", not any(c["learnable"] for c in cards))
  ok("only the third is scheduled", [c["scheduled"] for c in cards] == [False, False, True])
  ok("song names match the priority list despite ! read as l",
     [L.song_rank(c["name"]) for c in cards] == [2, 4, 3], [c["name"] for c in cards])
  effects = L.parse_effects(cards[1]["effects"])
  ok("a song's training bonus is its own effect", effects.get("train_wit") == 1 and "wit" not in effects, effects)
  action, card, why = L.choose(cards, energy=80, year="Junior Year Pre-Debut")
  ok("nothing learnable and one scheduled: wait", action == "none", why)
  for c in cards:
    c["scheduled"] = False
  action, card, why = L.choose(cards, energy=80, year="Junior Year Pre-Debut")
  ok("nothing scheduled: reserve the best-ranked", action == "schedule" and card["slot"] == 0, f"{action} ({why})")

def test_song_policy():
  song = lambda slot, name, learnable, scheduled=False: {
    "slot": slot, "kind": "song", "name": name, "effects": [], "learnable": learnable, "scheduled": scheduled}
  # On schedule in Classic Early Apr: expected 4 + 4 * 7/12 = 6.3, target 8.
  total = lambda n: (L._songs.clear(), L._songs.update({0: n - 1}))
  total(7)
  board = [song(0, "Ring Ring Diary", True), song(1, "Run for Our Dream!", False), song(2, "Go This Way", True)]
  action, card, why = L.choose(board, 80, "Classic Year Early Apr")
  ok("holds for a top-2 song rather than burying it", action == "schedule" and card["slot"] == 1, why)
  board = [song(0, "Ring Ring Diary", True), song(1, "Believe in Miracles!", False), song(2, "Go This Way", True)]
  action, card, why = L.choose(board, 80, "Classic Year Early Apr")
  ok("does not hold for an ordinary song", action == "learn", why)
  # The live case, in this test's priority list: the reservation outranks the
  # only learnable song (live it was Our Blue Bird Days, 8, against Getaway! 21).
  reserved = [song(0, "Believe in Miracles!", True), song(1, "Here Comes Our Time", False, scheduled=True),
              song(2, "Ring Ring Diary", False)]
  total(9)   # Classic Early Aug: expected 8 + 4 * 3/12 = 9
  action, card, why = L.choose(reserved, 80, "Classic Year Early Aug", turn=9)
  ok("on schedule, a scheduled song is not dropped for a worse one", action == "none", why)
  total(9)
  action, card, why = L.choose(reserved, 80, "Classic Year Early Nov", turn=9)   # expected 11
  ok("behind schedule, any learnable song beats waiting", action == "learn" and card["slot"] == 0, why)
  held = [song(0, "Ring Ring Diary", True), song(1, "Run for Our Dream!", False), song(2, "Go This Way", True)]
  ok("and it does not hold for a top song either", L.choose(held, 80, "Classic Year Early Nov", turn=9)[0] == "learn")
  # The live case: Senior Early Jun, 13 songs, expected 12 + 4 * 11/12 = 15.7.
  total(13)
  live = [song(0, "Precious Treasure Box", False, scheduled=True), song(1, "Sky-Blue Spring", True),
          song(2, "Present March♪", True)]
  ok("the live Senior H1 board buys instead of waiting", L.choose(live, 80, "Senior Year Early Jun", turn=3)[0] == "learn")
  total(9)
  ok("unless it is the concert screen",
     L.choose(reserved, 80, "Classic Year Late Dec", turn=L.CONCERT_TURN)[0] == "learn")
  reserved[0]["name"] = "Run n' Run!"
  ok("a better learnable song still wins over the reservation",
     L.choose(reserved, 80, "Classic Year Early Aug", turn=9)[0] == "learn")
  L._songs.update({0: 3, 1: 4, 2: 4, 3: 4, 4: 9})
  ok("the Grand Concert ignores the plan", L.choose(board, 80, "Senior Year Late Dec", spend_all=True)[0] == "learn")
  locked = [song(0, "Ring Ring Diary", False), song(1, "Go This Way", False), song(2, "Dream Sky", False)]
  ok("and never schedules", L.choose(locked, 80, "Senior Year Late Dec", spend_all=True)[0] == "none")
  held = [song(0, "Ring Ring Diary", True), song(1, "Run for Our Dream!", False), song(2, "Go This Way", True)]
  ok("and never holds out", L.choose(held, 80, "Senior Year Late Dec", spend_all=True)[0] == "learn")
  configure()

def test_energy_technique():
  tech = lambda slot, effect: {"slot": slot, "kind": "technique", "name": effect, "effects": [effect],
                               "learnable": True, "scheduled": False}
  board = [tech(0, "Energy +30"), tech(1, "Speed +5"), tech(2, "Skill Pts +5")]
  ok("energy when low", L.choose(board, 30, "Classic Year Early Apr")[1]["slot"] == 0)
  ok("not when high", L.choose(board, 90, "Classic Year Early Apr")[1]["slot"] == 1)
  # The live case: Energy +30 learnable, the useful cards still locked.
  lonely = [tech(0, "Wit +8"), tech(1, "Energy +30"), tech(2, "Skill Pts +8")]
  lonely[0]["learnable"] = lonely[2]["learnable"] = False
  year = "Classic Year Early Apr"
  ok("a lone Energy technique at high energy waits", L.choose(lonely, 85, year, turn=7)[0] == "none")
  ok("for the rest of that turn", L.choose(lonely, 85, year, turn=7)[0] == "none")
  ok("and is bought the next turn", L.choose(lonely, 85, year, turn=6)[1]["slot"] == 1)
  L.reset()
  ok("bought straight away when energy is low", L.choose(lonely, 30, year, turn=7)[1]["slot"] == 1)
  L.reset()
  ok("and at career end", L.choose(lonely, 85, "Senior Year Late Dec", spend_all=True)[1]["slot"] == 1)
  L.reset()
  L.choose(lonely, 85, year, turn=7)
  other = [tech(0, "Wit +8"), tech(1, "Energy +20"), tech(2, "Skill Pts +8")]
  other[0]["learnable"] = other[2]["learnable"] = False
  ok("a different Energy card starts its own wait", L.choose(other, 85, year, turn=6)[0] == "none")
  L.reset()

def test_concert_screens():
  """The concert turn's three screens, each matched by the main loop's templates."""
  import core.execute as E
  from core.recognizer import multi_match_templates
  found = lambda name: multi_match_templates(E.templates, screen=fixture(name))
  screen = found("concert_screen.png")
  ok("the concert screen is recognised", bool(screen["gc_concert"]))
  ok("and is not mistaken for the lobby", not screen["tazuna"])
  ok("the lessons module agrees", L.on_concert_screen(fixture("concert_screen.png")))
  confirm = found("concert_confirm.png")
  ok("Start is found on the concert confirmation", bool(confirm["gc_concert_start"]))
  ok("the Concert button behind it is not", not confirm["gc_concert"])
  notice = found("schedule_notification.png")
  ok("To Lessons is found on the Schedule Notification", bool(notice["gc_to_lessons"]))
  ok("the Concert button behind it is not", not notice["gc_concert"])
  for name in ("lobby_junior_jul.png", "training_concert_turn.png", "concert_great_success.png",
               "concert_schedule.png", "lessons_songs_locked.png"):
    hits = found(name)
    ok(f"no concert template fires on {name}",
       not (hits["gc_concert"] or hits["gc_concert_start"] or hits["gc_to_lessons"]
            or hits["gc_bonuses_updated"]))
  ok("Bonuses Updated is recognised", bool(found("bonuses_updated.png")["gc_bonuses_updated"]))
  grand = found("grand_concert_screen.png")
  ok("the Grand Concert screen is recognised", bool(grand["gc_grand_concert"]) and not grand["tazuna"])
  ok("On Stage is recognised", bool(found("on_stage.png")["gc_on_stage"]))
  ok("the Grand Concert confirmation still has Start", bool(found("grand_concert_confirm.png")["gc_concert_start"]))
  ok("its skip box reads unticked", L.cutscene_unticked(fixture("grand_concert_confirm.png")))
  ok("and ticked once ticked", not L.cutscene_unticked(fixture("grand_concert_confirm_ticked.png")))
  ok("an ordinary concert has no box", not L.cutscene_unticked(fixture("concert_confirm.png")))
  for name in ("concert_screen.png", "lobby_junior_jul.png", "concert_confirm.png", "all_concerts_great.png"):
    hits = found(name)
    ok(f"no Grand Concert template fires on {name}", not (hits["gc_grand_concert"] or hits["gc_on_stage"]))
  for name in ("concert_great_success.png", "concert_schedule.png"):
    ok(f"{name} has a Next the generic handler can press", bool(found(name)["next"]))
  ok("a Unity lobby has none of them",
     not any(multi_match_templates(E.templates, screen=Image.open(
       os.path.join("tests", "fixtures", "out_of_career", "in_career.png")))[k]
       for k in ("gc_concert", "gc_concert_start", "gc_to_lessons")))

def test_career_end():
  """Grand Concert's career-complete screen: Skills / Complete Career / Lessons."""
  import core.execute as E
  import utils.constants as C
  from core.recognizer import multi_match_templates
  screen = fixture("career_complete.png")
  found = multi_match_templates(E.templates, screen=screen)
  ok("the career-complete branch fires", bool(found["career_complete"]))
  ok("and the screen says Grand Concert by itself", L.lessons_available(screen))
  # The URA Skills point is the gap beside Complete Career; this one must be on
  # the cyan Skills button.
  r, g, b = screen.convert("RGB").getpixel(C.GC_CAREER_COMPLETE_SKILLS_MOUSE_POS)
  ok("the Skills point is on the cyan Skills button", b > r and g > r, (r, g, b))
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  ok("the dimmed career-end Lessons board is not visited", "GC_CAREER_COMPLETE_LESSONS" not in source)

def test_performance_reader():
  """Chips per facility and the short types, off the training screen."""
  read = lambda name: S.check_performance(fixture(name))
  plain = read("training.png")
  ok("one chip per facility", plain["chips"] == {"spd": ["da"], "sta": ["vo"], "pwr": ["vo"],
                                                 "guts": ["vi"], "wit": ["co"]}, plain["chips"])
  ok("short of Vo and Co (22 more, 2 more)", plain["short"] == ["vo", "co"], plain["short"])
  rainbow = read("training_concert_turn.png")
  ok("friendship trainings carry two chips",
     sorted(rainbow["chips"]["sta"]) == ["vi", "vo"] and sorted(rainbow["chips"]["wit"]) == ["co", "vi"],
     rainbow["chips"])
  ok("the raised, selected facility is read too", rainbow["chips"]["spd"] == ["vi"], rainbow["chips"])
  lobby = read("lobby_junior_jul.png")
  ok("no chips outside the training screen", not any(lobby["chips"].values()), lobby["chips"])
  ok("the lobby panel's badge still reads", lobby["short"] == ["vo"], lobby["short"])
  ok("nothing scheduled, nothing short", read("lessons_techniques.png")["short"] == [])

def test_performance_bonus():
  import core.logic as G
  S.PERFORMANCE_SHORT_POINTS = 0.75
  data = lambda types, short: {"performance": {"types": types, "short": short}}
  ok("a chip of a short type scores", G.performance_bonus(data(["vo"], ["vo", "co"])) == 0.75)
  ok("two short chips score twice", G.performance_bonus(data(["vo", "co"], ["vo", "co"])) == 1.5)
  ok("a type already covered scores nothing", G.performance_bonus(data(["da"], ["vo"])) == 0)
  ok("nothing scheduled, nothing scores", G.performance_bonus(data(["vo"], [])) == 0)
  ok("other scenarios score nothing", G.performance_bonus({}) == 0)

def test_dispatch_order():
  """Concert branches sit above the generic handlers, which would otherwise
  cancel the Start dialog and close the notification."""
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  loop = source.index("def career_lobby")
  generic = source.index("# Generic handlers.", loop)
  for key in ("gc_to_lessons", "gc_concert_start", "gc_concert", "gc_bonuses_updated",
              "gc_grand_concert", "gc_on_stage"):
    at = source.index(f'matches["{key}"]', loop)
    ok(f"{key} is handled before the generic handlers", at < generic)

def test_song_plan():
  """The running plan: 4/8/12/16/18 in total, Make Debut included."""
  S.SONG_PLAN = [4, 8, 12, 16, 18]
  L.reset()
  song = lambda slot, name, learnable: {"slot": slot, "kind": "song", "name": name, "effects": [],
                                        "learnable": learnable, "scheduled": False}
  board = [song(0, "Ring Ring Diary", True), song(1, "Go This Way", True), song(2, "Dream Sky", False)]
  ok("Make Debut counts once debuted", L.total_songs("Junior Year Early Jul") == 1
     and L.total_songs("Junior Year Pre-Debut") == 0)
  L._songs[0] = 3
  ok("on plan in Junior (1 + 3 = 4): save", L.choose(board, 80, "Junior Year Late Nov", turn=3)[0] == "none")
  ok("but the concert screen still tops up Hype when short",
     L.choose(board, 80, "Junior Year Late Dec", turn=L.CONCERT_TURN)[0] == "none")
  L._songs[0] = 1
  ok("a concert short of its songs buys on the concert screen",
     L.choose(board, 80, "Junior Year Late Dec", turn=L.CONCERT_TURN)[0] == "learn")
  L._songs.update({0: 3, 1: 2})
  ok("behind plan in Classic H1 (6 of 8): buy", L.choose(board, 80, "Classic Year Early Apr", turn=5)[0] == "learn")
  L._songs.update({0: 3, 1: 4, 2: 4, 3: 4, 4: 1})
  ok("17 in Senior H2: still buying for the 18th", L.choose(board, 80, "Senior Year Late Nov", turn=4)[0] == "learn")
  L._songs[4] = 2
  ok("18 reached: save for the Grand Concert", L.choose(board, 80, "Senior Year Late Nov", turn=4)[0] == "none")
  ok("and the Grand Concert spends it all", L.choose(board, 80, "Senior Year Late Dec", spend_all=True)[0] == "learn")
  L.reset()

def test_lyrics_event():
  import core.events as V
  panel = [["Full Speed! hint +1"], ["Concentration hint +1"], ["Trackblazer hint +1"],
           ["Come What May hint +1"], ["Lane Legerdemain hint +1"]]
  ok("known by name", V.is_lyrics_event("Closer Together", []))
  ok("or by its options, when the name will not read", V.is_lyrics_event("", panel))
  ok("an ordinary event is not it", not V.is_lyrics_event("New Year's Resolutions",
                                                             [["Power +25"], ["Energy +20"], ["Skill Pts +20"]]))

def test_point_readers():
  """The five totals and each card's cost row, off the captured boards."""
  want_points = {"lessons_song_learnable.png": [14, 99, 23, 19, 29], "lessons_techniques.png": [10] * 5,
                 "lessons_points_one.png": [25, 27, 1, 23, 14],
                 "lessons_songs_locked.png": [10, 10, 10, 0, 10], "lessons_career_end.png": [30, 4, 25, 48, 31]}
  for name, want in want_points.items():
    got = L.read_points(fixture(name))
    ok(f"points on {name}", got and [got[k] for k in L.POINT_KEYS] == want, got)
  want_costs = {"lessons_song_learnable.png": [[0, 0, 21, 0, 21], [0, 21, 0, 21, 0], [21, 0, 0, 21, 0]],
                "lessons_techniques.png": [[0, 0, 10, 0, 0], [15, 0, 0, 0, 0], [0, 0, 0, 10, 0]],
                "lessons_songs_locked.png": [[14, 0, 0, 16, 14], [0, 21, 0, 0, 21], [0, 0, 32, 0, 12]],
                "lessons_career_end.png": [[0, 24, 0, 0, 0], [0, 30, 0, 0, 0], [0, 12, 12, 0, 0]]}
  for name, want in want_costs.items():
    got = [L.read_cost(fixture(name), i) for i in range(3)]
    ok(f"cost rows on {name}", [[c[k] for k in L.POINT_KEYS] for c in got] == want, got)
  songs = L.song_table()
  ok("the song table has the 21 learnable songs", len(songs) == 21, len(songs))
  ok("and its totals match GameTora", {k: sum(s["cost"][k] for s in songs) for k in L.POINT_KEYS}
     == {"da": 252, "pa": 201, "vo": 150, "vi": 275, "co": 196})
  ok("OCR'd names find their row", L.song_info("Fanfare for the Futurel")["cost"]["vi"] == 42)

def test_points_strategy():
  tech = lambda slot, name, effect, cost, learnable=True: {
    "slot": slot, "kind": "technique", "name": name, "effects": [effect], "learnable": learnable,
    "scheduled": False, "cost": dict(zip(L.POINT_KEYS, cost))}
  song = lambda slot, name, learnable=True, scheduled=False: {
    "slot": slot, "kind": "song", "name": name, "effects": [], "learnable": learnable, "scheduled": scheduled}
  pts = lambda *v: dict(zip(L.POINT_KEYS, v))
  total = lambda n: (L._songs.clear(), L._songs.update({0: n - 1}))

  # Senior H1, short of target: the technique that spares the reserve wins.
  # The cheapest Senior songs lean on Pa/Co and Da/Vi; with Da scarce, a Speed
  # technique (Da) must lose to a Wit one (Co) of equal value.
  L.reset()
  total(13)
  board = [tech(0, "Dance Step Advanced Class", "Speed +12", [24, 0, 0, 0, 0]),
           tech(1, "Composure Training Advanced Class", "Wit +12", [0, 0, 0, 0, 24]),
           tech(2, "Group Lesson Basics", "Skill Hint Lvl +1", [0, 15, 0, 0, 0], learnable=False)]
  S.PRIORITY_STAT = ["spd", "wit", "sta", "pwr", "guts"]
  action, card, why = L.choose(board, 80, "Senior Year Early Mar", turn=4, points=pts(20, 60, 40, 30, 120))
  ok("short of Da, it buys the Co technique instead of the Speed one", card and card["slot"] == 1, why)

  # On target: hold, no filler techniques.
  total(16)
  action, card, why = L.choose(board, 80, "Senior Year Early Jun", turn=3, points=pts(100, 100, 100, 100, 100))
  ok("on target, techniques are held", action == "none", why)
  action, card, why = L.choose(board, 80, "Senior Year Early Jun", turn=3, points=pts(100, 100, 100, 100, 330))
  ok("but a type near its cap (350) is spent", action == "learn" and card["slot"] == 1, why)
  energy_board = board[:2] + [tech(2, "Relaxing Body Massage", "Energy +30", [0, 30, 0, 0, 0])]
  action, card, why = L.choose(energy_board, 30, "Senior Year Early Jun", turn=3, points=pts(100, 100, 100, 100, 100))
  ok("and energy is bought when low", action == "learn" and card["slot"] == 2, why)
  # All 18 in Senior H2: nothing to hold for, the best technique is bought.
  total(18)
  L._songs[4] = 3
  L._songs[0] -= 3
  action, card, why = L.choose(board, 80, "Senior Year Early Sep", turn=9, points=pts(100, 100, 100, 100, 100))
  ok("with all 18 in Senior H2, techniques are bought rather than held", action == "learn" and card["slot"] == 0, why)

  # Senior H2: the cheapest learnable song, whatever its rank.
  total(16)
  songs_board = [song(0, "Precious Treasure Box"), song(1, "Present March♪"), song(2, "Hey, Guess What!", False)]
  action, card, why = L.choose(songs_board, 80, "Senior Year Early Aug", turn=9, points=pts(100, 100, 100, 100, 100))
  ok("Senior H2 buys the cheapest song (44) over a better one (68)", card and card["slot"] == 1, why)
  ok("and Senior H2 pace ends by Late Oct", L.songs_expected("Senior Year Late Oct") == 18)
  # Career 3, Pre-Debut: all three learnable, the scheduled Run n' Run! (44,
  # ranked 5) must beat Ring Ring Diary (42, ranked 19).
  L.reset()
  debut = [song(0, "Ring Ring_ Diary"), song(1, "Run n' Runl", scheduled=True), song(2, "Getawayl Fallin' Love")]
  ok("Pre-Debut is never behind pace", L.songs_expected("Junior Year Pre-Debut") == 0)
  action, card, why = L.choose(debut, 60, "Junior Year Pre-Debut", turn=5, points=pts(25, 27, 0, 23, 20))
  ok("Pre-Debut buys the better song, not the 2-point-cheaper one", card and card["slot"] == 1, why)
  action, card, why = L.choose(debut, 60, "Junior Year Late Nov", turn=5, points=pts(25, 27, 0, 23, 20))
  ok("and behind pace, a song within a few points of the cheapest still wins on rank",
     card and card["slot"] == 1, why)
  # Career 4, Classic Late Jan: 4 songs against a pace of 4.67 is not behind;
  # the reserved Full Speed Ahead! (rank 6, 7 Da short) is waited for.
  total(4)
  saved_priority = S.SONG_PRIORITY
  S.SONG_PRIORITY = ["Run for Our Dream!", "Full Speed Ahead! Umadol Power☆", "Believe in Miracles!"]
  early = [song(0, "Full Speed Aheadl Umadol Powerx", False, scheduled=True),
           song(1, "Our Blue Bird Days", False), song(2, "Believe in Miraclesl")]
  action, card, why = L.choose(early, 80, "Classic Year Late Jan", turn=11, points=pts(25, 50, 19, 27, 28))
  ok("two turns into a segment, a reserved better song is waited for", action == "none", why)
  S.SONG_PRIORITY = saved_priority

  # Scheduling: the song closest to affordable.
  total(9)
  locked = [song(0, "Grow Up and Shine!", False), song(1, "Sunbeam Cheer", False), song(2, "Hoppity Sunny Days♪", False)]
  action, card, why = L.choose(locked, 80, "Classic Year Early Oct", turn=6, points=pts(0, 40, 0, 0, 20))
  ok("schedules the song closest to affordable", action == "schedule" and card["slot"] == 1, why)
  # Career 3, Classic Late Feb: Go This Way is 11 short against Getaway's 6,
  # close enough for its rank (12 against 21) to decide.
  total(6)
  locked = [song(0, "Hey, Guess Whatl", False), song(1, "Go This Way", False), song(2, "Getawayl Fallin' Love", False)]
  action, card, why = L.choose(locked, 80, "Classic Year Late Feb", turn=3, points=pts(15, 2, 17, 21, 14))
  ok("a song a few points further off but ranked higher is reserved", action == "schedule" and card["slot"] == 1, why)
  # Career 4, Senior H2: only the count matters there, so the closest wins
  # outright - it reserved rank 3 at 17 points short over rank 20 at 12.
  total(17)
  senior = [song(0, "Precious Treasure Box", False), song(1, "Hey, Guess Whatl", False)]
  action, card, why = L.choose(senior, 80, "Senior Year Late Sep", turn=6, points=pts(53, 12, 1, 9, 12))
  ok("in Senior H2 the closest song is reserved whatever its rank", action == "schedule" and card["slot"] == 1, why)

  # Carry-over on the concert screen, once the gauge is full.
  L.reset()
  L._songs.update({0: 3, 1: 3, 2: 3})
  plain = [song(0, "Sunbeam Cheer"), song(1, "Seven Colors Scenery", False), song(2, "Hoppity Sunny Days♪", False)]
  action, card, why = L.choose(plain, 80, "Classic Year Late Dec", turn=L.CONCERT_TURN, points=pts(100, 100, 100, 100, 100))
  ok("a plain song page is left to carry over", action == "none", why)
  L._note_year("Classic Year Late Dec")
  L._pattern.update({"pages": 3, "steps": 3, "purchases": 9})
  techs = [tech(0, "A", "Speed +8", [16, 0, 0, 0, 0]), tech(1, "B", "Skill Hint Lvl +1", [0, 15, 0, 0, 0]),
           tech(2, "C", "Wit +8", [0, 0, 0, 0, 16])]
  action, card, why = L.choose(techs, 80, "Classic Year Late Dec", turn=L.CONCERT_TURN, points=pts(100, 100, 100, 100, 100))
  ok("one technique from a page: the cheapest is bought to carry a page over", action == "learn" and card["slot"] == 1, why)
  L._pattern.update({"pages": 3, "steps": 0})
  action, card, why = L.choose(techs, 80, "Classic Year Late Dec", turn=L.CONCERT_TURN, points=pts(100, 100, 100, 100, 100))
  ok("four techniques away: points are held over the concert instead", action == "none", why)
  L.reset()

def test_pattern_tracking():
  L.reset()
  L._note_year("Classic Year Early Jan")
  ok("a new segment starts two techniques from a page", L.techs_to_next_page("Classic Year Early Jan") == 2)
  carried = {"kind": "song", "name": "Run for Our Dream!"}
  L._record_purchase(carried, "Classic Year Early Jan")
  ok("a carried song counts as the first step", L.techs_to_next_page("Classic Year Early Jan") == 1)
  ok("and is remembered as learned", "Run for Our Dream!" in L._learned)
  L._record_purchase({"kind": "technique", "name": "x"}, "Classic Year Early Jan")
  ok("one technique later the page is due", L.techs_to_next_page("Classic Year Early Jan") == 0)
  L._record_purchase({"kind": "song", "name": "Our Blue Bird Days"}, "Classic Year Early Feb")
  ok("after that page's song, the next needs two again", L.techs_to_next_page("Classic Year Early Feb") == 2)
  L._note_year("Classic Year Early Jul")
  ok("a concert resets the pattern", L._pattern["pages"] == 0 and L._pattern["steps"] == 0)
  ok("but not the learned list", len(L._learned) == 2)
  L.reset()

def test_counts_survive_a_restart():
  L.reset()
  L._note_year("Classic Year Early Aug")
  L._songs[2] = 3
  L.resume()
  ok("a stop and start keeps the song counts", L._songs.get(2) == 3)
  L._note_year("")
  L._note_year("Classic Year Late Aug")
  ok("an unreadable year changes nothing", L._songs.get(2) == 3)
  L._note_year("Junior Year Pre-Debut")
  ok("a new career clears them", not L._songs)
  L._note_year("Senior Year Early Aug")
  L._songs.update({0: 3, 1: 4, 2: 4, 3: 4, 4: 1})
  L._save_progress()
  L._songs.clear()
  L._load_progress()
  ok("a process restart reads them back from disk", L._songs == {0: 3, 1: 4, 2: 4, 3: 4, 4: 1}
     and L.total_songs("Senior Year Early Aug") == 17, L._songs)
  L.reset()

def test_one_visit_a_turn():
  """A visit that buys and then stops is not reopened on the same turn."""
  saved = (L._tap, L._wait_for_lessons, L._leave, L.shop)
  L._tap, L._wait_for_lessons, L._leave = (lambda *a: True), (lambda *a: True), (lambda *a: None)
  try:
    L._declined = None
    L.shop = lambda *a: 1
    ok("a visit that bought reports it", L.visit(80, "Classic Year Late Jan", 4))
    ok("and the turn is not visited again", not L.should_visit("Classic Year Late Jan", 4))
    ok("but the next turn is", L.should_visit("Classic Year Early Feb", 3))
    seen = []
    L.shop = lambda energy, year, spend_all, turn: seen.append(spend_all) or 0
    L.visit(80, "Finale Underway", "Race Day")
    ok("a Finale visit spends everything", seen == [True], seen)
    L._declined = None
    L.shop = lambda *a: L.purchase_limit()
    L.visit(80, "Classic Year Late Jan", 4)
    ok("a visit cut short by the purchase cap may come back", L.should_visit("Classic Year Late Jan", 4))
  finally:
    L._tap, L._wait_for_lessons, L._leave, L.shop = saved
    L._declined = None

def test_urgency():
  """What the Performance bonus counts as urgent."""
  L.reset()
  L._songs.clear()
  L._songs.update({0: 3, 1: 4, 2: 4, 3: 4, 4: 1})     # 17 of 18
  ok("short of 18 in Senior H2 is urgent", L.pushing_for_gold("Senior Year Late Sep"))
  ok("but not once the 18th is in", not (L._songs.update({4: 2}) or L.pushing_for_gold("Senior Year Late Sep")))
  ok("and not before Senior H2", not L.pushing_for_gold("Senior Year Early Mar"))
  import core.logic as logic
  S.PERFORMANCE_SHORT_POINTS, S.PERFORMANCE_URGENT_POINTS = 0.75, 4.0
  gentle = {"performance": {"types": ["vi"], "short": ["vi"], "urgent": False}}
  urgent = {"performance": {"types": ["vi"], "short": ["vi"], "urgent": True}}
  ok("a scheduled song's badge is a nudge", logic.performance_bonus(gentle) == 0.75)
  ok("an urgent type is worth much more", logic.performance_bonus(urgent) == 4.0)
  ok("and a facility paying nothing short scores nothing",
     logic.performance_bonus({"performance": {"types": ["da"], "short": ["vi"], "urgent": True}}) == 0)
  L.reset()

def test_blocked_board():
  """A board of locked techniques tells training what it is waiting on."""
  tech = lambda slot, cost, learnable=False: {
    "slot": slot, "kind": "technique", "name": f"T{slot}", "effects": ["Wit +8"], "learnable": learnable,
    "scheduled": False, "cost": dict(zip(L.POINT_KEYS, cost))}
  pts = lambda *v: dict(zip(L.POINT_KEYS, v))
  L.reset()
  # Career 4, Classic Early Oct: Wit 16 Co, Skill hint 15 Co, Energy 25 Vi.
  board = [tech(0, [0, 0, 0, 0, 16]), tech(1, [0, 0, 0, 0, 15]), tech(2, [0, 0, 0, 25, 0])]
  L._note_blocked(board, pts(23, 7, 19, 0, 10))
  ok("an all-locked technique board asks for the nearest card's types", L.blocked_types() == ["co"], L.blocked_types())
  L._note_blocked(board[:2] + [tech(2, [0, 0, 0, 25, 0], learnable=True)], pts(23, 7, 19, 30, 10))
  ok("and forgets it once anything is learnable", L.blocked_types() == [], L.blocked_types())
  L._note_blocked(board, pts(23, 7, 19, 0, 10))
  L._blocked.clear()
  L._load_progress()
  ok("and a restart remembers it, since nothing reopens a locked board", L.blocked_types() == ["co"], L.blocked_types())
  L.reset()
  ok("and a new career starts clear", L.blocked_types() == [])

def test_segments():
  cases = {"Junior Year Pre-Debut": 0, "Junior Year Late Dec": 0, "Classic Year Early Jan": 1,
           "Classic Year Late Jun": 1, "Classic Year Early Jul": 2, "Senior Year Late Jun": 3,
           "Senior Year Early Dec": 4, "Finale Season": 4,
           "0 Junior Year Pre-Debut": 0, "1 Classic Year Late Jun": 1}
  for year, want in cases.items():
    ok(f"segment of {year!r}", L.segment_of(year) == want, L.segment_of(year))

configure()
for test in [test_lobby_signals, test_screen_detection, test_dialog_titles, test_technique_board,
             test_board_settled, test_career_end_board, test_song_board,
             test_song_policy, test_energy_technique, test_concert_screens, test_career_end,
             test_performance_reader, test_performance_bonus, test_dispatch_order,
             test_song_plan, test_lyrics_event, test_point_readers, test_points_strategy,
             test_pattern_tracking, test_counts_survive_a_restart, test_one_visit_a_turn, test_urgency, test_blocked_board, test_segments]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
