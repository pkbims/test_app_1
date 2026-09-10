import Foundation

/// Mirrors `components/schemas/Tokens`. Returned by `/v1/auth/apple` and
/// `/v1/auth/refresh`.
///
/// Per the client brief: `accessToken` lives in memory only, `refreshToken` goes to
/// the Keychain. This type doesn't enforce that — `TokenStore` does — it just carries
/// the values across the wire.
public struct Tokens: Codable, Equatable, Sendable {
    public let accessToken: String
    public let refreshToken: String?
    public let expiresIn: Int

    public init(accessToken: String, refreshToken: String?, expiresIn: Int) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.expiresIn = expiresIn
    }
}

/// Mirrors `components/schemas/AppleSignIn` — the `POST /v1/auth/apple` request body.
public struct AppleSignIn: Codable, Equatable, Sendable {
    public let identityToken: String

    public init(identityToken: String) {
        self.identityToken = identityToken
    }
}

/// Mirrors `components/schemas/RefreshRequest` — the `POST /v1/auth/refresh` request body.
public struct RefreshRequest: Codable, Equatable, Sendable {
    public let refreshToken: String

    public init(refreshToken: String) {
        self.refreshToken = refreshToken
    }
}

/// Mirrors `components/schemas/Me`.
public struct Me: Codable, Equatable, Sendable {
    public let userId: String
    public let creditsLeft: Int

    public init(userId: String, creditsLeft: Int) {
        self.userId = userId
        self.creditsLeft = creditsLeft
    }
}
