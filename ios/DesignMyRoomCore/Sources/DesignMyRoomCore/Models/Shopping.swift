import Foundation

/// Mirrors `components/schemas/ShoppingStatus` (`shopping_proto/HANDOFF.md` §4.1).
/// `pending` while the job hasn't finished; `ready` once it has, even with zero
/// items; `none` when shopping was never attempted or failed after retries. The
/// client treats `none` and `ready`-with-no-items the same: no card.
public enum ShoppingStatus: String, Codable, Equatable, Hashable, Sendable {
    case pending
    case ready
    case none
}

/// Mirrors `components/schemas/ShoppingOption`. Never more than two per item,
/// cheapest first. `verified == false` means the store blocks automated checks
/// (HANDOFF §2 D3) — shown with a "link not checked" mark, not hidden.
public struct ShoppingOption: Codable, Equatable, Hashable, Sendable {
    public let store: String
    public let title: String
    public let price: Double
    public let url: String
    public let verified: Bool

    public init(store: String, title: String, price: Double, url: String, verified: Bool) {
        self.store = store
        self.title = title
        self.price = price
        self.url = url
        self.verified = verified
    }
}

/// Mirrors `components/schemas/ShoppingItem`. `options` is empty for a D2 item — one
/// the pipeline found no acceptable match for; still shown, with a Search link
/// instead of a price (HANDOFF §2 D2).
public struct ShoppingItem: Codable, Equatable, Hashable, Identifiable, Sendable {
    public let itemId: String
    public let name: String
    public let cropUrl: String
    public let options: [ShoppingOption]

    public var id: String { itemId }

    public init(itemId: String, name: String, cropUrl: String, options: [ShoppingOption]) {
        self.itemId = itemId
        self.name = name
        self.cropUrl = cropUrl
        self.options = options
    }
}

/// Mirrors `components/schemas/Shopping`. Returned by
/// `GET /v1/renders/{render_id}/shopping`, polled by `RenderStateMachine` on the same
/// 2s cadence as the render itself, starting once the render is `done` and stopping
/// on `ready`/`none`.
public struct Shopping: Codable, Equatable, Hashable, Sendable {
    public let renderId: String
    public let status: ShoppingStatus
    /// Date-only (`"2026-09-12"`), not a full timestamp — kept as a plain string
    /// rather than `Date` since it's only ever shown verbatim in the total card's
    /// fine print, never computed with. `nil` unless `status == .ready`.
    public let pricesAsOf: String?
    /// CAD, already rounded to cents by the backend. `nil` unless `ready` and at
    /// least one item has an option. The client displays this value verbatim
    /// (HANDOFF §3 "Total") — see `recomputedTotalFrom` for the test-only check.
    public let totalFrom: Double?
    public let currency: String
    public let items: [ShoppingItem]

    public init(
        renderId: String,
        status: ShoppingStatus,
        pricesAsOf: String?,
        totalFrom: Double?,
        currency: String,
        items: [ShoppingItem]
    ) {
        self.renderId = renderId
        self.status = status
        self.pricesAsOf = pricesAsOf
        self.totalFrom = totalFrom
        self.currency = currency
        self.items = items
    }

    /// Σ over items with ≥1 option of the cheapest option's price, rounded to cents —
    /// the same rule the backend uses for `totalFrom`. Test-only: the client always
    /// *displays* `totalFrom` verbatim and must never show this instead if the two
    /// disagree (HANDOFF §3 "Total" — "the client displays it and may recompute for
    /// a unit test but must not display its own number if they disagree").
    public var recomputedTotalFrom: Double? {
        let priced = items.compactMap { $0.options.map(\.price).min() }
        guard !priced.isEmpty else { return nil }
        let sum = priced.reduce(0, +)
        return (sum * 100).rounded() / 100
    }
}
