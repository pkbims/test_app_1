import DesignMyRoomCore
import SwiftUI

/// Screen 5: `RenderStateMachine` already owns the queued/running/done/failed
/// transitions and the 2s polling — this view only reflects `flow.renderState`.
/// `.done`/`.renderFailed` both move `flow.step` to `.compare` (the view model does
/// that, not this view), where the compare/edge-state distinction actually renders.
struct RenderingView: View {
    let flow: RoomFlowViewModel

    var body: some View {
        VStack(spacing: 20) {
            Spacer()
            ProgressView()
                .controlSize(.large)
            Text(statusText)
                .font(.title3.weight(.medium))
            Text("This usually takes under a minute.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
        }
        .padding(24)
    }

    private var statusText: String {
        switch flow.renderState {
        case .submitting:
            return "Sending your room..."
        case .polling(let render):
            switch render.status {
            case .running:
                return "Restyling your room..."
            default:
                return "Queued..."
            }
        default:
            return "Working on it..."
        }
    }
}
