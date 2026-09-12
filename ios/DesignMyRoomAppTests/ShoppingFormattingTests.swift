import XCTest
@testable import DesignMyRoom

final class ShoppingCurrencyTests: XCTestCase {
    func testFormatsCADWithTwoDecimalsByDefault() {
        XCTAssertEqual(ShoppingCurrency.string(amount: 609, currency: "CAD"), "CA$609.00")
    }

    func testFormatsWithZeroDecimalsWhenRequested() {
        XCTAssertEqual(ShoppingCurrency.string(amount: 609.49, currency: "CAD", decimals: 0), "CA$609")
    }

    func testUnknownCurrencyFallsBackToCodePrefix() {
        XCTAssertEqual(ShoppingCurrency.string(amount: 10, currency: "EUR"), "EUR 10.00")
    }
}

final class StoreDisplayNameTests: XCTestCase {
    func testKnownStoresMapToTheirDisplayName() {
        XCTAssertEqual(StoreDisplayName.name(forHost: "amazon.ca"), "Amazon")
        XCTAssertEqual(StoreDisplayName.name(forHost: "westelm.ca"), "West Elm")
        XCTAssertEqual(StoreDisplayName.name(forHost: "ikea.com"), "IKEA")
    }

    func testLookupIsCaseInsensitive() {
        XCTAssertEqual(StoreDisplayName.name(forHost: "Amazon.CA"), "Amazon")
    }

    func testUnknownStoreStripsTrailingTLD() {
        XCTAssertEqual(StoreDisplayName.name(forHost: "somenewstore.ca"), "somenewstore")
        XCTAssertEqual(StoreDisplayName.name(forHost: "othershop.com"), "othershop")
    }

    func testUnknownStoreWithNoRecognizedTLDIsReturnedAsIs() {
        XCTAssertEqual(StoreDisplayName.name(forHost: "example.store"), "example.store")
    }
}

final class ShoppingDateFormatTests: XCTestCase {
    func testFormatsIsoDateAsLongForm() {
        XCTAssertEqual(ShoppingDateFormat.longForm(isoDate: "2026-09-12"), "12 September 2026")
    }

    func testNilDateFallsBackGracefully() {
        XCTAssertEqual(ShoppingDateFormat.longForm(isoDate: nil), "an earlier date")
    }

    func testUnparsableDateFallsBackGracefully() {
        XCTAssertEqual(ShoppingDateFormat.longForm(isoDate: "not-a-date"), "an earlier date")
    }
}
