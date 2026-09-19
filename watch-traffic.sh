#!/bin/sh
# Live Wireshark view of the REAL traffic the board sees, streamed over SSH.
# Run on the laptop, in your desktop session. Close Wireshark to stop.
#
# How it works: tcpdump on the board writes packets to stdout; SSH pipes them
# to Wireshark here. 'not port 22' hides our own SSH tunnel so the view is clean.
BOARD=10.42.0.208
echo "Streaming $BOARD eth0 into Wireshark ... (close Wireshark to stop)"
ssh root@$BOARD "tcpdump -i eth0 -s0 -U -w - 'not port 22'" | sg wireshark -c "wireshark -k -i -"
