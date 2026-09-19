#!/usr/bin/env python3
# sample eth0 packet rate every 0.5s to traffic.csv (for the plot). runs ~28s.
import time
iface, dur = "eth0", 28

def rx():
    return int(open(f"/sys/class/net/{iface}/statistics/rx_packets").read())

r0, t0, start = rx(), time.time(), time.time()
with open("/root/ids/traffic.csv", "w") as f:
    f.write("t,pps\n")
    while time.time() - start < dur:
        time.sleep(0.5)
        r1, t1 = rx(), time.time()
        f.write(f"{t1 - start:.1f},{(r1 - r0) / (t1 - t0):.0f}\n"); f.flush()
        r0, t0 = r1, t1
