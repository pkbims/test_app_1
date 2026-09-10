import DesignMyRoomCore
import SwiftUI

/// Screen 3, as a labelled list rather than a photo overlay — the orchestrator's
/// deviation decision (`ios/AGENT.md`): the frozen `InventoryItem` has no
/// coordinates, so there is nothing to draw the outlines onto. The photo is shown for
/// reference only; architecture rows are informational ("locked" — never
/// removable); object rows toggle into `removeIds`. Everything not toggled is kept.
struct ConfirmView: View {
    @Bindable var flow: RoomFlowViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
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

                Text("What's in this room")
                    .font(.fraunces(21, weight: .medium))
                    .foregroundStyle(Color.ink)
                Text("The architecture stays exactly where it is. Tap anything else you'd like removed — everything else is kept.")
                    .font(.system(size: 14))
                    .foregroundStyle(Color.inkSoft)

                if let inventory = flow.inventory {
                    let architecture = inventory.items.filter { $0.kind == .architecture }
                    let objects = inventory.items.filter { $0.kind == .object }

                    if !architecture.isEmpty {
                        SectionHeader(title: "Architecture — locked")
                        ForEach(architecture) { item in
                            InventoryRow(item: item, isRemoving: false, isLocked: true) {}
                        }
                    }
                    if !objects.isEmpty {
                        SectionHeader(title: "Objects")
                        ForEach(objects) { item in
                            InventoryRow(
                                item: item,
                                isRemoving: flow.removeIds.contains(item.id),
                                isLocked: false
                            ) {
                                flow.toggleRemove(item)
                            }
                        }
                    }
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
                .padding(.top, 12)
            }
            .padding(20)
        }
        .background(Color.paper.ignoresSafeArea())
    }
}

private struct SectionHeader: View {
    let title: String
    var body: some View {
        Text(title.uppercased())
            .font(.system(size: 11, weight: .semibold, design: .monospaced))
            .tracking(0.8)
            .foregroundStyle(Color.faint)
            .padding(.top, 8)
    }
}

// HANDOFF §2 "What's in this room (Confirm)": architecture rows get a recessed
// `surface2` background in addition to the lock glyph so "locked" reads as a
// visual state, not just an icon; object rows stay on plain background so the two
// groups read apart at a glance. The inventory letter moves from plain monospace
// text into a small rounded badge; Remove/Removed becomes a pill chip instead of a
// bordered button. `onToggle`/`removeIds` are unchanged — styling only.
private struct InventoryRow: View {
    let item: InventoryItem
    let isRemoving: Bool
    let isLocked: Bool
    let onToggle: () -> Void

    var body: some View {
        HStack(spacing: Spacing.m) {
            letterBadge
            Text(item.name)
                .font(.system(size: 15))
                .strikethrough(isRemoving)
                .foregroundStyle(isRemoving ? Color.faint : Color.ink)
            Spacer()
            if isLocked {
                Image(systemName: "lock.fill")
                    .foregroundStyle(Color.faint)
                    .font(.system(size: 13))
            } else {
                removeChip
            }
        }
        .padding(.vertical, Spacing.sm)
        .padding(.horizontal, isLocked ? Spacing.m : 0)
        .opacity(isLocked ? 0.85 : 1)
        .background {
            if isLocked {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(Color.surface2)
            }
        }
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

    private var removeChip: some View {
        Button(action: onToggle) {
            Text(isRemoving ? "Removed" : "Remove")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(isRemoving ? Color.inkSoft : Color.accentDeep)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(Capsule().fill(isRemoving ? Color.surface2 : Color.accentSoft))
        }
        .buttonStyle(.plain)
    }
}
