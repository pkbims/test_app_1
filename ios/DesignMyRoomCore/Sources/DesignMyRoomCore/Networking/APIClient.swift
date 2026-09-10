import Foundation

/// Hand-written `URLSession` + `async/await` client for every `/v1/...` operation in
/// `contract/openapi.json` (PRD F4 — no generated client, no third-party dependency).
///
/// An `actor` so token refresh can't race itself: two calls that both hit
/// `401 token_expired` at once share one in-flight refresh instead of each starting
/// their own (see `refreshCoalesced`).
public actor APIClient {
    public struct Configuration: Sendable {
        public var baseURL: URL
        public var transport: HTTPTransport
        public var tokenStore: TokenStore
        public var retryPolicy: RetryPolicy
        /// Injectable so tests don't wait out real backoff delays.
        public var sleep: @Sendable (TimeInterval) async -> Void
        /// Injectable so multipart tests can assert on an exact body.
        public var boundaryGenerator: @Sendable () -> String

        public init(
            baseURL: URL = URL(string: "http://localhost:8000")!,
            transport: HTTPTransport = URLSessionTransport(),
            tokenStore: TokenStore,
            retryPolicy: RetryPolicy = .default,
            sleep: @escaping @Sendable (TimeInterval) async -> Void = { seconds in
                try? await Task.sleep(nanoseconds: UInt64(max(0, seconds) * 1_000_000_000))
            },
            boundaryGenerator: @escaping @Sendable () -> String = { "Boundary-\(UUID().uuidString)" }
        ) {
            self.baseURL = baseURL
            self.transport = transport
            self.tokenStore = tokenStore
            self.retryPolicy = retryPolicy
            self.sleep = sleep
            self.boundaryGenerator = boundaryGenerator
        }
    }

    private let config: Configuration
    private var refreshTask: Task<Void, Error>?

    public init(configuration: Configuration) {
        self.config = configuration
    }

    // MARK: - Auth

    /// `POST /v1/auth/apple`. No `Authorization` header — there's no session yet.
    /// Persists the returned tokens before handing them back.
    public func signInWithApple(identityToken: String) async throws -> Tokens {
        let request = try jsonRequest(path: "v1/auth/apple", method: "POST", body: AppleSignIn(identityToken: identityToken))
        let (data, response) = try await send(request, authorized: false, idempotent: false)
        let tokens: Tokens = try decodeOrThrow(data, response)
        await config.tokenStore.save(tokens: tokens)
        return tokens
    }

    /// Attempts to restore a session from a stored refresh token at app launch. The
    /// access token is in-memory only, so it's always nil right after a cold launch
    /// even when a refresh token survived in the Keychain — and a request sent with
    /// no `Authorization` header comes back `401 apple_token_invalid` (a *missing*
    /// token, not an aged-out one), which the 401-triggered refresh dance
    /// deliberately doesn't treat as refreshable. So this is its own explicit path,
    /// reusing the same refresh mechanics. Never throws: "no session yet" is a normal
    /// outcome at launch, not an error worth propagating.
    public func restoreSession() async -> Bool {
        guard await config.tokenStore.refreshToken() != nil else { return false }
        do {
            try await performRefresh()
            return true
        } catch {
            return false
        }
    }

    public func me() async throws -> Me {
        let request = plainRequest(path: "v1/me", method: "GET")
        let (data, response) = try await send(request, authorized: true, idempotent: true)
        return try decodeOrThrow(data, response)
    }

    // MARK: - Rooms

    /// Not idempotent — retrying blindly would create a second room.
    public func createRoom(label: String?) async throws -> Room {
        let request = try jsonRequest(path: "v1/rooms", method: "POST", body: RoomCreate(label: label))
        let (data, response) = try await send(request, authorized: true, idempotent: false)
        return try decodeOrThrow(data, response)
    }

    public func deleteRoom(roomId: String) async throws {
        let request = plainRequest(path: "v1/rooms/\(roomId)", method: "DELETE")
        let (data, response) = try await send(request, authorized: true, idempotent: true)
        guard response.statusCode == 204 else {
            try throwDecodedError(data, response)
        }
    }

    /// The user's own rooms, most recent first — powers the home/history screen.
    public func listRooms() async throws -> [Room] {
        let request = plainRequest(path: "v1/rooms", method: "GET")
        let (data, response) = try await send(request, authorized: true, idempotent: true)
        return try decodeOrThrow(data, response)
    }

    /// Not idempotent — a second call would re-upload over "one photo per room".
    public func uploadPhoto(roomId: String, data imageData: Data, filename: String, mimeType: String) async throws -> Photo {
        let boundary = config.boundaryGenerator()
        var request = plainRequest(path: "v1/rooms/\(roomId)/photos", method: "POST")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = Self.multipartBody(fileData: imageData, filename: filename, mimeType: mimeType, boundary: boundary)
        let (data, response) = try await send(request, authorized: true, idempotent: false)
        return try decodeOrThrow(data, response)
    }

    // MARK: - Inventory

    /// Not idempotent (a second vision call would cost again); `getInventory` is the
    /// idempotent way to re-read the same result.
    public func createInventory(roomId: String) async throws -> Inventory {
        let request = plainRequest(path: "v1/rooms/\(roomId)/inventory", method: "POST")
        let (data, response) = try await send(request, authorized: true, idempotent: false)
        return try decodeOrThrow(data, response)
    }

    public func getInventory(roomId: String) async throws -> Inventory {
        let request = plainRequest(path: "v1/rooms/\(roomId)/inventory", method: "GET")
        let (data, response) = try await send(request, authorized: true, idempotent: true)
        return try decodeOrThrow(data, response)
    }

    // MARK: - Renders

    /// Idempotent *because* `RenderCreate.idempotencyKey` makes a retry safe: per the
    /// contract, "a retry with the same key returns the existing render rather than
    /// spending a second credit."
    public func createRender(roomId: String, body: RenderCreate) async throws -> Render {
        let request = try jsonRequest(path: "v1/rooms/\(roomId)/renders", method: "POST", body: body)
        let (data, response) = try await send(request, authorized: true, idempotent: true)
        return try decodeOrThrow(data, response)
    }

    public func listRenders(roomId: String) async throws -> [Render] {
        let request = plainRequest(path: "v1/rooms/\(roomId)/renders", method: "GET")
        let (data, response) = try await send(request, authorized: true, idempotent: true)
        return try decodeOrThrow(data, response)
    }

    /// Polled every 2s by `RenderStateMachine`.
    public func getRender(renderId: String) async throws -> Render {
        let request = plainRequest(path: "v1/renders/\(renderId)", method: "GET")
        let (data, response) = try await send(request, authorized: true, idempotent: true)
        return try decodeOrThrow(data, response)
    }

    // MARK: - Request building

    private func jsonRequest(path: String, method: String, body: some Encodable) throws -> URLRequest {
        var request = plainRequest(path: path, method: method)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONCoding.encoder.encode(body)
        return request
    }

    private func plainRequest(path: String, method: String) -> URLRequest {
        var request = URLRequest(url: config.baseURL.appendingPathComponent(path))
        request.httpMethod = method
        return request
    }

    private static func multipartBody(fileData: Data, filename: String, mimeType: String, boundary: String) -> Data {
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append(
            "Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n"
                .data(using: .utf8)!
        )
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        return body
    }

    // MARK: - Sending, with retry/backoff and the silent-refresh dance

    /// `authorized` requests get a fresh `Authorization` header from the token store
    /// on every attempt (including the retry after a refresh). `idempotent` requests
    /// get `RetryPolicy`'s backoff on transient failures; non-idempotent ones don't,
    /// because a lost response after a non-idempotent request going through server-side
    /// means retrying could double it up.
    private func send(_ request: URLRequest, authorized: Bool, idempotent: Bool) async throws -> (Data, HTTPURLResponse) {
        try await sendInternal(request, authorized: authorized, idempotent: idempotent, allowRefresh: authorized)
    }

    private func sendInternal(
        _ request: URLRequest,
        authorized: Bool,
        idempotent: Bool,
        allowRefresh: Bool
    ) async throws -> (Data, HTTPURLResponse) {
        var attempt = 1
        while true {
            var attemptRequest = request
            if authorized, let token = await config.tokenStore.accessToken() {
                attemptRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }

            do {
                let (data, response) = try await config.transport.send(attemptRequest)

                if allowRefresh, response.statusCode == 401,
                   let apiError = try? JSONCoding.decoder.decode(ApiError.self, from: data),
                   apiError.code == .tokenExpired {
                    try await refreshCoalesced()
                    return try await sendInternal(request, authorized: authorized, idempotent: idempotent, allowRefresh: false)
                }

                if idempotent, config.retryPolicy.shouldRetry(afterStatus: response.statusCode), attempt < config.retryPolicy.maxAttempts {
                    await config.sleep(config.retryPolicy.delay(beforeAttempt: attempt))
                    attempt += 1
                    continue
                }

                return (data, response)
            } catch {
                if idempotent, config.retryPolicy.shouldRetry(after: error), attempt < config.retryPolicy.maxAttempts {
                    await config.sleep(config.retryPolicy.delay(beforeAttempt: attempt))
                    attempt += 1
                    continue
                }
                throw error
            }
        }
    }

    /// Concurrent callers that both see `token_expired` share one refresh instead of
    /// each firing their own — actor isolation makes this safe without extra locking.
    private func refreshCoalesced() async throws {
        if let existing = refreshTask {
            return try await existing.value
        }
        let task = Task { try await performRefresh() }
        refreshTask = task
        defer { refreshTask = nil }
        try await task.value
    }

    private func performRefresh() async throws {
        guard let refreshToken = await config.tokenStore.refreshToken() else {
            await config.tokenStore.clear()
            throw APIClientError.signedOut
        }

        let request = try jsonRequest(path: "v1/auth/refresh", method: "POST", body: RefreshRequest(refreshToken: refreshToken))

        let data: Data
        let response: HTTPURLResponse
        do {
            (data, response) = try await sendInternal(request, authorized: false, idempotent: false, allowRefresh: false)
        } catch {
            await config.tokenStore.clear()
            throw APIClientError.signedOut
        }

        guard (200..<300).contains(response.statusCode) else {
            await config.tokenStore.clear()
            throw APIClientError.signedOut
        }

        let tokens = try JSONCoding.decoder.decode(Tokens.self, from: data)
        await config.tokenStore.save(tokens: tokens)
    }

    // MARK: - Response decoding

    private func decodeOrThrow<T: Decodable>(_ data: Data, _ response: HTTPURLResponse) throws -> T {
        if (200..<300).contains(response.statusCode) {
            return try JSONCoding.decoder.decode(T.self, from: data)
        }
        try throwDecodedError(data, response)
    }

    private func throwDecodedError(_ data: Data, _ response: HTTPURLResponse) throws -> Never {
        if let apiError = try? JSONCoding.decoder.decode(ApiError.self, from: data) {
            throw apiError
        }
        if response.statusCode == 422, let validation = try? JSONCoding.decoder.decode(HTTPValidationError.self, from: data) {
            throw APIClientError.validation(validation)
        }
        throw APIClientError.unrecognizedResponse(status: response.statusCode)
    }
}
