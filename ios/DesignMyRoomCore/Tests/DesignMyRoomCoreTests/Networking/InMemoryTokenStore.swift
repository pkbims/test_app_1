import Foundation
@testable import DesignMyRoomCore

/// Plain in-memory `TokenStore` test double — isolates `APIClient` tests from the
/// real Keychain, which already has its own dedicated tests (`KeychainTokenStoreTests`).
final actor InMemoryTokenStore: TokenStore {
    private(set) var access: String?
    private(set) var refresh: String?
    private(set) var clearCallCount = 0

    init(access: String? = nil, refresh: String? = nil) {
        self.access = access
        self.refresh = refresh
    }

    func accessToken() async -> String? { access }
    func refreshToken() async -> String? { refresh }

    func save(tokens: Tokens) async {
        access = tokens.accessToken
        if let newRefresh = tokens.refreshToken {
            refresh = newRefresh
        }
    }

    func clear() async {
        access = nil
        refresh = nil
        clearCallCount += 1
    }
}
