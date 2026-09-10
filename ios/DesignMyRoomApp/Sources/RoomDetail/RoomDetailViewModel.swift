import DesignMyRoomCore
import Foundation

/// Narrow seam over `APIClient.listRenders(roomId:)` — same reasoning as
/// `RoomListProviding`.
protocol RenderListProviding: Sendable {
    func listRenders(roomId: String) async throws -> [Render]
}

extension APIClient: RenderListProviding {}

/// Read-only room history (product decision: no "restyle again" from here for v1 —
/// a new render always starts a brand-new room via the existing add-photo flow).
/// Holds the `Room` it was navigated with directly rather than re-fetching it —
/// there's no `GET /v1/rooms/{id}` in the contract, only within-room operations.
@Observable
@MainActor
final class RoomDetailViewModel {
    let room: Room
    private(set) var renders: [Render] = []
    private(set) var isLoading = false
    private(set) var errorMessage: String?

    var rendersProvider: RenderListProviding
    private let crashReporter: CrashReporter

    init(room: Room, rendersProvider: RenderListProviding, crashReporter: CrashReporter) {
        self.room = room
        self.rendersProvider = rendersProvider
        self.crashReporter = crashReporter
    }

    func loadRenders() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            renders = try await rendersProvider.listRenders(roomId: room.roomId)
        } catch {
            crashReporter.logHandledError(error, context: "RoomDetailViewModel.loadRenders")
            if let apiError = error as? ApiError {
                errorMessage = ErrorCopy.message(for: apiError)
            } else {
                errorMessage = "Couldn't load this room's history. Pull to refresh."
            }
        }
    }
}
