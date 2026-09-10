import XCTest
@testable import DesignMyRoomCore

/// PRD §16 "every error" maps each `ErrorCode` to fixed, plain-language copy — this
/// pins that table down so a screen can never silently fall back to a raw code.
final class ErrorCopyTests: XCTestCase {

    func testEveryErrorCodeHasCopy() {
        for code in [
            ErrorCode.appleTokenInvalid, .tokenExpired, .noCredits, .rateLimited,
            .photoTooLarge, .photoUnsupported, .noPhotos, .noInventory,
            .inventoryFailed, .renderFailed, .notFound,
        ] {
            XCTAssertFalse(ErrorCopy.message(for: code).isEmpty, "\(code) has no copy")
        }
    }

    func testSpecificCopyMatchesThePRDTable() {
        XCTAssertEqual(ErrorCopy.message(for: .appleTokenInvalid), "Sign in didn't work. Try again.")
        XCTAssertEqual(ErrorCopy.message(for: .noCredits), "You've used your free room.")
        XCTAssertEqual(ErrorCopy.message(for: .rateLimited), "Slow down for a moment.")
        XCTAssertEqual(ErrorCopy.message(for: .photoTooLarge), "That photo is too big.")
        XCTAssertEqual(ErrorCopy.message(for: .noPhotos), "Add a photo of this room first.")
        XCTAssertEqual(ErrorCopy.message(for: .renderFailed), "That didn't work. Your credit is back.")
        XCTAssertEqual(ErrorCopy.message(for: .notFound), "We couldn't find that.")
    }

    func testTokenExpiredHasNoUserFacingCopyBecauseItsHandledSilently() {
        // Per PRD §16: "Nothing — the app refreshes silently." Any screen that ever
        // shows this code did something wrong upstream, but it still needs *some*
        // fallback text rather than a blank alert.
        XCTAssertFalse(ErrorCopy.message(for: .tokenExpired).isEmpty)
    }

    func testApiErrorPrefersItsOwnMessageOverTheGenericCopy() {
        // "Show Error.message verbatim when present" (AGENT.md screen 7) — the
        // contract's own per-request message is more specific than the fixed table.
        let error = ApiError(code: .noCredits, message: "Custom server message.")
        XCTAssertEqual(ErrorCopy.message(for: error), "Custom server message.")
    }

    func testApiErrorFallsBackToTableCopyWhenMessageIsEmpty() {
        let error = ApiError(code: .noCredits, message: "")
        XCTAssertEqual(ErrorCopy.message(for: error), ErrorCopy.message(for: .noCredits))
    }
}
