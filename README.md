# Uma Autoplay

A bot that plays Umamusume careers for you: training, races, events, skills and the scenario mechanics, start to finish — and then starts the next career and plays that one too. It can run in the background on Linux while you use your desktop, you watch and control it from a web page including from your phone, and it can message you on Telegram when something worth knowing happens.

![Screenshot](screenshot.png)

## Credits

Uma Autoplay started as a fork of [samsulpanjul/umamusume-auto-train](https://github.com/samsulpanjul/umamusume-auto-train) (its [discord server](https://discord.gg/vKKmYUNZuk), [demo video](https://youtu.be/CXSYVD-iMJk)), which was inspired by [shiokaze/UmamusumeAutoTrainer](https://github.com/shiokaze/UmamusumeAutoTrainer). It has since grown far enough apart to go by its own name. Thanks to both projects.

# ⚠️ USE IT AT YOUR OWN RISK ⚠️

I am not responsible for any issues, account bans, or losses that may occur from using it.
Use responsibly and at your own discretion.

## Features

**Playing a career**

- Automatically trains Uma, scoring each facility by support cards, rainbow bonds, hints and the stat gains read off the screen
- Stat caps: a stat that already hit its cap isn't trained further
- Keeps racing until the goal is met, always picking races with matching aptitude, plus your own race schedule
- Any of the game's 402 races can be scheduled: a race is chosen by *reading its row* (track, surface, distance, fans), not by matching a picture, so OP races are as runnable as G1s
- Retries a lost goal race with an Alarm Clock (configurable)
- Checks mood, energy and debuffs, and rests, recreates or visits the infirmary when needed
- Picks event choices from the in-game Effects panel, or from your own list of chain-event picks
- Plays 3 game modes: URA Finale, Unity Cup and Grand Concert (see [Supported game modes](#supported-game-modes))
- Takes the Happy Meek duel when a facility carries the `Duel!` badge, picking the contest from the game's own Predictions column, and buys and keeps the Racing Spirit sparks it pays toward
- Friend-card outings (Light Hello, Tazuna, Aoi, ...) priced as a whole chain
- Buys skills for what the Uma will actually run (run style and distances), and spends every point at career end
- Keeps a 3★ blue spark, or rerolls once for a better set
- Race position selection, overall or per distance
- Trainee picker with aptitudes and growth read from the game's own data
- Sets the story **Skip** to ×2 itself at the start of each career

**Running for hours unattended**

- Starts the next career by itself from the home screen, keeping the last career's scenario, trainee, legacy and deck and re-borrowing the Friends card — optional, off by default, since a career costs 30 TP. A per-run career limit stops it where you want it to stop
- Spends a TP bottle to afford a career or a spark reroll, never below a floor you set
- Notices a frozen game client (it stops drawing entirely) and restarts it, then resumes through Continue Career
- Presses through the daily reset and the game's "Session Error" drop to the title screen, and carries on with the career
- Telegram messages for the four things worth knowing — a career started, a career finished, a goal race lost, the client froze and came back — each with a screenshot, plus `/health` on demand
- Web page for configuration, a live log, a race planner, one-click tools and a start/stop button, usable from your phone

## Supported game modes

| Game mode | What the bot handles |
| --- | --- |
| **URA Finale** | Training, goal races and your race schedule, the URA Finale race days, and the Happy Meek duels. |
| **Unity Cup** | Everything in URA Finale, plus Spirit gauges and Spirit bursts in training scores. An Extreme burst is taken even above the failure threshold, since it has no failure chance. |
| **Grand Concert** | Everything in URA Finale, plus the Lessons board, the song plan (18 songs for the gold "I Wanna Win With You"), the lyrics event, Performance points in training scores, and Light Hello's recreation chain. |

Pick the mode under **Game mode** on the web page (Trainee & strategy). **Auto-detect**, the default, recognises the mode from what it sees on screen: Spirit gauges for Unity Cup, the Lessons button for Grand Concert. Choosing a mode makes the bot use it from the first turn and skip looking for the others; it logs a warning if the screen shows a different mode. Trackblazer is **not supported**: it was parked on 2026-09-21 because its Climax Store cost more screen-reading than the mode was worth, and the code that played it is kept in `core/parked/` (see its README). The Race Plan tab, which is built on Trackblazer's epithet tables, still works.

## Getting Started

### Requirements

- [Python 3.10+](https://www.python.org/downloads/)

### Setup

#### Clone repository

```
git clone https://github.com/AkiraVD/uma-autoplay.git
cd uma-autoplay
```

#### Install dependencies

Windows:

```
pip install -r requirements.txt
```

Linux (X11 session, game running in the Steam client under Proton):

```
sudo apt install wmctrl python3-tk
python3 -m venv .venv
.venv/bin/pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements.txt
```

On Linux:
- Use an X11 session. Screen capture does not work on Wayland.
- Clicks go through a virtual mouse on `/dev/uinput`, so the game sees a real device. A normal desktop login can already write to it. If yours can't, the bot falls back to pyautogui and logs why.
- The `Pause` key is heard through the X server, so no root is needed.
- `master.mdb` is found in the Steam library automatically. Set `UMA_MASTER_MDB` if yours lives somewhere else.

To play in the background, with the game on a hidden display so your desktop stays free:
1. `bash tools/headless/start-display.sh` (asks for your sudo password; starts a second X server, `:1`, on the NVIDIA GPU).
2. In Steam, set the game's launch options to `DISPLAY=:1 %command%`, then start the game. It won't appear on your screen.
3. `./run_background.sh`, then press `Pause` on your desktop or **Start bot** on the web page.

The start script has to be run again after a reboot.

To undo it, run `bash tools/headless/stop-display.sh` and clear the launch options.

### BEFORE YOU START

Make sure these conditions are met:

- Screen resolution must be 1920x1080
- The game should be in fullscreen
- Your Uma must have already won the trophy for each race (the bot skips the race)
- In the game's Options → Require Confirmation, turn off "When selecting Rest", "When selecting Recreation" and "When selecting Infirmary"
- Either start a career yourself, or turn on **Start the next career by itself** on the web page's Bot tab and leave the game on its home screen
- Then start the bot

### Start

Run:

```
python main.py
```

On Linux: `./run_auto_uma.sh`

Press `Pause`, or use the **Start bot** button on the web page, to start/stop the bot.

### Web page

Open `http://127.0.0.1:8000/` in your browser. The page has six views:

- **Configuration**: what the bot trains — grouped by what it affects (trainee and race strategy, rest and mood, training, skills, races, events, Grand Concert). Every edit is saved as you make it, and picked up by the career already running between two actions, so there is nothing to apply and no need to restart the bot. **Save**/**Load** keep the whole thing as a named preset.
- **Live Log**: the bot's log as it plays.
- **Race Plan**: builds a race schedule out of the game's own `master.mdb`, turn by turn across all 59 turns, aimed at the Trackblazer epithets you pick and filtered to what the trainee can actually run. It also reports the Spark each race pays. A finished plan is saved as a race list, which the Configuration tab's Races section loads.
- **Tools**: health check, screenshot, "which screen is this", launch/close the game, advance or skip a race, scan the facilities, and click anywhere on the game screen. Anything that clicks is refused while the bot is running.
- **Bot**: how the bot runs, rather than what it trains — timing multiplier for a slower machine, the TP bottle floor, spark rerolling, starting the next career (and the count so far, with the per-run limit), and restarting a frozen game. Machine-level, so loading a config preset leaves it alone.
- **Telegram**: a bot token and chat id, what gets sent, and what you can ask it. Kept out of the presets, since the token is a secret.

The **Start bot**/**Stop bot** button in the top bar works like `Pause`. Use it when the page is opened from another device (for example over Tailscale), where a key press can't reach the bot. The page has a light and a dark theme.

### Training Logic

1. During the Junior Year, the bot trains where it builds friendship fastest, to unlock rainbow training early.
2. From the Classic Year on, it looks for rainbow training, falling back to the facility with the most support cards.

Both are skewed by your stat priority and weights, skip trainings above the failure threshold, and add scenario bonuses (Spirit gauge in Unity Cup, Performance points in Grand Concert, a Happy Meek duel in URA Finale).

### Known Issues

- Trainees with unusual goals, such as Gold Ship's restricted training, have no special handling and haven't been tested.
- Two races read identically on their shared turn — Akamatsu Sho and Begonia Sho, both Junior Late Nov, both Tokyo turf 1600m for +1,000 fans. They're marked as such everywhere they can be picked, and the bot refuses to enter either rather than risk the wrong one.
- The Unity Cup team race takes whichever opponent the game preselects; picking a harder team by hand raises team rank faster.
- The game client stops drawing every few hours, keeping one frame on screen. The bot spots that and, with **Restart the game if it freezes** on, closes and reopens the game and resumes the career. With it off, the bot stops and waits for you.

### Contribute

If you run into any issues or something doesn’t work as expected, feel free to [open an issue](https://github.com/AkiraVD/uma-autoplay/issues).
Contributions are very welcome!

## License

[MIT](LICENSE) — use it, change it, share it.

The upstream project this began as a fork of ships a disclaimer rather than a licence grant, so these terms cover the work in this repository.
