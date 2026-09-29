#!/usr/bin/env python3
# Draws docs/architecture.png. architecture.drawio next to it is the same
# picture for editing by hand in draw.io (app.diagrams.net).
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(13, 5.4))
ax.set_xlim(0, 13)
ax.set_ylim(0.4, 5.6)
ax.axis("off")


def box(x, y, w, h, text, fc, ec, fs=11, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.12",
                                linewidth=1.6, edgecolor=ec, facecolor=fc))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal")


def arrow(x1, y1, x2, y2, label="", at=None):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=1.8, color="#444"))
    if label:
        ax.text(*(at or ((x1 + x2) / 2, (y1 + y2) / 2 + 0.15)), label, ha="center", fontsize=9, color="#555")


ax.text(0.2, 5.3, "edge-ids: intrusion detection on the SAMA7D65", fontsize=16, fontweight="bold")

box(0.3, 2.3, 2.7, 1.4, "Any machine on the LAN\ntools/simulate.py\nscan, flood, brute force,\nslowloris", "#f8cecc", "#b85450")

ax.add_patch(FancyBboxPatch((3.8, 0.8), 4.8, 4.0, boxstyle="round,pad=0.05,rounding_size=0.12",
                            linewidth=1.8, edgecolor="#6c8ebf", facecolor="none"))
ax.text(6.2, 4.5, "SAMA7D65 board  (board/edge_ids.py)", ha="center", fontsize=11, fontweight="bold", color="#3b5b8c")
box(4.1, 3.6, 4.2, 0.6, "1  capture packets on eth0 (scapy)", "#dae8fc", "#6c8ebf", 10)
box(4.1, 2.75, 4.2, 0.65, "2  last 5 s per source IP -> 6 numbers", "#dae8fc", "#6c8ebf", 10)
box(4.1, 1.85, 4.2, 0.7, "3  int8 TFLite model\n(rules as fallback, ARP watch)", "#ffe6cc", "#d79b00", 10, True)
box(4.1, 1.05, 4.2, 0.6, "4  alert as JSON on MQTT ids/alerts", "#dae8fc", "#6c8ebf", 10)

box(9.5, 2.3, 3.2, 1.4, "tools/dashboard.py\nor any MQTT client", "#e1d5e7", "#9673a6", 10)

arrow(3.0, 3.0, 4.1, 3.85, "network", at=(3.25, 3.65))
arrow(6.2, 3.6, 6.2, 3.4)
arrow(6.2, 2.75, 6.2, 2.55)
arrow(6.2, 1.85, 6.2, 1.65)
arrow(8.3, 1.35, 9.5, 2.6, "MQTT", at=(9.35, 1.8))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture.png")
fig.savefig(out, dpi=150, bbox_inches="tight")
print("wrote", out)
