from __future__ import annotations

import json
import logging

from app.logs import JsonFormatter, configure


def _record(**extra) -> logging.LogRecord:
    r = logging.getLogger("t").makeRecord("t", logging.INFO, "f", 1, "hello %s", ("world",), None)
    r.__dict__.update(extra)
    return r


def test_format_is_one_json_object_with_the_core_fields():
    line = JsonFormatter().format(_record())
    obj = json.loads(line)
    assert obj["level"] == "info"
    assert obj["logger"] == "t"
    assert obj["msg"] == "hello world"
    assert "ts" in obj


def test_extras_are_merged_in():
    obj = json.loads(JsonFormatter().format(_record(request_id="abc", render_id="r1", status=200)))
    assert obj["request_id"] == "abc"
    assert obj["render_id"] == "r1"
    assert obj["status"] == 200


def test_exception_is_captured():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        r = logging.getLogger("t").makeRecord(
            "t", logging.ERROR, "f", 1, "died", (), sys.exc_info()
        )
    obj = json.loads(JsonFormatter().format(r))
    assert "ValueError: boom" in obj["exc"]


def test_configure_installs_a_single_json_handler(capsys):
    configure("info")
    logging.getLogger("app1.test").info("check", extra={"k": "v"})
    err = capsys.readouterr().err
    obj = json.loads(err.strip().splitlines()[-1])
    assert obj["msg"] == "check" and obj["k"] == "v"
