import XCTest
@testable import DesignMyRoomCore

/// Pure decision logic behind the style cards' image-or-placeholder fallback (a
/// user-facing "add a 7th style with no artwork yet" scenario) — kept here, not in
/// the app target, specifically so this branch is unit-tested without an Xcode UI
/// test target. The actual asset-catalog lookup stays app-side (Core has no
/// UIKit/Bundle dependency); this only decides what to do once that's known.
final class StyleImageResolverTests: XCTestCase {
    func testReturnsTheStyleIdWhenItHasABundledImage() {
        XCTAssertEqual(StyleImageResolver.imageAssetName(for: "warm-minimal"), "warm-minimal")
    }

    func testAllSixCurrentStylesHaveABundledImage() {
        for id in ["warm-minimal", "scandi", "mid-century", "japandi", "modern-coastal", "industrial"] {
            XCTAssertEqual(StyleImageResolver.imageAssetName(for: id), id, "\(id) should resolve to its own asset name")
        }
    }

    func testUnknownStyleIdFallsBackToNilRatherThanCrashingOrGuessing() {
        // The scenario the user's ask names directly: a 7th style added to
        // Style.all with no matching artwork yet must fall back gracefully.
        XCTAssertNil(StyleImageResolver.imageAssetName(for: "brand-new-style-nobody-made-art-for-yet"))
    }

    func testBundledStyleIdsIsExactlyTheSixShipped() {
        XCTAssertEqual(
            StyleImageResolver.bundledStyleIds,
            ["warm-minimal", "scandi", "mid-century", "japandi", "modern-coastal", "industrial"]
        )
    }
}
