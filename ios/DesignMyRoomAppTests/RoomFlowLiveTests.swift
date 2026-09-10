import XCTest
import DesignMyRoomCore
@testable import DesignMyRoom

/// Reproduces the bug report directly against the real running backend, at the
/// `RoomFlowViewModel` layer — no picker, no UI automation needed, since
/// `submitPhoto` takes plain `Data`. If this reproduces something, the bug is in
/// this layer (view-model/networking); if it stays clean here, the bug is in the
/// SwiftUI view hierarchy above it (RootView/HomeContainerView/NewRoomFlowView).
final class RoomFlowLiveTests: XCTestCase {
    private static let baseURL = URL(string: "http://localhost:8000")!

    override func setUp() async throws {
        try await super.setUp()
        var request = URLRequest(url: Self.baseURL.appendingPathComponent("health"))
        request.timeoutInterval = 1.5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                throw XCTSkip("Backend at \(Self.baseURL) not reachable; run docker compose up.")
            }
        } catch is XCTSkip {
            throw XCTSkip("Backend at \(Self.baseURL) not reachable; run docker compose up.")
        } catch {
            throw XCTSkip("Backend at \(Self.baseURL) not reachable (\(error)); run docker compose up.")
        }
    }

    @MainActor
    private func makeSignedInFlow(identifier: String) async throws -> (flow: RoomFlowViewModel, auth: AuthManager) {
        let tokenStore = KeychainTokenStore(service: "com.designmyroom.tests.\(UUID().uuidString)")
        let apiClient = APIClient(configuration: .init(baseURL: Self.baseURL, tokenStore: tokenStore))
        let crashReporter = CrashReporter(sink: NoOpCrashLogSink())
        let authManager = AuthManager(apiClient: apiClient, tokenStore: tokenStore, crashReporter: crashReporter)
        let devToken = DevJWT.signed(subject: identifier)
        _ = try await apiClient.signInWithApple(identityToken: devToken)
        await authManager.refreshMe()
        let flow = RoomFlowViewModel(
            apiClient: apiClient,
            authManager: authManager,
            crashReporter: crashReporter,
            onFinished: {}
        )
        return (flow, authManager)
    }

    private func fixtureJPEG() throws -> Data {
        var dir = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        for _ in 0..<10 {
            let candidate = dir.appendingPathComponent("inputs/room.jpg")
            if FileManager.default.fileExists(atPath: candidate.path) {
                return try Data(contentsOf: candidate)
            }
            dir = dir.deletingLastPathComponent()
        }
        throw XCTSkip("inputs/room.jpg not found relative to test file.")
    }

    @MainActor
    func testSubmitPhotoTransitionsToConfirmReliably() async throws {
        let (flow, authManager) = try await makeSignedInFlow(identifier: "livetest-single-\(UUID().uuidString)")
        let photoData = try fixtureJPEG()

        await flow.submitPhoto(data: photoData, filename: "room.jpg", mimeType: "image/jpeg")

        XCTAssertEqual(flow.step, .confirm, "banner: \(String(describing: flow.bannerMessage))")
        XCTAssertNil(flow.bannerMessage)
        if case .signedOut = authManager.state {
            XCTFail("AuthManager was unexpectedly signed out during a normal photo submission")
        }
    }

    @MainActor
    func testTwoConcurrentSubmitPhotoCallsOnTheSameFlowInstanceBothReachConfirm() async throws {
        // The bug report's log showed two POST /v1/rooms ~10s apart from what looked
        // like one user action — this simulates a double-fire of the picker's
        // completion handler (a known category of UIKit/SwiftUI interop quirk) onto
        // the SAME RoomFlowViewModel instance, both racing to mutate its state.
        let (flow, authManager) = try await makeSignedInFlow(identifier: "livetest-race-\(UUID().uuidString)")
        let photoData = try fixtureJPEG()

        async let first: Void = flow.submitPhoto(data: photoData, filename: "a.jpg", mimeType: "image/jpeg")
        async let second: Void = flow.submitPhoto(data: photoData, filename: "b.jpg", mimeType: "image/jpeg")
        _ = await (first, second)

        XCTAssertEqual(flow.step, .confirm, "banner: \(String(describing: flow.bannerMessage))")
        if case .signedOut = authManager.state {
            XCTFail("AuthManager was unexpectedly signed out from the concurrent-call race")
        }
    }
}
