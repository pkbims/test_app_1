import Foundation

/// One render's lifecycle (PRD F5 — "the polling and retry logic is where client
/// bugs will live"). Submits (or resumes) a render, then polls `GET /v1/renders/{id}`
/// every `pollInterval` until the *server* says the render is `done` or `failed`.
///
/// An `actor` so the polling loop's state mutations can't race a caller reading
/// `state` or calling `cancel()` from elsewhere.
public actor RenderStateMachine {
    /// Mirrors `RenderStatus` plus the client-only states around it. `.renderFailed`
    /// (the server finished and said `failed` — a business outcome, refund included)
    /// is kept distinct from `.requestFailed` (our own request to submit or poll
    /// broke) because the edge-state screen reads very differently for each: one
    /// shows `Render.errorCode`/`missingItems`, the other a generic retry.
    public enum State: Equatable, Sendable {
        case idle
        case submitting
        case polling(Render)
        case done(Render)
        case renderFailed(Render)
        case requestFailed(RequestFailure)
    }

    public enum RequestFailure: Error, Equatable, Sendable {
        case signedOut
        case api(ApiError)
        /// Catch-all for a decoding error or a `URLError` that exhausted
        /// `APIClient`'s own retry budget — `String(describing:)` because most
        /// `Error`s aren't `Equatable`.
        case other(String)
    }

    private let client: APIClient
    private let pollInterval: TimeInterval
    private let sleep: @Sendable (TimeInterval) async -> Void
    private var pollingTask: Task<Void, Never>?
    private var onChangeHandler: (@Sendable (State) async -> Void)?

    public private(set) var state: State = .idle

    public init(
        client: APIClient,
        pollInterval: TimeInterval = 2.0,
        sleep: @escaping @Sendable (TimeInterval) async -> Void = { seconds in
            try? await Task.sleep(nanoseconds: UInt64(max(0, seconds) * 1_000_000_000))
        }
    ) {
        self.client = client
        self.pollInterval = pollInterval
        self.sleep = sleep
    }

    /// Called on every state transition. One handler — this is a per-render machine
    /// owned by one view model, not a general pub/sub.
    public func onChange(_ handler: @escaping @Sendable (State) async -> Void) {
        onChangeHandler = handler
    }

    /// `POST /v1/rooms/{id}/renders`, then poll until finished.
    public func start(roomId: String, body: RenderCreate) async {
        pollingTask?.cancel()
        await setState(.submitting)
        do {
            let render = try await client.createRender(roomId: roomId, body: body)
            await apply(render, startPollingIfPending: true)
        } catch {
            await setState(.requestFailed(Self.classify(error)))
        }
    }

    /// Picks up an already-submitted render by id (app relaunched mid-render, or the
    /// user retried after a `.requestFailed`) — no new render is created.
    public func resumePolling(renderId: String) async {
        pollingTask?.cancel()
        do {
            let render = try await client.getRender(renderId: renderId)
            await apply(render, startPollingIfPending: true)
        } catch {
            await setState(.requestFailed(Self.classify(error)))
        }
    }

    /// Stops polling without changing `state` — e.g. the Compare screen was dismissed
    /// mid-render. A later `resumePolling` picks the same render back up.
    public func cancel() {
        pollingTask?.cancel()
        pollingTask = nil
    }

    private func apply(_ render: Render, startPollingIfPending: Bool) async {
        switch render.status {
        case .queued, .running:
            await setState(.polling(render))
            if startPollingIfPending {
                schedulePolling(renderId: render.renderId)
            }
        case .done:
            await setState(.done(render))
        case .failed:
            await setState(.renderFailed(render))
        }
    }

    /// Runs on a detached loop that only calls back into the actor per tick — `apply`
    /// here always passes `startPollingIfPending: false` so a still-pending result
    /// doesn't spawn a second concurrent loop; this same `while` keeps ticking until
    /// a terminal state is reached.
    private func schedulePolling(renderId: String) {
        let interval = pollInterval
        let sleepFn = sleep
        pollingTask = Task { [weak self] in
            while !Task.isCancelled {
                await sleepFn(interval)
                if Task.isCancelled { return }
                guard let self else { return }
                let shouldContinue = await self.tick(renderId: renderId)
                if !shouldContinue { return }
            }
        }
    }

    /// - Returns: whether the loop should keep polling.
    private func tick(renderId: String) async -> Bool {
        do {
            let render = try await client.getRender(renderId: renderId)
            await apply(render, startPollingIfPending: false)
            if case .polling = state { return true }
            return false
        } catch {
            await setState(.requestFailed(Self.classify(error)))
            return false
        }
    }

    private func setState(_ newState: State) async {
        state = newState
        await onChangeHandler?(newState)
    }

    private static func classify(_ error: Error) -> RequestFailure {
        if case APIClientError.signedOut = error {
            return .signedOut
        }
        if let apiError = error as? ApiError {
            return .api(apiError)
        }
        return .other(String(describing: error))
    }
}
