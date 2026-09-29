#!/usr/bin/env python3
# Charts from the board measurements: traffic.csv (board/sample_traffic.py)
# and metrics.csv (board/metrics.py, run with labels "idle" and "attack").
# Copy the CSVs off the board, then:
#
#   scp root@<board>:/root/ids/traffic.csv root@<board>:/root/ids/metrics.csv .
#   python3 tools/plot_results.py .
#
# Writes traffic.png and metrics.png into the same folder.
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

folder = sys.argv[1] if len(sys.argv) > 1 else "."

# packet rate over time
t, pps = [], []
with open(os.path.join(folder, "traffic.csv")) as f:
    for r in csv.DictReader(f):
        t.append(float(r["t"]))
        pps.append(float(r["pps"]))

fig, ax = plt.subplots(figsize=(18, 9))
ax.plot(t, pps, color="#c0392b", linewidth=2.5)
ax.fill_between(t, pps, color="#c0392b", alpha=0.15)
ax.set_xlabel("seconds", fontsize=17)
ax.set_ylabel("packets / second", fontsize=17)
ax.tick_params(labelsize=13)
fig.tight_layout()
fig.savefig(os.path.join(folder, "traffic.png"), dpi=160)

# idle vs attack, one small bar chart per number
m = {}
with open(os.path.join(folder, "metrics.csv")) as f:
    for r in csv.DictReader(f):
        m[r["label"]] = r            # last run per label wins
idle, atk = m["idle"], m["attack"]
fields = [("cpu %", "cpu_pct"), ("ids cpu %", "ids_cpu_pct"), ("ram mb", "mem_used_mb"),
          ("power w", "power_w_est"), ("temp c", "temp_c"), ("pkt/s", "pps")]

fig, axes = plt.subplots(2, 3, figsize=(18, 10))
for ax, (lab, key) in zip(axes.flat, fields):
    vals = [float(idle[key]), float(atk[key])]
    ax.bar(["idle", "attack"], vals, color=["#7f8c8d", "#c0392b"], width=0.6)
    ax.set_xlabel(lab, fontsize=16)
    ax.tick_params(labelsize=12)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:g}", ha="center", va="bottom", fontsize=13)
    ax.margins(y=0.18)
fig.tight_layout()
fig.savefig(os.path.join(folder, "metrics.png"), dpi=160)

print("wrote traffic.png and metrics.png in", folder)
