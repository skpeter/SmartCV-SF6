#!/usr/bin/env bash
# Run SmartCV, capture analysis, then print captured inputs for you to validate.
# You only need to run this script and check the output.
set -e
cd "$(dirname "$0")"

PORT=6565
# Free port if needed
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
sleep 2

echo "Starting SmartCV..."
source .venv/bin/activate
python3 -m core.core &
SMARTCV_PID=$!
trap "kill $SMARTCV_PID 2>/dev/null" EXIT

echo "Waiting for SmartCV to be ready..."
sleep 20

echo "Capturing analysis..."
python3 capture_analysis.py || true

kill $SMARTCV_PID 2>/dev/null || true
trap - EXIT

echo ""
echo "========== CAPTURED INPUTS (validate these) =========="
if [[ -f analysis_output.json ]]; then
  python3 -c "
import json
with open('analysis_output.json') as f:
  d = json.load(f)
latest = d.get('latest', {})
samples = d.get('input_samples', [])
print('Input P1:', repr(latest.get('input_p1')))
print('Input P2:', repr(latest.get('input_p2')))
print('Samples with inputs:', len(samples))
for i, (p1, p2) in enumerate(samples[:5]):
  print(f'  [{i+1}] P1={repr(p1)}  P2={repr(p2)}')
"
else
  echo "No analysis_output.json (capture failed or SmartCV not ready)."
fi
echo "======================================================"
