import Foundation

/// Which style ids currently have a bundled sample image, and the decision of what
/// a style card should do about it — kept as a pure function, no `UIKit`/`Bundle`
/// dependency, so the "a style with no artwork yet falls back gracefully" branch is
/// unit-tested without an Xcode UI test target.
///
/// `bundledStyleIds` is the single source of truth for what's actually shipped in
/// `ios/DesignMyRoomApp/Resources/Assets.xcassets` — update it there and here
/// together. A `Style.all` id not in this set (a newly added style with no artwork
/// yet) resolves to `nil`, and the app target falls back to its placeholder card
/// rather than showing a broken image reference or crashing.
public enum StyleImageResolver {
    public static let bundledStyleIds: Set<String> = [
        "warm-minimal", "scandi", "mid-century", "japandi", "modern-coastal", "industrial",
        "traditional", "art-deco", "dark-academia", "maximalism", "moroccan", "cottagecore",
        "rustic-farmhouse", "mediterranean", "cyberpunk", "memphis", "christmas", "valentines",
    ]

    public static func imageAssetName(for styleId: String) -> String? {
        bundledStyleIds.contains(styleId) ? styleId : nil
    }
}
