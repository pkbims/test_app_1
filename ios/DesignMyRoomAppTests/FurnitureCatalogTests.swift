import XCTest
import DesignMyRoomCore
@testable import DesignMyRoom

/// `options_review/HANDOFF.md` §7.2: every room type has its own closed furniture
/// list, ids are lower-cased and wire-safe, and lamps never appear (R6: "lamps are
/// decor, not furniture").
final class FurnitureCatalogTests: XCTestCase {
    func testEveryRoomTypeHasAtLeastFourPieces() {
        for roomType in RoomType.allCases {
            XCTAssertGreaterThanOrEqual(
                FurnitureCatalog.items(for: roomType).count, 4,
                "\(roomType) should have a real furniture list, not a stub"
            )
        }
    }

    func testLivingRoomMatchesTheHandoffExactly() {
        let ids = FurnitureCatalog.items(for: .livingRoom).map(\.id)
        XCTAssertEqual(ids, ["sofa", "armchair", "coffee_table", "side_table", "tv_unit", "bookcase", "sideboard"])
    }

    func testNoRoomTypeOffersALampAsFurniture() {
        for roomType in RoomType.allCases {
            for item in FurnitureCatalog.items(for: roomType) {
                XCTAssertFalse(item.id.contains("lamp"), "\(roomType) offered a lamp (\(item.id)) as furniture")
                XCTAssertFalse(item.displayName.lowercased().contains("lamp"))
            }
        }
    }

    func testIdsAreUniqueWithinARoomType() {
        for roomType in RoomType.allCases {
            let ids = FurnitureCatalog.items(for: roomType).map(\.id)
            XCTAssertEqual(ids.count, Set(ids).count, "\(roomType) has duplicate furniture ids")
        }
    }
}
