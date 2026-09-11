import XCTest
@testable import DesignMyRoom

final class ConfirmSummaryTests: XCTestCase {
    func testCountFormatsKeptAndRemoved() {
        XCTAssertEqual(ConfirmSummary.count(kept: 2, removed: 1), "keeping 2 · removing 1")
    }

    func testSentenceWithNothingRemoved() {
        XCTAssertEqual(
            ConfirmSummary.sentence(kept: ["Floor lamp", "Bookshelf"], removed: []),
            "Keeping the floor lamp and bookshelf. Removing nothing."
        )
    }

    func testSentenceWithNothingKept() {
        XCTAssertEqual(
            ConfirmSummary.sentence(kept: [], removed: ["Side table"]),
            "Keeping nothing. Removing the side table."
        )
    }

    func testSentenceWithOneKeptAndOneRemoved() {
        XCTAssertEqual(
            ConfirmSummary.sentence(kept: ["Floor lamp"], removed: ["Side table"]),
            "Keeping the floor lamp. Removing the side table."
        )
    }

    func testSentenceListsThreeOrMoreWithOxfordAnd() {
        XCTAssertEqual(
            ConfirmSummary.sentence(kept: ["Floor lamp", "Bookshelf", "Rug"], removed: []),
            "Keeping the floor lamp, bookshelf and rug. Removing nothing."
        )
    }

    func testSentenceLowercasesNamesRegardlessOfInputCasing() {
        XCTAssertEqual(
            ConfirmSummary.sentence(kept: ["Floor Lamp"], removed: []),
            "Keeping the floor lamp. Removing nothing."
        )
    }
}
