import CryptoKit
import XCTest
@testable import DesignMyRoomCore

/// `DevJWT` is `#if DEBUG`-only (see its own doc comment) — that's also true of
/// every XCTest target, so these tests exercise the exact same code path a Debug
/// app build would. The real proof that a token it produces is accepted stays in
/// `RenderFlowIntegrationTests`, which signs in with one against the live backend;
/// these just pin the pure token *shape* down with fast, no-network feedback.
final class DevJWTTests: XCTestCase {
    private let secret = "dev-insecure-do-not-use-in-production"

    func testProducesThreeDotSeparatedBase64URLSegments() {
        let token = DevJWT.signed(subject: "test@local", secret: secret)
        let parts = token.split(separator: ".", omittingEmptySubsequences: false)
        XCTAssertEqual(parts.count, 3)
        for part in parts {
            XCTAssertFalse(part.contains("+"))
            XCTAssertFalse(part.contains("/"))
            XCTAssertFalse(part.contains("="))
        }
    }

    func testHeaderDeclaresHS256() throws {
        let token = DevJWT.signed(subject: "test@local", secret: secret)
        let header = try decodeSegment(token, index: 0)
        XCTAssertEqual(header["alg"] as? String, "HS256")
        XCTAssertEqual(header["typ"] as? String, "JWT")
    }

    func testPayloadCarriesTheGivenSubjectAndAFutureExpiry() throws {
        let token = DevJWT.signed(subject: "someone@example.com", secret: secret, expiresIn: 120)
        let payload = try decodeSegment(token, index: 1)
        XCTAssertEqual(payload["sub"] as? String, "someone@example.com")
        let exp = try XCTUnwrap(payload["exp"] as? Int)
        XCTAssertGreaterThan(Double(exp), Date().timeIntervalSince1970)
    }

    func testSameSecretProducesAVerifiableSignature() throws {
        // Re-derive the signature the same way the backend's `verify_dev_token`
        // would, over the same signing input, and confirm it matches — a
        // lightweight stand-in for "the backend will accept this."
        let token = DevJWT.signed(subject: "test@local", secret: secret)
        let parts = token.split(separator: ".")
        let signingInput = "\(parts[0]).\(parts[1])"

        let expectedSignature = hmacSHA256Base64URL(signingInput, secret: secret)
        XCTAssertEqual(String(parts[2]), expectedSignature)
    }

    func testDifferentSubjectsProduceDifferentTokens() {
        let a = DevJWT.signed(subject: "a@local", secret: secret)
        let b = DevJWT.signed(subject: "b@local", secret: secret)
        XCTAssertNotEqual(a, b)
    }

    // MARK: - Helpers

    private func decodeSegment(_ token: String, index: Int) throws -> [String: Any] {
        let parts = token.split(separator: ".")
        var base64 = String(parts[index])
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")
        while base64.count % 4 != 0 { base64.append("=") }
        let data = try XCTUnwrap(Data(base64Encoded: base64))
        let object = try JSONSerialization.jsonObject(with: data)
        return try XCTUnwrap(object as? [String: Any])
    }

    private func hmacSHA256Base64URL(_ input: String, secret: String) -> String {
        let key = SymmetricKey(data: Data(secret.utf8))
        let signature = HMAC<SHA256>.authenticationCode(for: Data(input.utf8), using: key)
        return Data(signature).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .trimmingCharacters(in: CharacterSet(charactersIn: "="))
    }
}
