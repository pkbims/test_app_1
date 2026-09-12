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
                // Inline Fraunces title instead of the system `.navigationTitle` font,
                // matching the other screens (HANDOFF §2) — the back chevron still
                // comes from the NavigationStack push itself, not from this title.
                Text(viewModel.room.label ?? "Room")
                    .font(.fraunces(21, weight: .medium))
                    .foregroundStyle(Color.ink)

                if let errorMessage = viewModel.errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(Color.warn)
                }

                if viewModel.renders.isEmpty, !viewModel.isLoading, viewModel.errorMessage == nil {
                    Text("No renders yet for this room.")
                        .foregroundStyle(Color.inkSoft)
                        .padding(.top, 40)
                }

                ForEach(viewModel.renders, id: \.renderId) { render in
                    RenderHistoryRow(render: render, shopping: viewModel.shoppingByRenderId[render.renderId])
                        .task {
                            if render.status == .done {
                                await viewModel.loadShopping(for: render.renderId)
                            }
                        }
                    if render.renderId != viewModel.renders.last?.renderId {
                        Rectangle()
                            .fill(Color.line)
                            .frame(height: 1)
                    }
                }
            }
            .padding(20)
        }
        .background(Color.paper.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
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
    let shopping: Shopping?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(styleDisplayName)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(Color.ink)
                Spacer()
                Text(render.createdAt.formatted(date: .abbreviated, time: .shortened))
                    .font(.system(size: 12))
                    .foregroundStyle(Color.faint)
            }

            switch render.status {
            case .done:
                RenderSummaryView(render: render)
                UnlockShoppingCardLink(shopping: shopping)
            case .failed:
                Text(ErrorCopy.message(for: .renderFailed))
                    .font(.system(size: 13))
                    .foregroundStyle(Color.warn)
            case .queued, .running:
                Text("Still processing…")
                    .font(.system(size: 13))
                    .foregroundStyle(Color.inkSoft)
            }
        }
    }

    /// Falls back to the raw style id if it's not one of the known presets — keeps
    /// this cheap if the style catalog ever changes without a matching history entry.
    private var styleDisplayName: String {
        Style.all.first(where: { $0.id == render.style })?.displayName ?? render.style
    }
}
