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
            RenderingRing()
            Text(statusText)
                .font(.system(size: 17, weight: .medium))
                .foregroundStyle(Color.ink)
            Text("This usually takes under a minute.")
                .font(.system(size: 14))
                .foregroundStyle(Color.inkSoft)
            Spacer()
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.paper.ignoresSafeArea())
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

/// HANDOFF §2 "Rendering": a custom 88×88 ring replaces the system spinner — 5pt
/// stroke, `accentSoft` track, `accent` animated arc, continuous rotation. Purely
/// visual; `RenderStateMachine`'s polling/status logic is untouched.
private struct RenderingRing: View {
    @State private var isRotating = false

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.accentSoft, lineWidth: 5)
            Circle()
                .trim(from: 0, to: 0.25)
                .stroke(Color.accent, style: StrokeStyle(lineWidth: 5, lineCap: .round))
                .rotationEffect(.degrees(isRotating ? 360 : 0))
                .animation(.linear(duration: 1).repeatForever(autoreverses: false), value: isRotating)
        }
        .frame(width: 88, height: 88)
        .onAppear { isRotating = true }
    }
}
