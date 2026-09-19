#!/usr/bin/env python3
# Edge IDS live watcher dashboard. Runs on the LAPTOP (fires traffic at the board,
# streams the board's MQTT alerts back). stdlib only.  ->  http://<laptop-ip>:8080
import http.server, socketserver, json, subprocess, threading
import collections, urllib.parse, socket, time

BOARD = "10.42.0.208"
PEERS = ["10.40.58.23", "10.40.58.24", "10.40.58.136", "10.40.58.188"]
NAMES = {"10.42.0.1": "laptop", BOARD: "board", "10.40.58.23": "pc-23",
         "10.40.58.24": "pc-24", "10.40.58.136": "pc-136", "10.40.58.188": "pc-188"}
PORT = 8080
alerts = collections.deque(maxlen=80)     # newest first
seen = {}                                 # peer ip -> reachable


def alert_reader():                       # stream board MQTT alerts over ssh
    while True:
        try:
            p = subprocess.Popen(["ssh", "-o", "BatchMode=yes", f"root@{BOARD}",
                                  "mosquitto_sub -t ids/alerts"], stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                line = line.strip()
                if line:
                    alerts.appendleft(line)
        except Exception:
            time.sleep(2)


def peer_poller():
    while True:
        for ip in PEERS:
            ok = subprocess.call(["ping", "-c", "1", "-W", "1", ip],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
            seen[ip] = ok or seen.get(ip, False)
        time.sleep(3)


def do_normal():
    for _ in range(10):
        s = socket.socket(); s.settimeout(0.5)
        try: s.connect((BOARD, 1883))
        except OSError: pass
        s.close(); time.sleep(0.2)

def do_scan():
    for port in range(1, 1001):
        s = socket.socket(); s.settimeout(0.05)
        try: s.connect((BOARD, port))
        except OSError: pass
        s.close()

def do_flood():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); d = b"x" * 64
    end = time.time() + 5
    while time.time() < end:
        s.sendto(d, (BOARD, 80))

def do_bruteforce():                      # many quick connects to one service port
    for _ in range(50):
        s = socket.socket(); s.settimeout(0.3)
        try: s.connect((BOARD, 1883))
        except OSError: pass
        s.close()

def do_slowloris():                       # open many connections and hold them
    socks = []
    for _ in range(60):
        try:
            s = socket.socket(); s.settimeout(2); s.connect((BOARD, 1883)); socks.append(s)
        except OSError: pass
    time.sleep(16)
    for s in socks: s.close()

ATTACKS = {"normal": do_normal, "scan": do_scan, "flood": do_flood,
           "bruteforce": do_bruteforce, "slowloris": do_slowloris}


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(200, "text/html", PAGE.replace("__BOARD__", BOARD))
        elif path == "/peers":
            self._send(200, "application/json",
                       json.dumps([{"ip": ip, "name": NAMES.get(ip, ip), "up": seen.get(ip, False)} for ip in PEERS]))
        elif path == "/alerts":
            self._send(200, "application/json", json.dumps(list(alerts)))
        else:
            self._send(404, "text/plain", "not found")

    def do_POST(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        t = q.get("type", [""])[0]
        if t in ATTACKS:
            threading.Thread(target=ATTACKS[t], daemon=True).start()
            self._send(200, "application/json", json.dumps({"ok": True, "type": t}))
        else:
            self._send(400, "application/json", json.dumps({"ok": False}))

    def log_message(self, *a):
        pass


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Edge IDS</title><style>
:root{
  --bg:#0a0e14; --panel:#111823; --panel2:#0d141d; --line:#1e2a38; --line2:#2a3a4d;
  --tx:#e6edf3; --mut:#8493a5; --dim:#5b6b7d;
  --green:#3fb950; --greenbg:#0f2417; --red:#f85149; --redbg:#2a1113;
  --amber:#e3b341; --amberbg:#2a2210; --blue:#58a6ff; --violet:#bc8cff;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#111c2b 0,var(--bg) 60%);
  color:var(--tx);font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  padding-bottom:env(safe-area-inset-bottom,0px)}
a{color:inherit}
header{position:sticky;top:env(safe-area-inset-top,0px);z-index:10;display:flex;align-items:center;gap:14px;
  padding:14px 22px;background:rgba(10,14,20,.82);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;letter-spacing:.2px}
.hex{width:22px;height:22px;color:var(--blue)}
.live{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--mut);
  border:1px solid var(--line2);border-radius:999px;padding:5px 12px}
.live .pulse{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 0 0 rgba(63,185,80,.6);
  animation:pulse 1.8s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(63,185,80,.55)}70%{box-shadow:0 0 0 7px rgba(63,185,80,0)}100%{box-shadow:0 0 0 0 rgba(63,185,80,0)}}
main{max-width:1100px;margin:0 auto;padding:22px 16px;display:grid;gap:18px}
h2{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin:0 0 12px;font-weight:700}

/* threat hero */
.hero{border-radius:16px;padding:22px 24px;border:1px solid var(--line);background:var(--panel);
  display:flex;align-items:center;gap:18px;transition:.35s}
.hero .ic{width:52px;height:52px;flex:0 0 auto}
.hero .big{font-size:22px;font-weight:800;letter-spacing:.2px}
.hero .sub{color:var(--mut);font-size:13px;margin-top:2px}
.hero.safe{background:linear-gradient(120deg,var(--greenbg),var(--panel));border-color:#1c4029}
.hero.safe .ic{color:var(--green)} .hero.safe .big{color:#7ee2a8}
.hero.alarm{background:linear-gradient(120deg,var(--redbg),var(--panel));border-color:#5b1d1f;
  animation:flash 1.1s infinite}
.hero.alarm .ic{color:var(--red)} .hero.alarm .big{color:#ff8a80}
@keyframes flash{0%,100%{box-shadow:0 0 0 0 rgba(248,81,73,0)}50%{box-shadow:0 0 26px 0 rgba(248,81,73,.28)}}

.cols{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}
@media(max-width:820px){.cols{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}

/* live monitor */
.hosts{display:grid;gap:10px}
.host{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:12px;
  background:var(--panel2);border:1px solid var(--line);transition:.25s}
.host .dot{width:10px;height:10px;border-radius:50%;flex:0 0 auto;background:var(--dim)}
.host.on .dot{background:var(--green)}
.host.threat{border-color:#5b1d1f;background:linear-gradient(90deg,var(--redbg),var(--panel2))}
.host.threat .dot{background:var(--red);animation:pulse2 1.2s infinite}
@keyframes pulse2{0%{box-shadow:0 0 0 0 rgba(248,81,73,.6)}70%{box-shadow:0 0 0 7px rgba(248,81,73,0)}100%{box-shadow:0 0 0 0 rgba(248,81,73,0)}}
.host .id{display:flex;flex-direction:column}
.host .id b{font-size:14px} .host .id span{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.host .state{margin-left:auto;text-align:right}
.host .tag{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.host.threat .tag{color:#ff8a80}
.host .conf{font-size:11px;color:var(--dim);font-family:var(--mono)}

/* attack buttons */
.atk{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.btn{border:1px solid var(--line2);border-radius:12px;padding:14px 12px;cursor:pointer;
  background:var(--panel2);color:var(--tx);font:inherit;text-align:left;transition:.18s;display:flex;flex-direction:column;gap:3px}
.btn:hover{transform:translateY(-2px);border-color:var(--line2);filter:brightness(1.12)}
.btn:active{transform:translateY(0)} .btn:disabled{opacity:.55;cursor:wait}
.btn .n{font-weight:700;font-size:14px} .btn .d{font-size:11.5px;color:var(--mut)}
.btn.scan{border-left:3px solid var(--amber)} .btn.flood{border-left:3px solid var(--red)}
.btn.bruteforce{border-left:3px solid var(--violet)} .btn.slowloris{border-left:3px solid var(--blue)}
.btn.normal{border-left:3px solid var(--green);grid-column:1/-1}

/* feed */
#feed{max-height:340px;overflow:auto;display:flex;flex-direction:column;gap:6px}
.ev{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:10px;background:var(--panel2);
  border-left:3px solid var(--red);font-size:13px;animation:in .3s ease}
@keyframes in{from{opacity:0;transform:translateY(-4px)}to{opacity:1}}
.ev .t{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.ev .badge{font-size:10.5px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;
  padding:2px 8px;border-radius:6px;background:var(--redbg);color:#ff8a80}
.ev .who{font-weight:700} .ev .ip{font-family:var(--mono);color:var(--mut);font-size:12px}
.ev .det{margin-left:auto;color:var(--dim);font-size:11px;font-family:var(--mono)}
.ev.det-model .badge{background:#161f2e;color:var(--blue)}
.empty{color:var(--dim);text-align:center;padding:26px;font-size:13px}
.foot{color:var(--dim);font-size:11.5px;text-align:center;padding:6px 0 2px}
</style></head><body>
<header>
  <div class="brand"><svg class="hex" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M12 2l8.5 5v10L12 22l-8.5-5V7z"/><path d="M9 12l2 2 4-4"/></svg>Edge&nbsp;IDS</div>
  <div class="live"><span class="pulse"></span>MONITORING &middot; board __BOARD__</div>
</header>
<main>
  <div class="hero safe" id="hero">
    <svg class="ic" id="heroic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
      <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>
    <div><div class="big" id="herobig">SECURE</div>
      <div class="sub" id="herosub">no threats detected &middot; watching live traffic</div></div>
  </div>

  <div class="cols">
    <section class="panel"><h2>Live monitor &mdash; who's doing what</h2>
      <div class="hosts" id="hosts"><div class="empty">discovering hosts&hellip;</div></div></section>
    <section class="panel"><h2>Attack simulator</h2>
      <div class="atk">
        <button class="btn scan" onclick="fire('scan',this)"><span class="n">Port scan</span><span class="d">probe 1000 ports</span></button>
        <button class="btn flood" onclick="fire('flood',this)"><span class="n">UDP flood</span><span class="d">packet storm</span></button>
        <button class="btn bruteforce" onclick="fire('bruteforce',this)"><span class="n">Brute force</span><span class="d">hammer one port</span></button>
        <button class="btn slowloris" onclick="fire('slowloris',this)"><span class="n">Slowloris</span><span class="d">hold connections</span></button>
        <button class="btn normal" onclick="fire('normal',this)"><span class="n">Normal traffic</span><span class="d">behave &mdash; should stay silent</span></button>
      </div></section>
  </div>

  <section class="panel"><h2>Threat feed</h2>
    <div id="feed"><div class="empty">waiting for activity&hellip;</div></div></section>
  <div class="foot">Edge IDS &middot; quantized model + rules running on the SAMA7 board</div>
</main>
<script>
const LAPTOP="10.42.0.1";
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function fire(t,b){b.disabled=true;const o=b.querySelector('.n').textContent;b.querySelector('.n').textContent='running…';
  fetch('/attack?type='+t,{method:'POST'}).finally(()=>setTimeout(()=>{b.disabled=false;b.querySelector('.n').textContent=o},t==='slowloris'?17000:5200));}

let lastKey=null, quiet=99;
async function tick(){
  let raw=[],peers=[];
  try{raw=await (await fetch('/alerts')).json();}catch(e){}
  try{peers=await (await fetch('/peers')).json();}catch(e){}
  const evs=raw.map(s=>{try{return JSON.parse(s)}catch(e){return null}}).filter(Boolean);
  const now=Date.now();
  // recent (last ~8s) attacks per source, keyed by src
  const recent={};
  for(const e of evs){ if(!recent[e.src]) recent[e.src]=e; }   // evs newest-first
  const isFresh=evs.length && (()=>{const k=evs[0].time+evs[0].type+evs[0].src;
    if(k!==lastKey){lastKey=k;quiet=0;}else{quiet++;} return quiet<8;})();

  // hosts = laptop + peers + any attacking src
  const hostmap={};
  hostmap[LAPTOP]={ip:LAPTOP,name:'laptop',up:true};
  for(const p of peers) hostmap[p.ip]={ip:p.ip,name:p.name,up:p.up};
  for(const e of evs.slice(0,12)) if(!hostmap[e.src]) hostmap[e.src]={ip:e.src,name:e.who||'host',up:true};
  const hosts=Object.values(hostmap);
  document.getElementById('hosts').innerHTML = hosts.map(h=>{
    const a = isFresh ? recent[h.ip] : null;
    const threat = !!a;
    const tag = threat ? a.type : (h.up?'quiet':'offline');
    const conf = threat ? (a.detail||'') : '';
    return `<div class="host ${threat?'threat':(h.up?'on':'')}">
      <span class="dot"></span>
      <div class="id"><b>${esc(h.name)}</b><span>${esc(h.ip)}</span></div>
      <div class="state"><div class="tag">${esc(tag)}</div><div class="conf">${esc(conf)}</div></div></div>`;
  }).join('') || '<div class="empty">no hosts</div>';

  // hero
  const hero=document.getElementById('hero'), big=document.getElementById('herobig'),
        sub=document.getElementById('herosub');
  if(isFresh){const e=evs[0]; hero.className='hero alarm';
    big.textContent='UNDER ATTACK';
    sub.innerHTML=`<b>${esc(e.type)}</b> from ${esc(e.who||'?')} (${esc(e.src)}) &middot; detected by ${esc(e.detector||'rule')}`;}
  else{hero.className='hero safe'; big.textContent='SECURE';
    sub.textContent='no threats detected · watching live traffic';}

  // feed
  const feed=document.getElementById('feed');
  feed.innerHTML = evs.length ? evs.map(e=>
    `<div class="ev det-${esc(e.detector||'rule')}"><span class="t">${esc(e.time)}</span>
      <span class="badge">${esc(e.type)}</span>
      <span class="who">${esc(e.who||'?')}</span> <span class="ip">${esc(e.src)}</span>
      <span class="det">[${esc(e.detector||'rule')}] ${esc(e.detail||'')}</span></div>`).join('')
    : '<div class="empty">waiting for activity…</div>';
}
tick(); setInterval(tick,1000);
</script></body></html>"""


if __name__ == "__main__":
    threading.Thread(target=alert_reader, daemon=True).start()
    threading.Thread(target=peer_poller, daemon=True).start()
    print(f"dashboard on http://0.0.0.0:{PORT}  (attacks -> {BOARD})", flush=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer(("", PORT), H).serve_forever()
