import XCTest

/// Regression test for a real bug report (2026-09-10): "New Room -> add photo, it
/// loads and takes me back to the homepage." Confirmed root cause, via a controlled
/// A/B test against the real backend and a real `PHPickerViewController`:
/// `PhotoPicker.swift`'s picker delegates called `picker.dismiss(animated:)`
/// imperatively on a view controller that SwiftUI was *also* presenting
/// declaratively (`.sheet`/`.fullScreenCover(isPresented:)`). Driving the same
/// presentation from both sides desyncs SwiftUI's belief about what's presented
/// from the real UIKit hierarchy, and can cascade into SwiftUI incorrectly
/// collapsing an *ancestor* presentation (the whole New Room flow, not just the
/// picker sheet) — landing back on Home mid-flow, before the photo/inventory
/// network calls even mattered.
///
/// This needs the real UI, real taps, and a real out-of-process
/// `PHPickerViewController` — the bug is fundamentally about presentation-hierarchy
/// state, which no amount of testing at the view-model layer (see
/// `RoomFlowLiveTests` in `DesignMyRoomAppTests`) can catch on its own; that layer
/// was verified clean (including under a deliberate concurrent-call race) before
/// this was found here instead.
///
/// Requires a photo in the Simulator's library first —
/// `xcrun simctl addmedia <device> path/to/photo.jpg` — and the backend running
/// (`docker compose up`).
///
/// A hard-won detail: checking `.exists` on Home's own elements is **not** enough to
/// detect "bounced back to Home" — Home's `NavigationBar`/buttons still exist in the
/// accessibility tree underneath a `fullScreenCover` even while it's not the
/// frontmost, visible screen (the presenter is retained, not torn down). Only
/// `.isHittable` reflects "this is genuinely on screen and interactive right now" —
/// an early, `.exists`-only version of this test produced false-positive
/// reproductions before that was caught (via a screenshot that visibly contradicted
/// what `.exists` reported at the same instant).
final class AddPhotoFlowUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testAddingAPhotoReachesConfirmNotHome() throws {
        let app = XCUIApplication()
        app.launch()

        // A prior manual test session may have left a real refresh token in this
        // Simulator's Keychain, restoring the session silently and landing straight
        // on Home — or we're truly signed out and need the Q7 dev path
        // (../ORCH-QUESTIONS.md, deterministic, no Apple ID/Developer team needed;
        // Debug-only, this test target only runs against Debug builds). Handle both.
        let devSignIn = app.buttons["Continue (dev only)"]
        let newRoomButton = app.buttons["New Room"]
        let deadline = Date().addingTimeInterval(15)
        while !devSignIn.exists, !newRoomButton.exists, Date() < deadline {
            Thread.sleep(forTimeInterval: 0.2)
        }
        XCTAssertTrue(devSignIn.exists || newRoomButton.exists, "expected either the sign-in or Home screen to appear")

        if devSignIn.exists {
            devSignIn.tap()
        }
        XCTAssertTrue(newRoomButton.waitForExistence(timeout: 15), "expected to land on Home (My Rooms)")
        newRoomButton.tap()

        let addPhotoButton = app.buttons["Add a photo"]
        XCTAssertTrue(addPhotoButton.waitForExistence(timeout: 10), "expected the Add Photo screen")
        addPhotoButton.tap()

        let chooseFromLibrary = app.buttons["Choose from Library"]
        XCTAssertTrue(chooseFromLibrary.waitForExistence(timeout: 5), "expected the source-picker action sheet")
        chooseFromLibrary.tap()

        // A one-time "Private Access to Photos" onboarding banner overlaps the top
        // of the grid and intercepts taps until dismissed.
        let onboardingClose = app.buttons["Close"]
        if onboardingClose.waitForExistence(timeout: 3) {
            onboardingClose.tap()
        }

        // PHPickerViewController runs out-of-process; its cells are still queryable
        // through the same XCUIApplication proxy. The grid's real selectable photo
        // cells carry identifier "PXGGridLayout-Info" — a plain `.images.firstMatch`
        // can land on a decorative/onboarding image instead.
        let firstPhotoCell = app.images.matching(NSPredicate(format: "identifier == 'PXGGridLayout-Info'")).firstMatch
        XCTAssertTrue(firstPhotoCell.waitForExistence(timeout: 15), "expected at least one photo in the picker grid")
        // A plain .tap() fails XCUITest's "hittable" heuristic here (an overlapping
        // transparent system view confuses it, even though the cell is genuinely
        // visible and tappable) — a coordinate tap sends the touch directly and
        // sidesteps that check, a standard workaround for this exact class of
        // false negative.
        firstPhotoCell.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()

        // Some picker configurations need an explicit "Add"/checkmark confirmation
        // after selecting; harmless no-op if this build's config doesn't (single
        // selection mode auto-confirms on tap).
        let addConfirmButton = app.buttons["Add"]
        if addConfirmButton.waitForExistence(timeout: 3) {
            addConfirmButton.tap()
        }

        // The actual regression: did we land on Confirm (this room's inventory,
        // "Continue" button), or silently collapse back to a genuinely-visible Home?
        let confirmContinueButton = app.buttons["Continue"]
        var reachedConfirm = false
        var bouncedToHome = false
        let pollDeadline = Date().addingTimeInterval(20)
        while Date() < pollDeadline {
            if confirmContinueButton.exists { reachedConfirm = true; break }
            if newRoomButton.isHittable { bouncedToHome = true; break }
            Thread.sleep(forTimeInterval: 0.5)
        }

        if !reachedConfirm {
            // Diagnostic dump — printed to the xcodebuild log so the actual on-screen
            // state at the moment of failure is visible, not guessed at.
            print("=== ACCESSIBILITY TREE AT FAILURE ===")
            print(app.debugDescription)
            print("=== END ACCESSIBILITY TREE ===")
            let screenshot = XCTAttachment(screenshot: app.screenshot())
            screenshot.lifetime = .keepAlways
            screenshot.name = "failure-state"
            add(screenshot)
        }

        XCTAssertTrue(reachedConfirm, "expected the Confirm screen after adding a photo")
        XCTAssertFalse(bouncedToHome, "bounced back to Home instead of advancing to Confirm — the reported regression")
    }
}
