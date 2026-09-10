import AuthenticationServices
import SwiftUI

/// Screen 1: Sign in with Apple, one free room granted server-side on first sign-in.
struct SignInView: View {
    let authManager: AuthManager

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            Text("DesignMyRoom")
                .font(.largeTitle.weight(.bold))
            Text("Restyles your room. Never invents a different one.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Spacer()

            if case .signInFailed(let message) = authManager.state {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .padding(.horizontal, 32)
            }

            SignInWithAppleButton(.signIn) { request in
                // No name/email scope: the server never sends mail, and the identity
                // token's `sub` claim is all `POST /v1/auth/apple` needs.
                request.requestedScopes = []
            } onCompletion: { result in
                Task { await authManager.handleSignInResult(result) }
            }
            .signInWithAppleButtonStyle(.black)
            .frame(height: 50)
            .padding(.horizontal, 32)
            .padding(.bottom, 24)
            .disabled(isSigningIn)

            if isSigningIn {
                ProgressView()
                    .padding(.bottom, 16)
            }
        }
    }

    private var isSigningIn: Bool {
        if case .signingIn = authManager.state { return true }
        return false
    }
}
