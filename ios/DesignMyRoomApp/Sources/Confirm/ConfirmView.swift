import DesignMyRoomCore
import SwiftUI

/// Screen 3, reworked per the options round (`options_review/HANDOFF.md` §5.1):
/// retitled "Here's what we found", a new room-type chip row first, the
/// architecture section relabelled with a single heading-level "locked" note
/// instead of a per-row lock glyph, and a Keep | Remove segmented control per
/// object row with a live count and a live summary sentence above Continue.
///
/// Still a labelled list rather than a photo overlay — the orchestrator's
/// deviation decision (`ios/AGENT.md`): the frozen `InventoryItem` has no
/// coordinates, so there is nothing to draw outlines onto. The photo is shown for
/// reference only.
struct ConfirmView: View {
    @Bindable var flow: RoomFlowViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let url = flow.photo?.url, let imageURL = URL(string: url) {
                    AsyncImage(url: imageURL) { phase in
                        switch phase {
                        case .success(let image):
                            image.resizable().aspectRatio(contentMode: .fit)
                        case .failure:
                            Color.surface2
                        default:
                            ProgressView()
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 220)
                    .clipShape(RoundedRectangle(cornerRadius: Radius.beforeAfterImage, style: .continuous))
                    .cardShadow()
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("Here's what we found")
                        .font(.fraunces(22, weight: .medium))
                        .foregroundStyle(Color.ink)
                    Text("Check it before we restyle — nothing changes until you tap Continue")
                        .font(.eyebrow)
                        .foregroundStyle(Color.faint)
                }

                if let inventory = flow.inventory {
                    let architecture = inventory.items.filter { $0.kind == .architecture }
                    let objects = inventory.items.filter { $0.kind == .object }
                    let kept = objects.filter { !flow.removeIds.contains($0.id) }
                    let removed = objects.filter { flow.removeIds.contains($0.id) }

                    VStack(alignment: .leading, spacing: 0) {
                        OptionSection(
                            icon: "🏠",
                            title: "Room type",
                            isFirst: true,
                            helper: roomTypeHelper(detected: inventory.roomType)
                        ) {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 7) {
                                    ForEach(RoomType.allCases, id: \.self) { roomType in
                                        OptionChip(
                                            label: roomType.displayName,
                                            isSelected: flow.selectedRoomType == roomType
                                        ) {
                                            flow.selectRoomType(roomType)
                                        }
                                    }
                                }
                                .padding(.vertical, 2)
                            }
                        }

                        if !architecture.isEmpty {
                            OptionSection(
                                icon: "🔒",
                                title: "The room itself",
                                note: "locked",
                                helper: "Walls, windows and features like these stay exactly where they are. That's the whole point."
                            ) {
                                VStack(alignment: .leading, spacing: 2) {
                                    ForEach(architecture) { item in
                                        LockedRow(item: item)
                                    }
                                }
                            }
                        }

                        if !objects.isEmpty {
                            OptionSection(
                                icon: "🛋️",
                                title: "Your things",
                                note: ConfirmSummary.count(kept: kept.count, removed: removed.count),
                                helper: "Everything here stays unless you say so. Tap Remove on anything you'd like gone."
                            ) {
                                VStack(alignment: .leading, spacing: 2) {
                                    ForEach(objects) { item in
                                        ObjectRow(
                                            item: item,
                                            isRemoving: Binding(
                                                get: { flow.removeIds.contains(item.id) },
                                                set: { newValue in
                                                    if newValue != flow.removeIds.contains(item.id) {
                                                        flow.toggleRemove(item)
                                                    }
                                                }
                                            )
                                        )
                                    }
                                }
                            }
                        }
                    }

                    Text(ConfirmSummary.sentence(kept: kept.map(\.name), removed: removed.map(\.name)))
                        .font(.system(size: 12))
                        .foregroundStyle(Color.inkSoft)
                        .frame(maxWidth: .infinity, alignment: .center)
                        .multilineTextAlignment(.center)
                } else {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                        .padding(.top, 40)
                }

                if let bannerMessage = flow.bannerMessage {
                    Text(bannerMessage)
                        .font(.footnote)
                        .foregroundStyle(Color.warn)
                }

                Button {
                    flow.proceedToStylePicker()
                } label: {
                    Text("Continue")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                }
                .background(Color.accent, in: RoundedRectangle(cornerRadius: Radius.button, style: .continuous))
                .disabled(flow.inventory == nil)
                .opacity(flow.inventory == nil ? 0.5 : 1)
                .padding(.top, 4)
            }
            .padding(20)
        }
        .background(Color.paper.ignoresSafeArea())
    }

    private func roomTypeHelper(detected: RoomType?) -> String {
        if let detected {
            "We think it's a \(detected.displayName.lowercased()). Tap another if we're wrong."
        } else {
            "What kind of room is this?"
        }
    }
}

private extension Font {
    static var eyebrow: Font { .system(size: 11, weight: .semibold, design: .monospaced) }
}

/// An architecture row — informational only, no per-row lock glyph (the section
/// heading's "locked" note carries that now).
private struct LockedRow: View {
    let item: InventoryItem

    var body: some View {
        HStack(spacing: Spacing.m) {
            letterBadge
            Text(item.name)
                .font(.system(size: 15))
                .foregroundStyle(Color.ink)
            Spacer()
        }
        .padding(.vertical, Spacing.sm)
        .padding(.horizontal, Spacing.m)
        .opacity(0.85)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(Color.surface2)
        )
    }

    private var letterBadge: some View {
        Text(item.id)
            .font(.system(size: 12, weight: .semibold, design: .monospaced))
            .foregroundStyle(Color.inkSoft)
            .frame(width: 24, height: 24)
            .background(
                RoundedRectangle(cornerRadius: Radius.letterBadge, style: .continuous)
                    .fill(Color.surface2)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Radius.letterBadge, style: .continuous)
                    .stroke(Color.line, lineWidth: 1)
            )
    }
}

/// An object row — Keep | Remove segmented control, default Keep (HANDOFF §5.1).
private struct ObjectRow: View {
    let item: InventoryItem
    @Binding var isRemoving: Bool

    var body: some View {
        HStack(spacing: Spacing.m) {
            letterBadge
            Text(item.name)
                .font(.system(size: 15))
                .strikethrough(isRemoving)
                .foregroundStyle(isRemoving ? Color.faint : Color.ink)
            Spacer()
            KeepRemoveControl(isRemoving: $isRemoving)
        }
        .padding(.vertical, Spacing.sm)
    }

    private var letterBadge: some View {
        Text(item.id)
            .font(.system(size: 12, weight: .semibold, design: .monospaced))
            .foregroundStyle(Color.inkSoft)
            .frame(width: 24, height: 24)
            .background(
                RoundedRectangle(cornerRadius: Radius.letterBadge, style: .continuous)
                    .fill(Color.surface2)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Radius.letterBadge, style: .continuous)
                    .stroke(Color.line, lineWidth: 1)
            )
    }
}
