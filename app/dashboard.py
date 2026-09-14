"""Local web dashboard (Flask, read-only diagnostics)."""

from __future__ import annotations

import socket
import webbrowser

from app import adb as adb_mod


def find_free_port(start: int = 5000, end: int = 5100) -> int:
    """Find a free TCP port on localhost."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise OSError("No free port found in range")


def create_app():
    from flask import Flask, jsonify, render_template_string

    app = Flask(__name__)

    PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Device Info v1</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#141414;color:#eee;margin:0}
header{background:#ff8c00;color:#111;padding:16px 24px;font-weight:700;font-size:22px}
main{padding:24px;max-width:900px;margin:auto}
.card{background:#1e1e1e;border:1px solid #333;border-radius:12px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.label{color:#aaa;font-size:12px;text-transform:uppercase}
.value{font-size:18px;margin-top:4px}
.ok{color:#4caf50}.err{color:#f44336}
button{background:#ff8c00;border:0;border-radius:8px;padding:10px 16px;font-weight:700;cursor:pointer}
pre{background:#111;padding:12px;border-radius:8px;overflow:auto}
</style></head>
<body>
<header>DEVICE INFO v1 — dashboard</header>
<main>
<div class="card"><button onclick="load()">Refresh</button>
<span id="status" style="margin-left:12px;color:#aaa">read-only via ADB</span></div>
<div class="grid" id="grid"></div>
<div class="card"><div class="label">Raw JSON</div><pre id="raw">loading…</pre></div>
<script>
async function load(){
  const r = await fetch('/api/info');
  const j = await r.json();
  document.getElementById('raw').textContent = JSON.stringify(j,null,2);
  const g = document.getElementById('grid');
  g.innerHTML='';
  const items = [
    ['Device', (j.manufacturer||'')+' '+(j.model||'')],
    ['Android', j.android||'?'],
    ['Serial', j.serial||'-'],
    ['Status', j.status||'?'],
    ['Battery', j.summary ? j.summary.battery : '?'],
    ['Battery temp', j.summary ? j.summary.battery_temp : '?'],
    ['RAM', j.summary ? j.summary.ram : '?'],
    ['Storage', j.summary ? j.summary.storage : '?'],
    ['Resolution', j.summary ? j.summary.resolution : '?'],
  ];
  for (const [k,v] of items){
    const d=document.createElement('div');d.className='card';
    d.innerHTML='<div class="label">'+k+'</div><div class="value">'+(v||'?')+'</div>';
    g.appendChild(d);
  }
  document.getElementById('status').textContent='updated '+new Date().toLocaleTimeString();
}
load();setInterval(load,5000);
</script>
</main></body></html>"""

    @app.get("/")
    def index():
        return render_template_string(PAGE)

    @app.get("/api/info")
    def api_info():
        devices = adb_mod.get_connected_devices()
        authorized = [d for d in devices if d["state"] == "device"]
        if not authorized:
            return jsonify({"status": "no device", "devices": devices})
        serial = authorized[0]["serial"]
        info = adb_mod.get_device_info(serial)
        try:
            info["summary"] = adb_mod.get_summary(serial)
        except Exception:
            info["summary"] = {}
        info["devices"] = devices
        return jsonify(info)

    return app


def run_dashboard() -> None:
    """Find free port, open browser, serve until Ctrl+C."""
    try:
        from rich.console import Console
        console = Console()
        use_rich = True
    except ImportError:
        console = None  # type: ignore
        use_rich = False

    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    msg = f"Dashboard starting at {url}  (Ctrl+C to stop)"
    if use_rich:
        try:
            console.print(f"[green]OK {msg}[/green]")
        except Exception:
            print(msg)
    else:
        print(msg)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    app = create_app()
    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        if use_rich:
            try:
                console.print("\n[grey]Server stopped.[/grey]")
            except Exception:
                print("\nServer stopped.")
        else:
            print("\nServer stopped.")
