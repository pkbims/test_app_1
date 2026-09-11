import XCTest

/// The one UI test the options-round handoff specifically calls for
/// (`options_review/HANDOFF.md` §5.5): reach the style screen, select "Add new
/// pieces", and assert the furniture picker appears. This is the control that
/// failed silently in the prototype once (a hidden `<div id="furn" hidden>` that
/// never got un-hidden) — worth a real end-to-end proof, not just a view-model
/// unit test, since the bug lives in "does the view actually reveal," not in state.
///
/// Same setup as `AddPhotoFlowUITests`: needs a photo in the Simulator's library
/// (`xcrun simctl addmedia <device> path/to/photo.jpg`) and the backend running
/// (`docker compose up`).
final class StyleScreenFurniturePickerUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testSelectingAddNewPiecesRevealsTheFurniturePicker() throws {
        let app = XCUIApplication()
        app.launch()

        try reachStyleScreen(app)

        let addNewPieces = app.buttons["Add new pieces"]
        XCTAssertTrue(addNewPieces.waitForExistence(timeout: 10), "expected the Furniture segmented control on the style screen")
        addNewPieces.tap()

        // The picker only exists in the view hierarchy at all when
        // `flow.furniture == .add` (StylePickerView's `if flow.furniture == .add { FurniturePicker(...) }`)
        // — so `.exists` here is itself the real proof of the reveal (the prototype's
        // regression was a `hidden` attribute that never came off at all, i.e. this
        // node never existing).
        let picker = app.descendants(matching: .any)["FurniturePicker"]
        XCTAssertTrue(picker.waitForExistence(timeout: 5), "expected the 'What's missing?' furniture picker to appear")

        // `picker` is a plain grouping element (SwiftUI accessibility containers
        // aren't hittable themselves — only their leaf children are), so for the
        // "is it actually visible right now" half of the proof
        // (xcuitest-exists-vs-hittable), check the leaf static text inside it
        // instead, scrolling it into the viewport first since the style screen is
        // one long scroll.
        let missingLabel = app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "missing")).firstMatch
        var scrollAttempts = 0
        while !missingLabel.isHittable, scrollAttempts < 6 {
            app.swipeUp()
            scrollAttempts += 1
        }
        XCTAssertTrue(missingLabel.isHittable, "the furniture picker exists but never scrolled into view")

        // Switching back should remove it again — proves this is a real reveal/hide,
        // not a picker that was always there.
        let keepOnly = app.buttons["Only what I'm keeping"]
        XCTAssertTrue(keepOnly.exists)
        keepOnly.tap()
        XCTAssertFalse(picker.exists, "the furniture picker should be removed once 'Only what I'm keeping' is selected")
    }

    /// Sign in (dev path if needed), start a new room, add a photo, wait for
    /// Confirm, and tap through to the style screen. Mirrors
    /// `AddPhotoFlowUITests.testAddingAPhotoReachesConfirmNotHome` up through
    /// reaching Confirm, then goes one screen further.
    private func reachStyleScreen(_ app: XCUIApplication) throws {
        let devSignIn = app.buttons["Continue (dev only)"]
        let newRoomButton = app.buttons["New Room"]
        let signInDeadline = Date().addingTimeInterval(15)
        while !devSignIn.exists, !newRoomButton.exists, Date() < signInDeadline {
            Thread.sleep(forTimeInterval: 0.2)
        }
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

        let onboardingClose = app.buttons["Close"]
        if onboardingClose.waitForExistence(timeout: 3) {
            onboardingClose.tap()
        }

        let firstPhotoCell = app.images.matching(NSPredicate(format: "identifier == 'PXGGridLayout-Info'")).firstMatch
        XCTAssertTrue(firstPhotoCell.waitForExistence(timeout: 15), "expected at least one photo in the picker grid")
        firstPhotoCell.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()

        let addConfirmButton = app.buttons["Add"]
        if addConfirmButton.waitForExistence(timeout: 3) {
            addConfirmButton.tap()
        }

        let confirmContinueButton = app.buttons["Continue"]
        if !confirmContinueButton.waitForExistence(timeout: 20) {
            print("=== ACCESSIBILITY TREE AT FAILURE (waiting for Confirm) ===")
            print(app.debugDescription)
            print("=== END ACCESSIBILITY TREE ===")
            let screenshot = XCTAttachment(screenshot: app.screenshot())
            screenshot.lifetime = .keepAlways
            screenshot.name = "failure-state-confirm"
            add(screenshot)
        }
        XCTAssertTrue(confirmContinueButton.exists, "expected the Confirm screen after adding a photo")
        // Confirm's "Continue" is disabled until the inventory finishes loading.
        let enabledDeadline = Date().addingTimeInterval(20)
        while !confirmContinueButton.isEnabled, Date() < enabledDeadline {
            Thread.sleep(forTimeInterval: 0.3)
        }
        confirmContinueButton.tap()

        XCTAssertTrue(app.staticTexts["Pick a style"].waitForExistence(timeout: 10), "expected the style screen after Continue")
    }
}
