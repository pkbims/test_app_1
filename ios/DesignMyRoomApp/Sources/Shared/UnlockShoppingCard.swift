import DesignMyRoomCore
import SwiftUI

/// What `UnlockShoppingCardLink` should show — collapses the two different places
/// shopping data comes from (the live `RenderStateMachine` sub-state while polling,
/// or a one-off `Shopping?` fetch for room history) into one shape, so the view
/// itself only has three cases to handle. `ready` with zero items collapses to
/// `.hidden`, same as `none` — HANDOFF §3: "insert the Unlock card when shopping is
/// ready and at least one item was found."
enum ShoppingCardState {
    case hidden
    case pending
    case ready(Shopping)

    init(machineState: RenderStateMachine.ShoppingState) {
        switch machineState {
        case .idle, .none:
            self = .hidden
        case .pending:
            self = .pending
        case .ready(let shopping):
            self = shopping.items.isEmpty ? .hidden : .ready(shopping)
        }
    }

    init(shopping: Shopping?) {
        guard let shopping else {
            self = .hidden
            return
        }
        switch shopping.status {
        case .pending:
            self = .pending
        case .ready:
            self = shopping.items.isEmpty ? .hidden : .ready(shopping)
        case .none:
            self = .hidden
        }
    }
}

/// The one shared home for the shopping card (`shopping_proto/HANDOFF.md` §4.3:
/// "put the card in one shared view") — both `CompareView` and `RoomDetailView`
/// render this. Each caller places this wherever its own layout calls for (the live
/// Compare screen puts it between "rooms left" and Done, per the approved
/// prototype's element order).
struct UnlockShoppingCardLink: View {
    let state: ShoppingCardState

    var body: some View {
        switch state {
        case .hidden:
            EmptyView()
        case .pending:
            ShoppingPendingPill()
        case .ready(let shopping):
            NavigationLink(value: shopping) {
                UnlockShoppingCard(shopping: shopping)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("UnlockShoppingCard")
        }
    }
}

/// While shopping is `pending` — a compact tinted pill with three bouncing dots,
/// the lightest-weight of the four loading options reviewed in
/// `shopping_proto/loading-states.html` (option C, approved 2026-09-12). Sits in
/// the exact spot the Unlock card lands in once ready, so nothing shifts.
private struct ShoppingPendingPill: View {
    var body: some View {
        HStack(spacing: 8) {
            HStack(spacing: 4) {
                BouncingDot(delay: 0)
                BouncingDot(delay: 0.2)
                BouncingDot(delay: 0.4)
            }
            Text("Finding where to buy this…")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Color.accentDeep)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(Capsule().fill(Color.accentSoft))
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("ShoppingPendingPill")
    }
}

private struct BouncingDot: View {
    let delay: Double
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var animateUp = false

    var body: some View {
        Circle()
            .fill(Color.accentDeep)
            .frame(width: 6, height: 6)
            .scaleEffect(animateUp ? 1 : 0.7)
            .opacity(animateUp ? 1 : 0.4)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.6).repeatForever(autoreverses: true).delay(delay)) {
                    animateUp = true
                }
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
