import Foundation

/// Mirrors `components/schemas/ErrorCode` in `contract/openapi.json` verbatim.
///
/// Enum raw values are the wire strings; `JSONCoding`'s snake_case key conversion does
/// not touch string *values*, only object keys, so these must already read as the API
/// spells them.
public enum ErrorCode: String, Codable, Equatable, Sendable {
    case appleTokenInvalid = "apple_token_invalid"
    case tokenExpired = "token_expired"
    case noCredits = "no_credits"
    case rateLimited = "rate_limited"
    case photoTooLarge = "photo_too_large"
    case photoUnsupported = "photo_unsupported"
    case noPhotos = "no_photos"
    case noInventory = "no_inventory"
    case inventoryFailed = "inventory_failed"
    case renderFailed = "render_failed"
    case notFound = "not_found"
}
