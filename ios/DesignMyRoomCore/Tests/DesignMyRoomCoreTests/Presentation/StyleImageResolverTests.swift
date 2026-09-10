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

    func testAllEighteenCurrentStylesHaveABundledImage() {
        // The 6 original plus the 12 added by prompt_review/HANDOFF.md §2's 6->18
        // style expansion.
        for id in [
            "warm-minimal", "scandi", "mid-century", "japandi", "modern-coastal", "industrial",
            "traditional", "art-deco", "dark-academia", "maximalism", "moroccan", "cottagecore",
            "rustic-farmhouse", "mediterranean", "cyberpunk", "memphis", "christmas", "valentines",
        ] {
            XCTAssertEqual(StyleImageResolver.imageAssetName(for: id), id, "\(id) should resolve to its own asset name")
        }
    }

    func testUnknownStyleIdFallsBackToNilRatherThanCrashingOrGuessing() {
        // The scenario the user's ask names directly: a style added to Style.all
        // with no matching artwork yet must fall back gracefully.
        XCTAssertNil(StyleImageResolver.imageAssetName(for: "brand-new-style-nobody-made-art-for-yet"))
    }

    func testBundledStyleIdsIsExactlyTheEighteenShipped() {
        XCTAssertEqual(
            StyleImageResolver.bundledStyleIds,
            [
                "warm-minimal", "scandi", "mid-century", "japandi", "modern-coastal", "industrial",
                "traditional", "art-deco", "dark-academia", "maximalism", "moroccan", "cottagecore",
                "rustic-farmhouse", "mediterranean", "cyberpunk", "memphis", "christmas", "valentines",
            ]
        )
    }
}
