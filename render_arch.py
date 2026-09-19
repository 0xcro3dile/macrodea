#!/usr/bin/env python3
# render architecture.png from the same layout as architecture.drawio
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(13, 6)); ax.set_xlim(0, 13); ax.set_ylim(0, 6); ax.axis("off")
def box(x, y, w, h, text, fc, ec, fs=11, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.12",
                                linewidth=1.6, edgecolor=ec, facecolor=fc))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal")
def arrow(x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=1.8, color="#444"))
    if label: ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, label, ha="center", fontsize=9, color="#555")

ax.text(0.2, 5.7, "macrodea — Edge AI Intrusion Detection", fontsize=16, fontweight="bold")
box(0.3, 2.5, 2.6, 1.3, "Attacker PCs\n10.40.58.x\nsimulate.py\n(scan/flood/bf/loris)", "#f8cecc", "#b85450")
box(3.6, 2.5, 2.8, 1.3, "Laptop / Gateway\n10.40.58.21 · 10.42.0.1\nroute + forward + NAT", "#d5e8d4", "#82b366")
# board container
ax.add_patch(FancyBboxPatch((7.1, 1.3), 3.1, 4.0, boxstyle="round,pad=0.05,rounding_size=0.12",
                            linewidth=1.8, edgecolor="#6c8ebf", facecolor="none"))
ax.text(8.65, 5.05, "SAMA7 board — 10.42.0.208", ha="center", fontsize=11, fontweight="bold", color="#3b5b8c")
box(7.35, 4.25, 2.6, 0.6, "1 · sniff eth0 (scapy)", "#dae8fc", "#6c8ebf", 10)
box(7.35, 3.4, 2.6, 0.7, "2 · 5s window → 6 features", "#dae8fc", "#6c8ebf", 10)
box(7.35, 2.5, 2.6, 0.7, "3 · int8 TFLite model\n+ rules + ARP watch", "#ffe6cc", "#d79b00", 10, True)
box(7.35, 1.65, 2.6, 0.6, "4 · alert → MQTT", "#dae8fc", "#6c8ebf", 10)
box(10.7, 2.5, 2.1, 1.3, "Dashboard\n(defender)\nlive + red alerts\nnames attacker", "#e1d5e7", "#9673a6", 10)

arrow(2.9, 3.15, 3.6, 3.15, "wifi")
arrow(6.4, 3.15, 7.35, 3.15, "cable")
arrow(8.65, 4.25, 8.65, 4.1); arrow(8.65, 3.4, 8.65, 3.2); arrow(8.65, 2.5, 8.65, 2.35)
arrow(9.95, 1.95, 10.7, 2.9, "MQTT")
fig.tight_layout(); fig.savefig("architecture.png", dpi=150, bbox_inches="tight")
print("wrote architecture.png")
