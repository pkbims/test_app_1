#!/usr/bin/env python3
"""Local spec-review server. Serves the interactive PRD and persists decisions
and queued comments to disk so Claude can read them back."""

import json
import os
import http.server
import socketserver
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
INBOX = os.path.join(HERE, "INBOX.md")
PORT = int(os.environ.get("PORT", "7777"))

def _empty():
    return {"decisions": {}, "comments": [], "batches": []}


def load():
    if not os.path.exists(STATE):
        return _empty()
    try:
        with open(STATE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty()
    base = _empty()
    base.update(data)
    return base


def save(state):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE)


def write_inbox(state):
    """Human-readable snapshot Claude reads after a send."""
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    rnd = len(state["batches"])
    prev = state["batches"][-2]["decisions"] if len(state["batches"]) > 1 else {}
    cur = state["batches"][-1]["decisions"] if state["batches"] else state["decisions"]
    lines = [f"# Spec review inbox", "", f"Round {rnd} sent {now}", ""]

    changed = {k: v for k, v in cur.items() if prev.get(k) != v}
    if rnd > 1:
        lines.append(f"## Changed since round {rnd - 1} ({len(changed)})")
        lines.append("")
        if not changed:
            lines.append("_No decisions changed._")
        for k, v in changed.items():
            val = ", ".join(v) if isinstance(v, list) else v
            was = prev.get(k)
            was = ", ".join(was) if isinstance(was, list) else (was or "unanswered")
            lines.append(f"- **{k}** — {val}  _(was: {was})_")
        lines.append("")

    unanswered = [g for g in state.get("groups", []) if g not in cur]
    if unanswered:
        lines.append(f"## Still unanswered: {', '.join(unanswered)}")
        lines.append("")

    pending = [c for c in state["comments"] if c.get("status") == "sent"
               and not c.get("addressed")]
    lines.append(f"## Comments to address ({len(pending)})")
    lines.append("")
    if not pending:
        lines.append("_None._")
    for c in pending:
        lines.append(f"### {c.get('anchorLabel') or c.get('anchor')}")
        quoted = (c.get("anchorText") or "").strip()
        if quoted:
            lines.append(f"> {quoted[:300]}")
        lines.append("")
        lines.append(c.get("text", ""))
        lines.append("")

    lines.append(f"## Decisions as of round {rnd}")
    lines.append("")
    if not cur:
        lines.append("_None recorded._")
    for k, v in cur.items():
        val = ", ".join(v) if isinstance(v, list) else v
        lines.append(f"- **{k}** — {val}")
    lines.append("")

    with open(INBOX, "w") as f:
        f.write("\n".join(lines))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def log_message(self, fmt, *args):
        pass  # quiet

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/state":
            return self._json(load())
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "bad json"}, 400)

        state = load()

        if self.path == "/api/groups":
            state["groups"] = payload.get("groups", [])
            save(state)
            return self._json({"ok": True})

        if self.path == "/api/decision":
            state["decisions"][payload["id"]] = payload["value"]
            save(state)
            return self._json({"ok": True})

        if self.path == "/api/comment":
            payload["status"] = "queued"
            payload["ts"] = datetime.now(timezone.utc).isoformat()
            state["comments"].append(payload)
            save(state)
            return self._json({"ok": True, "comments": state["comments"]})

        if self.path == "/api/comment/delete":
            state["comments"] = [c for c in state["comments"]
                                 if c.get("id") != payload.get("id")]
            save(state)
            return self._json({"ok": True, "comments": state["comments"]})

        if self.path == "/api/send":
            ids = []
            for c in state["comments"]:
                if c.get("status") == "queued":
                    c["status"] = "sent"
                    ids.append(c.get("id"))
            state["batches"].append({
                "round": len(state["batches"]) + 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "commentIds": ids,
                "decisions": dict(state["decisions"]),
            })
            save(state)
            write_inbox(state)
            return self._json({"ok": True, "sent": len(ids)})

        return self._json({"error": "unknown endpoint"}, 404)


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"spec review running at http://localhost:{PORT}")
        httpd.serve_forever()
