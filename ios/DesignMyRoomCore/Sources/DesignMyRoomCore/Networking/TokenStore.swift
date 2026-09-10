import Foundation

/// Where `Tokens` live between requests. Per the client brief: access token in memory
/// only, refresh token in the Keychain.
public protocol TokenStore: Sendable {
    func accessToken() async -> String?
    func refreshToken() async -> String?
    /// `tokens.refreshToken == nil` must not erase a refresh token already stored —
    /// `/v1/auth/refresh`'s response doesn't always rotate it.
    func save(tokens: Tokens) async
    func clear() async
}
