import Foundation
#if canImport(Security)
import Security
#endif

/// Real `TokenStore`: the access token is a plain `actor`-isolated property (in
/// memory, gone on relaunch); the refresh token is a Keychain generic-password item
/// (30 days, per the contract — survives relaunch, is what re-establishes a session).
///
/// `service` scopes the Keychain item; production uses one fixed service string,
/// tests use a unique one per instance so they can't see each other's items.
public actor KeychainTokenStore: TokenStore {
    private let service: String
    private let account = "refresh_token"
    private var inMemoryAccessToken: String?

    public init(service: String = "com.designmyroom.app.tokens") {
        self.service = service
    }

    public func accessToken() async -> String? {
        inMemoryAccessToken
    }

    public func refreshToken() async -> String? {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    public func save(tokens: Tokens) async {
        inMemoryAccessToken = tokens.accessToken
        guard let refreshToken = tokens.refreshToken else { return }
        setRefreshToken(refreshToken)
    }

    public func clear() async {
        inMemoryAccessToken = nil
        SecItemDelete(baseQuery() as CFDictionary)
    }

    private func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }

    private func setRefreshToken(_ token: String) {
        let data = Data(token.utf8)
        var query = baseQuery()

        let attributesToUpdate: [String: Any] = [kSecValueData as String: data]
        let updateStatus = SecItemUpdate(query as CFDictionary, attributesToUpdate as CFDictionary)
        if updateStatus == errSecItemNotFound {
            query[kSecValueData as String] = data
            query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            SecItemAdd(query as CFDictionary, nil)
        }
    }
}
