import Foundation

/// Mirrors `components/schemas/Room`. `Hashable`/`Identifiable` so SwiftUI can list
/// it directly and navigate by value (`NavigationLink(value: room)`) — there's no
/// `GET /v1/rooms/{id}` in the contract, so the room list screen hands the whole
/// `Room` it already has straight to the detail screen rather than re-fetching it.
public struct Room: Codable, Equatable, Hashable, Identifiable, Sendable {
    public let roomId: String
    public let label: String?
    public let createdAt: Date
    public let hasPhoto: Bool
    public let hasInventory: Bool

    public var id: String { roomId }

    public init(roomId: String, label: String?, createdAt: Date, hasPhoto: Bool, hasInventory: Bool) {
        self.roomId = roomId
        self.label = label
        self.createdAt = createdAt
        self.hasPhoto = hasPhoto
        self.hasInventory = hasInventory
    }
}

/// Mirrors `components/schemas/RoomCreate` — the `POST /v1/rooms` request body.
public struct RoomCreate: Codable, Equatable, Sendable {
    public let label: String?

    public init(label: String?) {
        self.label = label
    }
}
