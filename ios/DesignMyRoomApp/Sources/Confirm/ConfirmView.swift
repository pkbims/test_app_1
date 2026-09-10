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
                            Color.secondary.opacity(0.15)
                        default:
                            ProgressView()
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 220)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                Text("What's in this room")
                    .font(.title2.weight(.semibold))
                Text("The architecture stays exactly where it is. Tap anything else you'd like removed — everything else is kept.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

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
                        .foregroundStyle(.red)
                }

                Button {
                    flow.proceedToStylePicker()
                } label: {
                    Text("Continue")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(flow.inventory == nil)
                .padding(.top, 12)
            }
            .padding(20)
        }
    }
}

private struct SectionHeader: View {
    let title: String
    var body: some View {
        Text(title.uppercased())
            .font(.caption.weight(.semibold))
            .foregroundStyle(.secondary)
            .padding(.top, 8)
    }
}

private struct InventoryRow: View {
    let item: InventoryItem
    let isRemoving: Bool
    let isLocked: Bool
    let onToggle: () -> Void

    var body: some View {
        HStack {
            Text(item.id)
                .font(.system(.body, design: .monospaced).weight(.semibold))
                .frame(width: 28, alignment: .leading)
                .foregroundStyle(.secondary)
            Text(item.name)
                .strikethrough(isRemoving)
                .foregroundStyle(isRemoving ? .secondary : .primary)
            Spacer()
            if isLocked {
                Image(systemName: "lock.fill")
                    .foregroundStyle(.secondary)
                    .font(.footnote)
            } else {
                Button(isRemoving ? "Removed" : "Remove", role: isRemoving ? nil : .destructive) {
                    onToggle()
                }
                .font(.footnote.weight(.medium))
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
        .padding(.vertical, 6)
    }
}
