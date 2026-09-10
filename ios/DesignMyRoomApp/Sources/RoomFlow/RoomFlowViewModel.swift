import DesignMyRoomCore
import Foundation

/// Orchestrates one room through the flow (PRD §8 / AGENT.md screens 2-6): add a
/// photo, confirm the inventory, pick a style, render, compare, restyle. All the real
/// logic (decoding, retry, the render state machine) already lives in
/// `DesignMyRoomCore` and is unit-tested there; this is deliberately thin glue that
/// maps its results onto what the views show — restyling a screen here should never
/// mean touching `APIClient` or `RenderStateMachine`.
@Observable
@MainActor
final class RoomFlowViewModel {
    enum Step: Equatable {
        case addPhoto
        case confirm
        case style
        case rendering
        case compare
    }

    private(set) var step: Step = .addPhoto
    private(set) var room: Room?
    private(set) var photo: Photo?
    private(set) var inventory: Inventory?
    private(set) var removeIds: Set<String> = []
    private(set) var selectedStyleId: String?
    var prompt: String = ""

    private(set) var isBusy = false
    /// Set on any request failure that isn't the render-specific states below —
    /// shown as a banner/alert with `ErrorCopy`-mapped text.
    private(set) var bannerMessage: String?

    private(set) var renderState: RenderStateMachine.State = .idle
    private var renderMachine: RenderStateMachine?

    private let apiClient: APIClient
    private let authManager: AuthManager
    private let crashReporter: CrashReporter
    /// Called when the user is done with this room — a finished render's "Done", or
    /// backing out early — so the presenting screen can dismiss this flow and return
    /// to Home. One room per `RoomFlowViewModel` instance; there's no in-place
    /// "start another room" anymore (see `finish()`).
    private let onFinished: () -> Void

    init(apiClient: APIClient, authManager: AuthManager, crashReporter: CrashReporter, onFinished: @escaping () -> Void) {
        self.apiClient = apiClient
        self.authManager = authManager
        self.crashReporter = crashReporter
        self.onFinished = onFinished
    }

    // MARK: - Add a photo

    /// Creates the room lazily on first use — one room per pass through the flow.
    private func ensureRoom() async throws -> Room {
        if let room { return room }
        let room = try await apiClient.createRoom(label: nil)
        self.room = room
        return room
    }

    /// `data` is already the accepted format (JPEG/PNG) and within the size limit —
    /// `PhotoFormatConverter`/`PhotoValidation` ran in the picker, not here, so this
    /// stays a pure network step.
    func submitPhoto(data: Data, filename: String, mimeType: String) async {
        isBusy = true
        bannerMessage = nil
        defer { isBusy = false }
        do {
            let room = try await ensureRoom()
            let photo = try await apiClient.uploadPhoto(roomId: room.roomId, data: data, filename: filename, mimeType: mimeType)
            self.photo = photo
            let inventory = try await apiClient.createInventory(roomId: room.roomId)
            self.inventory = inventory
            step = .confirm
        } catch {
            handle(error)
        }
    }

    // MARK: - Confirm

    /// Architecture rows are never toggleable — enforced here too, not just in the view.
    func toggleRemove(_ item: InventoryItem) {
        guard item.removable else { return }
        if removeIds.contains(item.id) {
            removeIds.remove(item.id)
        } else {
            removeIds.insert(item.id)
        }
    }

    func proceedToStylePicker() {
        step = .style
    }

    // MARK: - Style

    func selectStyle(_ style: Style) {
        selectedStyleId = style.id
    }

    /// `restyle` reuses the same room/inventory/removeIds and only asks for a new
    /// style — the Compare screen's "Restyle" per AGENT.md screen 6.
    func returnToStylePickerForRestyle() {
        step = .style
    }

    // MARK: - Render

    var canStartRender: Bool { selectedStyleId != nil }

    func startRender() async {
        guard let room, let selectedStyleId else { return }
        step = .rendering
        bannerMessage = nil
        let machine = RenderStateMachine(client: apiClient)
        renderMachine = machine
        await machine.onChange { [weak self] state in
            await self?.applyRenderState(state)
        }
        let trimmedPrompt = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        await machine.start(
            roomId: room.roomId,
            body: RenderCreate(
                style: selectedStyleId,
                prompt: trimmedPrompt.isEmpty ? nil : trimmedPrompt,
                removeIds: Array(removeIds),
                idempotencyKey: UUID().uuidString
            )
        )
    }

    func cancelRenderPolling() {
        Task { await renderMachine?.cancel() }
    }

    private func applyRenderState(_ state: RenderStateMachine.State) async {
        renderState = state
        switch state {
        case .done, .renderFailed:
            step = .compare
            await authManager.refreshMe() // credits_left may have changed (spent, or refunded)
        case .requestFailed(.signedOut):
            // The view hierarchy swaps to SignInView once AuthManager's state
            // changes, so `step` staying `.rendering` behind it doesn't matter.
            authManager.handleSignedOutFromServer()
        case .requestFailed(let failure):
            // CompareView also renders the requestFailed edge state (screen 7) — it
            // needs `step == .compare` to actually be shown instead of leaving
            // RenderingView spinning forever.
            crashReporter.logHandledError(failure, context: "RenderStateMachine.requestFailed")
            step = .compare
        default:
            break
        }
    }

    // MARK: - Finishing

    /// The Compare screen's "Done", or a "Cancel" partway through — either way,
    /// this room's flow is over. Product decision: a finished (or abandoned) room
    /// becomes read-only history; there is no in-place "restyle this room again" or
    /// "start another room without leaving" for v1 — both go through Home.
    func finish() {
        cancelRenderPolling()
        onFinished()
    }

    // MARK: - Errors

    private func handle(_ error: Error) {
        crashReporter.logHandledError(error, context: "RoomFlowViewModel.step=\(step)")
        if case APIClientError.signedOut = error {
            authManager.handleSignedOutFromServer()
            return
        }
        if let apiError = error as? ApiError {
            bannerMessage = ErrorCopy.message(for: apiError)
            return
        }
        bannerMessage = "Something went wrong. Please try again."
    }
}
