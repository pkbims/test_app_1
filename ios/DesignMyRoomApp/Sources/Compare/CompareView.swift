import DesignMyRoomCore
import SwiftUI

/// Screen 6 (done) and screen 7 (edge states), together, because both are just
/// different readings of the same `RenderStateMachine.State` the flow already holds.
/// Before/after is stacked, never a slider (U3) — output is never pixel-aligned with
/// input, so a wipe slider would be showing a false relationship.
struct CompareView: View {
    @Bindable var flow: RoomFlowViewModel

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
            RenderSummaryView(render: render)

            if let creditsLeft = render.creditsLeft {
                Text("\(creditsLeft) room\(creditsLeft == 1 ? "" : "s") left")
                    .font(.system(size: 12))
                    .foregroundStyle(Color.faint)
            }

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
