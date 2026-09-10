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
                .font(.title2.weight(.semibold))
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
                    .font(.subheadline.weight(.medium))
                TextField("e.g. \"more natural light\"", text: $flow.prompt, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(3, reservesSpace: true)
                    .onChange(of: flow.prompt) { _, newValue in
                        if newValue.count > promptLimit {
                            flow.prompt = String(newValue.prefix(promptLimit))
                        }
                    }
                Text("\(flow.prompt.count)/\(promptLimit) — can't override what's protected")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 20)

            if let bannerMessage = flow.bannerMessage {
                Text(bannerMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .padding(.horizontal, 20)
            }

            Spacer()

            Button {
                Task { await flow.startRender() }
            } label: {
                Text("Restyle this room")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!flow.canStartRender)
            .padding(.horizontal, 20)
            .padding(.bottom, 20)
        }
    }
}

private struct StyleCard: View {
    let style: Style
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(spacing: 8) {
                cardArt
                    .frame(width: 130, height: 130)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay {
                        if isSelected {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.title)
                                .foregroundStyle(.white, Color.accentColor)
                        }
                    }
                Text(style.displayName)
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(.primary)
            }
            .padding(6)
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(isSelected ? Color.accentColor : .clear, lineWidth: 2)
            )
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
            RoundedRectangle(cornerRadius: 12)
                .fill(LinearGradient(colors: [.accentColor.opacity(0.35), .accentColor.opacity(0.15)], startPoint: .topLeading, endPoint: .bottomTrailing))
        }
    }
}
