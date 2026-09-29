#!/bin/sh
# Resource use on the board, quiet vs. under a flood. Runs board/metrics.py on
# the board twice: once idle, once while this PC floods it for 5 seconds.
#
#   tools/measure.sh 192.168.1.50
BOARD=${1:-$BOARD}
if [ -z "$BOARD" ]; then
    echo "usage: tools/measure.sh <board-ip>" >&2
    exit 2
fi
DIR="$(dirname "$0")"

echo ">>> idle (keep the network quiet for a few seconds)"
ssh root@"$BOARD" 'cd /root/ids && python3 metrics.py idle'

echo ">>> under attack (5 s UDP flood from this PC)"
ssh root@"$BOARD" 'cd /root/ids && python3 metrics.py attack' &
sleep 1
python3 "$DIR/simulate.py" "$BOARD" flood >/dev/null 2>&1
wait

echo ">>> both runs were also appended to /root/ids/metrics.csv on the board"
