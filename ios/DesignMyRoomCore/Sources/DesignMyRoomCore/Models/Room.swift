import Foundation

/// Mirrors `components/schemas/Room`.
public struct Room: Codable, Equatable, Sendable {
    public let roomId: String
    public let label: String?
    public let createdAt: Date
    public let hasPhoto: Bool
    public let hasInventory: Bool

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
