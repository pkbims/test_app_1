import XCTest
@testable import DesignMyRoomCore

/// The per-render state machine (PRD F5 — "the polling and retry logic is where
/// client bugs will live"). Uses a real `APIClient` over `MockTransport` so these
/// tests exercise the exact same decoding/error path production traffic does, with
/// `sleep` faked to instant so the polling loop runs at test speed.
final class RenderStateMachineTests: XCTestCase {

    /// A small *real* delay between polls (not zero) so a test that calls `cancel()`
    /// from the main test task has a deterministic window to act before the next
    /// tick fires — with a zero delay the two concurrently-running tasks race.
    private static let pollTickDelayNanos: UInt64 = 20_000_000 // 20ms

    private func makeMachine(transport: MockTransport) -> RenderStateMachine {
        let client = APIClient(configuration: .init(
            transport: transport,
            tokenStore: InMemoryTokenStore(access: "a", refresh: "r"),
            retryPolicy: RetryPolicy(maxAttempts: 1, baseDelay: 0, maxDelay: 0),
            sleep: { _ in }
        ))
        return RenderStateMachine(client: client, pollInterval: 0, sleep: { _ in
            try? await Task.sleep(nanoseconds: Self.pollTickDelayNanos)
        })
    }

    private func renderJSON(
        status: String,
        id: String = "rd_1",
        beforeUrl: String? = nil,
        afterUrl: String? = nil,
        preservationRate: Double? = nil,
        missingItems: [String]? = nil,
        errorCode: String? = nil
    ) -> String {
        func str(_ value: String?) -> String { value.map { "\"\($0)\"" } ?? "null" }
        func num(_ value: Double?) -> String { value.map { String($0) } ?? "null" }
        func strArray(_ value: [String]?) -> String {
            guard let value else { return "null" }
            return "[" + value.map { "\"\($0)\"" }.joined(separator: ",") + "]"
        }
        return """
        {"render_id":"\(id)","room_id":"rm_1","status":"\(status)","style":"scandi","remove_ids":[],
         "before_url":\(str(beforeUrl)),"after_url":\(str(afterUrl)),"preservation_rate":\(num(preservationRate)),
         "missing_items":\(strArray(missingItems)),"error_code":\(str(errorCode)),
         "created_at":"2026-09-09T20:20:00Z","credits_left":1}
        """
    }

    /// Collects `onChange` callbacks off the actor safely (an actor, not a captured
    /// `var`, so this doesn't race the state machine's background polling task).
    private actor StateCollector {
        private(set) var states: [RenderStateMachine.State] = []
        private var expectation: XCTestExpectation?
        private var target = Int.max

        func awaitCount(_ count: Int) -> XCTestExpectation {
            target = count
            let expectation = XCTestExpectation(description: "collected \(count) states")
            self.expectation = states.count >= count ? nil : expectation
            if states.count >= count {
                expectation.fulfill()
            }
            return expectation
        }

        func record(_ state: RenderStateMachine.State) {
            states.append(state)
            if states.count >= target {
                expectation?.fulfill()
                expectation = nil
            }
        }
    }

    /// Registers the collector *and waits for that registration to land* before
    /// returning — the caller must do this before triggering `start`/`resumePolling`.
    /// (An earlier version raced `onChange` registration against `start()` from two
    /// separate tasks via `async let`; actor method ordering across unrelated tasks
    /// isn't guaranteed by program order, so early state transitions were sometimes
    /// dropped. Registering first, sequentially, in the same task removes the race.)
    private func makeCollector(on machine: RenderStateMachine) async -> StateCollector {
        let collector = StateCollector()
        await machine.onChange { state in
            await collector.record(state)
        }
        return collector
    }

    private func waitForStates(_ collector: StateCollector, count: Int) async -> [RenderStateMachine.State] {
        let expectation = await collector.awaitCount(count)
        await fulfillment(of: [expectation], timeout: 5)
        return await collector.states
    }

    func testInitialStateIsIdle() async {
        let machine = makeMachine(transport: MockTransport())
        let state = await machine.state
        XCTAssertEqual(state, .idle)
    }

    func testStartTransitionsThroughSubmittingToPolling() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 202, json: renderJSON(status: "queued"))
        let machine = makeMachine(transport: transport)

        let collector = await makeCollector(on: machine)
        await machine.start(roomId: "rm_1", body: RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "k"))
        let collected = await waitForStates(collector, count: 2) // submitting, polling
        await machine.cancel() // stop the loop before it polls again with an empty queue

        XCTAssertEqual(collected[0], .submitting)
        guard case .polling(let render) = collected[1] else {
            return XCTFail("expected .polling, got \(collected[1])")
        }
        XCTAssertEqual(render.status, .queued)
    }

    func testPollsUntilDone() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 202, json: renderJSON(status: "queued"))
        await transport.enqueueJSON(status: 200, json: renderJSON(status: "queued"))
        await transport.enqueueJSON(status: 200, json: renderJSON(status: "running"))
        await transport.enqueueJSON(status: 200, json: renderJSON(
            status: "done",
            beforeUrl: "https://x/b", afterUrl: "https://x/a", preservationRate: 0.95
        ))
        let machine = makeMachine(transport: transport)

        let collector = await makeCollector(on: machine)
        await machine.start(roomId: "rm_1", body: RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "k"))
        // submitting, polling(queued from create), polling(queued), polling(running), done
        let collected = await waitForStates(collector, count: 5)

        guard case .done(let render) = collected.last else {
            return XCTFail("expected final state .done, got \(String(describing: collected.last))")
        }
        XCTAssertEqual(render.preservationRate, 0.95)

        let requestCount = await transport.requestCount
        XCTAssertEqual(requestCount, 4, "1 create + 3 polls")
    }

    func testRenderFailedIsATerminalStateDistinctFromRequestFailure() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 202, json: renderJSON(status: "queued"))
        await transport.enqueueJSON(status: 200, json: renderJSON(
            status: "failed",
            missingItems: ["A"], errorCode: "render_failed"
        ))
        let machine = makeMachine(transport: transport)

        let collector = await makeCollector(on: machine)
        await machine.start(roomId: "rm_1", body: RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "k"))
        let collected = await waitForStates(collector, count: 3)

        guard case .renderFailed(let render) = collected.last else {
            return XCTFail("expected .renderFailed, got \(String(describing: collected.last))")
        }
        XCTAssertEqual(render.errorCode, "render_failed")
        XCTAssertEqual(render.missingItems, ["A"])
    }

    func testCreateRenderApiErrorSurfacesAsRequestFailed() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 402, json: #"{"code":"no_credits","message":"Out of credits."}"#)
        let machine = makeMachine(transport: transport)

        let collector = await makeCollector(on: machine)
        await machine.start(roomId: "rm_1", body: RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "k"))
        let collected = await waitForStates(collector, count: 2) // submitting, requestFailed

        guard case .requestFailed(.api(let apiError)) = collected.last else {
            return XCTFail("expected .requestFailed(.api), got \(String(describing: collected.last))")
        }
        XCTAssertEqual(apiError.code, .noCredits)
    }

    func testSignedOutDuringPollStopsPollingAndSurfacesSignedOut() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 202, json: renderJSON(status: "queued"))
        // Poll hits an expired token with no refresh token available -> immediate signedOut,
        // no refresh call attempted (see APIClientTests for that specific behaviour).
        await transport.enqueueJSON(status: 401, json: #"{"code":"token_expired","message":"expired"}"#)
        let tokenStore = InMemoryTokenStore(access: "a", refresh: nil)
        let client = APIClient(configuration: .init(transport: transport, tokenStore: tokenStore, sleep: { _ in }))
        let machine = RenderStateMachine(client: client, pollInterval: 0, sleep: { _ in })

        let collector = await makeCollector(on: machine)
        await machine.start(roomId: "rm_1", body: RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "k"))
        let collected = await waitForStates(collector, count: 3) // submitting, polling, requestFailed

        XCTAssertEqual(collected.last, .requestFailed(.signedOut))

        let countAfterFailure = await transport.requestCount
        try await Task.sleep(nanoseconds: 50_000_000)
        let countLater = await transport.requestCount
        XCTAssertEqual(countAfterFailure, countLater, "must not keep polling after signing out")
    }

    func testCancelStopsFurtherPolling() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 202, json: renderJSON(status: "queued"))
        await transport.enqueueJSON(status: 200, json: renderJSON(status: "queued"))
        let machine = makeMachine(transport: transport)

        let collector = await makeCollector(on: machine)
        await machine.start(roomId: "rm_1", body: RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "k"))
        _ = await waitForStates(collector, count: 2) // submitting, polling
        await machine.cancel()

        let countAtCancel = await transport.requestCount
        try await Task.sleep(nanoseconds: 50_000_000)
        let countLater = await transport.requestCount
        XCTAssertEqual(countAtCancel, countLater, "no further polls after cancel")
    }

    func testResumePollingFetchesByIdWithoutCreatingARender() async throws {
        let transport = MockTransport()
        await transport.enqueueJSON(status: 200, json: renderJSON(
            status: "done",
            beforeUrl: "https://x/b", afterUrl: "https://x/a", preservationRate: 1.0
        ))
        let machine = makeMachine(transport: transport)

        let collector = await makeCollector(on: machine)
        await machine.resumePolling(renderId: "rd_1")
        let collected = await waitForStates(collector, count: 1) // done, straight away

        guard case .done = collected.last else {
            return XCTFail("expected .done, got \(String(describing: collected.last))")
        }
        let request = await transport.recordedRequests[0]
        XCTAssertEqual(request.httpMethod, "GET")
        XCTAssertEqual(request.url?.path, "/v1/renders/rd_1")
    }
}
