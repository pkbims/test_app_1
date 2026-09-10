import XCTest
@testable import DesignMyRoomCore

final class RetryPolicyTests: XCTestCase {

    func testDefaultPolicyAllowsThreeAttemptsTotal() {
        let policy = RetryPolicy.default
        XCTAssertEqual(policy.maxAttempts, 3)
    }

    func testDelayDoublesEachAttemptUpToCap() {
        let policy = RetryPolicy(maxAttempts: 5, baseDelay: 0.5, maxDelay: 4.0)
        // attempt is 1-based: the delay *before* retry number `attempt`.
        XCTAssertEqual(policy.delay(beforeAttempt: 1), 0.5)
        XCTAssertEqual(policy.delay(beforeAttempt: 2), 1.0)
        XCTAssertEqual(policy.delay(beforeAttempt: 3), 2.0)
        XCTAssertEqual(policy.delay(beforeAttempt: 4), 4.0, "capped at maxDelay")
        XCTAssertEqual(policy.delay(beforeAttempt: 5), 4.0, "stays capped")
    }

    func testShouldRetryTransientNetworkErrors() {
        let policy = RetryPolicy.default
        XCTAssertTrue(policy.shouldRetry(after: URLError(.timedOut)))
        XCTAssertTrue(policy.shouldRetry(after: URLError(.cannotConnectToHost)))
        XCTAssertTrue(policy.shouldRetry(after: URLError(.networkConnectionLost)))
        XCTAssertFalse(policy.shouldRetry(after: URLError(.badURL)), "not a transient condition")
    }

    func testShouldRetryServiceUnavailableStatus() {
        let policy = RetryPolicy.default
        XCTAssertTrue(policy.shouldRetry(afterStatus: 503))
        XCTAssertFalse(policy.shouldRetry(afterStatus: 500), "not advertised as transient by /health semantics")
        XCTAssertFalse(policy.shouldRetry(afterStatus: 404))
        XCTAssertFalse(policy.shouldRetry(afterStatus: 401))
    }
}
