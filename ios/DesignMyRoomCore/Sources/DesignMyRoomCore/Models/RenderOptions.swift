import Foundation

/// Mirrors `components/schemas/WallsOption`. Default `leave` — the one field whose
/// default is not today's behaviour (`options_review/HANDOFF.md` §1.1).
public enum WallsOption: String, Codable, Equatable, Sendable {
    case repaint
    case leave
}

/// Mirrors `components/schemas/FurnitureOption`.
public enum FurnitureOption: String, Codable, Equatable, Sendable {
    case keepOnly = "keep_only"
    case add
}

/// Mirrors `components/schemas/DecorLevel`.
public enum DecorLevel: String, Codable, Equatable, CaseIterable, Sendable {
    case minimal
    case asStyle = "as_style"
    case plenty
}

/// Mirrors `components/schemas/PaletteOption`.
public enum PaletteOption: String, Codable, Equatable, CaseIterable, Sendable {
    case asStyle = "as_style"
    case neutral
    case warm
    case cool
    case bold
}
