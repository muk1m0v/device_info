"""Local web dashboard (Flask, read-only diagnostics, localhost only)."""

from __future__ import annotations

import socket
import threading
import time
import webbrowser

from app import __version__
from app import adb as adb_mod
from app.logging_setup import get_logger, short_serial

_STATIC_TTL = 120.0  # seconds: model/Android/resolution rarely change
_static_cache: dict[str, tuple[float, dict]] = {}


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


def get_cached_static(serial: str) -> dict:
    """Static per-device data with a TTL cache (saves getprop processes)."""
    now = time.monotonic()
    hit = _static_cache.get(serial)
    if hit and now - hit[0] < _STATIC_TTL:
        return hit[1]
    info = adb_mod.get_device_info(serial)
    static = {
        "model": info.get("model", "Unknown"),
        "manufacturer": info.get("manufacturer", ""),
        "android": info.get("android", "Unknown"),
        "sdk": info.get("sdk", ""),
    }
    _static_cache[serial] = (now, static)
    return static


def resolve_serial(requested: str | None) -> str | None:
    """Pick a usable serial: requested (if still authorized) else first."""
    devices = adb_mod.get_connected_devices()
    authorized = [d["serial"] for d in devices if d["state"] == "device"]
    if not authorized:
        return None
    if requested and requested in authorized:
        return requested
    return authorized[0]


def create_app(preferred_serial: str | None = None):
    from flask import Flask, jsonify, render_template_string, request

    app = Flask(__name__)

    PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Device Info vVERSION — dashboard</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#141414;color:#eee;margin:0}
header{background:#ff8c00;color:#111;padding:16px 24px;font-weight:700;font-size:22px}
main{padding:24px;max-width:900px;margin:auto}
.card{background:#1e1e1e;border:1px solid #333;border-radius:12px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.label{color:#aaa;font-size:12px;text-transform:uppercase}
.value{font-size:18px;margin-top:4px}
.ok{color:#4caf50}.err{color:#f44336}
button,select{background:#ff8c00;border:0;border-radius:8px;padding:10px 16px;font-weight:700;cursor:pointer;color:#111}
select{background:#2a2a2a;color:#eee;border:1px solid #444}
pre{background:#111;padding:12px;border-radius:8px;overflow:auto}
</style></head>
<body>
<header>DEVICE INFO vVERSION — dashboard</header>
<main>
<div class="card"><button onclick="load()">Refresh</button>
<select id="dev" onchange="pick(this.value)" style="margin-left:12px"></select>
<span id="status" style="margin-left:12px;color:#aaa">read-only via ADB</span></div>
<div class="grid" id="grid"></div>
<div class="card"><div class="label">Raw JSON</div><pre id="raw">loading…</pre></div>
<script>
let serial = localStorage.getItem('di_serial') || '';
function pick(v){ serial = v; localStorage.setItem('di_serial', v); load(); }
async function load(){
  const r = await fetch('/api/info' + (serial ? ('?serial=' + encodeURIComponent(serial)) : ''));
  const j = await r.json();
  if (j.serial) { serial = j.serial; localStorage.setItem('di_serial', serial); }
  document.getElementById('raw').textContent = JSON.stringify(j,null,2);
  const sel = document.getElementById('dev');
  sel.innerHTML = '';
  for (const d of (j.devices || [])){
    const o = document.createElement('option');
    o.value = d.serial; o.textContent = d.serial + ' (' + d.state + ')';
    if (d.serial === serial) o.selected = true;
    sel.appendChild(o);
  }
  const g = document.getElementById('grid');
  g.innerHTML='';
  const items = [
    ['Device', (j.manufacturer||'')+' '+(j.model||'')],
    ['Android', j.android||'N/A'],
    ['Serial', j.serial||'-'],
    ['Status', j.status||'N/A'],
    ['Battery', j.summary ? j.summary.battery : 'N/A'],
    ['Battery temp', j.summary ? j.summary.battery_temp : 'N/A'],
    ['RAM', j.summary ? j.summary.ram : 'N/A'],
    ['Storage', j.summary ? j.summary.storage : 'N/A'],
    ['Resolution', j.summary ? j.summary.resolution : 'N/A'],
  ];
  for (const [k,v] of items){
    const d=document.createElement('div');d.className='card';
    d.innerHTML='<div class="label">'+k+'</div><div class="value">'+(v||'N/A')+'</div>';
    g.appendChild(d);
  }
  document.getElementById('status').textContent='updated '+new Date().toLocaleTimeString();
}
load();setInterval(load,5000);
</script>
</main></body></html>""".replace("VERSION", __version__)

    @app.get("/")
    def index():
        return render_template_string(PAGE)

    @app.get("/api/info")
    def api_info():
        requested = request.args.get("serial")
        devices = adb_mod.get_connected_devices()
        authorized = [d["serial"] for d in devices if d["state"] == "device"]
        if not authorized:
            return jsonify({"status": "no device", "devices": devices})
        serial = requested if requested in authorized else preferred_serial
        if serial not in authorized:
            serial = authorized[0]
        static = get_cached_static(serial)
        info = {"serial": serial, "status": "device", **static}
        try:
            info["summary"] = adb_mod.get_summary(serial)
        except Exception:
            info["summary"] = {}
        info["devices"] = devices
        return jsonify(info)

    return app


def run_dashboard(preferred_serial: str | None = None) -> None:
    """Find free port, start localhost server, open browser, serve till Ctrl+C."""
    log = get_logger()
    try:
        from rich.console import Console
        console = Console()
        use_rich = True
    except ImportError:
        console = None  # type: ignore
        use_rich = False

    app = create_app(preferred_serial)
    # Bind-retry loop: the port may be taken between check and bind.
    port = find_free_port()
    bound_port: int | None = None
    last_err: Exception | None = None
    for candidate in range(port, min(port + 10, 5100) + 1):
        try:
            # Probe-bind first so we fail fast with a clear error.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", candidate))
            bound_port = candidate
            break
        except OSError as exc:
            last_err = exc
    if bound_port is None:
        msg = f"Could not bind a local port: {last_err}"
        if use_rich:
            try:
                console.print(f"[red]{msg}[/red]")
            except Exception:
                print(msg)
        else:
            print(msg)
        return
    url = f"http://127.0.0.1:{bound_port}"
    msg = f"Dashboard starting at {url}  (Ctrl+C to stop)"
    if use_rich:
        try:
            console.print(f"[green]OK {msg}[/green]")
        except Exception:
            print(msg)
    else:
        print(msg)
    log.info("dashboard start port=%s device=%s", bound_port,
             short_serial(preferred_serial or ""))
    # Open the browser only after the server is up (not before listen).
    def _open() -> None:
        try:
            webbrowser.open(url)
        except Exception as exc:
            log.warning("browser open failed: %s", exc)
    threading.Timer(1.0, _open).start()
    try:
        # Localhost only — never 0.0.0.0. No debug/Werkzeug debugger.
        app.run(host="127.0.0.1", port=bound_port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        msg = "Server stopped."
        if use_rich:
            try:
                console.print(f"\n[grey]{msg}[/grey]")
            except Exception:
                print(f"\n{msg}")
        else:
            print(f"\n{msg}")
    except OSError as exc:
        msg = f"Server failed to start: {exc}"
        if use_rich:
            try:
                console.print(f"[red]{msg}[/red]")
            except Exception:
                print(msg)
        else:
            print(msg)
    finally:
        log.info("dashboard stop port=%s", bound_port)
