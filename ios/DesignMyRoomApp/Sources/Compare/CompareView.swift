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
    }

    @ViewBuilder
    private func doneContent(_ render: Render) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            stackedImages(before: render.beforeUrl, after: render.afterUrl)

            if let rate = render.preservationRate {
                HStack {
                    Text("Preservation")
                        .font(.subheadline.weight(.medium))
                    Spacer()
                    Text("\(Int((rate * 100).rounded()))%")
                        .font(.subheadline.weight(.semibold))
                }
            }

            if let missing = render.missingItems, !missing.isEmpty {
                Text("Not found in the result: \(missing.joined(separator: ", "))")
                    .font(.footnote)
                    .foregroundStyle(.orange)
            }

            if let creditsLeft = render.creditsLeft {
                Text("\(creditsLeft) room\(creditsLeft == 1 ? "" : "s") left")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 12) {
                Button {
                    flow.returnToStylePickerForRestyle()
                } label: {
                    Text("Restyle").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)

                Button {
                    flow.startOver()
                } label: {
                    Text("New room").frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
            .controlSize(.large)
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

    @ViewBuilder
    private func edgeState(symbol: String, message: String, detail: String?) -> some View {
        VStack(spacing: 16) {
            Image(systemName: symbol)
                .font(.system(size: 44))
                .foregroundStyle(.secondary)
            Text(message)
                .font(.title3.weight(.medium))
                .multilineTextAlignment(.center)
            if let detail {
                Text(detail)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            Button {
                flow.returnToStylePickerForRestyle()
            } label: {
                Text("Try again").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
        }
        .padding(40)
    }

    @ViewBuilder
    private func stackedImages(before: String?, after: String?) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            labelledImage(title: "Before", urlString: before)
            labelledImage(title: "After", urlString: after)
        }
    }

    @ViewBuilder
    private func labelledImage(title: String, urlString: String?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased())
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            if let urlString, let url = URL(string: urlString) {
                AsyncImage(url: url) { phase in
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
                .frame(minHeight: 180)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }
}
