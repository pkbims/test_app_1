import DesignMyRoomCore
import Foundation

/// Wires the app to `DesignMyRoomCore`'s `APIClient` — the one place that knows the
/// base URL and how the app's `TokenStore`/`APIClient` are configured. Views never
/// construct their own `APIClient`; they read this from the SwiftUI environment.
///
/// Base URL is configurable per the brief (default `http://localhost:8000` for local
/// dev): `DESIGNMYROOM_BASE_URL` in the scheme's environment variables overrides it —
/// no code change needed to point the simulator at a different host.
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

    private static func resolveBaseURL() -> URL {
        if let override = ProcessInfo.processInfo.environment["DESIGNMYROOM_BASE_URL"],
           let url = URL(string: override) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
}
