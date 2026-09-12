import DesignMyRoomCore
import SwiftUI

/// "Shop your restyle" — pushed from the Unlock card (`RenderSummaryView`) via
/// `NavigationLink(value: Shopping)`. One card per item, in the order the backend
/// returns them, then the total. Pure display: `shopping` is already resolved
/// (`.ready`) by the time this screen exists. (`shopping_proto/HANDOFF.md` §3, visual
/// spec §4.4, pixel reference `shopping_proto/index.html`.)
struct ShoppingView: View {
    let shopping: Shopping

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Shop your restyle")
                        .font(.fraunces(22, weight: .medium))
                        .foregroundStyle(Color.ink)
                    Text("Similar items, not the exact ones in the picture. The cheaper option of each pair counts toward the total.")
                        .font(.system(size: 13))
                        .foregroundStyle(Color.inkSoft)
                }

                ForEach(shopping.items) { item in
                    ShoppingItemCard(item: item)
                }

                if let totalFrom = shopping.totalFrom {
                    TotalCard(totalFrom: totalFrom, currency: shopping.currency, itemCount: pricedItemCount, pricesAsOf: shopping.pricesAsOf)
                }
            }
            .padding(20)
        }
        .background(Color.paper.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
    }

    private var pricedItemCount: Int {
        shopping.items.filter { !$0.options.isEmpty }.count
    }
}

private struct ShoppingItemCard: View {
    let item: ShoppingItem
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 12) {
                AsyncImage(url: URL(string: item.cropUrl)) { phase in
                    if case .success(let image) = phase {
                        image.resizable().aspectRatio(contentMode: .fill)
                    } else {
                        Color.surface2
                    }
                }
                .frame(width: 56, height: 56)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

                VStack(alignment: .leading, spacing: 2) {
                    Text(item.name)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(Color.ink)
                    Text(metaLine)
                        .font(.system(size: 12))
                        .foregroundStyle(Color.faint)
                }
            }

            if item.options.isEmpty {
                searchRow
            } else {
                ForEach(Array(item.options.enumerated()), id: \.element.url) { index, option in
                    OptionRow(option: option, isCheapest: index == 0 && item.options.count > 1) {
                        if let url = URL(string: option.url) {
                            openURL(url)
                        }
                    }
                }
            }
        }
        .padding(14)
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

    private var metaLine: String {
        switch item.options.count {
        case 0: "no close match found"
        case 1: "1 option found · similar, not exact"
        default: "\(item.options.count) options · similar, not exact"
        }
    }

    // D2 (HANDOFF §2): no usable match — still listed, with a plain Search link
    // rather than a wrong or missing card.
    private var searchRow: some View {
        HStack {
            Text("Search for it yourself")
                .font(.system(size: 12.5))
                .foregroundStyle(Color.inkSoft)
            Spacer()
            Button {
                if let url = amazonSearchURL {
                    openURL(url)
                }
            } label: {
                Text("Search")
                    .font(.system(size: 12.5, weight: .semibold))
                    .foregroundStyle(Color.accent)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .overlay(
                        Capsule().stroke(Color.accent, lineWidth: 1.5)
                    )
            }
            .buttonStyle(.plain)
        }
        .padding(.top, 10)
        .overlay(alignment: .top) {
            Rectangle().fill(Color.line).frame(height: 1)
        }
        .padding(.top, 10)
    }

    private var amazonSearchURL: URL? {
        var components = URLComponents(string: "https://www.amazon.ca/s")
        components?.queryItems = [URLQueryItem(name: "k", value: item.name)]
        return components?.url
    }
}

private struct OptionRow: View {
    let option: ShoppingOption
    let isCheapest: Bool
    let onBuy: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(storeDisplayName.uppercased())
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Color.faint)
                    if !option.verified {
                        Text("· link not checked")
                            .font(.system(size: 11))
                            .foregroundStyle(Color.warn)
                    }
                }
                Text(option.title)
                    .font(.system(size: 12.5))
                    .foregroundStyle(Color.inkSoft)
                    .lineLimit(2)
            }

            Spacer(minLength: 8)

            VStack(alignment: .trailing, spacing: 4) {
                Text(ShoppingCurrency.string(amount: option.price, currency: "CAD"))
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(Color.ink)
                if isCheapest {
                    Text("cheapest")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(Color.accentDeep)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 1)
                        .background(Capsule().fill(Color.accentSoft))
                }
            }

            Button(action: onBuy) {
                Text("Buy")
                    .font(.system(size: 12.5, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(Capsule().fill(Color.accent))
            }
            .buttonStyle(.plain)
        }
        .padding(.top, 10)
        .overlay(alignment: .top) {
            Rectangle().fill(Color.line).frame(height: 1)
        }
        .padding(.top, 10)
    }

    private var storeDisplayName: String {
        StoreDisplayName.name(forHost: option.store)
    }
}

// HANDOFF §4.4 "Total": the preservation-card pattern — surface2 fill, line border,
// radius 16, the number in Fraunces 30 semibold accentDeep, explanation beside it.
private struct TotalCard: View {
    let totalFrom: Double
    let currency: String
    let itemCount: Int
    let pricesAsOf: String?

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text(ShoppingCurrency.string(amount: totalFrom, currency: currency))
                .font(.fraunces(30, weight: .semibold))
                .foregroundStyle(Color.accentDeep)
            Text(fineText)
                .font(.system(size: 13))
                .foregroundStyle(Color.inkSoft)
        }
        .padding(Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.surface2)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(Color.line, lineWidth: 1)
        )
    }

    private var fineText: String {
        let itemWord = itemCount == 1 ? "item" : "items"
        let dateText = ShoppingDateFormat.longForm(isoDate: pricesAsOf)
        return "\(itemCount) \(itemWord) at the cheaper option of each — prices as found \(dateText), before tax and delivery."
    }
}
