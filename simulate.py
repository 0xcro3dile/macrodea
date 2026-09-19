#!/usr/bin/env python3
# attacker simulator for OUR OWN board (edge-ids demo). run from another pc:
#   python3 simulate.py <board-ip> {normal|scan|flood|bruteforce|slowloris}
# wifi pcs add a route once:  sudo ip route add 10.42.0.0/24 via 10.40.58.21
import sys, time, socket


def normal(ip):                        # a few polite connections, like a real client
    for _ in range(10):
        s = socket.socket(); s.settimeout(0.5)
        try: s.connect((ip, 1883))
        except OSError: pass
        s.close(); time.sleep(1)


def scan(ip):                          # knock on ports 1..1000 -> port scan
    for port in range(1, 1001):
        s = socket.socket(); s.settimeout(0.05)
        try: s.connect((ip, port))
        except OSError: pass
        s.close()


def flood(ip, seconds=5, port=80):     # hammer one port with udp -> flood
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); data = b"x" * 64
    end, sent = time.time() + seconds, 0
    while time.time() < end:
        s.sendto(data, (ip, port)); sent += 1
    return sent


def bruteforce(ip, tries=40, port=22):  # many quick connects to one port -> brute-force
    for _ in range(tries):
        s = socket.socket(); s.settimeout(0.3)
        try: s.connect((ip, port))
        except OSError: pass
        s.close()


def slowloris(ip, conns=60, port=1883, hold=15):   # open many connections and HOLD them
    socks = []
    for _ in range(conns):
        try:
            s = socket.socket(); s.settimeout(2); s.connect((ip, port)); socks.append(s)
        except OSError: pass
    time.sleep(hold)                    # keep them open -- that is the attack
    for s in socks: s.close()
    return len(socks)


MODES = {"normal": normal, "scan": scan, "flood": flood,
         "bruteforce": bruteforce, "slowloris": slowloris}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in MODES:
        print("usage: python3 simulate.py <board-ip> {normal|scan|flood|bruteforce|slowloris}")
        sys.exit(1)
    ip, mode = sys.argv[1], sys.argv[2]
    print(f"sending {mode} traffic to {ip} ...", flush=True)
    r = MODES[mode](ip)
    print(f"done -- sent {r} packets." if mode == "flood" else f"done ({r} connections)." if mode == "slowloris" else "done.")
