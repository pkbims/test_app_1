import XCTest
import ImageIO
import UniformTypeIdentifiers
@testable import DesignMyRoomCore

/// HEIC->JPEG conversion (PRD §13 / AGENT.md — "the image API rejects HEIC"), tested
/// against real fixture files rather than synthetic bytes: `inputs/IMG_1519.HEIC` is
/// what an iPhone actually produces, so a fake HEIC blob would only prove the fake
/// works, not that this handles a real one.
final class PhotoFormatConverterTests: XCTestCase {

    private func fixture(_ relativePath: String) throws -> Data {
        var dir = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        for _ in 0..<10 {
            let candidate = dir.appendingPathComponent("inputs/\(relativePath)")
            if FileManager.default.fileExists(atPath: candidate.path) {
                return try Data(contentsOf: candidate)
            }
            dir = dir.deletingLastPathComponent()
        }
        throw XCTSkip("inputs/\(relativePath) not found relative to test file.")
    }

    private func typeIdentifier(of data: Data) -> String? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        return CGImageSourceGetType(source) as String?
    }

    func testConvertsRealHEICPhotoToJPEG() throws {
        let heicData = try fixture("IMG_1519.HEIC")
        XCTAssertEqual(typeIdentifier(of: heicData), UTType.heic.identifier, "sanity check on the fixture itself")

        let converted = try PhotoFormatConverter.convertToAcceptedFormatIfNeeded(heicData)

        XCTAssertEqual(typeIdentifier(of: converted), UTType.jpeg.identifier)
        // Round-trip: the output must itself be a valid, decodable image with real dimensions.
        guard let source = CGImageSourceCreateWithData(converted as CFData, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            return XCTFail("converted data is not a decodable image")
        }
        XCTAssertGreaterThan(image.width, 0)
        XCTAssertGreaterThan(image.height, 0)
    }

    func testAlreadyJPEGPassesThroughUnchanged() throws {
        let jpegData = try fixture("room.jpg")
        XCTAssertEqual(typeIdentifier(of: jpegData), UTType.jpeg.identifier, "sanity check on the fixture itself")

        let result = try PhotoFormatConverter.convertToAcceptedFormatIfNeeded(jpegData)

        XCTAssertEqual(result, jpegData, "must not re-encode a format the server already accepts")
    }

    func testAlreadyPNGPassesThroughUnchanged() throws {
        let pngData = try fixture("mask_fireplace.png")
        XCTAssertEqual(typeIdentifier(of: pngData), UTType.png.identifier, "sanity check on the fixture itself")

        let result = try PhotoFormatConverter.convertToAcceptedFormatIfNeeded(pngData)

        XCTAssertEqual(result, pngData, "must not re-encode a format the server already accepts")
    }

    func testUnreadableDataThrows() {
        let garbage = Data([0x00, 0x01, 0x02, 0x03, 0x04])
        XCTAssertThrowsError(try PhotoFormatConverter.convertToAcceptedFormatIfNeeded(garbage)) { error in
            XCTAssertEqual(error as? PhotoFormatError, .unreadableImage)
        }
    }
}

final class PhotoValidationTests: XCTestCase {
    func testWithinLimitPasses() {
        let data = Data(repeating: 0, count: 1024)
        XCTAssertTrue(PhotoValidation.isWithinSizeLimit(data))
    }

    func testExactlyAtLimitPasses() {
        let data = Data(repeating: 0, count: PhotoValidation.maxBytes)
        XCTAssertTrue(PhotoValidation.isWithinSizeLimit(data))
    }

    func testOverLimitFails() {
        let data = Data(repeating: 0, count: PhotoValidation.maxBytes + 1)
        XCTAssertFalse(PhotoValidation.isWithinSizeLimit(data))
    }
}
