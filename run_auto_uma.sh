#!/usr/bin/env bash
# Linux counterpart of run_auto_uma.bat: run the bot from the repo root,
# with the project's .venv when there is one.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python main.py
fi
exec python3 main.py
