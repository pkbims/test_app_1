import XCTest
@testable import DesignMyRoomCore

/// Exercises the real running backend end-to-end (`docker compose up --build`,
/// `VISION_BACKEND=fake`) instead of a mock — per the orchestrator's instruction,
/// a stronger test than a stub wherever practical. Every test signs in as a fresh
/// dev-token user (see `DevJWT`) so runs don't share credits or state.
///
/// Skips itself (not a failure) if the backend isn't reachable, so `swift test`
/// still passes for anyone who hasn't run `docker compose up`.
final class RenderFlowIntegrationTests: XCTestCase {
    private static let baseURL = URL(string: "http://localhost:8000")!
    private static let devSecret = "dev-insecure-do-not-use-in-production"

    override func setUp() async throws {
        try await super.setUp()
        try await Self.skipUnlessBackendReachable()
    }

    private static func skipUnlessBackendReachable() async throws {
        var request = URLRequest(url: baseURL.appendingPathComponent("health"))
        request.timeoutInterval = 1.5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                throw XCTSkip("Backend at \(baseURL) did not respond healthily; run `docker compose up --build`.")
            }
        } catch is XCTSkip {
            throw XCTSkip("Backend at \(baseURL) did not respond healthily; run `docker compose up --build`.")
        } catch {
            throw XCTSkip("Backend at \(baseURL) is not reachable (\(error)); run `docker compose up --build`.")
        }
    }

    private func makeSignedInClient() async throws -> (APIClient, TokenStore) {
        let tokenStore = InMemoryTokenStore()
        let client = APIClient(configuration: .init(baseURL: Self.baseURL, tokenStore: tokenStore))
        let devToken = DevJWT.signed(subject: "test-\(UUID().uuidString)", secret: Self.devSecret)
        _ = try await client.signInWithApple(identityToken: devToken)
        return (client, tokenStore)
    }

    /// Finds a fixture under `inputs/` by walking up from this source file, rather
    /// than hardcoding a relative-path depth that would silently break on
    /// reorganization.
    private func fixture(_ relativePath: String) throws -> Data {
        var dir = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        for _ in 0..<10 {
            let candidate = dir.appendingPathComponent("inputs/\(relativePath)")
            if FileManager.default.fileExists(atPath: candidate.path) {
                return try Data(contentsOf: candidate)
            }
            dir = dir.deletingLastPathComponent()
        }
        throw XCTSkip("inputs/\(relativePath) not found relative to test file; skipping photo-dependent test.")
    }

    func testFullFlowSignInThroughRender() async throws {
        let (client, _) = try await makeSignedInClient()

        let me = try await client.me()
        XCTAssertGreaterThanOrEqual(me.creditsLeft, 1, "signup grants one free room")

        let room = try await client.createRoom(label: "Integration test room")
        XCTAssertFalse(room.roomId.isEmpty)
        XCTAssertFalse(room.hasPhoto)

        let photoData = try fixture("room.jpg")
        let photo = try await client.uploadPhoto(
            roomId: room.roomId,
            data: photoData,
            filename: "room.jpg",
            mimeType: "image/jpeg"
        )
        XCTAssertEqual(photo.roomId, room.roomId)
        XCTAssertGreaterThan(photo.width, 0)
        XCTAssertFalse(photo.url.isEmpty)

        let inventory = try await client.createInventory(roomId: room.roomId)
        XCTAssertFalse(inventory.items.isEmpty, "the fake vision backend still returns a deterministic inventory")
        XCTAssertTrue(inventory.items.contains { $0.kind == .architecture }, "architecture is always listed")

        let removableIds = inventory.items.filter(\.removable).map(\.id)

        let render = try await client.createRender(
            roomId: room.roomId,
            body: RenderCreate(
                style: "warm-minimal",
                prompt: nil,
                removeIds: Array(removableIds.prefix(1)),
                idempotencyKey: UUID().uuidString
            )
        )
        XCTAssertEqual(render.roomId, room.roomId)
        XCTAssertTrue(render.status == .queued || render.status == .running)

        let finalRender = try await pollUntilFinished(client: client, renderId: render.renderId)
        XCTAssertEqual(finalRender.status, .done, "the fake image backend should always succeed")
        XCTAssertNotNil(finalRender.beforeUrl)
        XCTAssertNotNil(finalRender.afterUrl)
        XCTAssertNotNil(finalRender.preservationRate)

        try await client.deleteRoom(roomId: room.roomId)
    }

    func testRealHEICPhotoConvertsAndUploadsSuccessfully() async throws {
        // The full client-side path an iPhone photo actually takes: HEIC bytes from
        // the picker -> PhotoFormatConverter -> upload. Confirms the server accepts
        // what the converter produces, not just that ImageIO can decode it.
        let (client, _) = try await makeSignedInClient()
        let room = try await client.createRoom(label: nil)

        let heicData = try fixture("IMG_1519.HEIC")
        let jpegData = try PhotoFormatConverter.convertToAcceptedFormatIfNeeded(heicData)
        XCTAssertTrue(PhotoValidation.isWithinSizeLimit(jpegData))

        let photo = try await client.uploadPhoto(
            roomId: room.roomId,
            data: jpegData,
            filename: "photo.jpg",
            mimeType: "image/jpeg"
        )
        XCTAssertEqual(photo.roomId, room.roomId)
        XCTAssertGreaterThan(photo.width, 0)
    }

    func testCreateInventoryWithoutAPhotoReturnsNoPhotos() async throws {
        let (client, _) = try await makeSignedInClient()
        let room = try await client.createRoom(label: nil)

        do {
            _ = try await client.createInventory(roomId: room.roomId)
            XCTFail("expected no_photos")
        } catch let error as ApiError {
            XCTAssertEqual(error.code, .noPhotos)
        }
    }

    func testGetRenderWithUnknownIdReturnsNotFound() async throws {
        let (client, _) = try await makeSignedInClient()

        do {
            _ = try await client.getRender(renderId: "not-a-real-render-id")
            XCTFail("expected not_found")
        } catch let error as ApiError {
            XCTAssertEqual(error.code, .notFound)
        }
    }

    func testRenderCreationIdempotencyKeyReturnsTheSameRenderOnRetry() async throws {
        let (client, _) = try await makeSignedInClient()
        let room = try await client.createRoom(label: nil)
        let photoData = try fixture("room.jpg")
        _ = try await client.uploadPhoto(roomId: room.roomId, data: photoData, filename: "room.jpg", mimeType: "image/jpeg")
        _ = try await client.createInventory(roomId: room.roomId)

        let key = UUID().uuidString
        let body = RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: key)
        let first = try await client.createRender(roomId: room.roomId, body: body)
        let second = try await client.createRender(roomId: room.roomId, body: body)

        XCTAssertEqual(first.renderId, second.renderId, "same idempotency key must not spend a second credit")
    }

    private func pollUntilFinished(client: APIClient, renderId: String, timeout: TimeInterval = 30) async throws -> Render {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            let render = try await client.getRender(renderId: renderId)
            if render.status == .done || render.status == .failed {
                return render
            }
            try await Task.sleep(nanoseconds: 500_000_000)
        }
        XCTFail("render did not finish within \(timeout)s")
        return try await client.getRender(renderId: renderId)
    }
}
