/// Pure text formatting for the confirm screen's live count and summary sentence
/// (`options_review/HANDOFF.md` §5.1 / §6) — e.g. "Keeping the floor lamp and
/// bookshelf. Removing the side table." Kept out of the view so the branchy list-
/// joining logic (0/1/many items) is unit-testable without SwiftUI.
enum ConfirmSummary {
    static func count(kept: Int, removed: Int) -> String {
        "keeping \(kept) · removing \(removed)"
    }

    static func sentence(kept: [String], removed: [String]) -> String {
        let keepPart = kept.isEmpty ? "Keeping nothing." : "Keeping \(list(kept))."
        let removePart = removed.isEmpty ? "Removing nothing." : "Removing \(list(removed))."
        return "\(keepPart) \(removePart)"
    }

    private static func list(_ names: [String]) -> String {
        let lower = names.map { $0.lowercased() }
        switch lower.count {
        case 0:
            return ""
        case 1:
            return "the \(lower[0])"
        default:
            let allButLast = lower.dropLast().joined(separator: ", ")
            return "the \(allButLast) and \(lower.last!)"
        }
    }
}
