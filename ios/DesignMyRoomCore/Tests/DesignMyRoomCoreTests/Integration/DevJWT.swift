import CryptoKit
import Foundation

/// Signs an HS256 JWT for the backend's documented dev auth path
/// (`backend/app/auth/apple.py::verify_dev_token`), active whenever `APPLE_CLIENT_ID`
/// is unset — which is the committed `compose.env` default.
///
/// This exists only so integration tests can establish a real session against a real
/// running server without an Apple Developer team. It is test-only: the iOS app
/// itself always goes through `AuthenticationServices` and sends whatever token Apple
/// hands it, per the client brief ("do not add a fake-login path... without the
/// orchestrator's sign-off"). Uses `CryptoKit` (a system framework, not a
/// third-party dependency) to compute the HMAC-SHA256 signature.
enum DevJWT {
    static func signed(subject: String, secret: String, expiresIn: TimeInterval = 3600) -> String {
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
