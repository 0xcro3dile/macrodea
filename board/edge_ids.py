#!/usr/bin/env python3
"""edge-ids: network intrusion detection that runs on the board itself.

Sniffs one interface and keeps the last 5 seconds of traffic per source IP,
boiled down to six numbers. The int8 model (model.tflite) looks at those
numbers and says what the source is doing. If the model can't be loaded,
simple threshold rules take over. ARP replies are watched for spoofing.

Every alert is printed and published as JSON on the MQTT topic ids/alerts.
A small heartbeat goes to ids/status every 5 seconds while detection runs.

    python3 edge_ids.py                  # what the systemd service runs
    python3 edge_ids.py --record scan    # same, plus log every window to dataset.csv as "scan"

Settings (interface, LAN prefixes, host names) come from environment
variables, see edge-ids.service.
"""
import collections
import json
import os
import subprocess
import sys
import threading
import time

from scapy.all import ARP, IP, TCP, UDP, sniff

HERE = os.path.dirname(os.path.abspath(__file__))

IFACE = os.environ.get("IDS_IFACE", "eth0")
WINDOW = 5        # seconds of history kept per source
COOLDOWN = 5      # don't repeat the same alert for the same source within this time
CONN_TTL = 20     # forget an open connection after this many seconds
HEARTBEAT = 5     # seconds between "still watching" messages on ids/status

# Rule thresholds, tuned for a small single-core board.
SCAN_PORTS = 20   # distinct ports in the window
FLOOD_PPS = 1000  # packets/s seen by the NIC
BF_HITS = 12      # new connections to a single port
LORIS_CONNS = 30  # connections held open on a single port

def env_list(name, default=""):
    return [p.strip() for p in os.environ.get(name, default).split(",") if p.strip()]


# IDS_NAMES="192.168.1.10=plc,192.168.1.20=hmi" lets alerts say who it was.
NAMES = {ip.strip(): who.strip() for ip, _, who in (p.partition("=") for p in env_list("IDS_NAMES")) if who}
# Only sources on our own network are analysed. Replies from the internet
# (updates, NTP, ...) otherwise show up as noise.
PRIVATE = "10.,192.168.," + ",".join(f"172.{n}." for n in range(16, 32))
LAN = tuple(env_list("IDS_LAN", PRIVATE))

RECORD = sys.argv[2] if sys.argv[1:2] == ["--record"] and len(sys.argv) > 2 else None


def iface_ips(iface):
    out = subprocess.check_output(["ip", "-o", "-4", "addr", "show", iface]).decode()
    return {line.split()[3].split("/")[0] for line in out.splitlines()}


MY_IPS = iface_ips(IFACE)
hits = collections.defaultdict(collections.deque)   # src -> deque of (time, dport, is_syn)
conns = collections.defaultdict(dict)                # src -> {(sport, dport): time it was opened}
ipmac = {}                                           # ip -> mac, for the ARP watch
last = {}                                            # (src, type) -> time of the last alert
lock = threading.Lock()                              # hits/conns are shared by sniffer and watcher

rec = None
if RECORD:
    rec_path = os.path.join(HERE, "dataset.csv")
    rec = open(rec_path, "a")
    if os.path.getsize(rec_path) == 0:
        rec.write("ts,src,pkts,ports,syns,top_port,held,nic_pps,label\n")

# The model is optional. No model files or no TFLite runtime just means rules only.
MODEL, MODEL_ERR = None, ""
try:
    import numpy as np
    try:
        from tflite_runtime.interpreter import Interpreter    # what the board has
    except ImportError:
        try:
            import tensorflow as tf                           # full TensorFlow, e.g. on a PC
        except ImportError:
            raise ImportError("tflite_runtime is not installed") from None
        Interpreter = tf.lite.Interpreter
    with open(os.path.join(HERE, "model.json")) as f:
        meta = json.load(f)
    interp = Interpreter(os.path.join(HERE, "model.tflite"))
    interp.allocate_tensors()
    inp, out = interp.get_input_details()[0], interp.get_output_details()[0]
    in_scale, in_zero = inp["quantization"]
    out_scale, out_zero = out["quantization"]
    feat_scale = np.array(meta["scale"], np.float32)
    MODEL = meta["labels"]
except Exception as e:
    MODEL_ERR = str(e)


def model_predict(feats):
    """Run one window through the int8 model, return (label, confidence)."""
    x = np.log1p(np.array(feats, np.float32)) / feat_scale        # same scaling as in training
    q = np.clip(np.round(x / in_scale + in_zero), -128, 127).astype(np.int8)
    interp.set_tensor(inp["index"], q.reshape(inp["shape"]))
    interp.invoke()
    probs = (interp.get_tensor(out["index"]).astype(np.float32) - out_zero) * out_scale
    probs = probs.reshape(-1)
    best = int(probs.argmax())
    return MODEL[best], float(probs[best])


def publish(msg, topic="ids/alerts"):
    subprocess.Popen(["mosquitto_pub", "-t", topic, "-m", msg])


def alert(kind, src, detail, detector="rule"):
    now = time.time()
    if now - last.get((src, kind), 0) < COOLDOWN:
        return
    last[(src, kind)] = now
    msg = json.dumps({"time": time.strftime("%H:%M:%S"), "type": kind, "src": src,
                      "who": NAMES.get(src, "unknown"), "detector": detector, "detail": detail})
    print("ALERT", msg, flush=True)
    publish(msg)


def learn(ip, mac):
    # An IP that suddenly answers from a different MAC is being spoofed.
    if ipmac.get(ip, mac) != mac:
        alert("mitm", ip, f"mac changed {ipmac[ip]} -> {mac}")
    ipmac[ip] = mac


def on_packet(pkt):
    if pkt.haslayer(ARP):
        if pkt[ARP].op == 2:                      # is-at (reply)
            learn(pkt[ARP].psrc, pkt[ARP].hwsrc)
        return
    if not pkt.haslayer(IP) or pkt[IP].src in MY_IPS:
        return
    src = pkt[IP].src
    if not src.startswith(LAN):
        return
    learn(src, pkt.src)
    if pkt.haslayer(TCP):
        flags, sport, dport = pkt[TCP].flags, pkt[TCP].sport, pkt[TCP].dport
        syn = bool(flags & 0x02 and not flags & 0x10)             # SYN without ACK = new connection
        with lock:
            if syn:
                conns[src][(sport, dport)] = time.time()
            elif flags & 0x01 or flags & 0x04:                   # FIN or RST closes it
                conns[src].pop((sport, dport), None)
            hits[src].append((time.time(), dport, syn))
    elif pkt.haslayer(UDP):
        with lock:
            hits[src].append((time.time(), pkt[UDP].dport, False))


def rx_packets():
    # Under a flood scapy only gets to see a fraction of the packets on this
    # single core. The kernel's own counter sees all of them.
    with open(f"/sys/class/net/{IFACE}/statistics/rx_packets") as f:
        return int(f.read())


def check(now, pps):
    """Look at the last WINDOW seconds of every source and raise alerts."""
    snap = []
    with lock:                                  # copy quickly, do the real work without the lock
        for src in list(hits):
            q = hits[src]
            while q and now - q[0][0] > WINDOW:
                q.popleft()
            for key, opened in list(conns[src].items()):
                if now - opened > CONN_TTL:
                    del conns[src][key]
            if not q and not conns[src]:
                del hits[src]
                conns.pop(src, None)
                continue
            snap.append((src, list(q), list(conns[src])))

    if pps > FLOOD_PPS:
        # The NIC counter doesn't know who is flooding, so blame the loudest source.
        loudest = max(snap, key=lambda s: len(s[1]))[0] if snap else "?"
        alert("flood", loudest, f"{int(pps)} pkt/s")

    for src, pkts, open_conns in snap:
        ports = {dport for _, dport, _ in pkts}
        syns = collections.Counter(dport for _, dport, syn in pkts if syn)
        top = max(syns.values(), default=0)
        # Held connections on the busiest port. Port 22 is skipped so our own
        # ssh session to the board doesn't count.
        held = collections.Counter(dport for _, dport in open_conns if dport != 22).most_common(1)
        held_n = held[0][1] if held else 0
        feats = [len(pkts), len(ports), sum(syns.values()), top, held_n, int(pps)]

        # A source that is barely talking isn't worth asking the model about.
        # Those trickles were where the false alarms came from.
        busy = len(pkts) >= 15 or len(ports) > 4 or held_n > 4
        if MODEL and busy:
            label, conf = model_predict(feats)
            if label != "normal" and conf >= 0.75:
                alert(label, src, f"model {int(conf * 100)}% (ports={len(ports)} held={held_n})", detector="model")
        # No model (or a quiet source): plain rules.
        elif len(ports) > SCAN_PORTS:
            alert("scan", src, f"{len(ports)} ports in {WINDOW}s")
        elif held_n > LORIS_CONNS and pps < FLOOD_PPS:
            alert("slowloris", src, f"{held_n} connections held open on port {held[0][0]}")
        elif top > BF_HITS and len(ports) <= 3:
            alert("bruteforce", src, f"{top} attempts on port {syns.most_common(1)[0][0]}")

        if rec:
            rec.write(f"{now:.0f},{src}," + ",".join(str(v) for v in feats) + f",{RECORD}\n")
            rec.flush()


def watcher():
    r0, t0 = rx_packets(), time.time()
    ticks = 0
    while True:
        time.sleep(1)
        try:
            r1, t1 = rx_packets(), time.time()
            pps = (r1 - r0) / (t1 - t0)
            r0, t0 = r1, t1
            check(time.time(), pps)
            ticks += 1
            if ticks % HEARTBEAT == 0:
                # Sent from inside the loop on purpose: it proves detection is
                # actually running, not just that the process is still there.
                publish(json.dumps({"ts": int(time.time()), "model": "on" if MODEL else "off"}), "ids/status")
        except Exception as e:                  # one bad tick must not kill detection
            print("watcher error (continuing):", e, flush=True)


if __name__ == "__main__":
    model = "on" if MODEL else f"off, rules only ({MODEL_ERR})"
    print(f"edge-ids on {IFACE} {sorted(MY_IPS)} | model: {model}"
          + (f" | recording '{RECORD}'" if RECORD else ""), flush=True)
    threading.Thread(target=watcher, daemon=True).start()
    sniff(iface=IFACE, prn=on_packet, store=False)
