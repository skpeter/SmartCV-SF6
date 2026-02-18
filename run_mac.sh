#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Initialize core submodule if not present
if [[ ! -f core/core.py ]]; then
  echo "Initializing core submodule..."
  git submodule update --init
fi

if [[ ! -f core/core.py ]]; then
  echo "Error: core submodule not found. Run: git submodule update --init"
  exit 1
fi

# Use venv if present so dependencies (mss, obsws-python, etc.) are found
if [[ -d .venv ]]; then
  source .venv/bin/activate
fi

# Run as module from repo root so config.ini and routines are found
exec python3 -m core.core
