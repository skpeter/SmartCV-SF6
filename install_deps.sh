#!/usr/bin/env bash
# Install/repair dependencies into .venv. Run from repo root: ./install_deps.sh
set -e
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  echo "Creating .venv with Python 3.12 (required for PyTorch)..."
  python3.12 -m venv .venv
fi
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r core/requirements.txt
pip install obsws-python mss
# Mac: pygetwindow needs Quartz (core imports it even when using video/obs mode)
pip install pyobjc-framework-Quartz
pip install torch torchvision torchaudio

echo "Done. Run with: ./run_mac.sh"
