import XCTest
@testable import DesignMyRoomCore

final class APIClientTests: XCTestCase {

    private func makeClient(
        transport: MockTransport,
        tokenStore: TokenStore = InMemoryTokenStore(access: "initial-access", refresh: "initial-refresh"),
        retryPolicy: RetryPolicy = RetryPolicy(maxAttempts: 3, baseDelay: 0, maxDelay: 0)
    ) -> APIClient {
        APIClient(configuration: .init(
            baseURL: URL(string: "http://localhost:8000")!,
            transport: transport,
            tokenStore: tokenStore,
            retryPolicy: retryPolicy,
            sleep: { _ in } // no real waiting in tests
        ))
    }

    // MARK: - Happy path + auth header

    func testMeSendsAuthorizationHeaderAndDecodesResult() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 200, json: #"{"user_id":"u_1","credits_left":2}"#)
        let client = makeClient(transport: transport)

        let me = try await client.me()

        XCTAssertEqual(me.userId, "u_1")
        XCTAssertEqual(me.creditsLeft, 2)
        let request = await transport.recordedRequests[0]
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer initial-access")
        XCTAssertEqual(request.url?.path, "/v1/me")
        XCTAssertEqual(request.httpMethod, "GET")
    }

    func testSignInWithAppleDoesNotSendAuthorizationHeader() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 200, json: #"{"access_token":"a","refresh_token":"r","expires_in":900}"#)
        let tokenStore = InMemoryTokenStore()
        let client = makeClient(transport: transport, tokenStore: tokenStore)

        let tokens = try await client.signInWithApple(identityToken: "apple-identity-token")

        XCTAssertEqual(tokens.accessToken, "a")
        let request = await transport.recordedRequests[0]
        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
        XCTAssertEqual(request.url?.path, "/v1/auth/apple")
        XCTAssertEqual(request.httpMethod, "POST")

        // Signing in must persist the tokens for subsequent calls.
        let storedAccess = await tokenStore.accessToken()
        XCTAssertEqual(storedAccess, "a")
    }

    // MARK: - Token refresh on 401 token_expired

    func testTokenExpiredTriggersOneSilentRefreshThenRetriesOriginalRequest() async throws {
        let transport = MockTransport()
        // 1st attempt at GET /v1/me: expired.
        await transport.enqueueJSON(status: 401, json: #"{"code":"token_expired","message":"Session expired."}"#)
        // Refresh call: succeeds with a new access token.
        await transport.enqueueJSON(status: 200, json: #"{"access_token":"new-access","refresh_token":"new-refresh","expires_in":900}"#)
        // Retried GET /v1/me: succeeds.
        await transport.enqueueJSON(status: 200, json: #"{"user_id":"u_1","credits_left":5}"#)

        let tokenStore = InMemoryTokenStore(access: "stale-access", refresh: "still-valid-refresh")
        let client = makeClient(transport: transport, tokenStore: tokenStore)

        let me = try await client.me()

        XCTAssertEqual(me.creditsLeft, 5)
        let requests = await transport.recordedRequests
        XCTAssertEqual(requests.count, 3, "original + refresh + retry")
        XCTAssertEqual(requests[0].value(forHTTPHeaderField: "Authorization"), "Bearer stale-access")
        XCTAssertEqual(requests[1].url?.path, "/v1/auth/refresh")
        XCTAssertEqual(requests[2].value(forHTTPHeaderField: "Authorization"), "Bearer new-access", "retry must use the refreshed token")

        let storedAccess = await tokenStore.accessToken()
        XCTAssertEqual(storedAccess, "new-access")
    }

    func testRefreshFailureSignsOutAndClearsTokens() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 401, json: #"{"code":"token_expired","message":"Session expired."}"#)
        await transport.enqueueJSON(status: 401, json: #"{"code":"apple_token_invalid","message":"Refresh token invalid."}"#)

        let tokenStore = InMemoryTokenStore(access: "stale-access", refresh: "revoked-refresh")
        let client = makeClient(transport: transport, tokenStore: tokenStore)

        do {
            _ = try await client.me()
            XCTFail("expected signedOut")
        } catch APIClientError.signedOut {
            // expected
        }

        let clearCount = await tokenStore.clearCallCount
        XCTAssertEqual(clearCount, 1)
    }

    func testNoRefreshTokenStoredSignsOutImmediatelyWithoutCallingRefreshEndpoint() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 401, json: #"{"code":"token_expired","message":"Session expired."}"#)

        let tokenStore = InMemoryTokenStore(access: "stale-access", refresh: nil)
        let client = makeClient(transport: transport, tokenStore: tokenStore)

        do {
            _ = try await client.me()
            XCTFail("expected signedOut")
        } catch APIClientError.signedOut {
            // expected
        }

        let requests = await transport.recordedRequests
        XCTAssertEqual(requests.count, 1, "no refresh call was possible")
    }

    func test401WithOtherCodeDoesNotTriggerRefresh() async throws {
        // apple_token_invalid on a /v1/me call would be unusual, but the refresh dance
        // must only fire for token_expired specifically.
        let transport = MockTransport()
        await transport.enqueueJSON(status: 401, json: #"{"code":"apple_token_invalid","message":"nope"}"#)
        let client = makeClient(transport: transport)

        do {
            _ = try await client.me()
            XCTFail("expected ApiError")
        } catch let error as ApiError {
            XCTAssertEqual(error.code, .appleTokenInvalid)
        }

        let requests = await transport.recordedRequests
        XCTAssertEqual(requests.count, 1)
    }

    // MARK: - Retry / backoff on transient failures

    func testIdempotentGetRetriesTransientNetworkErrorThenSucceeds() async throws {
        let transport = MockTransport()
        await transport.enqueue(.failure(URLError(.networkConnectionLost)))
        await transport.enqueueJSON(status: 200, json: #"{"user_id":"u_1","credits_left":1}"#)
        let client = makeClient(transport: transport, retryPolicy: RetryPolicy(maxAttempts: 3, baseDelay: 0, maxDelay: 0))

        let me = try await client.me()

        XCTAssertEqual(me.creditsLeft, 1)
        let count = await transport.requestCount
        XCTAssertEqual(count, 2)
    }

    func testIdempotentGetGivesUpAfterMaxAttempts() async throws {
        let transport = MockTransport()
        await transport.enqueue(.failure(URLError(.networkConnectionLost)))
        await transport.enqueue(.failure(URLError(.networkConnectionLost)))
        await transport.enqueue(.failure(URLError(.networkConnectionLost)))
        let client = makeClient(transport: transport, retryPolicy: RetryPolicy(maxAttempts: 3, baseDelay: 0, maxDelay: 0))

        do {
            _ = try await client.me()
            XCTFail("expected URLError")
        } catch is URLError {
            // expected
        }

        let count = await transport.requestCount
        XCTAssertEqual(count, 3, "exactly maxAttempts tries, no more")
    }

    func testServiceUnavailableIsRetriedForIdempotentRequests() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 503, json: #"{"code":"no_credits","message":"ignored body on 503"}"#)
        await transport.enqueueJSON(status: 200, json: #"{"user_id":"u_1","credits_left":1}"#)
        let client = makeClient(transport: transport, retryPolicy: RetryPolicy(maxAttempts: 3, baseDelay: 0, maxDelay: 0))

        let me = try await client.me()
        XCTAssertEqual(me.creditsLeft, 1)
        let count = await transport.requestCount
        XCTAssertEqual(count, 2)
    }

    func testNonIdempotentPostDoesNotAutoRetryOnTransientNetworkError() async throws {
        // Room creation isn't idempotent — retrying blindly could create two rooms.
        let transport = MockTransport()
        await transport.enqueue(.failure(URLError(.networkConnectionLost)))
        let client = makeClient(transport: transport)

        do {
            _ = try await client.createRoom(label: "Living room")
            XCTFail("expected URLError")
        } catch is URLError {
            // expected
        }

        let count = await transport.requestCount
        XCTAssertEqual(count, 1, "no retry for a non-idempotent request")
    }

    func testRenderCreationIsRetriedBecauseItCarriesAnIdempotencyKey() async throws {
        let transport = MockTransport()
        await transport.enqueue(.failure(URLError(.networkConnectionLost)))
        await transport.enqueueJSON(status: 202, json: """
        {"render_id":"rd_1","room_id":"rm_1","status":"queued","style":"scandi","remove_ids":[],
         "before_url":null,"after_url":null,"preservation_rate":null,"missing_items":null,
         "error_code":null,"created_at":"2026-09-09T20:20:00Z","credits_left":1}
        """)
        let client = makeClient(transport: transport, retryPolicy: RetryPolicy(maxAttempts: 3, baseDelay: 0, maxDelay: 0))

        let render = try await client.createRender(
            roomId: "rm_1",
            body: RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "key-1")
        )

        XCTAssertEqual(render.status, .queued)
        let count = await transport.requestCount
        XCTAssertEqual(count, 2)
    }

    func test500IsNotRetried() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 500, json: #"{"code":"render_failed","message":"boom"}"#)
        let client = makeClient(transport: transport)

        do {
            _ = try await client.me()
            XCTFail("expected ApiError")
        } catch let error as ApiError {
            XCTAssertEqual(error.code, .renderFailed)
        }

        let count = await transport.requestCount
        XCTAssertEqual(count, 1, "a 500 is a real answer, not retried")
    }

    // MARK: - Error decoding

    func testNotFoundDecodesToApiErrorRegardlessOfWhichPathIdCall() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 404, json: #"{"code":"not_found","message":"Not found."}"#)
        let client = makeClient(transport: transport)

        do {
            _ = try await client.getRender(renderId: "does-not-exist")
            XCTFail("expected ApiError")
        } catch let error as ApiError {
            XCTAssertEqual(error.code, .notFound)
        }
    }

    func testMalformedErrorBodyDoesNotCrashAndSurfacesAsClientError() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 500, json: "not even json")
        let client = makeClient(transport: transport)

        do {
            _ = try await client.me()
            XCTFail("expected an error")
        } catch let error as APIClientError {
            if case .unrecognizedResponse(status: 500) = error {
                // expected
            } else {
                XCTFail("wrong APIClientError case: \(error)")
            }
        }
    }

    func testValidationErrorDecodesDistinctlyFromApiError() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 422, json: """
        {"detail":[{"loc":["body","style"],"msg":"field required","type":"missing"}]}
        """)
        let client = makeClient(transport: transport)

        do {
            _ = try await client.createRender(
                roomId: "rm_1",
                body: RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "k")
            )
            XCTFail("expected validation error")
        } catch let error as APIClientError {
            if case .validation(let detail) = error {
                XCTAssertEqual(detail.detail.first?.msg, "field required")
            } else {
                XCTFail("wrong APIClientError case: \(error)")
            }
        }
    }

    // MARK: - Multipart photo upload

    func testUploadPhotoBuildsMultipartRequest() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 200, json: """
        {"photo_id":"ph_1","room_id":"rm_1","width":100,"height":200,"url":"https://x/photos/ph_1"}
        """)
        let client = makeClient(transport: transport)
        let imageBytes = Data([0xFF, 0xD8, 0xFF, 0xD9]) // minimal JPEG-ish bytes, content is opaque here

        let photo = try await client.uploadPhoto(
            roomId: "rm_1",
            data: imageBytes,
            filename: "room.jpg",
            mimeType: "image/jpeg"
        )

        XCTAssertEqual(photo.photoId, "ph_1")
        let request = await transport.recordedRequests[0]
        XCTAssertEqual(request.url?.path, "/v1/rooms/rm_1/photos")
        XCTAssertEqual(request.httpMethod, "POST")
        let contentType = request.value(forHTTPHeaderField: "Content-Type") ?? ""
        XCTAssertTrue(contentType.hasPrefix("multipart/form-data; boundary="))
        let boundary = String(contentType.dropFirst("multipart/form-data; boundary=".count))

        let body = request.httpBodyFromStreamOrData()
        let bodyString = String(decoding: body, as: UTF8.self)
        XCTAssertTrue(bodyString.contains("--\(boundary)"))
        XCTAssertTrue(bodyString.contains("Content-Disposition: form-data; name=\"file\"; filename=\"room.jpg\""))
        XCTAssertTrue(bodyString.contains("Content-Type: image/jpeg"))
        XCTAssertTrue(body.contains(imageBytes))
    }

    // MARK: - 204 No Content

    func testDeleteRoomSucceedsOn204WithNoBody() async throws {
        let transport = MockTransport()
        await transport.enqueue(.success(status: 204, body: Data()))
        let client = makeClient(transport: transport)

        try await client.deleteRoom(roomId: "rm_1")

        let request = await transport.recordedRequests[0]
        XCTAssertEqual(request.httpMethod, "DELETE")
        XCTAssertEqual(request.url?.path, "/v1/rooms/rm_1")
    }

    // MARK: - restoreSession (app cold launch)
    //
    // The access token is in-memory only, so it's always nil right after launch even
    // when a refresh token survived in the Keychain. A request sent with no
    // Authorization header at all comes back `401 apple_token_invalid` (missing token
    // is a different case from an aged-out one — see middleware.py), which the
    // 401-triggered refresh dance deliberately does NOT treat as refreshable. So
    // restoring a session at launch needs its own explicit path.

    func testRestoreSessionWithNoStoredRefreshTokenReturnsFalseWithoutAnyRequest() async {
        let transport = MockTransport()
        let tokenStore = InMemoryTokenStore(access: nil, refresh: nil)
        let client = makeClient(transport: transport, tokenStore: tokenStore)

        let restored = await client.restoreSession()

        XCTAssertFalse(restored)
        let count = await transport.requestCount
        XCTAssertEqual(count, 0)
    }

    func testRestoreSessionWithValidRefreshTokenSucceeds() async {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 200, json: #"{"access_token":"fresh-access","refresh_token":"fresh-refresh","expires_in":900}"#)
        let tokenStore = InMemoryTokenStore(access: nil, refresh: "surviving-refresh")
        let client = makeClient(transport: transport, tokenStore: tokenStore)

        let restored = await client.restoreSession()

        XCTAssertTrue(restored)
        let request = await transport.recordedRequests[0]
        XCTAssertEqual(request.url?.path, "/v1/auth/refresh")
        let storedAccess = await tokenStore.accessToken()
        XCTAssertEqual(storedAccess, "fresh-access")
    }

    func testRestoreSessionWithRevokedRefreshTokenFailsAndClears() async {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 401, json: #"{"code":"apple_token_invalid","message":"nope"}"#)
        let tokenStore = InMemoryTokenStore(access: nil, refresh: "revoked-refresh")
        let client = makeClient(transport: transport, tokenStore: tokenStore)

        let restored = await client.restoreSession()

        XCTAssertFalse(restored)
        let clearCount = await tokenStore.clearCallCount
        XCTAssertEqual(clearCount, 1)
    }
}

private extension URLRequest {
    /// Tests build requests with `httpBody`, never `httpBodyStream`, so this is a
    /// convenience, not a general-purpose reader.
    func httpBodyFromStreamOrData() -> Data {
        httpBody ?? Data()
    }
}

private extension Data {
    func contains(_ other: Data) -> Bool {
        guard !other.isEmpty else { return true }
        guard count >= other.count else { return false }
        for i in 0...(count - other.count) {
            if self[self.index(startIndex, offsetBy: i)..<self.index(startIndex, offsetBy: i + other.count)] == other {
                return true
            }
        }
        return false
    }
}
