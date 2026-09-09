#!/usr/bin/env python3
"""Regenerate contract/openapi.json from the route signatures.

Run after any change to app/schemas.py or app/main.py. The generated file is the
contract both halves build against — it is never edited by hand.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from app.main import app  # noqa: E402

out = os.path.join(os.path.dirname(HERE), "contract", "openapi.json")
spec = app.openapi()
json.dump(spec, open(out, "w"), indent=2)
print(f"{out} — {len(spec['paths'])} paths, {len(spec['components']['schemas'])} schemas")
