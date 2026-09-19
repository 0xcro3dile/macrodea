#!/bin/sh
# One-shot before/after resource metrics for the demo. Run on the laptop.
# Measures the board while idle, then again during a flood, and shows both.
BOARD=10.42.0.208
DIR="$(dirname "$0")"

echo ">>> BASELINE (idle) -- keep the network quiet for a few seconds..."
ssh root@$BOARD 'cd /root/ids && python3 metrics.py idle'

echo ">>> UNDER ATTACK (flood)..."
ssh root@$BOARD 'cd /root/ids && python3 metrics.py attack' &
sleep 1
python3 "$DIR/simulate.py" $BOARD flood >/dev/null 2>&1
wait

echo ">>> Full history saved on the board: /root/ids/metrics.csv"
