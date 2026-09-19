#!/usr/bin/env python3
# contained MITM / arp-spoof SELF-TEST for our own IDS. run on the laptop with sudo.
# announces a DUMMY unused ip (10.42.0.99) twice with two different macs on the
# isolated board<->laptop cable, so the board's arp-watch flags the mac change.
# uses a dummy ip so nothing real is touched -- never point this at the wifi.
import socket, struct, time

IFACE, DUMMY, TPA = "enp2s0", "10.42.0.99", "10.42.0.208"
MAC_A, MAC_B = b"\x02\x00\x00\x00\x00\xaa", b"\x02\x00\x00\x00\x00\xbb"
ipb = lambda s: bytes(int(x) for x in s.split("."))


def arp(mac):
    return (b"\xff" * 6 + mac + b"\x08\x06"               # eth: broadcast, src mac, arp
            + struct.pack("!HHBBH", 1, 0x0800, 6, 4, 2)   # htype ptype hlen plen op=reply
            + mac + ipb(DUMMY) + b"\xff" * 6 + ipb(TPA))  # sender mac/dummy-ip, target board


s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW); s.bind((IFACE, 0))
s.send(arp(MAC_A)); time.sleep(0.5); s.send(arp(MAC_B))   # same ip, mac changes -> spoof
print(f"sent contained arp self-test: {DUMMY} mac a -> mac b, to board {TPA} on {IFACE}")
