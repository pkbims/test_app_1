import Foundation

/// Mirrors `components/schemas/RenderStatus`. This is the render state machine's
/// vocabulary — see `RenderStateMachine`.
public enum RenderStatus: String, Codable, Equatable, Sendable {
    case queued
    case running
    case done
    case failed
}

/// Mirrors `components/schemas/Render`. Returned by `POST /v1/rooms/{id}/renders`
/// (status `queued`) and polled via `GET /v1/renders/{id}` every 2s until `done` or
/// `failed`.
public struct Render: Codable, Equatable, Sendable {
    public let renderId: String
    public let roomId: String
    public let status: RenderStatus
    public let style: String
    public let removeIds: [String]
    public let beforeUrl: String?
    public let afterUrl: String?
    /// Share of architectural inventory items still present in the result, judged by a
    /// vision call — not a pixel comparison, per the validated architecture. `nil`
    /// until the render finishes.
    public let preservationRate: Double?
    /// Inventory ids the preservation check could not find in the result.
    public let missingItems: [String]?
    public let errorCode: String?
    public let createdAt: Date
    public let creditsLeft: Int?
    /// The options-round fields (`options_review/HANDOFF.md` §3.2), echoed from the
    /// request so the compare screen's "What you asked for" row and render history
    /// are self-describing. A pre-options-round response has none of these keys, so
    /// decoding falls back to the same defaults the backend applies.
    public let roomType: RoomType?
    public let walls: WallsOption
    public let furniture: FurnitureOption
    public let addFurniture: [String]
    public let decor: DecorLevel
    public let plants: Bool
    public let palette: PaletteOption

    public init(
        renderId: String,
        roomId: String,
        status: RenderStatus,
        style: String,
        removeIds: [String],
        beforeUrl: String?,
        afterUrl: String?,
        preservationRate: Double?,
        missingItems: [String]?,
        errorCode: String?,
        createdAt: Date,
        creditsLeft: Int?,
        roomType: RoomType? = nil,
        walls: WallsOption = .leave,
        furniture: FurnitureOption = .keepOnly,
        addFurniture: [String] = [],
        decor: DecorLevel = .asStyle,
        plants: Bool = false,
        palette: PaletteOption = .asStyle
    ) {
        self.renderId = renderId
        self.roomId = roomId
        self.status = status
        self.style = style
        self.removeIds = removeIds
        self.beforeUrl = beforeUrl
        self.afterUrl = afterUrl
        self.preservationRate = preservationRate
        self.missingItems = missingItems
        self.errorCode = errorCode
        self.createdAt = createdAt
        self.creditsLeft = creditsLeft
        self.roomType = roomType
        self.walls = walls
        self.furniture = furniture
        self.addFurniture = addFurniture
        self.decor = decor
        self.plants = plants
        self.palette = palette
    }

    private enum CodingKeys: String, CodingKey {
        case renderId, roomId, status, style, removeIds, beforeUrl, afterUrl,
             preservationRate, missingItems, errorCode, createdAt, creditsLeft,
             roomType, walls, furniture, addFurniture, decor, plants, palette
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        renderId = try container.decode(String.self, forKey: .renderId)
        roomId = try container.decode(String.self, forKey: .roomId)
        status = try container.decode(RenderStatus.self, forKey: .status)
        style = try container.decode(String.self, forKey: .style)
        removeIds = try container.decode([String].self, forKey: .removeIds)
        beforeUrl = try container.decodeIfPresent(String.self, forKey: .beforeUrl)
        afterUrl = try container.decodeIfPresent(String.self, forKey: .afterUrl)
        preservationRate = try container.decodeIfPresent(Double.self, forKey: .preservationRate)
        missingItems = try container.decodeIfPresent([String].self, forKey: .missingItems)
        errorCode = try container.decodeIfPresent(String.self, forKey: .errorCode)
        createdAt = try container.decode(Date.self, forKey: .createdAt)
        creditsLeft = try container.decodeIfPresent(Int.self, forKey: .creditsLeft)
        roomType = try container.decodeIfPresent(RoomType.self, forKey: .roomType)
        walls = try container.decodeIfPresent(WallsOption.self, forKey: .walls) ?? .leave
        furniture = try container.decodeIfPresent(FurnitureOption.self, forKey: .furniture) ?? .keepOnly
        addFurniture = try container.decodeIfPresent([String].self, forKey: .addFurniture) ?? []
        decor = try container.decodeIfPresent(DecorLevel.self, forKey: .decor) ?? .asStyle
        plants = try container.decodeIfPresent(Bool.self, forKey: .plants) ?? false
        palette = try container.decodeIfPresent(PaletteOption.self, forKey: .palette) ?? .asStyle
    }
}

/// Mirrors `components/schemas/RenderCreate` — the `POST /v1/rooms/{id}/renders`
/// request body.
///
/// Request-only, so it's `Encodable`, not `Codable`. Encodes `prompt` and `roomType`
/// as an explicit `null` rather than omitting the key when absent — functionally
/// identical to Pydantic (an optional field defaults to `None` either way), but
/// explicit matches the schema, which lists the key, and keeps `swift test` fixtures
/// unambiguous. The other five options-round fields (`options_review/HANDOFF.md`
/// §3.1) always default to today's behaviour except `walls`, whose default flips to
/// `.leave` — a deliberate change, not a bug.
public struct RenderCreate: Encodable, Equatable, Sendable {
    public let style: String
    public let prompt: String?
    public let removeIds: [String]
    public let idempotencyKey: String
    public let roomType: RoomType?
    public let walls: WallsOption
    public let furniture: FurnitureOption
    public let addFurniture: [String]
    public let decor: DecorLevel
    public let plants: Bool
    public let palette: PaletteOption

    public init(
        style: String,
        prompt: String?,
        removeIds: [String],
        idempotencyKey: String,
        roomType: RoomType? = nil,
        walls: WallsOption = .leave,
        furniture: FurnitureOption = .keepOnly,
        addFurniture: [String] = [],
        decor: DecorLevel = .asStyle,
        plants: Bool = false,
        palette: PaletteOption = .asStyle
    ) {
        self.style = style
        self.prompt = prompt
        self.removeIds = removeIds
        self.idempotencyKey = idempotencyKey
        self.roomType = roomType
        self.walls = walls
        self.furniture = furniture
        self.addFurniture = addFurniture
        self.decor = decor
        self.plants = plants
        self.palette = palette
    }

    private enum CodingKeys: String, CodingKey {
        case style, prompt, removeIds, idempotencyKey, roomType, walls, furniture, addFurniture, decor, plants, palette
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(style, forKey: .style)
        if let prompt {
            try container.encode(prompt, forKey: .prompt)
        } else {
            try container.encodeNil(forKey: .prompt)
        }
        try container.encode(removeIds, forKey: .removeIds)
        try container.encode(idempotencyKey, forKey: .idempotencyKey)
        if let roomType {
            try container.encode(roomType, forKey: .roomType)
        } else {
            try container.encodeNil(forKey: .roomType)
        }
        try container.encode(walls, forKey: .walls)
        try container.encode(furniture, forKey: .furniture)
        try container.encode(addFurniture, forKey: .addFurniture)
        try container.encode(decor, forKey: .decor)
        try container.encode(plants, forKey: .plants)
        try container.encode(palette, forKey: .palette)
    }
}
