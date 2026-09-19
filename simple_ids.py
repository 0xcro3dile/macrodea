#!/usr/bin/env python3
# edge-ids: scan / flood / brute-force / slow-loris / arp-spoof(mitm). counting + arp watch.
# alerts name the attacker (who + ip + type) -> print + mqtt ids/alerts.
# "--record LABEL" logs feature rows to dataset.csv for training.
import os, sys, time, json, threading, subprocess, collections
from scapy.all import sniff, IP, TCP, UDP, ARP

IFACE, WINDOW, COOLDOWN = "eth0", 5, 5
SCAN_PORTS, FLOOD_PPS, BF_HITS, LORIS_CONNS = 20, 1000, 12, 30      # thresholds (small device)
NAMES = {"10.42.0.1": "laptop", "10.40.58.23": "pc-23", "10.40.58.24": "pc-24",
         "10.40.58.136": "pc-136", "10.40.58.188": "pc-188"}       # ip -> who
LAN = ("10.42.0.", "10.40.58.")            # only analyze our own segments (ignore internet return traffic)
RECORD = sys.argv[2] if sys.argv[1:2] == ["--record"] and len(sys.argv) > 2 else None


def iface_ips(i):
    out = subprocess.check_output(["ip", "-o", "-4", "addr", "show", i]).decode()
    return {l.split()[3].split("/")[0] for l in out.splitlines()}


MY_IPS = iface_ips(IFACE)
hits   = collections.defaultdict(collections.deque)   # src -> deque(t, dport, syn)
conns  = collections.defaultdict(dict)                # src -> {(sport,dport): open_time}
ipmac  = {}                                           # ip -> mac (arp watch)
last   = {}
csv    = open("/root/ids/dataset.csv", "a") if RECORD else None
if RECORD and os.path.getsize("/root/ids/dataset.csv") == 0:
    csv.write("ts,src,pkts,ports,syns,top_port,held,nic_pps,label\n")

# --- optional int8 tflite model (auto-loaded if model.tflite is present) ---------
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = None
try:
    import numpy as _np, tflite_runtime.interpreter as _tfl
    _mj = json.load(open(os.path.join(HERE, "model.json")))
    _it = _tfl.Interpreter(os.path.join(HERE, "model.tflite")); _it.allocate_tensors()
    _inp, _out = _it.get_input_details()[0], _it.get_output_details()[0]
    _si, _zi = _inp["quantization"]; _so, _zo = _out["quantization"]
    _scale = _np.array(_mj["scale"], _np.float32); MODEL = _mj["labels"]
except Exception:
    MODEL = None


def model_predict(feats):                  # feats -> (label, confidence)
    x = _np.log1p(_np.array(feats, _np.float32)) / _scale
    q = _np.clip(_np.round(x/_si + _zi), -128, 127).astype(_np.int8).reshape(_inp["shape"])
    _it.set_tensor(_inp["index"], q); _it.invoke()
    o = (_it.get_tensor(_out["index"]).astype(_np.float32) - _zo) * _so
    o = o.reshape(-1); c = int(o.argmax())
    return MODEL[c], float(o[c])


def alert(kind, src, detail, detector="rule"):
    t = time.time()
    if t - last.get((src, kind), 0) < COOLDOWN:
        return
    last[(src, kind)] = t
    m = json.dumps({"time": time.strftime("%H:%M:%S"), "type": kind, "src": src,
                    "who": NAMES.get(src, "unknown"), "detector": detector, "detail": detail})
    print("ALERT", m, flush=True)
    subprocess.Popen(["mosquitto_pub", "-t", "ids/alerts", "-m", m])


def learn(ip, mac):                        # an ip's mac must not change -> else arp spoof
    if ipmac.get(ip, mac) != mac:
        alert("mitm", ip, f"mac changed {ipmac[ip]} -> {mac}")
    ipmac[ip] = mac


def on_packet(pkt):
    if pkt.haslayer(ARP):
        if pkt[ARP].op == 2:
            learn(pkt[ARP].psrc, pkt[ARP].hwsrc)
        return
    if not pkt.haslayer(IP) or pkt[IP].src in MY_IPS:
        return
    src = pkt[IP].src
    if not src.startswith(LAN):            # ignore internet return traffic (no false alarms)
        return
    learn(src, pkt.src)
    if pkt.haslayer(TCP):
        fl, sp, dp = pkt[TCP].flags, pkt[TCP].sport, pkt[TCP].dport
        syn = bool(fl & 0x02 and not fl & 0x10)
        if syn:
            conns[src][(sp, dp)] = time.time()             # connection opened
        elif fl & 0x01 or fl & 0x04:
            conns[src].pop((sp, dp), None)                 # FIN/RST -> closed
        hits[src].append((time.time(), dp, syn))
    elif pkt.haslayer(UDP):
        hits[src].append((time.time(), pkt[UDP].dport, False))


def rx():
    return int(open(f"/sys/class/net/{IFACE}/statistics/rx_packets").read())


def watcher():
    r0, t0 = rx(), time.time()
    while True:
        time.sleep(1)
        r1, t1 = rx(), time.time()
        pps = (r1 - r0) / (t1 - t0); r0, t0 = r1, t1
        now = time.time()
        if pps > FLOOD_PPS:
            alert("flood", max(hits, key=lambda s: len(hits[s]), default="?"), f"{int(pps)} pkt/s")
        for src in list(hits):
            q = hits[src]
            while q and now - q[0][0] > WINDOW:
                q.popleft()
            for k, ts in list(conns[src].items()):         # forget connections held absurdly long
                if now - ts > 120:
                    del conns[src][k]
            if not q and not conns[src]:
                del hits[src]; conns.pop(src, None); continue
            ports = {d for _, d, _ in q}
            syns = collections.Counter(d for _, d, s in q if s)
            top = max(syns.values(), default=0)
            held = collections.Counter(d for _, d in conns[src] if d != 22).most_common(1)  # ignore mgmt ssh
            held_n = held[0][1] if held else 0
            active = len(q) >= 15 or len(ports) > 4 or held_n > 4    # ignore trickle traffic
            if MODEL and active:                       # AI model makes the call
                lab, conf = model_predict([len(q), len(ports), sum(syns.values()), top, held_n, int(pps)])
                if lab != "normal" and conf >= 0.75:      # ignore low-confidence guesses
                    alert(lab, src, f"model {int(conf*100)}% (ports={len(ports)} held={held_n})", detector="model")
            elif len(ports) > SCAN_PORTS:              # rules (fallback when no model)
                alert("scan", src, f"{len(ports)} ports in {WINDOW}s")
            elif held_n > LORIS_CONNS and pps < FLOOD_PPS:
                alert("slowloris", src, f"{held_n} connections held open on port {held[0][0]}")
            elif top > BF_HITS and len(ports) <= 3:
                alert("bruteforce", src, f"{top} attempts on port {syns.most_common(1)[0][0]}")
            if csv:
                csv.write(f"{now:.0f},{src},{len(q)},{len(ports)},{sum(syns.values())},{top},{held_n},{int(pps)},{RECORD}\n")
                csv.flush()


if __name__ == "__main__":
    print(f"edge-ids on {IFACE} {sorted(MY_IPS)} | model:{'on' if MODEL else 'off (rules)'}"
          + (f" | recording '{RECORD}'" if RECORD else ""), flush=True)
    threading.Thread(target=watcher, daemon=True).start()
    sniff(iface=IFACE, prn=on_packet, store=False)
