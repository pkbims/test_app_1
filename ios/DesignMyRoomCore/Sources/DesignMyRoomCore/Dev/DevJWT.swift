#if DEBUG
import CryptoKit
import Foundation

/// Signs an HS256 JWT for the backend's documented dev auth path
/// (`backend/app/auth/apple.py::verify_dev_token`), active whenever `APPLE_CLIENT_ID`
/// is unset — which is the committed `compose.env` default for local development.
///
/// **`#if DEBUG` only — compiles out of a Release build entirely, in the app and
/// here.** This is not a bypass of the contract: whatever calls this still sends the
/// result to the real, unmodified `POST /v1/auth/apple`. Only the identity token
/// differs from a real Apple one.
///
/// Two authorized consumers, both explicit, both recorded in `../ORCH-QUESTIONS.md`:
/// `RenderFlowIntegrationTests` uses it to establish a real session against the live
/// backend without an Apple Developer team (Q1-era groundwork); the app's
/// `#if DEBUG`-only "Test sign-in (dev only)" entry point (Q7) uses the exact same
/// implementation rather than a second copy, alongside — never replacing — the real
/// `AuthenticationServices` path. Uses `CryptoKit`, a system framework, not a
/// third-party dependency.
public enum DevJWT {
    /// The dev secret is only ever the committed `compose.env` value in a local dev
    /// setup — never a real secret, and this whole type is Debug-only regardless.
    public static let localDevSecret = "dev-insecure-do-not-use-in-production"

    public static func signed(subject: String, secret: String = localDevSecret, expiresIn: TimeInterval = 3600) -> String {
        let header = base64URL(json: ["alg": "HS256", "typ": "JWT"])
        let now = Int(Date().timeIntervalSince1970)
        let payload = base64URL(json: [
            "sub": subject,
            "iat": now,
            "exp": now + Int(expiresIn),
        ])
        let signingInput = "\(header).\(payload)"
        let key = SymmetricKey(data: Data(secret.utf8))
        let signature = HMAC<SHA256>.authenticationCode(for: Data(signingInput.utf8), using: key)
        let signatureB64 = base64URLEncode(Data(signature))
        return "\(signingInput).\(signatureB64)"
    }

    private static func base64URL(json: [String: Any]) -> String {
        // JSONSerialization key order isn't guaranteed, which is fine — nothing here
        // depends on byte-for-byte header/payload stability, only on a valid signature
        // over whatever bytes were actually produced.
        let data = try! JSONSerialization.data(withJSONObject: json, options: [.sortedKeys])
        return base64URLEncode(data)
    }

    private static func base64URLEncode(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .trimmingCharacters(in: CharacterSet(charactersIn: "="))
    }
}
#endif
