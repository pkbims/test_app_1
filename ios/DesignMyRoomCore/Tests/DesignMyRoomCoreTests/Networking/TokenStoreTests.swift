import XCTest
@testable import DesignMyRoomCore

/// The brief is explicit: access token in memory only, refresh token in the Keychain.
/// These tests exercise the real Keychain (this sandbox has one) rather than a fake,
/// since a fake would only prove the fake works.
final class KeychainTokenStoreTests: XCTestCase {

    private func makeStore() -> KeychainTokenStore {
        KeychainTokenStore(service: "com.designmyroom.tests.\(UUID().uuidString)")
    }

    override func tearDown() {
        super.tearDown()
    }

    func testStartsEmpty() async {
        let store = makeStore()
        let access = await store.accessToken()
        let refresh = await store.refreshToken()
        XCTAssertNil(access)
        XCTAssertNil(refresh)
    }

    func testSaveThenRead() async {
        let store = makeStore()
        await store.save(tokens: Tokens(accessToken: "a1", refreshToken: "r1", expiresIn: 900))
        let access = await store.accessToken()
        let refresh = await store.refreshToken()
        XCTAssertEqual(access, "a1")
        XCTAssertEqual(refresh, "r1")
    }

    func testSaveWithNilRefreshTokenKeepsPreviousRefreshToken() async {
        // /v1/auth/refresh's response can omit refresh_token (rotation isn't required
        // every call) — the schema marks it optional. Overwriting a real refresh
        // token with nil would strand the user at the next expiry, so a nil in a
        // save() call must not erase a refresh token already in the Keychain.
        let store = makeStore()
        await store.save(tokens: Tokens(accessToken: "a1", refreshToken: "r1", expiresIn: 900))
        await store.save(tokens: Tokens(accessToken: "a2", refreshToken: nil, expiresIn: 900))
        let access = await store.accessToken()
        let refresh = await store.refreshToken()
        XCTAssertEqual(access, "a2")
        XCTAssertEqual(refresh, "r1")
    }

    func testClearRemovesBoth() async {
        let store = makeStore()
        await store.save(tokens: Tokens(accessToken: "a1", refreshToken: "r1", expiresIn: 900))
        await store.clear()
        let access = await store.accessToken()
        let refresh = await store.refreshToken()
        XCTAssertNil(access)
        XCTAssertNil(refresh)
    }

    func testAccessTokenDoesNotSurviveANewStoreInstance() async {
        // Only the refresh token is persisted to the Keychain; the access token is
        // in-memory state scoped to one KeychainTokenStore instance, standing in for
        // "in memory only, gone on relaunch" without needing a process relaunch to
        // prove it.
        let service = "com.designmyroom.tests.\(UUID().uuidString)"
        let store1 = KeychainTokenStore(service: service)
        await store1.save(tokens: Tokens(accessToken: "a1", refreshToken: "r1", expiresIn: 900))

        let store2 = KeychainTokenStore(service: service)
        let access = await store2.accessToken()
        let refresh = await store2.refreshToken()
        XCTAssertNil(access, "access token must not be persisted")
        XCTAssertEqual(refresh, "r1", "refresh token must be persisted")
    }
}
