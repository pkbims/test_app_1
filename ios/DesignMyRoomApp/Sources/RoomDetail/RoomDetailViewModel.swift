import DesignMyRoomCore
import Foundation

/// Narrow seam over `APIClient.listRenders(roomId:)` — same reasoning as
/// `RoomListProviding`.
protocol RenderListProviding: Sendable {
    func listRenders(roomId: String) async throws -> [Render]
}

extension APIClient: RenderListProviding {}

/// Narrow seam over `APIClient.shopping(renderId:)` — same reasoning as
/// `RoomListProviding`.
protocol ShoppingProviding: Sendable {
    func shopping(renderId: String) async throws -> Shopping
}

extension APIClient: ShoppingProviding {}

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
    /// One-off fetch per render, not polled — by the time a finished render shows up
    /// in history, shopping should already be `ready`/`none`; if it's still
    /// `pending` this simply shows no card, same as the live screen does while
    /// waiting (`shopping_proto/HANDOFF.md` §3).
    private(set) var shoppingByRenderId: [String: Shopping] = [:]

    var rendersProvider: RenderListProviding
    private let shoppingProvider: ShoppingProviding
    private let crashReporter: CrashReporter

    init(room: Room, rendersProvider: RenderListProviding, shoppingProvider: ShoppingProviding, crashReporter: CrashReporter) {
        self.room = room
        self.rendersProvider = rendersProvider
        self.shoppingProvider = shoppingProvider
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

    /// Best-effort: a failure here just means no shopping card for that render,
    /// never a visible error — shopping is a nice-to-have overlay on history too.
    func loadShopping(for renderId: String) async {
        guard shoppingByRenderId[renderId] == nil else { return }
        do {
            shoppingByRenderId[renderId] = try await shoppingProvider.shopping(renderId: renderId)
        } catch {
            crashReporter.logHandledError(error, context: "RoomDetailViewModel.loadShopping")
        }
    }
}
