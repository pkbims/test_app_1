import SwiftUI

/// Visual system tokens from `ui_design_v2/HANDOFF.md` §1. Named color sets live in
/// `Assets.xcassets` (not hardcoded hex) so a future palette swap stays a one-file
/// change. Restyling only — nothing here changes flow or state-machine logic.
extension Color {
    static let paper = Color("Paper")
    static let surface = Color("Surface")
    static let surface2 = Color("Surface2")
    static let ink = Color("Ink")
    static let inkSoft = Color("InkSoft")
    static let faint = Color("Faint")
    static let line = Color("Line")
    /// `accent` (clay, `#B2582F`) — the asset catalog's global `AccentColor`.
    static let accent = Color("AccentColor")
    static let accentDeep = Color("AccentDeep")
    static let accentSoft = Color("AccentSoft")
    static let accentInk = Color("AccentInk")
    static let warn = Color("Warn")
    static let warnSoft = Color("WarnSoft")
}

enum Spacing {
    static let xs: CGFloat = 6
    static let s: CGFloat = 8
    static let sm: CGFloat = 10
    static let m: CGFloat = 12
    static let l: CGFloat = 16
    static let xl: CGFloat = 24
    static let xxl: CGFloat = 32
    static let screenEdge: CGFloat = 20
}

enum Radius {
    static let button: CGFloat = 16
    static let gridCard: CGFloat = 16
    static let feedCard: CGFloat = 18
    static let styleCard: CGFloat = 16
    static let beforeAfterImage: CGFloat = 16
    static let letterBadge: CGFloat = 7
    static let dashedCard: CGFloat = 18
}

extension View {
    /// Room/style cards, before/after images — HANDOFF §1 "Card" tier.
    func cardShadow() -> some View {
        shadow(color: .black.opacity(0.08), radius: 6, x: 0, y: 2)
    }

    /// HANDOFF §1 "Raised" tier — not used by any screen yet, kept for parity with the token set.
    func raisedShadow() -> some View {
        shadow(color: .black.opacity(0.12), radius: 14, x: 0, y: 6)
    }

    /// Accent-tinted shadow reserved for the primary CTA pill.
    func ctaShadow() -> some View {
        shadow(color: Color(red: 0.698, green: 0.345, blue: 0.184).opacity(0.28), radius: 8, x: 0, y: 6)
    }
}

extension Font {
    enum FrauncesWeight {
        case medium, semibold

        var swiftUIWeight: Font.Weight {
            switch self {
            case .medium: .medium
            case .semibold: .semibold
            }
        }
    }

    /// Fraunces isn't bundled yet (real work — licensing/downloading static weights,
    /// Xcode target + `Info.plist` registration — tracked in HANDOFF.md §5). Using the
    /// system serif ("New York") as the spec's own sanctioned temporary stand-in;
    /// swap the body of this one function once Fraunces lands.
    static func fraunces(_ size: CGFloat, weight: FrauncesWeight = .medium) -> Font {
        .system(size: size, design: .serif).weight(weight.swiftUIWeight)
    }
}
