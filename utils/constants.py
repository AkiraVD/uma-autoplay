import json

MOOD_REGION=(705, 125, 835 - 705, 150 - 125)
TURN_REGION=(255, 45, 380 - 255, 165 - 45)
# The calendar box's top row: the big "turns left" number and the small
# "turn(s) left" beside it, which the glyph reader drops by height. Wide enough
# to take in all of a race day's GOAL, whose four tall letters are then too many
# to be a number.
TURN_DIGITS_REGION=(258, 48, 112, 58)
# Trackblazer draws the same box with taller digits set lower: measured at
# y 84..131 (h 47) against URA's 36..40, so URA's crop keeps only the top 22px
# of every glyph. The reader returned None on 49 of 49 live frames because of
# it, and the h=22 that produced looked like a threshold problem for two days -
# TURN_GLYPH_HEIGHT and TURN_MIN_WHITE are both correct, and a whole glyph here
# lands inside them. Same 112x58 window, shifted 30px down onto the card.
# Per mode, not a shared edit: URA's and Grand Concert's boxes fit as they are,
# and moving the shared constant breaks the 17 fixtures that pass on it.
TB_TURN_DIGITS_REGION=(258, 78, 112, 58)
FAILURE_REGION=(250, 770, 855 - 295, 835 - 770)
YEAR_REGION=(255, 32, 570 - 255, 58 - 32)
CRITERIA_REGION=(455, 55, 765 - 455, 115 - 55)
EVENT_NAME_REGION=(241, 205, 365, 30)
SKILL_PTS_REGION=(750, 715, 845 - 750, 820 - 715)
SKIP_BTN_BIG_REGION_LANDSCAPE=(1500, 750, 1920-1500, 1080-750)
SCREEN_BOTTOM_REGION=(125, 800, 1000-125, 1080-800)
SCREEN_MIDDLE_REGION=(125, 300, 1000-125, 800-300)
SCREEN_TOP_REGION=(125, 0, 1000-125, 300)
RACE_INFO_TEXT_REGION=(285, 335, 810-285, 370-335)
RACE_LIST_BOX_REGION=(260, 580, 850-265, 870-580)
CLAW_EVENT_REGION=(740, 20, 190, 50)

FULL_STATS_STATUS_REGION=(265, 575, 845-265, 940-575)
FULL_STATS_APTITUDE_REGION=(395, 340, 820-395, 440-340)

SCROLLING_SELECTION_MOUSE_POS=(560, 680)

# Dragging the skill list. Measured on a live buy screen, and every number here
# is a correction to something that was wrong:
#
# - The old call dragged from y=850 by +450 to scroll up, which targets y=1300
#   on a 1080-tall screen. It clamps, so an up drag travelled ~229px while a
#   down drag got its full 450. Ten downs could not be undone by twelve ups,
#   and that is why the buying pass never saw the rows the planning pass chose.
#   These two positions are 400 apart and both on screen, so travel is
#   symmetric and a scan can actually rewind.
#
# - x=320 does not scroll at all: the skill icon swallows the drag. Measured
#   0.00 change against ~24 for every column to its right.
#
# - x=400 is deliberate. drag_scroll ends with a bare click wherever the
#   pointer stopped, and 400 is clear of Confirm (x 445-665, y 887-938) and of
#   the +/- column (x 669-800). Scrolling must never be able to press either.
# The scrollable list area, used to tell whether a drag actually moved it.
SKILL_LIST_BBOX = (260, 395, 850, 950)
SKILL_SCROLL_UP_FROM_MOUSE_POS = (400, 460)
SKILL_SCROLL_DOWN_FROM_MOUSE_POS = (400, 860)
SKILL_SCROLL_DISTANCE = 400

# The three things read off a row of the skill buy screen, each as an offset
# from that row's buy button: (dx, dy, width, height).
#
# Deliberately NOT suffixed _REGION: these are relative to a button whose
# position is already found on screen, not absolute screen rectangles.
#
# Measured on a live buy screen at 1920x1080 (Grass Wonder, Junior Pre-Debut).
# Buttons sat at x=784 with a row pitch of 156.
#
# The name offset used to be dy=-40 with height 30, which covered y-40..y-10.
# The name actually sits at y-45..y-29, so that crop cut the ascenders off and
# padded the bottom with empty row. It is the whole reason skill names read as
# "benoia nine Emperor $ DiviIne mignt". At dy=-52 the same OCR returns
# "Behold Thine Emperor's Divine Might" exactly.
# The buy screen prints "Skill Points NNN" in its own header. SKILL_PTS_REGION
# is the lobby's counter and reads garbage here ("v 2 DFFi 0"), which is why
# the end-of-career optimizer got a budget of 0 and never ran.
SKILL_BUY_PTS_REGION = (690, 332, 150, 46)

SKILL_NAME_OFFSET = (-420, -52, 305, 30)
# The price, between the minus button and the buy button.
SKILL_COST_OFFSET = (-75, -8, 70, 40)
# The orange hint badge above the price: two lines, "Hint Lvl 2" then
# "20% OFF!". Absent entirely on a skill with no hint, which reads as "".
SKILL_HINT_OFFSET = (-102, -56, 118, 44)
RACE_SCROLL_BOTTOM_MOUSE_POS=(560, 850)

# The "/NNNN" cap printed under each stat value. Caps move between game
# versions and between runs (inherited sparks raise individual caps), so they
# are read rather than hardcoded.
SPD_STAT_CAP_REGION = (310, 744, 58, 24)
STA_STAT_CAP_REGION = (405, 744, 58, 24)
PWR_STAT_CAP_REGION = (500, 744, 58, 24)
GUTS_STAT_CAP_REGION = (595, 744, 58, 24)
WIT_STAT_CAP_REGION = (690, 744, 58, 24)

SPD_STAT_REGION = (310, 723, 55, 20)
STA_STAT_REGION = (405, 723, 55, 20)
PWR_STAT_REGION = (500, 723, 55, 20)
GUTS_STAT_REGION = (595, 723, 55, 20)
WIT_STAT_REGION = (690, 723, 55, 20)

# The five training buttons never move: always spd, sta, pwr, guts, wit, left to
# right, 107.5px apart. The selected one is drawn 45px higher, so y=886 is inside
# the disc in both the resting (centre y=910) and the selected (centre y=865)
# state. Clicking by position instead of by icon template means a bouncing event
# badge (a "Duel!" starburst) sitting on an icon can no longer hide a training.
SPD_TRAIN_MOUSE_POS = (337, 886)
STA_TRAIN_MOUSE_POS = (445, 886)
PWR_TRAIN_MOUSE_POS = (552, 886)
GUTS_TRAIN_MOUSE_POS = (660, 886)
WIT_TRAIN_MOUSE_POS = (767, 886)

# Green banner naming the currently selected facility, e.g. "Speed Lvl 1".
TRAINING_BANNER_REGION = (150, 168, 390, 68)

# Scenario dialogue (the Unity Cup tutorial, for one) has no Back button and no
# choice icons - it only advances on a tap. This sits in the character/backdrop
# area, well above the lobby's buttons (all below y~800), so tapping it cannot
# press anything when we turn out to be in the lobby after all.
DIALOG_ADVANCE_MOUSE_POS = (553, 400)
# A second blind-tap point, for scenario screens the first one does not advance.
# The career-start Inspiration screen ("HINT Lvl UP!", the aptitude and hint
# summary) ignores a tap on the artwork completely: the bot sat on it for seven
# minutes, logging "No back button, tapping to advance dialogue" every 32s,
# until this point was tapped instead. It sits on the advance marker, above the
# Skip/Quick row at y~1050, so it does not toggle either of those.
#
# That reasoning only ever covered the *career* screens. Outside a career the
# game draws its own navigation bar along the bottom - Enhance / Story / Home /
# Race / Scout - whose tiles start at y~1002, and this point lands on Scout,
# the gacha. Careers kept ending up in the summon menu because of it. The loop
# now stops on the "game_nav" template before it can blind-tap there, so this
# point is only ever used inside a career. Keep it that way: moving it is not
# free, the Inspiration screen is what it was measured against.
DIALOG_ADVANCE_ALT_MOUSE_POS = (756, 980)

# The login bonus' Skip, measured on the reload after a date change (2026-09-12)
# and unchanged at the end of a career. Only used once the login-bonus banner
# has already identified the screen.
LOGIN_BONUS_SKIP_MOUSE_POS = (903, 1024)

# The story Skip button, bottom-left of the story UI and of the lobby. It
# cycles Off -> x1 -> x2 and resets to Off with every new career, and nothing
# used to set it: with Skip off the bot taps each story line about every 9 s,
# so a career intro read as a stall. Measured live 2026-09-17 - two presses
# took it Off -> x1 -> x2, each state matching its own template at 1.000
# against a worst confusion of 0.832, so the state is read, never counted.
SKIP_BUTTON_MOUSE_POS = (567, 1052)
SKIP_BUTTON_BBOX = (500, 1028, 680, 1078)

# "Quick Mode Settings", the one-time dialog at the start of every career.
# Four radios 68px apart: Don't use (460), Shorten all events (529), Only
# scenario (597), Only trainee (664). Note that is **not** the 112px
# event-choice spacing, although the radios do match event_choice_1.png at
# 0.974 - deriving them from LAST_EVENT_CHOICE_ICON_TOP would land wrong.
# Measured live 2026-09-17; the chosen radio reads ~273 green pixels in an
# 18x18 patch against 0 for the rest.
QUICK_MODE_SHORTEN_ALL_MOUSE_POS = (308, 529)
QUICK_MODE_CONFIRM_MOUSE_POS = (553, 773)

# Event choices are bottom-anchored: the last option sits at the same y whether
# the event offers two of them or five. That makes "pick the last option" a
# fixed click, which is how you escape an info menu that reopens after every
# answer (the Unity Cup tutorial's "That's all, thank you.").
LAST_EVENT_CHOICE_ICON_TOP = 736

# The URA Finale race-day button animates across its whole area (measured std
# 35-86 per pixel over consecutive frames), so no crop of it matches reliably -
# ura_finale_race_btn.png peaks around 0.805, right on the click threshold. It
# never moves, though, so fall back to its position the way the training buttons
# do. Only used on a race day, when this screen is the only thing it can be.
FINALE_RACE_MOUSE_POS = (690, 905)
# Grand Concert ends in the URA Finale too, but its race-day lobby keeps a
# Lessons button: Skills (352) / URA Finale Race! (553) / Lessons (752). The
# URA position above lands on the Lessons button's edge there, and
# ura_finale_race_btn.png only reaches 0.75, so the fallback is what runs.
GC_FINALE_RACE_MOUSE_POS = (545, 925)
# Trackblazer ends in the Twinkle Star Climax, not the URA Finale, and its race
# day lays out Skills (340) / TS Climax Race! (537) / Shop (755). URA's position
# above falls in the gap beside the Shop, which is where the bot kept landing:
# three laps, 0/3 races run. Measured by hand on 2026-09-17.
TB_CLIMAX_RACE_MOUSE_POS = (537, 908)

# Trackblazer's Climax Store. The shelf is a scrolling list walked through
# core/menu_scan.py (profile SHOP_BUY) and read by core/shop.py. Measured
# 2026-09-19 on live frames; the row pitch is 121px (names at 429/550/671/792).
SHOP_BUTTON_MOUSE_POS = (622, 952)          # the lobby's facility-grid button
SHOP_LIST_BBOX = (275, 395, 845, 815)
# Drag at x=400: the checkbox column is x~765 and dragging there would toggle
# a row, and Confirm sits at (552,913) so the drag column stays clear of it.
# The two y values are symmetric about the list's middle so an up-drag is not
# clamped by the bottom of the screen.
SHOP_SCROLL_UP_FROM_MOUSE_POS = (400, 460)
SHOP_SCROLL_DOWN_FROM_MOUSE_POS = (400, 760)
SHOP_SCROLL_DISTANCE = 240                  # about two rows at a 121px pitch
SHOP_ROW_PITCH = 121

# Offsets from the "Cost" anchor's top-left corner, as (dx, dy, w, h).
SHOP_NAME_OFFSET = (-10, -42, 330, 36)
SHOP_COST_OFFSET = (80, -6, 120, 38)
SHOP_EFFECT_OFFSET = (10, 24, 450, 34)
# Anchor top-left -> the row's checkbox centre (392,452 -> 766,459).
SHOP_CHECKBOX_OFFSET = (374, 7)

SHOP_COINS_REGION = (640, 330, 160, 45)
SHOP_CONFIRM_MOUSE_POS = (552, 913)
SHOP_RESET_MOUSE_POS = (771, 913)
SHOP_BACK_MOUSE_POS = (216, 1039)
# Confirm Exchange, Exchange Complete and Confirm Use all put their green
# button here and their Cancel/Close there. They can only be told apart by the
# title bar, never by position - see docs/screen-map.md.
SHOP_DIALOG_GREEN_MOUSE_POS = (686, 997)
SHOP_DIALOG_CANCEL_MOUSE_POS = (419, 997)
SHOP_DIALOG_TITLE_REGION = (260, 20, 590, 60)
# The Exchange Complete quantity stepper. It defaults to 0, so storing is what
# happens if nothing is pressed and using on purchase is the opt-in.
SHOP_QTY_PLUS_MOUSE_POS = (797, 222)
SHOP_QTY_MINUS_MOUSE_POS = (706, 222)
SHOP_QTY_COUNT_REGION = (725, 200, 55, 48)
# The career-complete screen puts its own Skills / Complete Career buttons at
# the bottom of the game panel. The in-career skills_btn template does not
# match them (0.59), so these two are reached by position.
CAREER_COMPLETE_SKILLS_MOUSE_POS = (425, 888)
CAREER_COMPLETE_CONFIRM_MOUSE_POS = (552, 912)
# Grand Concert's career-complete screen has three: Skills (352) / Complete
# Career (553) / Lessons (752), over a "Remaining Performance Points" panel.
# The URA Skills position above is the gap beside Complete Career there.
GC_CAREER_COMPLETE_SKILLS_MOUSE_POS = (352, 890)

# Unity Cup draws a flame-shaped spirit gauge to the LEFT of each support card,
# partly outside SUPPORT_CARD_ICON_BBOX, so it needs its own region. The burst
# badge sits at the card's top-right and is covered by the support-card region.
SPIRIT_GAUGE_BBOX = (808, 150, 878, 710)

MOOD_LIST = ["AWFUL", "BAD", "NORMAL", "GOOD", "GREAT", "UNKNOWN"]

SUPPORT_CARD_ICON_BBOX=(845, 155, 945, 700)
# The Extreme Spirit Burst flame renders to the RIGHT of the card portrait
# (x~924) while charging and ready flames sit to the LEFT (x~836), so the
# extreme scan needs a bbox spanning both columns.
UNITY_RAIL_BBOX=(800, 145, 950, 715)
# The Recreation button carries a pink badge when an outing with a friend
# support (Tazuna and the like) is available. Absent on turn 1 of a career,
# present later, so it is a real signal rather than decoration.
RECREATION_BADGE_BBOX=(555, 875, 705, 975)
# The training screen prints the stat gains above the stat row: a bubble and
# an orange number per column, which sum to the actual gain. Plain x centres
# rather than a suffixed rect.
GAIN_STRIP_Y = (630, 706)
GAIN_COLUMN_HALF = 58
GAIN_COLUMN_X = {"spd": 337, "sta": 432, "pwr": 527, "guts": 622, "wit": 717, "skill": 795}

# The Recreation panel that opens when a friend support offers an outing. It
# lists each friend card with an Event Progress row - one chevron per chain
# step, filled blue as the chain advances - and then the trainee, whose row is
# plain recreation. Its only other button is Cancel, which cancel_btn.png
# matches at 0.982, so the panel has to be handled before the generic cancel
# handler ever sees it.
#
# Measured on a 1920x1080 Steam window: five chevrons 33x36 at x centres 627,
# 669, 712, 754, 797, all on y 399. The bbox is deliberately wider than that,
# because the row is centred on however many steps the chain has (three for
# Sasami, five for the rest).
RECREATION_CHEVRON_BBOX = (595, 372, 835, 428)
# First row's name, e.g. "Riko Kashimoto". Text measured at x382-516, y342-356.
RECREATION_NAME_REGION = (375, 334, 150, 30)
# The friend row sits just above its Event Progress pill; the trainee row is
# the one below it and is plain recreation. Both are clicked at x=552, which
# is clear of the name text, the Friendship Gauge pill and the chevrons.
RECREATION_ROW_X = 552
RECREATION_FRIEND_ROW_ABOVE_PROGRESS = 30
RECREATION_TRAINEE_ROW_MOUSE_POS = (552, 500)


# The game's own Log, the right-hand panel. It states what an action actually
# did - "Energy recovered by 30", "Gained 3 hint level(s) for Rushing Gale!" -
# which is the only way to check a predicted outing against the real one. The
# newest entry is at the bottom, so only the lower part of the panel is read;
# OCR over the whole column is slow and the older entries are not wanted.
LOG_PANEL_REGION = (958, 380, 700, 650)

# The "Choices" panel, which takes over the right-hand column while an event
# with options is up and lists what each option does. Options > Career >
# "Always display choice effects" opens it by itself; otherwise the Effects
# button on the event bubble does.
#
# The top starts below the panel title so the title bar's own green is not
# mistaken for an option header, and the bottom stops above the Close button.
CHOICES_PANEL_BBOX = (1060, 100, 1660, 950)
CHOICES_CLOSE_MOUSE_POS = (1357, 995)

# Grand Concert. From turn 5 its lobby has a fourth bottom button, Lessons,
# between Recreation and Races, which pushes Recreation left - so the outing
# badge sits outside RECREATION_BADGE_BBOX and needs a box of its own here.
# Measured on a 1920x1080 Steam window (Mihono Bourbon, Junior Pre-Debut).
LESSONS_BUTTON_MOUSE_POS = (622, 955)
# The game's own home screen: the CAREER banner, for resuming a career the
# daily reset reloaded out from under the bot.
CAREER_BUTTON_MOUSE_POS = (712, 930)
# Spark Selection after a reroll: two pages, "Rerolled Sparks" and "Original
# Sparks", with an arrow either side of the label.
SPARK_PAGE_LABEL_REGION = (400, 108, 310, 44)
SPARK_PAGE_NEXT_MOUSE_POS = (806, 128)
# "Recover TP": each row's Use button sits at this x, the row's own y.
TP_RESTORE_USE_X = 763
SPARK_PAGE_PREV_MOUSE_POS = (298, 128)
# The concert screen's larger Lessons button, left of the Concert button.
CONCERT_LESSONS_MOUSE_POS = (425, 912)
# The Grand Concert's confirmation adds "Skip the Grand Concert cutscene", a
# checkbox that is grey when unticked and green when ticked.
SKIP_CUTSCENE_BBOX = (370, 640, 420, 690)
SKIP_CUTSCENE_MOUSE_POS = (395, 665)
# "Race Playback" (Landscape / Portrait), over the race preview. Its "Do not
# show again." box works the same way: grey tick off, green tick on (146 green
# pixels ticked, 0 unticked, measured 2026-09-15).
RACE_PLAYBACK_CHECKBOX_BBOX = (401, 562, 451, 612)
RACE_PLAYBACK_CHECKBOX_MOUSE_POS = (426, 587)
RACE_PLAYBACK_OK_MOUSE_POS = (686, 703)
# "This will put you at N consecutive races.", raised when the race list is
# opened on a third race in a row. Measured 2026-09-20: OK is 235x61 centred on
# (686,702) - the same geometry as the Race Playback OK a line above, one pixel
# apart, so these confirmations share a layout. Cancel sits at (419,702).
CONSECUTIVE_RACES_OK_MOUSE_POS = (686, 702)
# "You have a scheduled race. Proceed to the Races screen?", raised on entering
# a career whose agenda has a race this turn. Same dialog geometry again: Race
# at (686,704), Close at (419,704). The template for it is the message text, so
# it cannot be clicked at its own centre - that would press the dialog body.
SCHEDULED_RACE_NOTICE_RACE_MOUSE_POS = (686, 704)
# The Lessons button carries a pink "!" when something on the board is
# learnable, and a "Scheduled" tag or a note badge otherwise. The same "!"
# artwork appears elsewhere in the lobby (0.93 on a Unity lobby), so it is only
# ever looked for beside the button's "Lessons" label. The button moves: summer
# camp merges Rest and Recreation, and the bottom row shifts left (label centre
# (623,980) normally, (552,980) at camp; the badge 51-61px right and 68px up).
# URA Finale race days have one row, Skills / Race / Lessons, label at (753,940).
LESSONS_LABEL_SEARCH_BBOX = (270, 915, 830, 1005)
# Relative to the label's centre: where to look for the badge, where to tap.
LESSONS_BADGE_FROM_LABEL = (10, -110, 100, -25)
LESSONS_TAP_FROM_LABEL = (0, -25)
# Training screen: each facility carries one small chip naming the Performance
# type it pays this turn ("Da", "Pa", "Vo", "Vi", "Co"), two on a friendship
# (rainbow) training, stacked 30px apart. They sit ~37px left of the facility's
# centre, at y~865 resting and y~818 on the raised, selected facility.
PERFORMANCE_CHIP_BBOX = (260, 780, 800, 930)
PERFORMANCE_CHIP_OFFSET_X = -37
# The Performance panel (lobby and training screen) puts a red "N more" badge on
# a type's row when a scheduled song still needs more of it. Rows are 55px
# apart, Da first; the badge is centred at x~222, Da's at y~302.
PERFORMANCE_BADGE_BBOX = (195, 290, 258, 535)
PERFORMANCE_BADGE_FIRST_Y = 302
PERFORMANCE_ROW_PITCH = 55
GC_RECREATION_BADGE_BBOX = (455, 875, 590, 975)
# The Lessons screen is three cards on a fixed grid, 230px apart. Everything
# below is card 1's; card i is the same box moved down by i * LESSON_CARD_PITCH.
# The card's own header colour says whether it is a Technique (green) or a Song
# (purple), the gold "Learnable!" ribbon over its top-right corner says whether
# it can be bought now, and its cost row is drawn dimmed when it cannot.
LESSON_CARD_PITCH = 230
LESSON_TITLE_REGION = (290, 196, 385, 32)
LESSON_EFFECT_1_REGION = (468, 248, 350, 38)
LESSON_EFFECT_2_REGION = (468, 307, 350, 38)
LESSON_RIBBON_BBOX = (700, 176, 825, 204)
LESSON_COST_ROW_BBOX = (425, 368, 815, 392)
LESSON_HEADER_BBOX = (280, 198, 295, 224)
# The Lessons screen's own point totals, one box per type across the top.
# Read as plain numbers, they came back right on every captured board.
LESSON_POINTS_DA_BBOX = (335, 90, 405, 124)
LESSON_POINTS_PA_BBOX = (438, 90, 508, 124)
LESSON_POINTS_VO_BBOX = (542, 90, 612, 124)
LESSON_POINTS_VI_BBOX = (646, 90, 716, 124)
LESSON_POINTS_CO_BBOX = (748, 90, 818, 124)
# Card 1's cost row read as one line: the type icons read as "Da", "Pa"... and
# the numbers fall into five slots by x. Split points are offsets from the
# row's left edge. A lone "0" is
# the only thing that goes missing, so an empty slot is a 0.
LESSON_COST_TEXT_REGION = (425, 364, 395, 32)
LESSON_COST_SLOT_EDGES = (80, 158, 237, 315)
# Card 1's red "Scheduled" pill, drawn over the bottom of the song art.
LESSON_SCHEDULED_BBOX = (300, 332, 400, 356)
# Tapping a card opens its dialog. Clear of the effect text, so it lands on the
# card whatever is written there.
LESSON_CARD_MOUSE_POS = (610, 295)
# Every lesson dialog puts its title in the green bar and its two buttons in
# the same places: Cancel on the left, Learn or Schedule on the right.
LESSON_DIALOG_TITLE_REGION = (400, 32, 310, 44)
LESSON_DIALOG_CANCEL_MOUSE_POS = (419, 997)
LESSON_DIALOG_ACCEPT_MOUSE_POS = (686, 997)
# Learning a song while a different one is scheduled asks a second time, in a
# smaller "Confirm" dialog on top: "Your trainee won't be able to learn the
# scheduled song." Its title sits mid-screen, so the Confirmation title behind
# it still reads - which is how the first live visit cancelled it five times.
LESSON_CONFIRM_TITLE_REGION = (400, 255, 310, 44)
LESSON_CONFIRM_OK_MOUSE_POS = (686, 774)
# "TECHNIQUE LEARNED!" and "Scheduling Complete" are dismissed by a tap. This
# point is on the "Select a technique or song to learn." banner, above the first
# card: a tap that lands after the overlay has already gone must not open a card.
LESSON_DISMISS_MOUSE_POS = (553, 150)
# "Scheduling Complete" is a small popup too, titled mid-screen.
LESSON_SCHEDULING_TITLE_REGION = (400, 325, 310, 44)
LESSON_SCHEDULING_CLOSE_MOUSE_POS = (553, 703)
ENERGY_BBOX=(440, 120, 800, 160)
RACE_BUTTON_IN_RACE_BBOX_LANDSCAPE=(800, 950, 1150, 1050)

GAME_SCREEN_REGION = (150, 0, 800, 1080)

# Load all races once to be used when selecting them
RACES = ""
with open("data/races.json", "r", encoding="utf-8") as file:
  RACES = json.load(file)

# Build a lookup dict for fast (year, date) searches
RACE_LOOKUP = {}
for year, races in RACES.items():
  for name, data in races.items():
    key = f"{year} {data['date']}"
    race_entry = {"name": name, **data}
    RACE_LOOKUP.setdefault(key, []).append(race_entry)

DATE_ARRAY = [
    "Early Jan", "Late Jan", "Early Feb", "Late Feb",
    "Early Mar", "Late Mar", "Early Apr", "Late Apr",
    "Early May", "Late May", "Early Jun", "Late Jun",
    "Early Jul", "Late Jul", "Early Aug", "Late Aug",
    "Early Sep", "Late Sep", "Early Oct", "Late Oct",
    "Early Nov", "Late Nov", "Early Dec", "Late Dec"
]
