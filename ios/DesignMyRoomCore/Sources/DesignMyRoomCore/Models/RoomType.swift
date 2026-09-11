import Foundation

/// Mirrors `components/schemas/RoomType` — the 12 room types from the options-round
/// handoff (`options_review/HANDOFF.md` §7.1). Detected by the inventory vision call;
/// the user may confirm or change it on the render request. Declaration order matches
/// §7.1 so `CaseIterable.allCases` is display order for free.
public enum RoomType: String, Codable, Equatable, CaseIterable, Sendable {
    case livingRoom = "living_room"
    case bedroom
    case kitchen
    case diningRoom = "dining_room"
    case homeOffice = "home_office"
    case kidsRoom = "kids_room"
    case nursery
    case bathroom
    case hallway
    case studio
    case workshop
    case serverRoom = "server_room"
}
