import Foundation

/// Mirrors `components/schemas/Error`. Named `ApiError` (not `Error`) so it doesn't
/// shadow Swift's own `Error` protocol, which it also conforms to — every failed
/// request throws one of these directly.
///
/// `message` is shown to the user verbatim per the contract's own field description;
/// screens should never invent their own copy for a code that already has a message.
public struct ApiError: Codable, Equatable, Error, Sendable {
    public let code: ErrorCode
    public let message: String

    public init(code: ErrorCode, message: String) {
        self.code = code
        self.message = message
    }
}
