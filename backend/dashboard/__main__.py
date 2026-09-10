"""A small server-rendered dashboard.

**Why not Grafana + Prometheus.** Those buy history and alerting, at the cost of
two more services, a scrape config, and a dashboard JSON to provision and keep in
sync. This page reads `/health` and `/metrics` live and renders them — point in
time only, no graphs over time — which is enough to see on camera what the system
is doing. Swap in Grafana if we ever need trends.
"""

from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_BASE = os.environ.get("API_BASE", "http://api:8000")
PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))


def _fetch(path: str, timeout: float = 3.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(f"{API_BASE}{path}", timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def _render() -> str:
    h_status, h_body = _fetch("/health")
    m_status, m_body = _fetch("/metrics")

    try:
        health = json.loads(h_body)
        state = health.get("state", "?")
        rows = "".join(
            f"<tr><td>{html.escape(c['name'])}</td>"
            f"<td class='s-{html.escape(c['state'])}'>{html.escape(c['state'])}</td>"
            f"<td>{html.escape(c.get('detail') or '')}</td></tr>"
            for c in health.get("checks", [])
        )
    except Exception:  # noqa: BLE001
        state = "unreachable"
        rows = f"<tr><td colspan=3>{html.escape(h_body)}</td></tr>"

    metrics = (
        f"<pre>{html.escape(m_body)}</pre>"
        if m_status == 200
        else f"<p class='muted'>/metrics not available yet (HTTP {m_status})</p>"
    )

    return f"""<!doctype html>
<meta charset=utf-8>
<meta http-equiv=refresh content=5>
<title>app_1 dashboard</title>
<style>
  body {{ font: 14px system-ui, sans-serif; margin: 2rem; max-width: 60rem; }}
  h1 {{ font-size: 1.2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  td, th {{ border: 1px solid #ccc; padding: .4rem .6rem; text-align: left; }}
  .state {{ font-weight: 700; }}
  .s-ok {{ color: #137333; }}
  .s-degraded {{ color: #b06000; }}
  .s-down {{ color: #c5221f; }}
  .muted {{ color: #666; }}
  pre {{ background: #f6f6f6; padding: 1rem; overflow-x: auto; }}
</style>
<h1>app_1 — <span class="state s-{html.escape(state)}">{html.escape(state)}</span></h1>
<p class="muted">source: {html.escape(API_BASE)} · refreshes every 5s</p>
<table>
  <tr><th>check</th><th>state</th><th>detail</th></tr>
  {rows}
</table>
<h2 style="font-size:1rem">/metrics</h2>
{metrics}
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            body = _render().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args) -> None:  # quieter logs
        pass


def main() -> None:
    print(f"dashboard on :{PORT} → {API_BASE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
