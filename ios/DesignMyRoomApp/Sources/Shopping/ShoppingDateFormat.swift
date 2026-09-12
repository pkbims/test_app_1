import Foundation

/// Formats the shopping total card's "prices as found …" date. `Shopping.pricesAsOf`
/// is a bare `"yyyy-MM-dd"` string, not a timestamp (`shopping_proto/HANDOFF.md`
/// §4.1) — this turns it into the long form the copy uses, e.g. "12 September 2026"
/// (HANDOFF §2 D4).
enum ShoppingDateFormat {
    private static let isoDateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    private static let longFormFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "d MMMM yyyy"
        return formatter
    }()

    static func longForm(isoDate: String?) -> String {
        guard let isoDate, let date = isoDateFormatter.date(from: isoDate) else {
            return "an earlier date"
        }
        return longFormFormatter.string(from: date)
    }
}
