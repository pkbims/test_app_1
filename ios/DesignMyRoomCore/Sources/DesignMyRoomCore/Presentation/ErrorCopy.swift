import Foundation

/// Fixed, plain-language copy for every `ErrorCode` (PRD §16 "every error" — the
/// codes here are the frozen contract's, which supersede the PRD table's now-removed
/// `structure_unavailable` and adds a few the PRD predates: `photo_unsupported`,
/// `no_inventory`, `not_found`). No jargon, no raw error code shown to the user.
public enum ErrorCopy {
    public static func message(for code: ErrorCode) -> String {
        switch code {
        case .appleTokenInvalid:
            return "Sign in didn't work. Try again."
        case .tokenExpired:
            // Handled silently by APIClient's refresh-and-retry — a screen should
            // never actually show this, but every code still gets real copy rather
            // than an empty fallback if one ever slips through.
            return "Your session expired. Please try again."
        case .noCredits:
            return "You've used your free room."
        case .rateLimited:
            return "Slow down for a moment."
        case .photoTooLarge:
            return "That photo is too big."
        case .photoUnsupported:
            return "That photo format isn't supported. Use a JPEG or PNG."
        case .noPhotos:
            return "Add a photo of this room first."
        case .noInventory:
            return "Let's check what's in this room first."
        case .inventoryFailed:
            return "We can't check your room right now."
        case .renderFailed:
            return "That didn't work. Your credit is back."
        case .notFound:
            return "We couldn't find that."
        }
    }

    /// Per the client brief (screen 7): show `Error.message` verbatim when the server
    /// sent one — it's more specific than the fixed table — and fall back to the
    /// table only when the message is missing or blank.
    public static func message(for error: ApiError) -> String {
        error.message.isEmpty ? message(for: error.code) : error.message
    }
}
