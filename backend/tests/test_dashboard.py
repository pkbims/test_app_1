from __future__ import annotations

from dashboard.__main__ import _int, _parse_metrics, _pct, _ratio

_SAMPLE = """\
# HELP app1_preservation_rate_mean Mean preservation rate
# TYPE app1_preservation_rate_mean gauge
app1_preservation_rate_mean 0.93
app1_preservation_rate_p5 0.71
app1_queue_depth 4.0
app1_workers_active 1.0
app1_renders_total{status="done"} 12.0
app1_renders_total{status="failed"} 2.0
app1_render_duration_seconds{quantile="0.95"} 41.3
app1_preservation_rate_mean_missing NaN
"""


def test_parses_plain_and_labelled_metrics_including_digit_suffixes():
    m = _parse_metrics(_SAMPLE)
    assert m["app1_preservation_rate_mean"] == 0.93
    assert m["app1_preservation_rate_p5"] == 0.71  # the digit in _p5 must not break it
    assert m["app1_queue_depth"] == 4.0
    assert m['app1_renders_total{status="done"}'] == 12.0
    assert m['app1_render_duration_seconds{quantile="0.95"}'] == 41.3


def test_nan_is_skipped():
    assert "app1_preservation_rate_mean_missing" not in _parse_metrics(_SAMPLE)


def test_format_helpers():
    assert _pct(0.931) == "93%"
    assert _pct(None) == "—"
    assert _pct(float("nan")) == "—"
    assert _ratio(2, 10) == "20%"
    assert _ratio(0, 0) == "—"
    assert _int(4.0) == "4"
    assert _int(None) == "0"
