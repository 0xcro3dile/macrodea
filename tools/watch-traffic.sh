#!/bin/sh
# See what the board sees: tcpdump runs on the board and streams over ssh into
# Wireshark on this PC. Port 22 is filtered out so you don't watch your own ssh
# stream. Close Wireshark to stop.
#
#   tools/watch-traffic.sh 192.168.1.50
BOARD=${1:-$BOARD}
if [ -z "$BOARD" ]; then
    echo "usage: tools/watch-traffic.sh <board-ip>" >&2
    exit 2
fi
IFACE=${IDS_IFACE:-eth0}
echo "streaming $BOARD $IFACE into Wireshark (close Wireshark to stop)"
ssh root@"$BOARD" "tcpdump -i $IFACE -s0 -U -w - 'not port 22'" | wireshark -k -i -
