import Foundation

/// Shared JSON encoder/decoder for every wire type in this module.
///
/// The contract (`contract/openapi.json`) uses snake_case field names; Swift models use
/// idiomatic camelCase properties. `convertFromSnakeCase` / `convertToSnakeCase` bridge
/// the two so no model needs a hand-written `CodingKeys` enum just to rename fields.
/// Dates are ISO-8601 with optional fractional seconds, which is what FastAPI/Pydantic
/// emit (`datetime.isoformat()`), and Foundation's plain `.iso8601` strategy rejects the
/// fractional-second form, so we try both.
enum JSONCoding {
    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom(decodeFlexibleISO8601Date)
        return decoder
    }()

    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .custom(encodeISO8601DateWithFractionalSeconds)
        return encoder
    }()
}

private let iso8601WithFractionalSeconds: ISO8601DateFormatter = {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter
}()

private let iso8601Plain: ISO8601DateFormatter = {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    return formatter
}()

func decodeFlexibleISO8601Date(from decoder: Decoder) throws -> Date {
    let container = try decoder.singleValueContainer()
    let string = try container.decode(String.self)
    if let date = iso8601WithFractionalSeconds.date(from: string) {
        return date
    }
    if let date = iso8601Plain.date(from: string) {
        return date
    }
    throw DecodingError.dataCorruptedError(
        in: container,
        debugDescription: "Expected an ISO-8601 date string, got \"\(string)\"."
    )
}

func encodeISO8601DateWithFractionalSeconds(_ date: Date, encoder: Encoder) throws {
    var container = encoder.singleValueContainer()
    try container.encode(iso8601WithFractionalSeconds.string(from: date))
}
