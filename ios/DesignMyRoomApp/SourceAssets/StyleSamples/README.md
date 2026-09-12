# Style sample sources

The full-resolution originals here (1024×1024 PNG, gpt-image-2, not from any user's
room — PRD U4) are the masters behind the compressed versions actually shipped in
`../Resources/Assets.xcassets/<style-id>.imageset/`. Kept here, outside `Resources/`,
so they're **not** picked up by the app target's resource bundling (that path is
recursive over `Resources/` in `project.yml`) — the app only ships the compressed
copies.

Originally 6 styles (`warm-minimal`, `scandi`, `mid-century`, `japandi`,
`modern-coastal`, `industrial`); grew to 18 in `Style.swift` per
`prompt_review/HANDOFF.md` §2, then to the full 62 for DecorAI name parity
(backend `prompt.py` commit 6959d92) — same process for each new id's source PNG:
one real render per style through the actual running pipeline (dev sign-in, one
room, one sample photo, `walls: "repaint"` explicitly set so new styles match the
older 18's visual character now that the options round defaults walls to
"leave"), the after-image downloaded as the master PNG. `gpt-image-2` is
rate-limited by OpenAI to 5 requests/minute org-wide — generate sequentially
(one worker replica) rather than in parallel, which reliably hits that ceiling
and fails renders instead of just queuing them.

Regenerate the shipped copies (e.g. to change size/quality) with:

```bash
sips -Z 450 -s format jpeg -s formatOptions 78 <style-id>.png \
  --out ../../Resources/Assets.xcassets/<style-id>.imageset/<style-id>.jpg
```

`450px` because the card displays at 118×150 points (150pt tall ≈ 450px at 3x) — no
reason to ship more resolution than the largest size it's ever shown at. `78`
quality JPEG cut each file from ~1.6–2MB to well under 100KB with no visible
artifacting at card size; re-check that visually if you change either number.
