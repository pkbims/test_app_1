import DesignMyRoomCore
import SwiftUI

/// Screen 4: scrollable image cards with generic sample photos (U4), a preset style
/// id plus an optional free-text prompt (≤280 chars), plus — per the options round
/// (`options_review/HANDOFF.md` §5.2) — five small controls inserted between the
/// style rail and the free-text field: walls, furniture (with a reveal-on-select
/// picker filtered by room type), decor, plants, and colour. Every control defaults
/// to today's behaviour except walls, which defaults to "Leave as they are" — a
/// deliberate change (§1.1), not a bug.
struct StylePickerView: View {
    @Bindable var flow: RoomFlowViewModel

    private let promptLimit = 280

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Text("Pick a style")
                    .font(.fraunces(21, weight: .medium))
                    .foregroundStyle(Color.ink)
                    .padding(.horizontal, 20)
                    .padding(.top, 16)
                    .padding(.bottom, 12)

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

                Text("Then, a few choices — or skip straight to Restyle")
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Color.faint)
                    .padding(.horizontal, 20)
                    .padding(.top, 10)
                    .padding(.bottom, 4)

                VStack(alignment: .leading, spacing: 0) {
                    OptionSection(icon: "🎨", title: "Walls", isFirst: true, helper: wallsHelper) {
                        OptionSegmentedControl(
                            options: [(WallsOption.repaint, "Repaint"), (WallsOption.leave, "Leave as they are")],
                            selection: Binding(get: { flow.walls }, set: flow.setWalls)
                        )
                    }

                    OptionSection(icon: "🛋️", title: "Furniture", helper: furnitureHelper) {
                        VStack(alignment: .leading, spacing: 10) {
                            OptionSegmentedControl(
                                options: [(FurnitureOption.keepOnly, "Only what I'm keeping"), (FurnitureOption.add, "Add new pieces")],
                                selection: Binding(get: { flow.furniture }, set: flow.setFurnitureOption)
                            )
                            if flow.furniture == .add {
                                FurniturePicker(flow: flow)
                            }
                        }
                    }

                    OptionSection(
                        icon: "🖼️",
                        title: "Decor",
                        note: "art, lamps, cushions, vases, books, mirrors",
                        helper: decorHelper
                    ) {
                        OptionSegmentedControl(
                            options: [
                                (DecorLevel.minimal, "Minimal"),
                                (DecorLevel.asStyle, "As the style"),
                                (DecorLevel.plenty, "Plenty"),
                            ],
                            selection: Binding(get: { flow.decor }, set: flow.setDecor)
                        )
                    }

                    OptionSection(
                        icon: "🪴",
                        title: "Add plants",
                        trailingAccessory: AnyView(PlantsSwitch(flow: flow)),
                        helper: plantsHelper
                    ) {
                        EmptyView()
                    }

                    OptionSection(icon: "🌈", title: "Colour", note: "optional", helper: paletteHelper) {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 7) {
                                ForEach(PaletteOption.allCases, id: \.self) { option in
                                    OptionChip(label: paletteLabel(option), isSelected: flow.palette == option) {
                                        flow.setPalette(option)
                                    }
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }

                    OptionSection(icon: "✏️", title: "Anything else?", note: "optional", helper: "") {
                        VStack(alignment: .leading, spacing: 6) {
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
                    }
                }
                .padding(.horizontal, 20)

                if let bannerMessage = flow.bannerMessage {
                    Text(bannerMessage)
                        .font(.footnote)
                        .foregroundStyle(Color.warn)
                        .padding(.horizontal, 20)
                        .padding(.top, 8)
                }

                Spacer(minLength: 20)
            }
        }
        .safeAreaInset(edge: .bottom) {
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
            .padding(.top, 8)
            .padding(.bottom, 12)
            .background(.ultraThinMaterial)
        }
        .background(Color.paper.ignoresSafeArea())
    }

    // MARK: - Helper copy (options_review/HANDOFF.md §6, shared with the prompt)

    private var wallsHelper: String {
        switch flow.walls {
        case .repaint: "We'll repaint the walls in colours the style uses."
        case .leave: "Wall colour stays exactly as it is. Good if you rent."
        }
    }

    private var furnitureHelper: String {
        switch flow.furniture {
        case .keepOnly: "Just the pieces you kept, refinished to match the style. Nothing new."
        case .add: "We'll add furniture the room is missing, in this style, around what you kept."
        }
    }

    private var decorHelper: String {
        switch flow.decor {
        case .minimal: "A few pieces, each chosen on purpose. One artwork, one lamp, one object. Most surfaces clear."
        case .asStyle: "However much this style normally has. Japandi: one vase. Maximalism: a wall of frames."
        case .plenty: "More than the style's usual. Layered art, lamps, cushions, objects on every surface."
        }
    }

    private var plantsHelper: String {
        flow.plants ? "A few plants, placed where they'd naturally sit." : "No plants added."
    }

    private var paletteHelper: String {
        switch flow.palette {
        case .asStyle: "Whatever colours the style calls for."
        case .neutral: "Whites, greys, beiges. Colour from wood and texture only."
        case .warm: "Creams, terracotta, honey wood, soft browns."
        case .cool: "Blues, greens, slate greys, pale wood."
        case .bold: "Strong, saturated colour on walls or big pieces."
        }
    }

    private func paletteLabel(_ option: PaletteOption) -> String {
        switch option {
        case .asStyle: "As the style"
        case .neutral: "Neutral"
        case .warm: "Warm"
        case .cool: "Cool"
        case .bold: "Bold"
        }
    }
}

/// "Add plants" — a heading with a switch on the same line (HANDOFF §5.2), passed as
/// `OptionSection.trailingAccessory` so it sits directly on the heading row without
/// any layout hackery. Not a native `Toggle` — a small pill switch matching the
/// prototype's `.sw` exactly, same visual language as the segmented controls and
/// chips around it.
private struct PlantsSwitch: View {
    @Bindable var flow: RoomFlowViewModel

    var body: some View {
        Button {
            flow.setPlants(!flow.plants)
        } label: {
            Capsule()
                .fill(flow.plants ? Color.accent : Color.line)
                .frame(width: 44, height: 26)
                .overlay(alignment: flow.plants ? .trailing : .leading) {
                    Circle()
                        .fill(.white)
                        .frame(width: 22, height: 22)
                        .shadow(color: .black.opacity(0.25), radius: 1.5, x: 0, y: 1)
                        .padding(2)
                }
        }
        .buttonStyle(.plain)
    }
}

/// "What's missing?" — the reveal-on-select multi-select chip row, filtered by the
/// currently-selected room type (`options_review/HANDOFF.md` §7.2). This is the
/// control the one required UI test exercises (§5.5): reach this screen, select
/// "Add new pieces", assert this picker appears.
private struct FurniturePicker: View {
    @Bindable var flow: RoomFlowViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text("What's missing?")
                    .font(.fraunces(14, weight: .semibold))
                    .foregroundStyle(Color.ink)
                Text("pick any")
                    .font(.system(size: 11.5))
                    .foregroundStyle(Color.faint)
            }
            .accessibilityIdentifier("FurniturePicker")

            FlowChips(items: FurnitureCatalog.items(for: flow.selectedRoomType ?? .livingRoom)) { item in
                OptionChip(
                    label: "\(item.emoji) \(item.displayName)",
                    isSelected: flow.addFurniture.contains(item.id)
                ) {
                    flow.toggleAddFurniture(item.id)
                }
            }

            Text(furnHelp)
                .font(.system(size: 12))
                .foregroundStyle(Color.inkSoft)
        }
        .padding(.top, 2)
    }

    private var furnHelp: String {
        let picked = FurnitureCatalog.items(for: flow.selectedRoomType ?? .livingRoom)
            .filter { flow.addFurniture.contains($0.id) }
            .map { $0.displayName.lowercased() }
        if picked.isEmpty {
            return "Pick what the room needs. We'll add only those, in this style, sized for the room."
        }
        return "We'll add \(picked.joined(separator: ", ")) — nothing else — in this style, sized for the room."
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
