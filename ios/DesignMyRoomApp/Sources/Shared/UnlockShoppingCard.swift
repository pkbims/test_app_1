import DesignMyRoomCore
import SwiftUI

/// The one shared home for the shopping card (`shopping_proto/HANDOFF.md` §4.3:
/// "put the card in one shared view") — both `CompareView` and `RoomDetailView`
/// render this, passing whatever `Shopping?` they have (from live polling, or a
/// one-off fetch for history). Renders nothing unless shopping is `ready` with at
/// least one item — `none`, `pending`, and ready-with-zero-items all show nothing
/// (HANDOFF §3). Each caller places this wherever its own layout calls for (the
/// live Compare screen puts it between "rooms left" and Done, per the approved
/// prototype's element order).
struct UnlockShoppingCardLink: View {
    let shopping: Shopping?

    var body: some View {
        if let shopping, shopping.status == .ready, !shopping.items.isEmpty {
            NavigationLink(value: shopping) {
                UnlockShoppingCard(shopping: shopping)
            }
            .buttonStyle(.plain)
        }
    }
}

/// The "N new items found in your restyle" card itself (`shopping_proto/HANDOFF.md`
/// §2 D1, §4.4). Purely presentational — used by `UnlockShoppingCardLink` above.
private struct UnlockShoppingCard: View {
    let shopping: Shopping

    private var itemCount: Int { shopping.items.count }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                thumbnails
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(itemCount) new item\(itemCount == 1 ? "" : "s") found in your restyle")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(Color.ink)
                    Text("See where to buy something similar — from about \(fromPriceText) for all of them.")
                        .font(.system(size: 13))
                        .foregroundStyle(Color.inkSoft)
                }
            }

            Text("Unlock")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Color.accent)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .overlay(
                    RoundedRectangle(cornerRadius: Radius.button, style: .continuous)
                        .stroke(Color.accent, lineWidth: 1.5)
                )
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: Radius.feedCard, style: .continuous)
                .fill(Color.surface)
        )
        .overlay(
            RoundedRectangle(cornerRadius: Radius.feedCard, style: .continuous)
                .stroke(Color.line, lineWidth: 1)
        )
        .cardShadow()
    }

    private var thumbnails: some View {
        HStack(spacing: -12) {
            ForEach(Array(shopping.items.prefix(3))) { item in
                AsyncImage(url: URL(string: item.cropUrl)) { phase in
                    if case .success(let image) = phase {
                        image.resizable().aspectRatio(contentMode: .fill)
                    } else {
                        Color.surface2
                    }
                }
                .frame(width: 40, height: 40)
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .stroke(Color.surface, lineWidth: 2)
                )
            }
        }
    }

    /// Rounded to the nearest whole unit — "from about CA$609", not "…$609.14" —
    /// matching the approved prototype's card copy exactly. `ShoppingView`'s own
    /// total card shows the full two-decimal `totalFrom` verbatim instead.
    private var fromPriceText: String {
        guard let totalFrom = shopping.totalFrom else { return "—" }
        return ShoppingCurrency.string(amount: totalFrom.rounded(), currency: shopping.currency, decimals: 0)
    }
}
