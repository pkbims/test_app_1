import Foundation
import ImageIO
import UniformTypeIdentifiers

public enum PhotoFormatError: Error, Equatable, Sendable {
    /// `ImageIO` couldn't decode the input at all.
    case unreadableImage
    /// The image decoded but re-encoding it as JPEG failed.
    case encodingFailed
}

/// Converts a photo to a format the server accepts (JPEG or PNG) — the image edit
/// API it calls rejects HEIC, which is what an iPhone's camera and photo picker
/// produce by default (PRD §13 / AGENT.md).
///
/// Already-JPEG or already-PNG input passes through byte-for-byte rather than
/// round-tripping through a lossy re-encode for no reason; only HEIC/HEIF (or
/// anything else the server wouldn't accept) gets converted. Uses `ImageIO`, a
/// system framework — no third-party dependency, per the client brief.
public enum PhotoFormatConverter {
    private static let acceptedTypes: Set<String> = [UTType.jpeg.identifier, UTType.png.identifier]

    public static func convertToAcceptedFormatIfNeeded(_ data: Data, jpegQuality: CGFloat = 0.9) throws -> Data {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else {
            throw PhotoFormatError.unreadableImage
        }

        if let type = CGImageSourceGetType(source) as String?, acceptedTypes.contains(type) {
            return data
        }

        guard let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            throw PhotoFormatError.unreadableImage
        }

        let output = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(output, UTType.jpeg.identifier as CFString, 1, nil) else {
            throw PhotoFormatError.encodingFailed
        }
        let options: [CFString: Any] = [kCGImageDestinationLossyCompressionQuality: jpegQuality]
        CGImageDestinationAddImage(destination, image, options as CFDictionary)
        guard CGImageDestinationFinalize(destination) else {
            throw PhotoFormatError.encodingFailed
        }
        return output as Data
    }
}

/// Client-side size check (PRD §13 — "Check ≤12 MB") so a too-large photo fails fast
/// with local copy instead of waiting on a round trip for the server's own
/// `photo_too_large` (413) — the server still enforces the real limit either way.
public enum PhotoValidation {
    public static let maxBytes = 12 * 1024 * 1024

    public static func isWithinSizeLimit(_ data: Data) -> Bool {
        data.count <= maxBytes
    }
}
