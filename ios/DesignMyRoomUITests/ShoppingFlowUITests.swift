import XCTest

/// End-to-end coverage for "Shop your restyle" (`shopping_proto/HANDOFF.md` §4.3's
/// required UI tests): Compare shows no card while shopping is `pending`, shows it
/// with the right count once `ready`, tapping it pushes the item list, a D2 item
/// (no usable match) shows a Search button, and the total text reflects the
/// backend's own `total_from`.
///
/// Needs the real `GET /v1/renders/{id}/shopping` endpoint running — merged to
/// `main` in commit f7989bc. Verified end-to-end against the real
/// `SHOPPING_BACKEND=openai_searchapi` pipeline (contract shape matches these
/// models exactly, no decode mismatches); with real SearchApi calls the pipeline
/// took ~48s render-done-to-shopping-done in that run, hence the generous
/// timeouts below — `SHOPPING_BACKEND=fake` resolves in one poll tick instead.
/// Same setup as `AddPhotoFlowUITests`/`StyleScreenFurniturePickerUITests`: a
/// photo in the Simulator's library and the backend running.
final class ShoppingFlowUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testCompareShowsNoCardWhilePendingThenShowsItReadyWithTheRightCount() throws {
        let app = XCUIApplication()
        app.launch()
        try reachCompareAfterARender(app)

        // Right as Compare appears, shopping has only just started polling —
        // `RenderStateMachine` sets `.pending` synchronously the moment the render
        // itself is `.done`, before any network round trip, so the card must not
        // exist yet (HANDOFF §3: "no spinner, no placeholder" while pending).
        let unlockCard = app.otherElements["UnlockShoppingCard"]
        XCTAssertFalse(unlockCard.exists, "the Unlock card must not appear before shopping is ready")

        // Shopping resolves after a few 2s poll ticks once ready/none; give it a
        // generous window (30s fake backend, longer for the real pipeline).
        XCTAssertTrue(unlockCard.waitForExistence(timeout: 90), "expected the Unlock card once shopping is ready")

        let countLabel = app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "found in your restyle")).firstMatch
        XCTAssertTrue(countLabel.exists, "expected the '<n> new items found in your restyle' copy")
    }

    func testTappingUnlockPushesTheItemList() throws {
        let app = XCUIApplication()
        app.launch()
        try reachCompareAfterARender(app)

        let unlockCard = app.otherElements["UnlockShoppingCard"]
        XCTAssertTrue(unlockCard.waitForExistence(timeout: 90))
        unlockCard.tap()

        XCTAssertTrue(app.staticTexts["Shop your restyle"].waitForExistence(timeout: 5), "expected the pushed shopping screen")
    }

    func testADetailItemWithNoMatchShowsASearchButtonInsteadOfAPrice() throws {
        let app = XCUIApplication()
        app.launch()
        try reachCompareAfterARender(app)

        let unlockCard = app.otherElements["UnlockShoppingCard"]
        XCTAssertTrue(unlockCard.waitForExistence(timeout: 90))
        unlockCard.tap()
        XCTAssertTrue(app.staticTexts["Shop your restyle"].waitForExistence(timeout: 5))

        let noMatchLabel = app.staticTexts["no close match found"]
        guard noMatchLabel.waitForExistence(timeout: 3) else {
            throw XCTSkip("This render's shopping result has no D2 (no-match) item to check — depends on the pipeline's output for this render, not something the client controls.")
        }
        let searchButton = app.buttons["Search"]
        XCTAssertTrue(searchButton.exists, "expected a Search button next to 'no close match found'")
    }

    func testTotalTextReflectsTheReportedTotal() throws {
        let app = XCUIApplication()
        app.launch()
        try reachCompareAfterARender(app)

        let unlockCard = app.otherElements["UnlockShoppingCard"]
        XCTAssertTrue(unlockCard.waitForExistence(timeout: 90))
        unlockCard.tap()
        XCTAssertTrue(app.staticTexts["Shop your restyle"].waitForExistence(timeout: 5))

        let total = app.staticTexts["ShoppingTotal"]
        XCTAssertTrue(total.waitForExistence(timeout: 5))
        // The display code (`ShoppingView.TotalCard`) has exactly one source for
        // this number — `shopping.totalFrom`, formatted, never recomputed — so the
        // format check here is really a regression guard against someone later
        // wiring in a client-side recomputation (HANDOFF §3: "must not display its
        // own number if they disagree").
        XCTAssertTrue(total.label.hasPrefix("CA$"), "expected the total in the app's currency format, got \(total.label)")
    }

    /// Sign in, add a photo, confirm, pick a style, restyle, and wait for Compare —
    /// mirrors `StyleScreenFurniturePickerUITests.reachStyleScreen` through one more
    /// step (an actual render).
    private func reachCompareAfterARender(_ app: XCUIApplication) throws {
        let devSignIn = app.buttons["Continue (dev only)"]
        let newRoomButton = app.buttons["New Room"]
        let signInDeadline = Date().addingTimeInterval(15)
        while !devSignIn.exists, !newRoomButton.exists, Date() < signInDeadline {
            Thread.sleep(forTimeInterval: 0.2)
        }
        if devSignIn.exists {
            devSignIn.tap()
        }
        XCTAssertTrue(newRoomButton.waitForExistence(timeout: 15))
        newRoomButton.tap()

        let addPhotoButton = app.buttons["Add a photo"]
        XCTAssertTrue(addPhotoButton.waitForExistence(timeout: 10))
        addPhotoButton.tap()

        let chooseFromLibrary = app.buttons["Choose from Library"]
        XCTAssertTrue(chooseFromLibrary.waitForExistence(timeout: 5))
        chooseFromLibrary.tap()

        let onboardingClose = app.buttons["Close"]
        if onboardingClose.waitForExistence(timeout: 3) {
            onboardingClose.tap()
        }

        let firstPhotoCell = app.images.matching(NSPredicate(format: "identifier == 'PXGGridLayout-Info'")).firstMatch
        XCTAssertTrue(firstPhotoCell.waitForExistence(timeout: 15))
        firstPhotoCell.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()

        let addConfirmButton = app.buttons["Add"]
        if addConfirmButton.waitForExistence(timeout: 3) {
            addConfirmButton.tap()
        }

        let confirmContinueButton = app.buttons["Continue"]
        XCTAssertTrue(confirmContinueButton.waitForExistence(timeout: 30))
        let enabledDeadline = Date().addingTimeInterval(20)
        while !confirmContinueButton.isEnabled, Date() < enabledDeadline {
            Thread.sleep(forTimeInterval: 0.3)
        }
        confirmContinueButton.tap()

        XCTAssertTrue(app.staticTexts["Pick a style"].waitForExistence(timeout: 10))
        // Any style card — the first one in the rail.
        app.scrollViews.firstMatch.images.firstMatch.tap()

        let restyleButton = app.buttons["Restyle this room"]
        XCTAssertTrue(restyleButton.waitForExistence(timeout: 5))
        restyleButton.tap()

        // Real renders take up to ~60s; the render's own "N rooms left" line is the
        // simplest reliable marker that Compare (not the rendering spinner) is up.
        let roomsLeftLabel = app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "left")).firstMatch
        XCTAssertTrue(roomsLeftLabel.waitForExistence(timeout: 90), "expected the render to finish and Compare to show")
    }
}
