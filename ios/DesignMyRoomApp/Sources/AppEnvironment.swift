import DesignMyRoomCore
import Foundation

/// Narrow seam over `Bundle.object(forInfoDictionaryKey:)` so `resolveBaseURL` is
/// testable without a real app bundle — same reasoning as `RoomListProviding`.
protocol InfoDictionaryProviding {
    func object(forInfoDictionaryKey key: String) -> Any?
}

extension Bundle: InfoDictionaryProviding {}

/// Wires the app to `DesignMyRoomCore`'s `APIClient` — the one place that knows the
/// base URL and how the app's `TokenStore`/`APIClient` are configured. Views never
/// construct their own `APIClient`; they read this from the SwiftUI environment.
///
/// Base URL is configurable per the brief (default `http://localhost:8000` for local
/// dev): `DESIGNMYROOM_BASE_URL` in the scheme's environment variables overrides it —
/// no code change needed to point the simulator at a different host. That scheme
/// variable is Xcode-only, though — it's injected only when Xcode itself launches
/// the app via the debugger, never on a plain tap of the home-screen icon (found by
/// hand: closing and reopening the app on a physical device with no cable attached
/// silently reverted to `localhost:8000`, losing the dev override). So the same key
/// is also baked into Info.plist at build time, which does survive a cold launch;
/// `ProcessInfo` is still checked first so Xcode's live override wins when
/// attached, for quickly swapping without regenerating the project.
@MainActor
final class AppEnvironment {
    let apiClient: APIClient
    let tokenStore: TokenStore
    let crashReporter: CrashReporter

    init() {
        let baseURL = Self.resolveBaseURL()
        let tokenStore = KeychainTokenStore()
        self.tokenStore = tokenStore
        self.apiClient = APIClient(configuration: .init(baseURL: baseURL, tokenStore: tokenStore))

        // Client's share of "error tracking" (PRD F5) — no vendor SDK (the client
        // brief locks "no third-party dependencies"), so a small home-grown JSON-line
        // log in the app's container. See CrashReporter's own doc comment for what
        // this can and can't catch.
        let supportDir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: supportDir, withIntermediateDirectories: true)
        let logFileURL = supportDir.appendingPathComponent("crash_log.jsonl")
        let crashReporter = CrashReporter(sink: FileCrashLogSink(fileURL: logFileURL))
        crashReporter.install()
        self.crashReporter = crashReporter
    }

    /// Internal, not private — visible to `AppEnvironmentTests` via `@testable
    /// import`, same reasoning as `HomeViewModel.roomsProvider`. Defaults match
    /// production; tests inject both seams to exercise each fallback in isolation.
    /// `nonisolated` because it's a pure function touching no actor state — no
    /// reason to force callers (including tests) onto the main actor for it.
    nonisolated static func resolveBaseURL(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        infoDictionaryProvider: InfoDictionaryProviding = Bundle.main
    ) -> URL {
        if let override = environment["DESIGNMYROOM_BASE_URL"],
           let url = URL(string: override) {
            return url
        }
        if let plistValue = infoDictionaryProvider.object(forInfoDictionaryKey: "DESIGNMYROOM_BASE_URL") as? String,
           let url = URL(string: plistValue) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
}
