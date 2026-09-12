"""`/metrics` in Prometheus text format (PRD §17 dashboard).

Two sources, one endpoint:
- **in-process** counters/histogram for HTTP traffic, rate-limit rejections and
  inventory calls — incremented as requests happen;
- a **scrape-time collector** that queries Postgres for everything about renders
  (preservation rate, durations, failures by code, queue depth, live workers),
  because that data already lives in the database and the worker writes it, not
  the API.

The page leads with preservation rate (mean and 5th percentile) and the inventory
failure rate — together they say whether the promise is holding.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

HTTP_REQUESTS = Counter("app1_http_requests_total", "HTTP requests", ["route", "method", "status"])
HTTP_DURATION = Histogram(
    "app1_http_request_duration_seconds", "HTTP request duration", ["route", "method"]
)
INVENTORY_ATTEMPTS = Counter("app1_inventory_attempts_total", "Inventory vision calls started")
INVENTORY_FAILURES = Counter("app1_inventory_failures_total", "Inventory vision calls that failed")
RATE_LIMITED = Counter("app1_rate_limited_total", "Requests rejected by a rate limit", ["rule"])

# gpt-4.1 inventory + gpt-image-2 edit + gpt-4.1 preservation check. The spike
# measured ~2 cents/render; this is deliberately an estimate until the worker
# records real token usage.
_EST_COST_PER_RENDER_USD = 0.04


class _DatabaseMetrics:
    def __init__(self, pool) -> None:
        self._pool = pool

    def collect(self):
        try:
            with self._pool.connection() as conn:
                yield from self._collect(conn)
        except Exception:  # noqa: BLE001 — a DB blip must not 500 /metrics
            return

    def _collect(self, conn):
        mean, p5, scored = conn.execute(
            "SELECT avg(preservation_rate), "
            "percentile_cont(0.05) WITHIN GROUP (ORDER BY preservation_rate), count(*) "
            "FROM renders WHERE preservation_rate IS NOT NULL"
        ).fetchone()
        yield _gauge("app1_preservation_rate_mean", "Mean preservation rate", mean)
        yield _gauge("app1_preservation_rate_p5", "5th-percentile preservation rate", p5)
        yield GaugeMetricFamily(
            "app1_preservation_scored_renders", "Renders with a preservation score", value=scored
        )

        by_status = CounterMetricFamily("app1_renders", "Renders by status", labels=["status"])
        for status, count in conn.execute("SELECT status, count(*) FROM renders GROUP BY status"):
            by_status.add_metric([status], count)
        yield by_status

        failed = CounterMetricFamily(
            "app1_renders_failed", "Failed renders by error code", labels=["error_code"]
        )
        for code, count in conn.execute(
            "SELECT coalesce(error_code, 'unknown'), count(*) "
            "FROM renders WHERE status = 'failed' GROUP BY 1"
        ):
            failed.add_metric([code], count)
        yield failed

        d50, d95 = conn.execute(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY secs), "
            "       percentile_cont(0.95) WITHIN GROUP (ORDER BY secs) "
            "FROM (SELECT extract(epoch FROM updated_at - created_at) AS secs "
            "      FROM renders WHERE status = 'done') d"
        ).fetchone()
        duration = GaugeMetricFamily(
            "app1_render_duration_seconds", "Submit-to-done render duration", labels=["quantile"]
        )
        duration.add_metric(["0.5"], _num(d50))
        duration.add_metric(["0.95"], _num(d95))
        yield duration

        depth = conn.execute("SELECT count(*) FROM jobs WHERE status = 'queued'").fetchone()[0]
        yield GaugeMetricFamily("app1_queue_depth", "Jobs waiting in the queue", value=depth)

        workers = conn.execute(
            "SELECT count(*) FROM worker_heartbeats WHERE last_seen > now() - interval '60 seconds'"
        ).fetchone()[0]
        yield GaugeMetricFamily(
            "app1_workers_active", "Workers seen in the last 60s", value=workers
        )

        total = conn.execute("SELECT count(*) FROM renders").fetchone()[0]
        yield GaugeMetricFamily(
            "app1_render_cost_usd_estimate_total",
            "Estimated OpenAI cost over all renders (estimate, not metered)",
            value=total * _EST_COST_PER_RENDER_USD,
        )

        yield from self._collect_shopping(conn)

    def _collect_shopping(self, conn):
        """'Shop your restyle' (shopping_proto/HANDOFF.md §4.2). Same DB-scrape
        approach as the render metrics above, for the same reason: the pipeline
        runs in the worker process, a separate process from whatever serves
        /metrics, so an in-process counter incremented there would never be
        seen here."""
        by_status = CounterMetricFamily(
            "app1_shopping_jobs", "Shopping jobs by status", labels=["status"]
        )
        for status, count in conn.execute("SELECT status, count(*) FROM shopping GROUP BY status"):
            by_status.add_metric([status], count)
        yield by_status

        items_mean, items_p50 = conn.execute(
            "SELECT avg(jsonb_array_length(items)), "
            "percentile_cont(0.5) WITHIN GROUP (ORDER BY jsonb_array_length(items)) "
            "FROM shopping WHERE status = 'ready'"
        ).fetchone()
        yield _gauge("app1_shopping_items_found_mean", "Mean items found per ready render", items_mean)
        yield _gauge(
            "app1_shopping_items_found_p50", "Median items found per ready render", items_p50
        )

        options_mean = conn.execute(
            "SELECT avg(jsonb_array_length(item -> 'options')) "
            "FROM shopping s, jsonb_array_elements(s.items) AS item "
            "WHERE s.status = 'ready'"
        ).fetchone()[0]
        yield _gauge(
            "app1_shopping_options_per_item_mean", "Mean options per found item", options_mean
        )

        calls, errors = conn.execute(
            "SELECT coalesce(sum(searchapi_calls), 0), coalesce(sum(searchapi_errors), 0) "
            "FROM shopping WHERE status IN ('ready', 'none')"
        ).fetchone()
        searchapi_calls = CounterMetricFamily(
            "app1_shopping_searchapi_calls", "SearchApi calls by outcome", labels=["outcome"]
        )
        searchapi_calls.add_metric(["error"], errors)
        searchapi_calls.add_metric(["ok"], max(0, calls - errors))
        yield searchapi_calls

        cost_mean = conn.execute(
            "SELECT avg(cost_cents) FROM shopping WHERE status = 'ready'"
        ).fetchone()[0]
        yield _gauge("app1_shopping_cost_cents_mean", "Mean estimated cost per ready render", cost_mean)

        d50, d95 = conn.execute(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY secs), "
            "       percentile_cont(0.95) WITHIN GROUP (ORDER BY secs) "
            "FROM (SELECT extract(epoch FROM updated_at - created_at) AS secs "
            "      FROM shopping WHERE status = 'ready') d"
        ).fetchone()
        duration = GaugeMetricFamily(
            "app1_shopping_duration_seconds", "Enqueue-to-ready shopping duration",
            labels=["quantile"],
        )
        duration.add_metric(["0.5"], _num(d50))
        duration.add_metric(["0.95"], _num(d95))
        yield duration


_installed: _DatabaseMetrics | None = None


def install(pool) -> None:
    global _installed
    if _installed is not None:
        REGISTRY.unregister(_installed)
    _installed = _DatabaseMetrics(pool)
    REGISTRY.register(_installed)


def render() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def _gauge(name: str, doc: str, value) -> GaugeMetricFamily:
    return GaugeMetricFamily(name, doc, value=_num(value))


def _num(value) -> float:
    return float(value) if value is not None else float("nan")
