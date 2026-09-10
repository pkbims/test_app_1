import DesignMyRoomCore
import SwiftUI

/// Screen 4: scrollable image cards with generic sample photos (U4), a preset style
/// id plus an optional free-text prompt (≤280 chars). Sample photos are bundled in
/// `Assets.xcassets` (see `ios/DesignMyRoomApp/SourceAssets/StyleSamples/README.md`
/// for their origin and how they're compressed); a style with no matching asset
/// falls back to a plain tinted placeholder (`StyleImageResolver`, tested in
/// `DesignMyRoomCore`) rather than a broken image reference — swap art in or out
/// without touching anything else, since restyling the UI must not touch the flow
/// logic (CLAUDE.md).
struct StylePickerView: View {
    @Bindable var flow: RoomFlowViewModel

    private let promptLimit = 280

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Pick a style")
                .font(.fraunces(21, weight: .medium))
                .foregroundStyle(Color.ink)
                .padding(.horizontal, 20)
                .padding(.top, 16)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 14) {
                    ForEach(Style.all) { style in
                        StyleCard(style: style, isSelected: flow.selectedStyleId == style.id) {
                            flow.selectStyle(style)
                        }
                    }
                }
                .padding(.horizontal, 20)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Anything else? (optional)")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(Color.ink)
                TextField("e.g. \"more natural light\"", text: $flow.prompt, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(3, reservesSpace: true)
                    .onChange(of: flow.prompt) { _, newValue in
                        if newValue.count > promptLimit {
                            flow.prompt = String(newValue.prefix(promptLimit))
                        }
                    }
                Text("\(flow.prompt.count)/\(promptLimit) — can't override what's protected")
                    .font(.system(size: 12))
                    .foregroundStyle(Color.faint)
            }
            .padding(.horizontal, 20)

            if let bannerMessage = flow.bannerMessage {
                Text(bannerMessage)
                    .font(.footnote)
                    .foregroundStyle(Color.warn)
                    .padding(.horizontal, 20)
            }

            Spacer()

            Button {
                Task { await flow.startRender() }
            } label: {
                Text("Restyle this room")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .background(Color.accent, in: RoundedRectangle(cornerRadius: Radius.button, style: .continuous))
            .disabled(!flow.canStartRender)
            .opacity(flow.canStartRender ? 1 : 0.5)
            .padding(.horizontal, 20)
            .padding(.bottom, 20)
        }
        .background(Color.paper.ignoresSafeArea())
    }
}

// HANDOFF §2 "Pick a style": cards become 118×150 portrait (not square — the
// bundled photos are real interiors and read better tall). Selection state moves
// from a thin ring overlay to a filled accent circular check-badge in the
// top-right corner. `StyleImageResolver`'s fallback behavior is unchanged.
private struct StyleCard: View {
    let style: Style
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(spacing: Spacing.s) {
                ZStack(alignment: .topTrailing) {
                    cardArt
                        .frame(width: 118, height: 150)
                        .clipShape(RoundedRectangle(cornerRadius: Radius.styleCard, style: .continuous))

                    if isSelected {
                        ZStack {
                            Circle().fill(Color.accent)
                            Image(systemName: "checkmark")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundStyle(.white)
                        }
                        .frame(width: 22, height: 22)
                        .padding(6)
                    }
                }
                Text(style.displayName)
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(Color.ink)
            }
        }
        .buttonStyle(.plain)
    }

    /// The real sample photo when one's bundled; otherwise the original tinted
    /// placeholder, so a style with no artwork yet (a 7th style added to
    /// `Style.all`) still renders a card instead of a broken image or a crash.
    @ViewBuilder
    private var cardArt: some View {
        if let assetName = StyleImageResolver.imageAssetName(for: style.id) {
            Image(assetName)
                .resizable()
                .aspectRatio(contentMode: .fill)
        } else {
            RoundedRectangle(cornerRadius: Radius.styleCard, style: .continuous)
                .fill(LinearGradient(colors: [Color.accent.opacity(0.35), Color.accent.opacity(0.15)], startPoint: .topLeading, endPoint: .bottomTrailing))
        }
    }
}
