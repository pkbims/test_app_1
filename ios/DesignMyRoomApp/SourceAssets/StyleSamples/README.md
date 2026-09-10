# Style sample sources

The six full-resolution originals here (1024×1024 PNG, gpt-image-2, not from any
user's room — PRD U4) are the masters behind the compressed versions actually
shipped in `../Resources/Assets.xcassets/<style-id>.imageset/`. Kept here, outside
`Resources/`, so they're **not** picked up by the app target's resource bundling
(that path is recursive over `Resources/` in `project.yml`) — the app only ships the
compressed copies.

Regenerate the shipped copies (e.g. to change size/quality) with:

```bash
sips -Z 450 -s format jpeg -s formatOptions 78 <style-id>.png \
  --out ../../Resources/Assets.xcassets/<style-id>.imageset/<style-id>.jpg
```

`450px` because the card displays at 130×130 points (≈390px at 3x) — no reason to
ship more resolution than the largest size it's ever shown at. `78` quality JPEG cut
each file from ~1.6–2MB to 45–96KB (~96% smaller) with no visible artifacting at
card size; re-check that visually if you change either number.
