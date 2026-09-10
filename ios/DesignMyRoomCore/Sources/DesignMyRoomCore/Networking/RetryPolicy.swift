import Foundation

/// Retry/backoff for the networking layer (PRD F5 — "where client bugs live").
///
/// Only transient failures are retried automatically: a network error that means the
/// request may never have reached the server, or a `503` — the backend's own
/// documented "a deploy must stop here" state (`backend/README.md` — three-state
/// health), which is explicitly *not* a permanent rejection of the request. A `500`,
/// by contrast, means the server did something wrong with a request it received, so
/// retrying it blindly isn't safe by default; `404`/`401`/etc. are real answers, not
/// transient conditions.
///
/// This governs *whether/when* to retry. *What* is safe to retry (GET/DELETE always;
/// POST only when idempotent, e.g. render creation's `idempotency_key`) is decided by
/// the caller — see `APIClient`.
public struct RetryPolicy: Sendable {
    public let maxAttempts: Int
    public let baseDelay: TimeInterval
    public let maxDelay: TimeInterval

    public init(maxAttempts: Int, baseDelay: TimeInterval, maxDelay: TimeInterval) {
        self.maxAttempts = maxAttempts
        self.baseDelay = baseDelay
        self.maxDelay = maxDelay
    }

    /// 3 attempts total (1 try + 2 retries), starting at 0.5s and doubling, capped at 4s.
    public static let `default` = RetryPolicy(maxAttempts: 3, baseDelay: 0.5, maxDelay: 4.0)

    /// The delay before the given 1-based retry attempt (`1` = the delay before the
    /// first retry, i.e. after the first failed try).
    public func delay(beforeAttempt attempt: Int) -> TimeInterval {
        let raw = baseDelay * pow(2.0, Double(attempt - 1))
        return min(raw, maxDelay)
    }

    public func shouldRetry(after error: Error) -> Bool {
        guard let urlError = error as? URLError else { return false }
        switch urlError.code {
        case .timedOut, .cannotConnectToHost, .networkConnectionLost, .notConnectedToInternet, .dnsLookupFailed:
            return true
        default:
            return false
        }
    }

    public func shouldRetry(afterStatus status: Int) -> Bool {
        status == 503
    }
}
