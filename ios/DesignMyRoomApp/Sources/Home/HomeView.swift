import DesignMyRoomCore
import SwiftUI

/// The home/history screen (product decision: the app lands here after sign-in, not
/// straight into a fresh room). Room rows are text-only for v1 — label/date, no
/// thumbnails — tapping one pushes the read-only `RoomDetailView`; "New Room" is a
/// separate entry point into the existing add-photo flow, presented modally by
/// whatever hosts this view.
struct HomeView: View {
    var viewModel: HomeViewModel
    var creditsLeft: Int
    var onNewRoom: () -> Void

    var body: some View {
        List {
            // Plain list content, not a toolbar item — arbitrary-length text (any
            // digit count) never gets truncated by the system's fixed-width
            // toolbar-item chrome that way.
            Text("\(creditsLeft) room\(creditsLeft == 1 ? "" : "s") left")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .listRowSeparator(.hidden)

            if let errorMessage = viewModel.errorMessage {
                Text(errorMessage)
                    .foregroundStyle(.red)
                    .listRowSeparator(.hidden)
            }

            ForEach(viewModel.rooms) { room in
                NavigationLink(value: room) {
                    RoomRow(room: room)
                }
            }

            if viewModel.rooms.isEmpty, !viewModel.isLoading, viewModel.errorMessage == nil {
                Text("No rooms yet. Tap New Room to get started.")
                    .foregroundStyle(.secondary)
                    .listRowSeparator(.hidden)
            }
        }
        .listStyle(.plain)
        .navigationTitle("My Rooms")
        .overlay {
            if viewModel.isLoading, viewModel.rooms.isEmpty {
                ProgressView()
            }
        }
        .refreshable {
            await viewModel.loadRooms()
        }
        .safeAreaInset(edge: .bottom) {
            Button(action: onNewRoom) {
                Text("New Room")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .padding()
            .background(.bar)
        }
        .task {
            await viewModel.loadRooms()
        }
    }
}

private struct RoomRow: View {
    let room: Room

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(room.label ?? "Room")
                .font(.body.weight(.medium))
            Text(room.createdAt.formatted(date: .abbreviated, time: .shortened))
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}
