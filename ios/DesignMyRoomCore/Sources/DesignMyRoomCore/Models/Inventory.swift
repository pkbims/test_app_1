import Foundation

/// Mirrors `components/schemas/ItemKind`.
public enum ItemKind: String, Codable, Equatable, Sendable {
    case architecture
    case object
}

/// Mirrors `components/schemas/InventoryItem`.
///
/// The frozen contract has no coordinates — `id`, `kind`, `name`, `description`,
/// `removable` only. Per the orchestrator's deviation decision, the confirm screen is
/// therefore a labelled list grouped by `kind`, not a photo overlay: architecture rows
/// are informational (never `removable`), object rows get a "Remove" toggle whose
/// tapped ids become `RenderCreate.removeIds`.
public struct InventoryItem: Codable, Equatable, Identifiable, Sendable {
    public let id: String
    public let kind: ItemKind
    public let name: String
    public let description: String
    public let removable: Bool

    public init(id: String, kind: ItemKind, name: String, description: String, removable: Bool) {
        self.id = id
        self.kind = kind
        self.name = name
        self.description = description
        self.removable = removable
    }
}

/// Mirrors `components/schemas/Inventory`. Returned by both
/// `POST /v1/rooms/{id}/inventory` and `GET /v1/rooms/{id}/inventory`.
public struct Inventory: Codable, Equatable, Sendable {
    public let roomId: String
    public let items: [InventoryItem]
    public let createdAt: Date

    public init(roomId: String, items: [InventoryItem], createdAt: Date) {
        self.roomId = roomId
        self.items = items
        self.createdAt = createdAt
    }
}
