import Foundation

/// The style catalog — hard-coded per the client brief, shared with the backend by
/// convention rather than a contract field (`RenderCreate.style` is a bare string).
/// If the backend's accepted list ever differs, that's a cross-cutting question, not
/// something to guess at silently (see `../../ORCH-QUESTIONS.md`).
struct Style: Identifiable, Equatable {
    let id: String
    let displayName: String

    static let all: [Style] = [
        Style(id: "warm-minimal", displayName: "Warm Minimal"),
        Style(id: "scandi", displayName: "Scandi"),
        Style(id: "mid-century", displayName: "Mid-Century"),
        Style(id: "japandi", displayName: "Japandi"),
        Style(id: "modern-coastal", displayName: "Modern Coastal"),
        Style(id: "industrial", displayName: "Industrial"),
    ]
}
