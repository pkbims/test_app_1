/// Currency display for shopping prices/totals (`shopping_proto/HANDOFF.md` — every
/// example in the doc and the approved prototype shows "CA$…"). Only CAD is
/// exercised in this round; an unrecognized code falls back to "<CODE> <amount>"
/// rather than guessing a symbol.
enum ShoppingCurrency {
    static func string(amount: Double, currency: String, decimals: Int = 2) -> String {
        let formatted = String(format: "%.\(decimals)f", amount)
        return "\(symbol(for: currency))\(formatted)"
    }

    private static func symbol(for currency: String) -> String {
        switch currency {
        case "CAD": "CA$"
        case "USD": "US$"
        default: "\(currency) "
        }
    }
}
