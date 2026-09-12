import XCTest
@testable import DesignMyRoom

/// `AppEnvironment.resolveBaseURL()` is what a cold tap on the home-screen icon
/// actually gets — Xcode's scheme `environmentVariables` are only injected when
/// Xcode itself launches the app via the debugger, never on a plain launch off a
/// physical device. A real bug (found by hand on-device): closing and reopening
/// the app without Xcode attached silently reverted to the hardcoded
/// `localhost:8000` default, losing the dev backend override entirely. Fix: also
/// bake the override into Info.plist at build time (survives any launch method),
/// with `ProcessInfo` still checked first so Xcode's live override wins when
/// attached, for quickly swapping without regenerating the project.
final class AppEnvironmentTests: XCTestCase {
    private struct StubInfoDictionaryProvider: InfoDictionaryProviding {
        var values: [String: Any] = [:]
        func object(forInfoDictionaryKey key: String) -> Any? { values[key] }
    }

    func testProcessInfoOverrideWinsWhenBothAreSet() {
        let url = AppEnvironment.resolveBaseURL(
            environment: ["DESIGNMYROOM_BASE_URL": "http://192.168.1.5:8000"],
            infoDictionaryProvider: StubInfoDictionaryProvider(values: ["DESIGNMYROOM_BASE_URL": "http://100.116.233.124:8000"])
        )
        XCTAssertEqual(url, URL(string: "http://192.168.1.5:8000"))
    }

    func testFallsBackToInfoPlistWhenProcessInfoIsAbsent() {
        // The exact scenario the bug report describes: no Xcode attached, so no
        // scheme environment variables at all — only what's baked into the bundle.
        let url = AppEnvironment.resolveBaseURL(
            environment: [:],
            infoDictionaryProvider: StubInfoDictionaryProvider(values: ["DESIGNMYROOM_BASE_URL": "http://100.116.233.124:8000"])
        )
        XCTAssertEqual(url, URL(string: "http://100.116.233.124:8000"))
    }

    func testFallsBackToLocalhostWhenNeitherIsSet() {
        let url = AppEnvironment.resolveBaseURL(
            environment: [:],
            infoDictionaryProvider: StubInfoDictionaryProvider(values: [:])
        )
        XCTAssertEqual(url, URL(string: "http://localhost:8000"))
    }

    func testInfoPlistValueIsIgnoredIfNotAString() {
        // GENERATE_INFOPLIST_FILE/XcodeGen quirks aside, this shouldn't crash on a
        // malformed or missing-type entry.
        let url = AppEnvironment.resolveBaseURL(
            environment: [:],
            infoDictionaryProvider: StubInfoDictionaryProvider(values: ["DESIGNMYROOM_BASE_URL": 12345])
        )
        XCTAssertEqual(url, URL(string: "http://localhost:8000"))
    }
}
