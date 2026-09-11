import DesignMyRoomCore

/// Pure chip-list builder for the compare screen's "What you asked for" readback
/// row (`options_review/HANDOFF.md` §5.4) — a read-back of the echoed `Render`
/// options fields, no interaction. Kept out of the view so the branchy assembly
/// (which chips appear, in what order, with what text) is unit-testable without
/// SwiftUI. `inventory` is only used to turn `removeIds` back into names for the
/// "Removed: …" chip — the frozen `Render` has ids, not names; if the inventory
/// that produced this render isn't loaded, that one chip is simply skipped rather
/// than showing raw ids.
enum CompareAskedFor {
    static func chips(render: Render, inventory: Inventory?) -> [String] {
        var chips: [String] = [
            render.roomType?.displayName ?? "Room",
            wallsLabel(render.walls),
            furnitureLabel(render.furniture),
            decorLabel(render.decor),
        ]

        if render.furniture == .add, !render.addFurniture.isEmpty {
            let names = render.addFurniture.map(furnitureDisplayName)
            chips.append("Add: \(names.joined(separator: ", "))")
        }
        if render.plants {
            chips.append("Plants added")
        }
        if render.palette != .asStyle {
            chips.append("\(paletteLabel(render.palette)) colours")
        }
        if let inventory {
            let removedNames = inventory.items
                .filter { render.removeIds.contains($0.id) }
                .map(\.name)
            if !removedNames.isEmpty {
                chips.append("Removed: \(removedNames.joined(separator: ", "))")
            }
        }
        return chips
    }

    private static func wallsLabel(_ value: WallsOption) -> String {
        switch value {
        case .repaint: "Repaint"
        case .leave: "Leave as they are"
        }
    }

    private static func furnitureLabel(_ value: FurnitureOption) -> String {
        switch value {
        case .keepOnly: "Only what I'm keeping"
        case .add: "Add new pieces"
        }
    }

    private static func decorLabel(_ value: DecorLevel) -> String {
        switch value {
        case .minimal: "Minimal decor"
        case .asStyle: "Decor as the style"
        case .plenty: "Plenty of decor"
        }
    }

    private static func paletteLabel(_ value: PaletteOption) -> String {
        switch value {
        case .asStyle: "As the style"
        case .neutral: "Neutral"
        case .warm: "Warm"
        case .cool: "Cool"
        case .bold: "Bold"
        }
    }

    /// Furniture ids repeat their display name identically wherever they appear in
    /// more than one room's list (checked against every list in
    /// `options_review/HANDOFF.md` §7.2), so a flat search across every room type is
    /// safe regardless of which room this render was actually for.
    private static func furnitureDisplayName(_ id: String) -> String {
        for roomType in RoomType.allCases {
            if let match = FurnitureCatalog.items(for: roomType).first(where: { $0.id == id }) {
                return match.displayName.lowercased()
            }
        }
        return id.replacingOccurrences(of: "_", with: " ")
    }
}
