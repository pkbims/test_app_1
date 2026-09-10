import XCTest
@testable import DesignMyRoomCore

/// The client's share of "error tracking" (PRD F5/CLAUDE.md) — no vendor SDK, since
/// the brief locks "no third-party dependencies" for the client (the backend's own
/// Sentry choice doesn't extend here). `FileCrashLogSink` is the part worth testing:
/// one JSON object per line, append-only, readable back.
final class CrashReporterTests: XCTestCase {
    private var fileURL: URL!

    override func setUp() {
        super.setUp()
        fileURL = FileManager.default.temporaryDirectory.appendingPathComponent("crashlog-\(UUID().uuidString).jsonl")
    }

    override func tearDown() {
        try? FileManager.default.removeItem(at: fileURL)
        super.tearDown()
    }

    func testWritesOneJSONLinePerRecord() throws {
        let sink = FileCrashLogSink(fileURL: fileURL)
        sink.write(CrashRecord(timestamp: Date(), kind: .handledError, detail: "first"))
        sink.write(CrashRecord(timestamp: Date(), kind: .handledError, detail: "second"))
        sink.waitForPendingWrites()

        let contents = try String(contentsOf: fileURL, encoding: .utf8)
        let lines = contents.split(separator: "\n").map(String.init)
        XCTAssertEqual(lines.count, 2)

        let records = try lines.map { try JSONCoding.decoder.decode(CrashRecord.self, from: Data($0.utf8)) }
        XCTAssertEqual(records[0].detail, "first")
        XCTAssertEqual(records[1].detail, "second")
    }

    func testCreatesTheFileIfItDoesNotExistYet() throws {
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))
        let sink = FileCrashLogSink(fileURL: fileURL)
        sink.write(CrashRecord(timestamp: Date(), kind: .exception, detail: "boom"))
        sink.waitForPendingWrites()
        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path))
    }

    func testAppendsAcrossSeparateSinkInstancesRatherThanOverwriting() throws {
        // The real-world case this guards: the app relaunches (a fresh process, a
        // fresh CrashReporter/sink instance) and must not stomp on crash records a
        // previous launch already wrote.
        let firstLaunchSink = FileCrashLogSink(fileURL: fileURL)
        firstLaunchSink.write(CrashRecord(timestamp: Date(), kind: .exception, detail: "one"))
        firstLaunchSink.waitForPendingWrites()

        let secondLaunchSink = FileCrashLogSink(fileURL: fileURL)
        secondLaunchSink.write(CrashRecord(timestamp: Date(), kind: .exception, detail: "two"))
        secondLaunchSink.waitForPendingWrites()

        let contents = try String(contentsOf: fileURL, encoding: .utf8)
        XCTAssertEqual(contents.split(separator: "\n").count, 2)
    }

    func testLogHandledErrorFormatsContextAndDescription() throws {
        let sink = FileCrashLogSink(fileURL: fileURL)
        let reporter = CrashReporter(sink: sink)
        reporter.logHandledError(ApiError(code: .noCredits, message: "You're out."), context: "startRender")
        sink.waitForPendingWrites()

        let contents = try String(contentsOf: fileURL, encoding: .utf8)
        let record = try JSONCoding.decoder.decode(CrashRecord.self, from: Data(contents.trimmingCharacters(in: .whitespacesAndNewlines).utf8))
        XCTAssertEqual(record.kind, .handledError)
        XCTAssertTrue(record.detail.contains("startRender"))
        XCTAssertTrue(record.detail.contains("noCredits") || record.detail.contains("no_credits") || record.detail.contains("You're out."))
    }
}
