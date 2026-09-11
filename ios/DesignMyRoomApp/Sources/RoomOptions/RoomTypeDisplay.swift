import DesignMyRoomCore

/// UI strings for `RoomType` — kept out of `DesignMyRoomCore` because the wire enum
/// is pure contract, and display copy is a client concern (same split as `Style`,
/// whose display names live here in the app target too). Order follows
/// `options_review/HANDOFF.md` §7.1 via `RoomType.allCases`.
extension RoomType {
    var displayName: String {
        switch self {
        case .livingRoom: "Living room"
        case .bedroom: "Bedroom"
        case .kitchen: "Kitchen"
        case .diningRoom: "Dining room"
        case .homeOffice: "Home office"
        case .kidsRoom: "Kids' room"
        case .nursery: "Nursery"
        case .bathroom: "Bathroom"
        case .hallway: "Hallway"
        case .studio: "Studio"
        case .workshop: "Workshop"
        case .serverRoom: "Server room"
        }
    }
}
