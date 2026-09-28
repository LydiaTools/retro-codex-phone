#!/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo 'Install Python 3.11 or newer from python.org, then run this launcher again.'
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Install Python 3.11 or newer from python.org"'
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.txt
exec .venv/bin/python -m retro_phone
