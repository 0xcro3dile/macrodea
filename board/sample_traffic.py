#!/usr/bin/env python3
# Log the board's packet rate every 0.5 s for about 30 s into traffic.csv (next
# to this script). Start it, throw a few attacks at the board, then plot the
# result with tools/plot_results.py.
import os
import time

IFACE = os.environ.get("IDS_IFACE", "eth0")
DURATION = 28
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic.csv")


def rx():
    with open(f"/sys/class/net/{IFACE}/statistics/rx_packets") as f:
        return int(f.read())


r0, t0 = rx(), time.time()
start = t0
with open(OUT, "w") as f:
    f.write("t,pps\n")
    while time.time() - start < DURATION:
        time.sleep(0.5)
        r1, t1 = rx(), time.time()
        f.write(f"{t1 - start:.1f},{(r1 - r0) / (t1 - t0):.0f}\n")
        f.flush()
        r0, t0 = r1, t1
print("wrote", OUT)
