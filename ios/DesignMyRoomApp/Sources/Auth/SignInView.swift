import AuthenticationServices
import SwiftUI

/// Screen 1: Sign in with Apple, one free room granted server-side on first sign-in.
/// Full-bleed three-photo mosaic per `ui_design_v2/HANDOFF.md` §2/§4 — restyle only,
/// same `AuthManager` wiring and the same `#if DEBUG` dev sign-in path (only its
/// placement changes: a small translucent panel pinned below the real button, since
/// a full-bleed photo layout leaves no plain-background zone for a text field).
struct SignInView: View {
    let authManager: AuthManager

    #if DEBUG
    @State private var devIdentifier = "test@local"
    #endif

    private let scrim = LinearGradient(
        stops: [
            .init(color: .black.opacity(0.18), location: 0),
            .init(color: .black.opacity(0.08), location: 0.45),
            .init(color: .black.opacity(0.62), location: 0.78),
            .init(color: .black.opacity(0.94), location: 1),
        ],
        startPoint: .top,
        endPoint: .bottom
    )

    var body: some View {
        ZStack {
            ZStack {
                mosaic
                scrim
            }
            .ignoresSafeArea()

            // Only the background bleeds edge-to-edge; content stays inside the
            // safe area so the bottom-anchored button/trust line/dev panel don't
            // collide with the home indicator.
            content
        }
    }

    // Left photo ~57% width spanning the full height; right column split into two
    // equal-height stacked photos. Bleeds to all four screen edges — background, not
    // a card, so no corner rounding. UIScreen width (not GeometryReader) keeps this
    // asymmetric split simple and avoids a `Text`-adjacent GeometryReader/ZStack
    // combination — see the ios memory note on that Home-screen grid-card bug.
    private var mosaic: some View {
        let totalWidth = UIScreen.main.bounds.width
        return HStack(spacing: 3) {
            mosaicImage("japandi")
                .frame(width: totalWidth * 0.57)
            VStack(spacing: 3) {
                mosaicImage("warm-minimal")
                mosaicImage("industrial")
            }
            .frame(width: totalWidth * 0.43 - 3)
        }
    }

    private func mosaicImage(_ name: String) -> some View {
        Image(name)
            .resizable()
            .aspectRatio(contentMode: .fill)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .clipped()
    }

    private var content: some View {
        VStack {
            Spacer()
            VStack(alignment: .leading, spacing: 0) {
                Text("DESIGNMYROOM")
                    .font(.system(size: 10.5, weight: .semibold, design: .monospaced))
                    .tracking(1.5)
                    .foregroundStyle(.white.opacity(0.72))
                    .padding(.bottom, 10)

                Text("It's still\nyour room.")
                    .font(.fraunces(34, weight: .medium))
                    .foregroundStyle(.white)
                    .lineSpacing(1)
                    .padding(.bottom, 10)

                Text("Restyles your room. Never invents a different one.")
                    .font(.system(size: 14))
                    .foregroundStyle(.white.opacity(0.82))
                    .frame(maxWidth: 280, alignment: .leading)
                    .padding(.bottom, 24)

                if case .signInFailed(let message) = authManager.state {
                    Text(message)
                        .font(.system(size: 13))
                        .foregroundStyle(.white)
                        .padding(.bottom, 10)
                }

                SignInWithAppleButton(.signIn) { request in
                    // No name/email scope: the server never sends mail, and the
                    // identity token's `sub` claim is all `POST /v1/auth/apple` needs.
                    request.requestedScopes = []
                } onCompletion: { result in
                    Task { await authManager.handleSignInResult(result) }
                }
                .signInWithAppleButtonStyle(.white)
                .frame(height: 50)
                .disabled(isSigningIn)

                if isSigningIn {
                    ProgressView()
                        .tint(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 10)
                }

                Text("ONE FREE ROOM \u{00B7} NO PASSWORD, EVER")
                    .font(.system(size: 10, design: .monospaced))
                    .tracking(1.2)
                    .foregroundStyle(.white.opacity(0.6))
                    .frame(maxWidth: .infinity)
                    .multilineTextAlignment(.center)
                    .padding(.top, 14)

                #if DEBUG
                devSignInPanel
                #endif
            }
            .padding(.horizontal, 26)
            .padding(.bottom, 26)
        }
    }

    #if DEBUG
    // Stripped from Release builds entirely — see AuthManager.signInWithDevToken.
    // Explicitly authorized (ORCH-QUESTIONS Q7) while a paid Developer account is
    // pending; alongside the real button above, never in place of it.
    private var devSignInPanel: some View {
        VStack(spacing: 8) {
            Text("TEST SIGN-IN (DEV ONLY)")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(.orange)
            TextField("Identifier", text: $devIdentifier)
                .textFieldStyle(.roundedBorder)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            Button("Continue (dev only)") {
                Task { await authManager.signInWithDevToken(identifier: devIdentifier) }
            }
            .tint(.white)
            .disabled(isSigningIn || devIdentifier.isEmpty)
        }
        .padding(12)
        .background(.white.opacity(0.12), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .padding(.top, 12)
    }
    #endif

    private var isSigningIn: Bool {
        if case .signingIn = authManager.state { return true }
        return false
    }
}
