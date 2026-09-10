import Foundation

/// `loc` elements are `anyOf` string or integer (a field name or an array index) —
/// stringify either so callers don't need to care which.
public struct ValidationLocComponent: Codable, Equatable, Sendable, CustomStringConvertible {
    public let description: String

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) {
            description = string
        } else {
            description = String(try container.decode(Int.self))
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(description)
    }
}

/// Mirrors `components/schemas/ValidationError`. Only ever seen inside a `422`
/// `HTTPValidationError` — a client bug (a malformed request body), not a
/// user-facing flow.
public struct ValidationErrorDetail: Codable, Equatable, Sendable {
    public let loc: [ValidationLocComponent]
    public let msg: String
    public let type: String
}

/// Mirrors `components/schemas/HTTPValidationError` — the `422` response shape,
/// distinct from `ApiError`.
public struct HTTPValidationError: Codable, Equatable, Sendable {
    public let detail: [ValidationErrorDetail]
}
