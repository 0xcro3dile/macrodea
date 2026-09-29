#!/usr/bin/env python3
# How much of the board does the IDS use? Averages CPU, RAM, temperature and
# traffic over a few seconds. Run it once while the network is quiet and once
# during an attack:
#   python3 metrics.py idle
#   python3 metrics.py attack
# Every run also appends a row to metrics.csv, which tools/plot_results.py turns
# into a chart. tools/measure.sh does both runs for you from a PC.
import os
import sys
import time

WINDOW = 4                     # seconds to average over
HZ = os.sysconf("SC_CLK_TCK")
IDS_NAME = "edge_ids.py"
IFACE = os.environ.get("IDS_IFACE", "eth0")

# The board has no power sensor, so power is estimated from CPU load between
# these two figures (rough idle/full numbers for a 1 GHz Cortex-A7 board).
# Put in readings from a USB power meter if you have one.
P_IDLE_W, P_FULL_W = 0.9, 2.0


def cpu_times():               # (total, idle) jiffies from /proc/stat
    with open("/proc/stat") as f:
        v = list(map(int, f.readline().split()[1:]))
    return sum(v), v[3] + v[4]          # idle + iowait


def proc_ticks(pid):           # utime + stime of one process
    with open(f"/proc/{pid}/stat") as f:
        p = f.read().split()
    return int(p[13]) + int(p[14])


def net_counts(iface=IFACE):   # (rx_packets, rx_bytes)
    with open("/proc/net/dev") as f:
        for line in f:
            if line.strip().startswith(iface + ":"):
                v = line.split(":")[1].split()
                return int(v[1]), int(v[0])
    return 0, 0


def find_pid(name):
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                with open(f"/proc/{pid}/cmdline") as f:
                    if name in f.read():
                        return int(pid)
            except OSError:
                pass
    return None


def read_int(path, default=0):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except OSError:
        return default


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "sample"
    pid = find_pid(IDS_NAME)

    c0, i0 = cpu_times()
    rxp0, rxb0 = net_counts()
    pt0 = proc_ticks(pid) if pid else 0
    time.sleep(WINDOW)
    c1, i1 = cpu_times()
    rxp1, rxb1 = net_counts()
    pt1 = proc_ticks(pid) if pid else 0

    cpu = 100 * (1 - (i1 - i0) / (c1 - c0)) if c1 > c0 else 0
    ids_cpu = 100 * (pt1 - pt0) / (WINDOW * HZ) if pid else 0
    pps = (rxp1 - rxp0) / WINDOW
    mbps = (rxb1 - rxb0) * 8 / 1e6 / WINDOW

    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            mem[line.split(":")[0]] = int(line.split()[1])    # kB
    mem_used_mb = (mem["MemTotal"] - mem["MemAvailable"]) / 1024
    mem_pct = 100 * (mem["MemTotal"] - mem["MemAvailable"]) / mem["MemTotal"]

    ids_rss_kb = 0
    if pid:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    ids_rss_kb = int(line.split()[1])
    ids_rss_mb = ids_rss_kb / 1024

    temp = read_int("/sys/class/thermal/thermal_zone0/temp") / 1000
    freq = read_int("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") / 1000
    with open("/proc/loadavg") as f:
        load1 = f.read().split()[0]
    power_est = P_IDLE_W + (cpu / 100) * (P_FULL_W - P_IDLE_W)

    rows = [
        ("CPU load (whole core)", f"{cpu:5.1f} %"),
        ("  - used by the IDS",   f"{ids_cpu:5.1f} %"),
        ("RAM used",              f"{mem_used_mb:5.0f} MB  ({mem_pct:.0f}% of {mem['MemTotal']//1024} MB)"),
        ("  - IDS process (RSS)", f"{ids_rss_mb:5.0f} MB"),
        ("Power (estimated)",     f"{power_est:5.2f} W   (no sensor, from CPU load)"),
        ("CPU temperature",       f"{temp:5.1f} C"),
        (f"Traffic on {IFACE}",   f"{pps:5.0f} pkt/s  ({mbps:.2f} Mbit/s)"),
        ("Load average (1 min)",  f"{load1}   @ {freq:.0f} MHz"),
    ]
    print(f"\n=== edge-ids metrics [{label}]  (avg over {WINDOW}s) "
          f"{'IDS running' if pid else 'IDS NOT RUNNING'} ===")
    for k, v in rows:
        print(f"  {k:24s} {v}")

    csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metrics.csv")
    new = not os.path.exists(csv)
    with open(csv, "a") as f:
        if new:
            f.write("label,cpu_pct,ids_cpu_pct,mem_used_mb,ids_rss_mb,power_w_est,temp_c,pps,mbps\n")
        f.write(f"{label},{cpu:.1f},{ids_cpu:.1f},{mem_used_mb:.0f},{ids_rss_mb:.0f},"
                f"{power_est:.2f},{temp:.1f},{pps:.0f},{mbps:.2f}\n")
    print(f"  (saved to {csv})\n")


if __name__ == "__main__":
    main()
