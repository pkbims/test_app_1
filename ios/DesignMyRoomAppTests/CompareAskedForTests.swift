import XCTest
import DesignMyRoomCore
@testable import DesignMyRoom

final class CompareAskedForTests: XCTestCase {
    private func makeRender(
        roomType: RoomType? = .livingRoom,
        walls: WallsOption = .leave,
        furniture: FurnitureOption = .keepOnly,
        addFurniture: [String] = [],
        decor: DecorLevel = .asStyle,
        plants: Bool = false,
        palette: PaletteOption = .asStyle,
        removeIds: [String] = []
    ) -> Render {
        Render(
            renderId: "rd_1", roomId: "rm_1", status: .done, style: "warm-minimal",
            removeIds: removeIds, beforeUrl: nil, afterUrl: nil, preservationRate: 1,
            missingItems: [], errorCode: nil, createdAt: Date(), creditsLeft: 1,
            roomType: roomType, walls: walls, furniture: furniture, addFurniture: addFurniture,
            decor: decor, plants: plants, palette: palette
        )
    }

    func testDefaultsProduceTheFourBaseChipsOnly() {
        let chips = CompareAskedFor.chips(render: makeRender(), inventory: nil)
        XCTAssertEqual(chips, ["Living room", "Leave as they are", "Only what I'm keeping", "Decor as the style"])
    }

    func testUnknownRoomTypeFallsBackToRoom() {
        let chips = CompareAskedFor.chips(render: makeRender(roomType: nil), inventory: nil)
        XCTAssertEqual(chips.first, "Room")
    }

    func testAddFurnitureChipListsPicksByDisplayName() {
        let chips = CompareAskedFor.chips(
            render: makeRender(furniture: .add, addFurniture: ["sofa", "coffee_table"]),
            inventory: nil
        )
        XCTAssertTrue(chips.contains("Add: sofa, coffee table"))
    }

    func testAddFurnitureChipOmittedWhenListIsEmptyEvenIfAddIsSelected() {
        let chips = CompareAskedFor.chips(render: makeRender(furniture: .add, addFurniture: []), inventory: nil)
        XCTAssertFalse(chips.contains { $0.hasPrefix("Add:") })
    }

    func testPlantsChipOnlyAppearsWhenTrue() {
        XCTAssertTrue(CompareAskedFor.chips(render: makeRender(plants: true), inventory: nil).contains("Plants added"))
        XCTAssertFalse(CompareAskedFor.chips(render: makeRender(plants: false), inventory: nil).contains("Plants added"))
    }

    func testPaletteChipOmittedWhenAsStyle() {
        let chips = CompareAskedFor.chips(render: makeRender(palette: .asStyle), inventory: nil)
        XCTAssertFalse(chips.contains { $0.hasSuffix("colours") })
    }

    func testPaletteChipShowsFamilyWhenOverridden() {
        let chips = CompareAskedFor.chips(render: makeRender(palette: .warm), inventory: nil)
        XCTAssertTrue(chips.contains("Warm colours"))
    }

    func testRemovedChipUsesInventoryNamesForTheRemovedIds() {
        let inventory = Inventory(
            roomId: "rm_1",
            items: [
                InventoryItem(id: "D", kind: .object, name: "Floor lamp", description: "d", removable: true),
                InventoryItem(id: "E", kind: .object, name: "Side table", description: "d", removable: true),
            ],
            createdAt: Date()
        )
        let chips = CompareAskedFor.chips(render: makeRender(removeIds: ["E"]), inventory: inventory)
        XCTAssertTrue(chips.contains("Removed: Side table"))
    }

    func testRemovedChipOmittedWithoutInventoryEvenIfRemoveIdsIsNonEmpty() {
        let chips = CompareAskedFor.chips(render: makeRender(removeIds: ["E"]), inventory: nil)
        XCTAssertFalse(chips.contains { $0.hasPrefix("Removed:") })
    }
}
