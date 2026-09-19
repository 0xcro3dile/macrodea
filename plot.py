#!/usr/bin/env python3
# make big png charts from traffic.csv + metrics.csv. lowercase, minimal, no titles.
import csv, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = "/root/ids"

# ---- 1) traffic captured over time
t, pps = [], []
with open(f"{D}/traffic.csv") as f:
    for r in csv.DictReader(f):
        t.append(float(r["t"])); pps.append(float(r["pps"]))

fig, ax = plt.subplots(figsize=(18, 9))
ax.plot(t, pps, color="#c0392b", linewidth=2.5)
ax.fill_between(t, pps, color="#c0392b", alpha=0.15)
ax.set_xlabel("seconds", fontsize=17)
ax.set_ylabel("packets / second", fontsize=17)
ax.tick_params(labelsize=13)
peak = max(pps)
for x, y, lab in [(4.5, 2000, "scan"), (10.3, peak, "flood"), (18.7, peak, "flood")]:
    ax.annotate(lab, xy=(x, y), xytext=(x, y + peak * 0.08), ha="center",
                fontsize=14, color="#333")
fig.tight_layout()
fig.savefig(f"{D}/traffic.png", dpi=160)

# ---- 2) footprint: idle vs attack
m = {}
with open(f"{D}/metrics.csv") as f:
    for r in csv.DictReader(f):
        m[r["label"]] = r
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
fig.savefig(f"{D}/metrics.png", dpi=160)

print("wrote traffic.png and metrics.png")
