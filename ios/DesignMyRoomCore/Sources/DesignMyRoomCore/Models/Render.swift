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
        creditsLeft: Int?
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
    }
}

/// Mirrors `components/schemas/RenderCreate` — the `POST /v1/rooms/{id}/renders`
/// request body.
///
/// Request-only, so it's `Encodable`, not `Codable`. Encodes `prompt` as an explicit
/// `null` rather than omitting the key when absent — functionally identical to
/// Pydantic (an optional field defaults to `None` either way), but explicit matches
/// the schema, which lists the key, and keeps `swift test` fixtures unambiguous.
public struct RenderCreate: Encodable, Equatable, Sendable {
    public let style: String
    public let prompt: String?
    public let removeIds: [String]
    public let idempotencyKey: String

    public init(style: String, prompt: String?, removeIds: [String], idempotencyKey: String) {
        self.style = style
        self.prompt = prompt
        self.removeIds = removeIds
        self.idempotencyKey = idempotencyKey
    }

    private enum CodingKeys: String, CodingKey {
        case style, prompt, removeIds, idempotencyKey
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
    }
}
