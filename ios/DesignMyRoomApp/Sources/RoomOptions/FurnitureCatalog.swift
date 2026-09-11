import DesignMyRoomCore

/// One selectable "add new pieces" option in the style screen's furniture picker.
/// `id` is the wire value that goes into `RenderCreate.addFurniture` and the prompt
/// (`options_review/HANDOFF.md` §7.2) — lower-cased, matches the backend's closed
/// list for the room type. `emoji` is UI only.
struct FurnitureType: Identifiable, Equatable {
    let id: String
    let displayName: String
    let emoji: String
}

/// The big-furniture list per room type (`options_review/HANDOFF.md` §7.2). Lamps
/// are deliberately absent everywhere — R6: "lamps are decor, not furniture."
enum FurnitureCatalog {
    static func items(for roomType: RoomType) -> [FurnitureType] {
        table[roomType] ?? table[.livingRoom]!
    }

    private static let table: [RoomType: [FurnitureType]] = [
        .livingRoom: [
            FurnitureType(id: "sofa", displayName: "Sofa", emoji: "🛋️"),
            FurnitureType(id: "armchair", displayName: "Armchair", emoji: "🪑"),
            FurnitureType(id: "coffee_table", displayName: "Coffee table", emoji: "☕"),
            FurnitureType(id: "side_table", displayName: "Side table", emoji: "🫖"),
            FurnitureType(id: "tv_unit", displayName: "TV unit", emoji: "📺"),
            FurnitureType(id: "bookcase", displayName: "Bookcase", emoji: "📚"),
            FurnitureType(id: "sideboard", displayName: "Sideboard", emoji: "🗄️"),
        ],
        .bedroom: [
            FurnitureType(id: "bed", displayName: "Bed", emoji: "🛏️"),
            FurnitureType(id: "bedside_table", displayName: "Bedside table", emoji: "🕯️"),
            FurnitureType(id: "wardrobe", displayName: "Wardrobe", emoji: "🚪"),
            FurnitureType(id: "chest_of_drawers", displayName: "Chest of drawers", emoji: "🧺"),
            FurnitureType(id: "desk", displayName: "Desk", emoji: "🖥️"),
            FurnitureType(id: "armchair", displayName: "Armchair", emoji: "🪑"),
            FurnitureType(id: "dressing_table", displayName: "Dressing table", emoji: "💄"),
        ],
        .kitchen: [
            FurnitureType(id: "dining_table", displayName: "Dining table", emoji: "🍽️"),
            FurnitureType(id: "chairs", displayName: "Chairs", emoji: "🪑"),
            FurnitureType(id: "bar_stools", displayName: "Bar stools", emoji: "🥂"),
            FurnitureType(id: "island", displayName: "Island", emoji: "🧑‍🍳"),
            FurnitureType(id: "open_shelving", displayName: "Open shelving", emoji: "🫙"),
        ],
        .diningRoom: [
            FurnitureType(id: "dining_table", displayName: "Dining table", emoji: "🍽️"),
            FurnitureType(id: "chairs", displayName: "Chairs", emoji: "🪑"),
            FurnitureType(id: "sideboard", displayName: "Sideboard", emoji: "🗄️"),
            FurnitureType(id: "bench", displayName: "Bench", emoji: "🪵"),
            FurnitureType(id: "bar_cart", displayName: "Bar cart", emoji: "🍸"),
        ],
        .homeOffice: [
            FurnitureType(id: "desk", displayName: "Desk", emoji: "🖥️"),
            FurnitureType(id: "office_chair", displayName: "Office chair", emoji: "💺"),
            FurnitureType(id: "bookcase", displayName: "Bookcase", emoji: "📚"),
            FurnitureType(id: "storage_cabinet", displayName: "Storage cabinet", emoji: "🗄️"),
            FurnitureType(id: "armchair", displayName: "Armchair", emoji: "🪑"),
        ],
        .kidsRoom: [
            FurnitureType(id: "bed", displayName: "Bed", emoji: "🛏️"),
            FurnitureType(id: "desk", displayName: "Desk", emoji: "✏️"),
            FurnitureType(id: "wardrobe", displayName: "Wardrobe", emoji: "🚪"),
            FurnitureType(id: "toy_storage", displayName: "Toy storage", emoji: "🧸"),
            FurnitureType(id: "bookcase", displayName: "Bookcase", emoji: "📚"),
            FurnitureType(id: "chair", displayName: "Chair", emoji: "🪑"),
        ],
        .nursery: [
            FurnitureType(id: "cot", displayName: "Cot", emoji: "👶"),
            FurnitureType(id: "changing_table", displayName: "Changing table", emoji: "🧷"),
            FurnitureType(id: "nursing_chair", displayName: "Nursing chair", emoji: "🪑"),
            FurnitureType(id: "wardrobe", displayName: "Wardrobe", emoji: "🚪"),
            FurnitureType(id: "shelving", displayName: "Shelving", emoji: "🧸"),
        ],
        .bathroom: [
            FurnitureType(id: "vanity", displayName: "Vanity", emoji: "🚿"),
            FurnitureType(id: "storage_cabinet", displayName: "Storage cabinet", emoji: "🗄️"),
            FurnitureType(id: "stool", displayName: "Stool", emoji: "🪑"),
            FurnitureType(id: "shelving", displayName: "Shelving", emoji: "🧴"),
        ],
        .hallway: [
            FurnitureType(id: "console_table", displayName: "Console table", emoji: "🪞"),
            FurnitureType(id: "bench", displayName: "Bench", emoji: "🪵"),
            FurnitureType(id: "coat_stand", displayName: "Coat stand", emoji: "🧥"),
            FurnitureType(id: "shoe_storage", displayName: "Shoe storage", emoji: "👟"),
        ],
        .studio: [
            FurnitureType(id: "sofa_bed", displayName: "Sofa bed", emoji: "🛋️"),
            FurnitureType(id: "desk", displayName: "Desk", emoji: "🖥️"),
            FurnitureType(id: "table", displayName: "Table", emoji: "🍽️"),
            FurnitureType(id: "chairs", displayName: "Chairs", emoji: "🪑"),
            FurnitureType(id: "shelving", displayName: "Shelving", emoji: "📚"),
            FurnitureType(id: "wardrobe", displayName: "Wardrobe", emoji: "🚪"),
        ],
        .workshop: [
            FurnitureType(id: "workbench", displayName: "Workbench", emoji: "🔨"),
            FurnitureType(id: "stool", displayName: "Stool", emoji: "🪑"),
            FurnitureType(id: "shelving", displayName: "Shelving", emoji: "🧰"),
            FurnitureType(id: "tool_cabinet", displayName: "Tool cabinet", emoji: "🗄️"),
        ],
        .serverRoom: [
            FurnitureType(id: "rack", displayName: "Rack", emoji: "🖧"),
            FurnitureType(id: "desk", displayName: "Desk", emoji: "🖥️"),
            FurnitureType(id: "chair", displayName: "Chair", emoji: "💺"),
            FurnitureType(id: "cabinet", displayName: "Cabinet", emoji: "🗄️"),
        ],
    ]
}
