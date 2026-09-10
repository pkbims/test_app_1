import DesignMyRoomCore
import Foundation

/// Narrow seam over `APIClient.listRooms()` — lets `HomeViewModel` be tested with a
/// plain stub instead of standing up a real `APIClient`/transport stack (that
/// machinery already has its own coverage in `DesignMyRoomCore`'s `APIClientTests`).
protocol RoomListProviding: Sendable {
    func listRooms() async throws -> [Room]
}

extension APIClient: RoomListProviding {}

/// The home/history screen (per the user's ask: the app no longer auto-starts a
/// fresh room — it lands here first). Lists the user's rooms, most recent first per
/// the contract; "New Room" is a separate, unrelated entry point handled by the view
/// that presents the existing add-photo flow, not by this view model.
@Observable
@MainActor
final class HomeViewModel {
    private(set) var rooms: [Room] = []
    private(set) var isLoading = false
    private(set) var errorMessage: String?

    var roomsProvider: RoomListProviding
    private let crashReporter: CrashReporter

    init(roomsProvider: RoomListProviding, crashReporter: CrashReporter) {
        self.roomsProvider = roomsProvider
        self.crashReporter = crashReporter
    }

    func loadRooms() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            rooms = try await roomsProvider.listRooms()
        } catch {
            crashReporter.logHandledError(error, context: "HomeViewModel.loadRooms")
            if let apiError = error as? ApiError {
                errorMessage = ErrorCopy.message(for: apiError)
            } else {
                errorMessage = "Couldn't load your rooms. Pull to refresh."
            }
        }
    }
}
