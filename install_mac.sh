#!/usr/bin/env bash
# Install SmartCV-SF6 on Mac. Run from repo root: ./install_mac.sh
set -e
cd "$(dirname "$0")"

echo "==> Initializing core submodule..."
git submodule update --init

echo "==> Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing Python dependencies..."
if [[ -f core/requirements.txt ]]; then
  pip install -r core/requirements.txt
else
  pip install -r requirements.txt
fi
# Ensure these are installed (core uses them)
pip install obsws-python mss

echo "==> Installing PyTorch (Mac)..."
pip install torch torchvision torchaudio

echo "==> Done. Activate and run with:"
echo "    source .venv/bin/activate"
echo "    ./run_mac.sh"
