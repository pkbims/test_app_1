# Style sample sources

The full-resolution originals here (1024×1024 PNG, gpt-image-2, not from any user's
room — PRD U4) are the masters behind the compressed versions actually shipped in
`../Resources/Assets.xcassets/<style-id>.imageset/`. Kept here, outside `Resources/`,
so they're **not** picked up by the app target's resource bundling (that path is
recursive over `Resources/` in `project.yml`) — the app only ships the compressed
copies.

Originally 6 styles (`warm-minimal`, `scandi`, `mid-century`, `japandi`,
`modern-coastal`, `industrial`); grew to the full 18 in `Style.swift` per
`prompt_review/HANDOFF.md` §2 — same process for each new id's source PNG.

Regenerate the shipped copies (e.g. to change size/quality) with:

```bash
sips -Z 450 -s format jpeg -s formatOptions 78 <style-id>.png \
  --out ../../Resources/Assets.xcassets/<style-id>.imageset/<style-id>.jpg
```

`450px` because the card displays at 118×150 points (150pt tall ≈ 450px at 3x) — no
reason to ship more resolution than the largest size it's ever shown at. `78`
quality JPEG cut each file from ~1.6–2MB to well under 100KB with no visible
artifacting at card size; re-check that visually if you change either number.
