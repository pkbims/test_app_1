import Foundation

/// Everything `APIClient` can throw that isn't a well-formed `ApiError` from the
/// contract, or a `URLError` propagated straight from the transport.
public enum APIClientError: Error, Equatable, Sendable {
    /// The `401 token_expired` -> refresh -> retry dance failed (no refresh token
    /// stored, or the refresh call itself was rejected). The caller should sign out.
    case signedOut
    /// A `422` — the request body failed server-side validation. This is a client
    /// bug, not a user-facing error; the contract's `Error` schema doesn't cover it.
    case validation(HTTPValidationError)
    /// A non-2xx response whose body was neither a valid `ApiError` nor a valid
    /// `HTTPValidationError` — should not happen against the real backend, but must
    /// not crash the app if it ever does.
    case unrecognizedResponse(status: Int)
}
