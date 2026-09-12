import XCTest
@testable import DesignMyRoomCore

/// Pure decision logic behind the style cards' image-or-placeholder fallback (a
/// user-facing "add a new style with no artwork yet" scenario) — kept here, not in
/// the app target, specifically so this branch is unit-tested without an Xcode UI
/// test target. The actual asset-catalog lookup stays app-side (Core has no
/// UIKit/Bundle dependency); this only decides what to do once that's known.
final class StyleImageResolverTests: XCTestCase {
    /// The 18 original ids plus the 44 added by the DecorAI-name-parity expansion
    /// (backend/app/render/prompt.py STYLES, commit 6959d92) — every id that dict
    /// declares, in the same order.
    private static let allSixtyTwoIds = [
        "warm-minimal", "scandi", "japandi", "modern-coastal", "mid-century", "industrial",
        "traditional", "art-deco", "dark-academia", "maximalism", "moroccan", "cottagecore",
        "rustic-farmhouse", "mediterranean", "cyberpunk", "memphis", "christmas", "valentines",
        "minimalistic", "modern", "transitional", "contemporary", "japanese", "eclectic",
        "rustic", "bohemian", "farmhouse", "vintage", "victorian", "retro", "zen",
        "biophilic", "solarpunk", "tropical", "parisian", "brutalist", "vaporwave",
        "hollywood-regency", "art-nouveau", "korean-hanok", "southwestern", "nordic-hygge",
        "baroque", "bauhaus", "futuristic", "colonial", "tudor", "shaker", "rococo",
        "deconstructivism", "wabi-sabi", "organic-modern", "quiet-luxury", "french-country",
        "english-country", "neoclassical", "alpine-chalet", "hacienda", "chinoiserie",
        "shabby-chic", "gothic", "steampunk",
    ]

    func testReturnsTheStyleIdWhenItHasABundledImage() {
        XCTAssertEqual(StyleImageResolver.imageAssetName(for: "warm-minimal"), "warm-minimal")
    }

    func testAllSixtyTwoCurrentStylesHaveABundledImage() {
        for id in Self.allSixtyTwoIds {
            XCTAssertEqual(StyleImageResolver.imageAssetName(for: id), id, "\(id) should resolve to its own asset name")
        }
    }

    func testUnknownStyleIdFallsBackToNilRatherThanCrashingOrGuessing() {
        // The scenario the user's ask names directly: a style added to Style.all
        // with no matching artwork yet must fall back gracefully.
        XCTAssertNil(StyleImageResolver.imageAssetName(for: "brand-new-style-nobody-made-art-for-yet"))
    }

    func testBundledStyleIdsIsExactlyTheSixtyTwoShipped() {
        XCTAssertEqual(StyleImageResolver.bundledStyleIds, Set(Self.allSixtyTwoIds))
        XCTAssertEqual(StyleImageResolver.bundledStyleIds.count, 62)
    }
}
