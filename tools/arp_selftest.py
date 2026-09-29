#!/usr/bin/env python3
# Set off the ARP-spoof (mitm) detector without spoofing anybody. Sends the board
# two ARP replies for an IP nobody uses, first with one MAC, then another. The
# board sees that IP "change" MAC and raises a mitm alert.
#
#   sudo python3 tools/arp_selftest.py <iface> <board-ip> <unused-ip>
#   sudo python3 tools/arp_selftest.py eth0 192.168.1.50 192.168.1.250
#
# Run it from a machine on the same wire/switch as the board. Pick an address
# that really is free, so no real host's ARP entry gets touched.
import socket
import struct
import sys
import time

if len(sys.argv) != 4:
    print("usage: sudo python3 arp_selftest.py <iface> <board-ip> <unused-ip>", file=sys.stderr)
    sys.exit(2)
IFACE, BOARD, SPARE = sys.argv[1:]
MAC_A, MAC_B = b"\x02\x00\x00\x00\x00\xaa", b"\x02\x00\x00\x00\x00\xbb"   # locally administered, fake


def arp_reply(mac):
    return (b"\xff" * 6 + mac + b"\x08\x06"                 # ethernet: broadcast, from mac, ARP
            + struct.pack("!HHBBH", 1, 0x0800, 6, 4, 2)     # ethernet / IPv4, op 2 = reply
            + mac + socket.inet_aton(SPARE)                 # "SPARE is at mac"
            + b"\xff" * 6 + socket.inet_aton(BOARD))        # addressed to the board


s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
s.bind((IFACE, 0))
s.send(arp_reply(MAC_A))
time.sleep(0.5)
s.send(arp_reply(MAC_B))
print(f"sent: {SPARE} is at ..:aa, then ..:bb, to {BOARD} on {IFACE}. The board should report mitm.")
