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
import re
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

    m = _parse_metrics(m_body) if m_status == 200 else {}
    scored = m.get("app1_preservation_scored_renders", 0.0)
    inv_att = m.get("app1_inventory_attempts_total", 0.0)
    inv_fail = m.get("app1_inventory_failures_total", 0.0)
    cards = "".join(
        _card(label, value)
        for label, value in [
            (
                "preservation rate — mean",
                _pct(m.get("app1_preservation_rate_mean")) if scored else "—",
            ),
            (
                "preservation rate — p5 (worst)",
                _pct(m.get("app1_preservation_rate_p5")) if scored else "—",
            ),
            ("inventory failure rate", _ratio(inv_fail, inv_att)),
            ("render duration p95", _secs(m.get('app1_render_duration_seconds{quantile="0.95"}'))),
            ("queue depth", _int(m.get("app1_queue_depth"))),
            ("workers active", _int(m.get("app1_workers_active"))),
            ("renders done", _int(m.get('app1_renders_total{status="done"}'))),
            ("renders failed", _int(m.get('app1_renders_total{status="failed"}'))),
            ("est. OpenAI cost", f"${m.get('app1_render_cost_usd_estimate_total', 0.0):.2f}"),
        ]
    )
    sa_ok = m.get('app1_shopping_searchapi_calls_total{outcome="ok"}', 0.0)
    sa_err = m.get('app1_shopping_searchapi_calls_total{outcome="error"}', 0.0)
    shopping_cards = "".join(
        _card(label, value)
        for label, value in [
            ("items found — p50", _int(m.get("app1_shopping_items_found_p50"))),
            ("options per item — mean", f"{m.get('app1_shopping_options_per_item_mean', 0.0):.1f}"),
            ("SearchApi failure rate", _ratio(sa_err, sa_ok + sa_err)),
            ("cost per render — mean", f"{m.get('app1_shopping_cost_cents_mean', 0.0):.1f}¢"),
        ]
    )

    raw = (
        f"<details><summary>raw /metrics</summary><pre>{html.escape(m_body)}</pre></details>"
        if m_status == 200
        else f"<p class='muted'>/metrics unavailable (HTTP {m_status})</p>"
    )

    return f"""<!doctype html>
<meta charset=utf-8>
<meta http-equiv=refresh content=5>
<title>app_1 dashboard</title>
<style>
  body {{ font: 14px system-ui, sans-serif; margin: 2rem; max-width: 60rem; }}
  h1 {{ font-size: 1.2rem; }}
  h2 {{ font-size: 1rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  td, th {{ border: 1px solid #ccc; padding: .4rem .6rem; text-align: left; }}
  .state {{ font-weight: 700; }}
  .s-ok {{ color: #137333; }}
  .s-degraded {{ color: #b06000; }}
  .s-down, .s-unreachable {{ color: #c5221f; }}
  .muted {{ color: #666; }}
  .cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .75rem; }}
  .card {{ border: 1px solid #ddd; border-radius: 6px; padding: .75rem; }}
  .card .v {{ font-size: 1.5rem; font-weight: 700; }}
  .card .l {{ color: #666; font-size: .8rem; }}
  pre {{ background: #f6f6f6; padding: 1rem; overflow-x: auto; }}
</style>
<h1>app_1 — <span class="state s-{html.escape(state)}">{html.escape(state)}</span></h1>
<p class="muted">source: {html.escape(API_BASE)} · refreshes every 5s</p>

<h2>Is the promise holding?</h2>
<div class="cards">{cards}</div>

<h2>Shop your restyle</h2>
<div class="cards">{shopping_cards}</div>

<h2>Health checks</h2>
<table>
  <tr><th>check</th><th>state</th><th>detail</th></tr>
  {rows}
</table>

{raw}
"""


_METRIC_LINE = re.compile(r"^(app1_[a-z0-9_]+(?:\{[^}]*\})?)\s+([0-9eE.+-]+|NaN)$", re.MULTILINE)


def _parse_metrics(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, value in _METRIC_LINE.findall(text):
        if value == "NaN":
            continue
        try:
            out[name] = float(value)
        except ValueError:
            pass
    return out


def _card(label: str, value: str) -> str:
    return (
        f"<div class='card'><div class='v'>{html.escape(value)}</div>"
        f"<div class='l'>{html.escape(label)}</div></div>"
    )


def _pct(v: float | None) -> str:
    return "—" if v is None or v != v else f"{v * 100:.0f}%"


def _ratio(num: float, denom: float) -> str:
    return "—" if not denom else f"{num / denom * 100:.0f}%"


def _secs(v: float | None) -> str:
    return "—" if v is None or v != v else f"{v:.1f}s"


def _int(v: float | None) -> str:
    return "0" if v is None else f"{int(v)}"


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
