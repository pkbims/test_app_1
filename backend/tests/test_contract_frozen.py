"""The contract is frozen. This fails if `main.py` or `schemas.py` drift from the
committed `contract/openapi.json`. If this test goes red, the fix is to revert the
change — never to regenerate the JSON. Contract changes go through the orchestrator
(see ../ORCH-QUESTIONS.md)."""

from __future__ import annotations

import json
import pathlib

from app.main import app


def test_generated_openapi_matches_frozen_contract():
    committed = json.loads(
        (pathlib.Path(__file__).resolve().parents[2] / "contract" / "openapi.json").read_text()
    )
    assert app.openapi() == committed
