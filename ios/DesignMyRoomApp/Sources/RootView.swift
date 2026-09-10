import DesignMyRoomCore
import SwiftUI

/// Top-level switch: sign-in state decides whether we're showing `SignInView` or the
/// room flow. A fresh `RoomFlowViewModel` per signed-in session — restarting the flow
/// on sign-out and back in is simplest, and matches "one room per pass" already being
/// the flow's own model.
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
                RoomFlowContainerView(environment: environment, authManager: authManager, me: me)
            }
        }
        .task {
            await authManager.restoreSessionIfPossible()
        }
    }
}

/// Owns the `RoomFlowViewModel` for one signed-in session and routes between its
/// steps — a plain `switch` on `flow.step`, not a `NavigationStack`, since the flow
/// is strictly linear and never wants back-swipe to skip a step (PRD §8: one photo,
/// asked once; no going back to re-add).
private struct RoomFlowContainerView: View {
    let environment: AppEnvironment
    let authManager: AuthManager
    let me: Me
    @State private var flow: RoomFlowViewModel

    init(environment: AppEnvironment, authManager: AuthManager, me: Me) {
        self.environment = environment
        self.authManager = authManager
        self.me = me
        _flow = State(initialValue: RoomFlowViewModel(
            apiClient: environment.apiClient,
            authManager: authManager,
            crashReporter: environment.crashReporter
        ))
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("\(me.creditsLeft) room\(me.creditsLeft == 1 ? "" : "s") left")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("Sign out") {
                    Task { await authManager.signOut() }
                }
                .font(.footnote)
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)

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
    }
}
