"""Mock Global Token Revocation (GTR) receiver for the FBM Universal Logout test.

Listens on :8098 and logs any POST to /gtr-A (App1, explicitly assigned) or
/gtr-B (App2, Federation Broker Mode). Always answers 200 so Okta records success.

A live dashboard is served at / showing each call as it arrives (the page polls
/api/events, so it works behind proxies like Render with no long-lived streams).

Usage: python3 -I mock_gtr_server.py [port]   (falls back to $PORT, then 8098)
"""
import base64
import itertools
import json
import os
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8098))
MAX_EVENTS = 200
ROUTES = {"/gtr-A": "App1 (assigned)", "/gtr-B": "App2 (FBM)"}

# In-memory call log shown on the dashboard; capped so a long-running deploy
# doesn't grow without bound.
events = []
lock = threading.Lock()
next_id = itertools.count(1)


def decode_jwt_payload(token):
    # Display only; the signature is deliberately not verified in this mock.
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return None


def record(event):
    with lock:
        event["id"] = next(next_id)
        events.append(event)
        del events[:-MAX_EVENTS]


def reset():
    with lock:
        events.clear()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/reset":
            reset()
            self.send_response(204)
            self.end_headers()
            return

        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        label = ROUTES.get(self.path, "UNKNOWN PATH")
        status = 200 if self.path in ROUTES else 404
        print(f"\n[{datetime.now():%H:%M:%S}] GTR received -> {self.path} [{label}]")
        print(f"  Content-Type: {self.headers.get('Content-Type')}")
        claims = decode_jwt_payload(body.strip())
        if claims is None:
            try:
                claims = json.loads(body)
            except Exception:
                claims = None
        print("  Body:", json.dumps(claims, indent=2) if claims else body)

        auth = self.headers.get("Authorization", "")
        auth_claims = decode_jwt_payload(auth.split(" ", 1)[-1]) if auth else None
        record({
            "time": datetime.now().isoformat(timespec="milliseconds"),
            "path": self.path,
            "label": label,
            "status": status,
            "client": self.client_address[0],
            "headers": dict(self.headers.items()),
            "raw_body": body,
            "body": claims,
            "auth_claims": auth_claims,
        })
        self.send_response(status)
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            self._send(200, "text/html; charset=utf-8", DASHBOARD.encode())
        elif self.path == "/api/events":
            with lock:
                data = json.dumps(events).encode()
            self._send(200, "application/json", data)
        else:
            self._send(200, "text/plain", b"mock GTR server up\n")

    def _send(self, status, ctype, data):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


DASHBOARD = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mock GTR Receiver &mdash; Universal Logout</title>
<style>
  :root { --bg:#0f1420; --panel:#171e2e; --line:#263048; --text:#e6e9f0; --muted:#8b93a7;
          --ok:#2ecc71; --wait:#f0b429; --bad:#e5534b; --accent:#4c8dff; }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:var(--bg); color:var(--text); }
  header { display:flex; align-items:center; gap:16px; padding:16px 28px;
           border-bottom:1px solid var(--line); background:var(--panel); }
  header h1 { font-size:18px; margin:0; flex:1; }
  header h1 small { color:var(--muted); font-weight:400; margin-left:8px; }
  .live { display:flex; align-items:center; gap:6px; color:var(--muted); font-size:13px; }
  .dot { width:9px; height:9px; border-radius:50%; background:var(--bad); }
  .live.on .dot { background:var(--ok); box-shadow:0 0 0 0 rgba(46,204,113,.6); animation:pulse 1.6s infinite; }
  @keyframes pulse { 70% { box-shadow:0 0 0 8px rgba(46,204,113,0); } 100% { box-shadow:0 0 0 0 rgba(46,204,113,0); } }
  button { background:transparent; color:var(--text); border:1px solid var(--line);
           border-radius:6px; padding:6px 12px; cursor:pointer; font:inherit; }
  button:hover { border-color:var(--accent); }
  main { padding:24px 28px; max-width:1400px; margin:0 auto; }
  .routes { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:24px; }
  .route { background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--wait);
           border-radius:8px; padding:16px 20px; transition:border-color .3s; }
  .route.ok { border-left-color:var(--ok); }
  .route .name { font-size:16px; font-weight:600; }
  .route code { color:var(--muted); }
  .route .state { margin-top:10px; font-size:15px; }
  .route.ok .state { color:var(--ok); }
  .route:not(.ok) .state { color:var(--wait); }
  .route .meta { color:var(--muted); font-size:12px; margin-top:4px; }
  h2 { font-size:14px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:0 0 10px; }
  .empty { color:var(--muted); padding:40px; text-align:center; border:1px dashed var(--line); border-radius:8px; }
  .call { background:var(--panel); border:1px solid var(--line); border-radius:8px; margin-bottom:10px; overflow:hidden; }
  .call.fresh { animation:flash 2s ease-out; }
  @keyframes flash { from { background:#1f3b2c; } to { background:var(--panel); } }
  .call summary { display:flex; gap:14px; align-items:center; padding:12px 16px; cursor:pointer; list-style:none; }
  .call summary::-webkit-details-marker { display:none; }
  .badge { font-weight:600; font-size:12px; padding:2px 8px; border-radius:4px; }
  .b200 { background:rgba(46,204,113,.15); color:var(--ok); }
  .b404 { background:rgba(229,83,75,.15); color:var(--bad); }
  .path { font-family:ui-monospace,Menlo,monospace; font-weight:600; }
  .label { color:var(--muted); }
  .time { margin-left:auto; color:var(--muted); font-family:ui-monospace,Menlo,monospace; font-size:12px; }
  .body { padding:0 16px 16px; display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .body section { min-width:0; }
  .body h3 { font-size:12px; color:var(--muted); margin:8px 0 4px; font-weight:500; }
  pre { margin:0; background:#0b0f18; border:1px solid var(--line); border-radius:6px; padding:10px;
        font:12px/1.5 ui-monospace,Menlo,monospace; overflow:auto; max-height:360px; white-space:pre-wrap; word-break:break-all; }
  .k { color:#7cc4ff; } .s { color:#a5d6a7; } .n { color:#f0b429; }
</style>
</head>
<body>
<header>
  <h1>Mock GTR Receiver <small>Universal Logout &middot; Federation Broker Mode test</small></h1>
  <div class="live" id="live"><span class="dot"></span><span id="liveText">connecting&hellip;</span></div>
  <button id="reset" title="Clear all received calls">Clear</button>
</header>
<main>
  <div class="routes" id="routes"></div>
  <h2>Received calls <span id="count"></span></h2>
  <div id="calls"><div class="empty">Waiting for logout requests&hellip;</div></div>
</main>
<script>
const ROUTES = __ROUTES__;
const seen = new Set();
const open = new Set();

const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pretty = v => esc(JSON.stringify(v, null, 2))
  .replace(/(&quot;[^&]*?&quot;)(\s*:)/g, '<span class="k">$1</span>$2')
  .replace(/(:\s*)(&quot;.*?&quot;)/g, '$1<span class="s">$2</span>')
  .replace(/(:\s*)(-?\d+(\.\d+)?|true|false|null)/g, '$1<span class="n">$2</span>');
const fmtTime = iso => new Date(iso).toLocaleTimeString([], {hour12:false}) + "." + iso.slice(-3);

function render(events) {
  document.getElementById("routes").innerHTML = Object.entries(ROUTES).map(([path, label]) => {
    const hits = events.filter(e => e.path === path);
    const last = hits[hits.length - 1];
    return `<div class="route ${hits.length ? "ok" : ""}">
      <div class="name">${esc(label)}</div><code>POST ${esc(path)}</code>
      <div class="state">${hits.length ? `&#10004; Received (${hits.length})` : "&#9203; Waiting for request"}</div>
      <div class="meta">${last ? "Last at " + fmtTime(last.time) : "&nbsp;"}</div></div>`;
  }).join("");

  document.getElementById("count").textContent = events.length ? `(${events.length})` : "";
  const calls = document.getElementById("calls");
  if (!events.length) { calls.innerHTML = '<div class="empty">Waiting for logout requests&hellip;</div>'; seen.clear(); return; }

  calls.innerHTML = events.slice().reverse().map(e => {
    const fresh = !seen.has(e.id);
    const sections = [];
    if (e.body) sections.push(["Body (decoded)", pretty(e.body)]);
    else sections.push(["Body (raw)", esc(e.raw_body || "(empty)")]);
    if (e.auth_claims) sections.push(["Authorization JWT claims (unverified)", pretty(e.auth_claims)]);
    sections.push(["Headers", pretty(e.headers)]);
    return `<details class="call ${fresh ? "fresh" : ""}" data-id="${e.id}" ${open.has(e.id) || fresh ? "open" : ""}>
      <summary><span class="badge b${e.status}">${e.status}</span>
        <span class="path">POST ${esc(e.path)}</span><span class="label">${esc(e.label)}</span>
        <span class="time">#${e.id} &middot; ${fmtTime(e.time)}</span></summary>
      <div class="body">${sections.map(([t, c]) => `<section><h3>${t}</h3><pre>${c}</pre></section>`).join("")}</div>
    </details>`;
  }).join("");
  events.forEach(e => { if (!seen.has(e.id)) { seen.add(e.id); open.add(e.id); } });
}

document.getElementById("calls").addEventListener("toggle", ev => {
  const id = Number(ev.target.dataset.id);
  ev.target.open ? open.add(id) : open.delete(id);
}, true);

let lastPayload = null;
async function poll() {
  const live = document.getElementById("live"), text = document.getElementById("liveText");
  try {
    const res = await fetch("/api/events", {cache: "no-store"});
    if (!res.ok) throw new Error(res.status);
    const payload = await res.text();
    live.classList.add("on"); text.textContent = "Live";
    if (payload !== lastPayload) { lastPayload = payload; render(JSON.parse(payload)); }
  } catch (err) {
    live.classList.remove("on"); text.textContent = "Disconnected — retrying";
  }
  setTimeout(poll, 1500);
}

document.getElementById("reset").onclick = () => fetch("/api/reset", {method: "POST"}).then(() => { lastPayload = null; });
poll();
</script>
</body>
</html>
""".replace("__ROUTES__", json.dumps(ROUTES))


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # so hosted logs show calls immediately
    print(f"Listening on :{PORT}  routes: {', '.join(ROUTES)}")
    print(f"Live dashboard: http://localhost:{PORT}/")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
