import AuthenticationServices
import DesignMyRoomCore
import Foundation

/// The app's session state. Views read `isSignedIn`/`me` and call
/// `handleSignInResult()`/`signOut()`; nothing else touches `APIClient` auth calls
/// directly.
@Observable
@MainActor
final class AuthManager {
    enum State: Equatable {
        case checkingForExistingSession
        case signedOut
        case signingIn
        case signedIn(Me)
        /// Sign-in itself failed (bad/expired Apple token, or the network) — shown as
        /// a banner on the sign-in screen, per ErrorCopy.
        case signInFailed(String)
    }

    private(set) var state: State = .checkingForExistingSession

    private let apiClient: APIClient
    private let tokenStore: TokenStore
    private let crashReporter: CrashReporter

    init(apiClient: APIClient, tokenStore: TokenStore, crashReporter: CrashReporter) {
        self.apiClient = apiClient
        self.tokenStore = tokenStore
        self.crashReporter = crashReporter
    }

    /// Called once at launch. `APIClient.restoreSession()` picks up a Keychain
    /// refresh token if one survived (see its own doc comment for why this needs to
    /// be an explicit path rather than relying on the usual 401 dance).
    func restoreSessionIfPossible() async {
        guard await apiClient.restoreSession() else {
            state = .signedOut
            return
        }
        await refreshMe()
    }

    /// `SignInWithAppleButton`'s own `onCompletion` — real `AuthenticationServices`,
    /// per the brief. Requires the `com.apple.developer.applesignin` entitlement and
    /// an App ID registered for it; see `ios/README.md` for the current state of that
    /// (no Apple Developer team is configured in this environment).
    func handleSignInResult(_ result: Result<ASAuthorization, Error>) async {
        state = .signingIn
        switch result {
        case .success(let authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = credential.identityToken,
                  let identityToken = String(data: tokenData, encoding: .utf8) else {
                state = .signInFailed(ErrorCopy.message(for: .appleTokenInvalid))
                return
            }
            do {
                _ = try await apiClient.signInWithApple(identityToken: identityToken)
                await refreshMe()
            } catch let error as ApiError {
                crashReporter.logHandledError(error, context: "AuthManager.signIn")
                state = .signInFailed(ErrorCopy.message(for: error))
            } catch {
                crashReporter.logHandledError(error, context: "AuthManager.signIn")
                state = .signInFailed(ErrorCopy.message(for: .appleTokenInvalid))
            }
        case .failure(let error):
            crashReporter.logHandledError(error, context: "AuthManager.signIn.appleSide")
            if let authError = error as? ASAuthorizationError, authError.code == .canceled {
                // The user dismissed the sheet — not a failure worth a red banner.
                state = .signedOut
            } else {
                // Anything else (an entitlement/capability problem, no network, ...)
                // used to also fall through to plain `.signedOut` with nothing shown
                // — which looked identical to a cancel and made this undebuggable
                // from the screen alone. Show the real error instead.
                state = .signInFailed(Self.describe(error))
            }
        }
    }

    private static func describe(_ error: Error) -> String {
        if let authError = error as? ASAuthorizationError {
            return "Sign in with Apple couldn't complete (\(authError.code.rawValue): \(authError.localizedDescription))."
        }
        return "Sign in with Apple couldn't complete (\(error))."
    }

    #if DEBUG
    /// Explicitly authorized for local testing while a paid Apple Developer account
    /// is pending (`../ORCH-QUESTIONS.md` Q7) — alongside `handleSignInResult`, never
    /// replacing it. Calls the exact same real `POST /v1/auth/apple` the Apple
    /// button does; only the identity token differs, a self-signed one the
    /// backend's already-running dev auth path accepts (`DevJWT`, shared with
    /// `DesignMyRoomCore`'s own integration tests rather than a second
    /// implementation). `#if DEBUG` means this method compiles out of a Release
    /// build entirely, not just hidden UI.
    func signInWithDevToken(identifier: String) async {
        state = .signingIn
        let devToken = DevJWT.signed(subject: identifier)
        do {
            _ = try await apiClient.signInWithApple(identityToken: devToken)
            await refreshMe()
        } catch let error as ApiError {
            crashReporter.logHandledError(error, context: "AuthManager.signInWithDevToken")
            state = .signInFailed(ErrorCopy.message(for: error))
        } catch {
            crashReporter.logHandledError(error, context: "AuthManager.signInWithDevToken")
            state = .signInFailed(Self.describe(error))
        }
    }
    #endif

    /// A voluntary sign-out (a "Sign out" button) — the tokens are still valid, so
    /// this clears them itself. Compare `handleSignedOutFromServer()`, used when
    /// `APIClientError.signedOut` surfaces from some other call: `APIClient` has
    /// already cleared the token store by the time that error is thrown.
    func signOut() async {
        await tokenStore.clear()
        state = .signedOut
    }

    /// Call when any screen catches `APIClientError.signedOut` (a token refresh
    /// failed mid-flow — e.g. the render poll noticed first). The token store is
    /// already clear at that point; this just updates what the UI shows.
    func handleSignedOutFromServer() {
        state = .signedOut
    }

    /// Re-reads `/v1/me` — call after anything that changes `credits_left`
    /// (a render was created, one failed and refunded, ...) so the UI never shows a
    /// stale count.
    func refreshMe() async {
        do {
            let me = try await apiClient.me()
            state = .signedIn(me)
        } catch {
            state = .signedOut
        }
    }
}
