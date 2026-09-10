import Foundation

/// The style catalog — hard-coded per the client brief, shared with the backend by
/// convention rather than a contract field (`RenderCreate.style` is a bare string).
/// If the backend's accepted list ever differs, that's a cross-cutting question, not
/// something to guess at silently (see `../../ORCH-QUESTIONS.md`).
///
/// Grew from 6 to 18 per `prompt_review/HANDOFF.md` §2 (backend's prompt.py rewrite).
/// Twelve of these have no bundled sample-card image yet — `StyleImageResolver`
/// already falls back to a tinted placeholder for any id not in its
/// `bundledStyleIds` set, so shipping the full list doesn't wait on the art.
struct Style: Identifiable, Equatable {
    let id: String
    let displayName: String

    static let all: [Style] = [
        Style(id: "warm-minimal", displayName: "Warm Minimal"),
        Style(id: "scandi", displayName: "Scandi"),
        Style(id: "japandi", displayName: "Japandi"),
        Style(id: "modern-coastal", displayName: "Modern Coastal"),
        Style(id: "mid-century", displayName: "Mid-Century"),
        Style(id: "industrial", displayName: "Industrial"),
        Style(id: "traditional", displayName: "Traditional"),
        Style(id: "art-deco", displayName: "Art Deco"),
        Style(id: "dark-academia", displayName: "Dark Academia"),
        Style(id: "maximalism", displayName: "Maximalism"),
        Style(id: "moroccan", displayName: "Moroccan"),
        Style(id: "cottagecore", displayName: "Cottagecore"),
        Style(id: "rustic-farmhouse", displayName: "Rustic Farmhouse"),
        Style(id: "mediterranean", displayName: "Mediterranean"),
        Style(id: "cyberpunk", displayName: "Cyberpunk"),
        Style(id: "memphis", displayName: "Memphis"),
        Style(id: "christmas", displayName: "Christmas"),
        Style(id: "valentines", displayName: "Valentine's Day"),
    ]
}
