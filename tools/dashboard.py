#!/usr/bin/env python3
# Live dashboard for edge-ids. Runs on your PC, follows the board's MQTT alerts
# over ssh and shows them in the browser. Standard library only.
#
#   python3 tools/dashboard.py 192.168.1.50     ->  http://localhost:8080
#
# Needs key-based ssh to root@<board> (ssh-copy-id root@<board>).
# IDS_NAMES="192.168.1.10=plc,192.168.1.20=hmi" puts names on the host cards.
import collections
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

PORT = 8080
BOARD = None
NAMES = {ip.strip(): who.strip() for ip, _, who in
         (p.partition("=") for p in os.environ.get("IDS_NAMES", "").split(",")) if who}
alerts = collections.deque(maxlen=80)     # newest first
link = False                              # True while the ssh stream from the board is up
link_since = 0.0                          # when it came up
last_beat = 0.0                           # last heartbeat from the detector (ids/status)
BEAT_TIMEOUT = 15                         # the detector sends one every 5 s


def alert_reader():
    # The remote side prints "link-up" first, so we know ssh really got through.
    # That alone doesn't mean edge-ids is running though, so "all clear" also
    # needs its heartbeat on ids/status.
    global link, link_since, last_beat
    while True:
        try:
            p = subprocess.Popen(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                 "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
                 f"root@{BOARD}", "echo link-up; exec mosquitto_sub -v -t ids/alerts -t ids/status"],
                stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                line = line.strip()
                if line == "link-up":
                    link, link_since = True, time.time()
                    continue
                topic, _, payload = line.partition(" ")      # mosquitto_sub -v: "topic payload"
                try:
                    msg = json.loads(payload)
                except ValueError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if topic == "ids/status":
                    last_beat = time.time()
                elif topic == "ids/alerts":
                    msg["_ts"] = time.time()          # when we got it, for "live" vs "recent"
                    alerts.appendleft(msg)
            p.wait()
        except Exception as e:
            print("alert stream:", e, flush=True)
        link = False
        time.sleep(2)


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", PAGE)
        elif path == "/state":
            now = time.time()
            detector = link and now - last_beat < BEAT_TIMEOUT
            self._send(200, "application/json", json.dumps(
                {"board": BOARD, "link": link, "detector": detector,
                 "waiting": link and not detector and now - link_since < BEAT_TIMEOUT,
                 "names": NAMES, "alerts": list(alerts)}))
        else:
            self._send(404, "text/plain", "not found")

    def log_message(self, *args):
        pass


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>edge-ids</title><style>
:root{
  --bg:#0a0e14; --panel:#111823; --panel2:#0d141d; --line:#1e2a38; --line2:#2a3a4d;
  --tx:#e6edf3; --mut:#8493a5; --dim:#5b6b7d;
  --green:#3fb950; --greenbg:#0f2417; --red:#f85149; --redbg:#2a1113; --blue:#58a6ff;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#111c2b 0,var(--bg) 60%);
  color:var(--tx);font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  padding-bottom:env(safe-area-inset-bottom,0px)}
header{position:sticky;top:env(safe-area-inset-top,0px);z-index:10;display:flex;align-items:center;gap:14px;
  padding:14px 22px;background:rgba(10,14,20,.82);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;letter-spacing:.2px}
.hex{width:22px;height:22px;color:var(--blue)}
.live{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--mut);
  border:1px solid var(--line2);border-radius:999px;padding:5px 12px}
.live .pulse{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 1.8s infinite}
.live.off .pulse{background:var(--dim);animation:none}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(63,185,80,.55)}70%{box-shadow:0 0 0 7px rgba(63,185,80,0)}100%{box-shadow:0 0 0 0 rgba(63,185,80,0)}}
main{max-width:1100px;margin:0 auto;padding:22px 16px;display:grid;gap:18px}
h2{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin:0 0 12px;font-weight:700}

.hero{border-radius:16px;padding:22px 24px;border:1px solid var(--line);background:var(--panel);
  display:flex;align-items:center;gap:18px;transition:.35s}
.hero .ic{width:52px;height:52px;flex:0 0 auto}
.hero .big{font-size:22px;font-weight:800;letter-spacing:.2px}
.hero .sub{color:var(--mut);font-size:13px;margin-top:2px}
.hero.safe{background:linear-gradient(120deg,var(--greenbg),var(--panel));border-color:#1c4029}
.hero.safe .ic{color:var(--green)} .hero.safe .big{color:#7ee2a8}
.hero.alarm{background:linear-gradient(120deg,var(--redbg),var(--panel));border-color:#5b1d1f;animation:flash 1.1s infinite}
.hero.alarm .ic{color:var(--red)} .hero.alarm .big{color:#ff8a80}
.hero.offline{border-color:var(--line2)} .hero.offline .ic{color:var(--dim)} .hero.offline .big{color:var(--mut)}
@keyframes flash{0%,100%{box-shadow:0 0 0 0 rgba(248,81,73,0)}50%{box-shadow:0 0 26px 0 rgba(248,81,73,.28)}}

.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}
.hosts{display:grid;gap:10px}
.host{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:12px;
  background:var(--panel2);border:1px solid var(--line);transition:.25s}
.host .dot{width:10px;height:10px;border-radius:50%;flex:0 0 auto;background:var(--green)}
.host.threat{border-color:#5b1d1f;background:linear-gradient(90deg,var(--redbg),var(--panel2))}
.host.threat .dot{background:var(--red);animation:pulse2 1.2s infinite}
@keyframes pulse2{0%{box-shadow:0 0 0 0 rgba(248,81,73,.6)}70%{box-shadow:0 0 0 7px rgba(248,81,73,0)}100%{box-shadow:0 0 0 0 rgba(248,81,73,0)}}
.host .id{display:flex;flex-direction:column}
.host .id b{font-size:14px} .host .id span{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.host .state{margin-left:auto;text-align:right}
.host .tag{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.host.threat .tag{color:#ff8a80}
.host .conf{font-size:11px;color:var(--dim);font-family:var(--mono)}

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
.note{color:var(--dim);font-size:12px;margin-top:12px}.note code{color:var(--blue);font-family:var(--mono)}
.foot{color:var(--dim);font-size:11.5px;text-align:center;padding:6px 0 2px}
</style></head><body>
<header>
  <div class="brand"><svg class="hex" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M12 2l8.5 5v10L12 22l-8.5-5V7z"/><path d="M9 12l2 2 4-4"/></svg>edge-ids</div>
  <div class="live off" id="pill"><span class="pulse"></span><span id="pilltext">CONNECTING</span>
    &middot; board <span id="board"></span></div>
</header>
<main>
  <div class="hero offline" id="hero">
    <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
      <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>
    <div><div class="big" id="herobig">CONNECTING</div>
      <div class="sub" id="herosub">waiting for the board&hellip;</div></div>
  </div>

  <section class="panel"><h2>Live monitor &middot; who's doing what</h2>
    <div class="hosts" id="hosts"><div class="empty">no hosts seen yet</div></div>
    <div class="note">Read-only view. Attacks come from other machines running <code>tools/simulate.py</code>
      against the board, nothing is launched from here.</div></section>

  <section class="panel"><h2>Threat feed</h2>
    <div id="feed"><div class="empty">waiting for activity&hellip;</div></div></section>
  <div class="foot">edge-ids &middot; int8 model + rules running on the board</div>
</main>
<script>
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
const $=id=>document.getElementById(id);
// only touch the DOM when something changed, otherwise the fade-in replays every second
function put(id,html){const el=$(id); if(el.dataset.html!==html){el.innerHTML=html; el.dataset.html=html;}}

function show(kind,big,sub,pill){
  $('hero').className='hero '+kind; $('herobig').textContent=big; $('herosub').innerHTML=sub;
  $('pill').className=kind==='offline'?'live off':'live';
  $('pilltext').textContent=pill||'MONITORING';
}

async function tick(){
  let st;
  try{st=await (await fetch('/state')).json();}
  catch(e){show('offline','NO CONNECTION','the dashboard server is not responding','OFFLINE');return;}
  $('board').textContent=st.board;
  const now=Date.now()/1000;
  const live=st.alerts.filter(a=>now-(a._ts||0)<8);      // happening right now
  const feed=st.alerts.filter(a=>now-(a._ts||0)<120);    // the last two minutes

  // named hosts first, then anyone who showed up in the feed
  const hosts={};
  for(const [ip,name] of Object.entries(st.names)) hosts[ip]={ip,name};
  for(const a of feed.slice(0,12)) if(!hosts[a.src]) hosts[a.src]={ip:a.src,name:a.who&&a.who!=='unknown'?a.who:'host'};
  const current={};
  for(const a of live) if(!current[a.src]) current[a.src]=a;
  put('hosts',Object.values(hosts).map(h=>{
    const a=current[h.ip];
    return `<div class="host ${a?'threat':''}"><span class="dot"></span>
      <div class="id"><b>${esc(h.name)}</b><span>${esc(h.ip)}</span></div>
      <div class="state"><div class="tag">${esc(a?a.type:'quiet')}</div><div class="conf">${esc(a?a.detail||'':'')}</div></div></div>`;
  }).join('')||'<div class="empty">no hosts seen yet</div>');

  if(!st.link) show('offline','NO LINK',`not hearing from the board (${esc(st.board)}), retrying`,'NO LINK');
  else if(st.waiting) show('offline','CONNECTING','connected to the board, waiting for the detector&hellip;','CONNECTING');
  else if(!st.detector) show('offline','DETECTOR DOWN',"connected to the board, but edge-ids isn't reporting. Is the service running?",'NO DETECTOR');
  else if(live.length){const e=live[0];
    show('alarm','UNDER ATTACK',`<b>${esc(e.type)}</b> from ${esc(e.who||'?')} (${esc(e.src)}) &middot; detected by ${esc(e.detector||'rule')}`);}
  else show('safe','SECURE','no threats detected &middot; watching live traffic');

  put('feed',feed.length?feed.map(e=>
    `<div class="ev det-${esc(e.detector||'rule')}"><span class="t">${esc(e.time)}</span>
      <span class="badge">${esc(e.type)}</span>
      <span class="who">${esc(e.who||'?')}</span> <span class="ip">${esc(e.src)}</span>
      <span class="det">[${esc(e.detector||'rule')}] ${esc(e.detail||'')}</span></div>`).join('')
    :'<div class="empty">no recent activity</div>');
}
tick(); setInterval(tick,1000);
</script></body></html>"""


def main():
    global BOARD
    if len(sys.argv) != 2:
        print("usage: python3 tools/dashboard.py <board-ip>", file=sys.stderr)
        sys.exit(2)
    BOARD = sys.argv[1]
    threading.Thread(target=alert_reader, daemon=True).start()
    print(f"dashboard on http://localhost:{PORT} (all interfaces), following board {BOARD}", flush=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
