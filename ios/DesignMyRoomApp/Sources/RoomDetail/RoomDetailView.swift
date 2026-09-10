import DesignMyRoomCore
import SwiftUI

/// Read-only room history (product decision: no "restyle again" from here for v1 —
/// a new render always starts a brand-new room via Home's "New Room"). Every past
/// render for this room: style, preservation rate, before/after — reusing
/// `RenderSummaryView`, the same view the live flow's Compare screen uses for a
/// render that just finished.
struct RoomDetailView: View {
    var viewModel: RoomDetailViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                if let errorMessage = viewModel.errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(.red)
                }

                if viewModel.renders.isEmpty, !viewModel.isLoading, viewModel.errorMessage == nil {
                    Text("No renders yet for this room.")
                        .foregroundStyle(.secondary)
                        .padding(.top, 40)
                }

                ForEach(viewModel.renders, id: \.renderId) { render in
                    RenderHistoryRow(render: render)
                    if render.renderId != viewModel.renders.last?.renderId {
                        Divider()
                    }
                }
            }
            .padding(20)
        }
        .navigationTitle(viewModel.room.label ?? "Room")
        .overlay {
            if viewModel.isLoading, viewModel.renders.isEmpty {
                ProgressView()
            }
        }
        .refreshable {
            await viewModel.loadRenders()
        }
        .task {
            await viewModel.loadRenders()
        }
    }
}

private struct RenderHistoryRow: View {
    let render: Render

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(styleDisplayName)
                    .font(.headline)
                Spacer()
                Text(render.createdAt.formatted(date: .abbreviated, time: .shortened))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            switch render.status {
            case .done:
                RenderSummaryView(render: render)
            case .failed:
                Text(ErrorCopy.message(for: .renderFailed))
                    .font(.footnote)
                    .foregroundStyle(.orange)
            case .queued, .running:
                Text("Still processing…")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }

    /// Falls back to the raw style id if it's not one of the known presets — keeps
    /// this cheap if the style catalog ever changes without a matching history entry.
    private var styleDisplayName: String {
        Style.all.first(where: { $0.id == render.style })?.displayName ?? render.style
    }
}
