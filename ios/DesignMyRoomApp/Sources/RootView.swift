import DesignMyRoomCore
import SwiftUI

/// Top-level switch: sign-in state decides whether we're showing `SignInView` or
/// Home. Per the product decision, signing in lands on the room history/Home
/// screen, not straight into a fresh room — a new room is now always a deliberate
/// "New Room" tap, presented modally over Home.
struct RootView: View {
    let environment: AppEnvironment
    @State private var authManager: AuthManager

    init(environment: AppEnvironment) {
        self.environment = environment
        _authManager = State(initialValue: AuthManager(
            apiClient: environment.apiClient,
            tokenStore: environment.tokenStore,
            crashReporter: environment.crashReporter
        ))
    }

    var body: some View {
        Group {
            switch authManager.state {
            case .checkingForExistingSession:
                ProgressView()
            case .signedOut, .signingIn, .signInFailed:
                SignInView(authManager: authManager)
            case .signedIn(let me):
                HomeContainerView(environment: environment, authManager: authManager, me: me)
            }
        }
        .task {
            await authManager.restoreSessionIfPossible()
        }
    }
}

/// Owns the `HomeViewModel` for one signed-in session, and the modal presentation of
/// a brand-new `RoomFlowViewModel` per "New Room" tap — a fresh flow instance every
/// time, never reused, since a finished (or abandoned) room's flow is simply thrown
/// away once `finish()` dismisses it (see `RoomFlowViewModel.finish()`).
private struct HomeContainerView: View {
    let environment: AppEnvironment
    let authManager: AuthManager
    let me: Me
    @State private var homeViewModel: HomeViewModel
    @State private var showingNewRoomFlow = false

    init(environment: AppEnvironment, authManager: AuthManager, me: Me) {
        self.environment = environment
        self.authManager = authManager
        self.me = me
        _homeViewModel = State(initialValue: HomeViewModel(
            roomsProvider: environment.apiClient,
            crashReporter: environment.crashReporter
        ))
    }

    var body: some View {
        NavigationStack {
            HomeView(
                viewModel: homeViewModel,
                creditsLeft: me.creditsLeft,
                onNewRoom: { showingNewRoomFlow = true },
                onSignOut: { Task { await authManager.signOut() } }
            )
            .navigationDestination(for: Room.self) { room in
                RoomDetailView(viewModel: RoomDetailViewModel(
                    room: room,
                    rendersProvider: environment.apiClient,
                    crashReporter: environment.crashReporter
                ))
            }
        }
        .fullScreenCover(isPresented: $showingNewRoomFlow) {
            NewRoomFlowView(environment: environment, authManager: authManager) {
                showingNewRoomFlow = false
                Task { await homeViewModel.loadRooms() }
            }
        }
    }
}

/// The existing add-photo → confirm → style → render → compare flow (screens 2-6),
/// unchanged, just now presented modally from Home instead of being the app's only
/// screen. `onFinished` fires on the Compare screen's "Done" or an early "Cancel" —
/// either way this whole flow (and its `RoomFlowViewModel`) is discarded.
private struct NewRoomFlowView: View {
    let environment: AppEnvironment
    let authManager: AuthManager
    let onFinished: () -> Void
    @State private var flow: RoomFlowViewModel

    init(environment: AppEnvironment, authManager: AuthManager, onFinished: @escaping () -> Void) {
        self.environment = environment
        self.authManager = authManager
        self.onFinished = onFinished
        _flow = State(initialValue: RoomFlowViewModel(
            apiClient: environment.apiClient,
            authManager: authManager,
            crashReporter: environment.crashReporter,
            onFinished: onFinished
        ))
    }

    var body: some View {
        NavigationStack {
            Group {
                switch flow.step {
                case .addPhoto:
                    AddPhotoView(flow: flow)
                case .confirm:
                    ConfirmView(flow: flow)
                case .style:
                    StylePickerView(flow: flow)
                case .rendering:
                    RenderingView(flow: flow)
                case .compare:
                    CompareView(flow: flow)
                }
            }
            .toolbar {
                // Not shown once a render has actually finished — Compare's own
                // "Done" is the way out of that state; this is for backing out of
                // an in-progress room before it gets that far.
                if flow.step != .compare {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { flow.finish() }
                    }
                }
            }
        }
    }
}
