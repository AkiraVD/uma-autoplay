#!/usr/bin/env bash
# Run the bot against the game on its own display, so it plays in the background.
#
# The game renders on the headless display from tools/headless/start-display.sh
# (Steam launch options: DISPLAY=:1 %command%). The bot reads and clicks that
# display through XTEST, so your desktop, mouse and keyboard stay free, and the
# Pause key is still heard on your desktop. run_auto_uma.sh is the foreground one.
cd "$(dirname "$0")" || exit 1

GAME_DISPLAY="${UMA_GAME_DISPLAY:-:1}"
DESKTOP_DISPLAY="${DISPLAY:-:0}"
if [ "$DESKTOP_DISPLAY" = "$GAME_DISPLAY" ]; then
  DESKTOP_DISPLAY=":0"
fi

PY=.venv/bin/python
[ -x "$PY" ] || PY=python3

if ! DISPLAY="$GAME_DISPLAY" timeout 5 xprop -root >/dev/null 2>&1; then
  echo "Display $GAME_DISPLAY is not up. Start it first:"
  echo "  bash tools/headless/start-display.sh"
  exit 1
fi

running=$("$PY" -c "import sys; sys.path.insert(0, 'tools'); import health; print(' '.join(map(str, health.bot_processes() or [])))")
if [ -n "$running" ]; then
  echo "A bot is already running from this repo (pid $running). Stop it first: two bots fight over one game."
  exit 1
fi

echo "Playing on display $GAME_DISPLAY. Pause on $DESKTOP_DISPLAY starts and stops the bot."
exec env DISPLAY="$GAME_DISPLAY" UMA_INPUT=xtest UMA_HOTKEY_DISPLAY="$DESKTOP_DISPLAY" "$PY" main.py
