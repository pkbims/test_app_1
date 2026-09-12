import DesignMyRoomCore
import SwiftUI

/// Screen 6 (done) and screen 7 (edge states), together, because both are just
/// different readings of the same `RenderStateMachine.State` the flow already holds.
/// Before/after is stacked, never a slider (U3) — output is never pixel-aligned with
/// input, so a wipe slider would be showing a false relationship.
struct CompareView: View {
    @Bindable var flow: RoomFlowViewModel

    private var shoppingIfReady: Shopping? {
        if case .ready(let shopping) = flow.shoppingState { shopping } else { nil }
    }

    var body: some View {
        ScrollView {
            switch flow.renderState {
            case .done(let render):
                doneContent(render)
            case .renderFailed(let render):
                renderFailedContent(render)
            case .requestFailed(let failure):
                requestFailedContent(failure)
            default:
                ProgressView().padding(40)
            }
        }
        .background(Color.paper.ignoresSafeArea())
    }

    @ViewBuilder
    private func doneContent(_ render: Render) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            CompareTitle(render: render)
            RenderSummaryView(render: render)

            AskedForRow(render: render, inventory: flow.inventory)

            if let creditsLeft = render.creditsLeft {
                Text("\(creditsLeft) room\(creditsLeft == 1 ? "" : "s") left")
                    .font(.system(size: 12))
                    .foregroundStyle(Color.faint)
            }

            UnlockShoppingCardLink(shopping: shoppingIfReady)

            // Per the product decision: an existing room becomes read-only history
            // once you leave it — a new render always starts a brand-new room via
            // Home's "New Room", not a "restyle this room again" from here.
            Button {
                flow.finish()
            } label: {
                Text("Done")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .background(Color.accent, in: RoundedRectangle(cornerRadius: Radius.button, style: .continuous))
            .padding(.top, 8)
        }
        .padding(20)
    }

    @ViewBuilder
    private func renderFailedContent(_ render: Render) -> some View {
        edgeState(
            symbol: "exclamationmark.triangle",
            message: ErrorCopy.message(for: .renderFailed),
            detail: render.missingItems?.isEmpty == false
                ? "Missing: \(render.missingItems!.joined(separator: ", "))"
                : nil
        )
    }

    @ViewBuilder
    private func requestFailedContent(_ failure: RenderStateMachine.RequestFailure) -> some View {
        switch failure {
        case .signedOut:
            edgeState(symbol: "person.crop.circle.badge.exclamationmark", message: ErrorCopy.message(for: .appleTokenInvalid), detail: nil)
        case .api(let apiError):
            edgeState(symbol: "exclamationmark.triangle", message: ErrorCopy.message(for: apiError), detail: nil)
        case .other:
            edgeState(symbol: "wifi.exclamationmark", message: "Something went wrong. Please try again.", detail: nil)
        }
    }

    // HANDOFF §2 "Compare — edge states": container becomes a plain `surface` card,
    // and "Try again" is a recovery action, not the primary flow — a ghost
    // (outlined, not filled) button instead of a full-width filled one. Same
    // three-way switch, same `ErrorCopy` messages as before.
    @ViewBuilder
    private func edgeState(symbol: String, message: String, detail: String?) -> some View {
        VStack(spacing: 16) {
            Image(systemName: symbol)
                .font(.system(size: 40))
                .foregroundStyle(Color.faint)
            Text(message)
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(Color.ink)
                .multilineTextAlignment(.center)
            if let detail {
                Text(detail)
                    .font(.system(size: 13))
                    .foregroundStyle(Color.inkSoft)
                    .multilineTextAlignment(.center)
            }
            Button {
                flow.returnToStylePickerForRestyle()
            } label: {
                Text("Try again")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(Color.accent)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            }
            .overlay(
                RoundedRectangle(cornerRadius: Radius.button, style: .continuous)
                    .stroke(Color.accent, lineWidth: 1.5)
            )
        }
        .padding(28)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(Color.surface)
        )
        .padding(20)
    }
}

/// "Your {room type}, {style}" — the compare screen's headline (HANDOFF §5.4).
private struct CompareTitle: View {
    let render: Render

    var body: some View {
        Text("Your \(roomTypeText), \(styleDisplayName)")
            .font(.fraunces(22, weight: .medium))
            .foregroundStyle(Color.ink)
    }

    private var roomTypeText: String {
        render.roomType?.displayName.lowercased() ?? "room"
    }

    private var styleDisplayName: String {
        Style.all.first { $0.id == render.style }?.displayName ?? render.style
    }
}

/// The small, optional "What you asked for" readback row — faint chips, purely a
/// read-back, no interaction (HANDOFF §5.4).
private struct AskedForRow: View {
    let render: Render
    let inventory: Inventory?

    var body: some View {
        let chips = CompareAskedFor.chips(render: render, inventory: inventory)
        if !chips.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                Text("What you asked for")
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Color.faint)
                FlowChips(items: chips.indexedForDisplay) { chip in
                    Text(chip.value)
                        .font(.system(size: 11.5, weight: .medium))
                        .foregroundStyle(Color.inkSoft)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(Capsule().fill(Color.surface2))
                        .overlay(Capsule().stroke(Color.line, lineWidth: 1))
                }
            }
        }
    }
}

private extension [String] {
    /// `FlowChips` needs `Identifiable` items; chip text can repeat in principle, so
    /// pair each with its index rather than assuming uniqueness.
    var indexedForDisplay: [IndexedChip] {
        enumerated().map { IndexedChip(id: $0.offset, value: $0.element) }
    }
}

private struct IndexedChip: Identifiable {
    let id: Int
    let value: String
}
