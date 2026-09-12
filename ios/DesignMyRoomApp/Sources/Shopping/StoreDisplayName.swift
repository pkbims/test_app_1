/// Store domain → display name, mirroring the approved prototype's `storeName` map
/// (`shopping_proto/index.html`) so the app doesn't show raw domains for stores we
/// already know. An unrecognized domain falls back to itself with a trailing
/// ".ca"/".com" stripped.
enum StoreDisplayName {
    private static let known: [String: String] = [
        "amazon.ca": "Amazon",
        "walmart.ca": "Walmart",
        "wayfair.ca": "Wayfair",
        "jysk.ca": "JYSK",
        "ikea.com": "IKEA",
        "bouclair.com": "Bouclair",
        "simons.ca": "Simons",
        "homedepot.ca": "Home Depot",
        "desenio.ca": "Desenio",
        "westelm.ca": "West Elm",
        "vevor.ca": "VEVOR",
        "boutiquekozy.ca": "Boutique Kozy",
        "urbanbarn.com": "Urban Barn",
        "linenchest.com": "Linen Chest",
    ]

    static func name(forHost host: String) -> String {
        let lowercased = host.lowercased()
        if let known = known[lowercased] {
            return known
        }
        for suffix in [".ca", ".com"] where lowercased.hasSuffix(suffix) {
            return String(lowercased.dropLast(suffix.count))
        }
        return host
    }
}
