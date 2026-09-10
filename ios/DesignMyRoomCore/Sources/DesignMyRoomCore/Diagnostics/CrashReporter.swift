import Foundation

/// The client's share of "error tracking" (PRD F5 / CLAUDE.md baseline). The backend
/// chose a vendor SDK (Sentry) for that; the client brief locks "no third-party
/// dependencies," so this is a small home-grown logger instead — one JSON line per
/// event, appended to a file in the app's container.
///
/// **The tradeoff, stated plainly:** this has no dashboard, no alerting, no crash
/// symbolication, and — because it has no vendor SDK's own signal/Mach-exception
/// handlers — it cannot catch a Swift-level fatal trap (`fatalError`, an array index
/// out of range, a force-unwrapped `nil`); only Objective-C-style uncaught
/// `NSException`s and explicitly logged handled errors. A real crash reporter is
/// worth paying a vendor for once this app has to justify recording video of; this
/// is the honest, free baseline.
public struct CrashRecord: Codable, Equatable, Sendable {
    public enum Kind: String, Codable, Sendable {
        case exception
        case handledError = "handled_error"
    }

    public let timestamp: Date
    public let kind: Kind
    public let detail: String

    public init(timestamp: Date, kind: Kind, detail: String) {
        self.timestamp = timestamp
        self.kind = kind
        self.detail = detail
    }
}

/// Where `CrashRecord`s go. A protocol so `CrashReporter` doesn't hard-code "a file"
/// — useful for a future dashboard/upload sink without touching call sites.
public protocol CrashLogSink: Sendable {
    func write(_ record: CrashRecord)
}

/// Appends one JSON line per record to a file, serialized onto its own queue so
/// concurrent writers (a handled error logged from two screens at once) don't
/// interleave partial lines.
public final class FileCrashLogSink: CrashLogSink, Sendable {
    private let fileURL: URL
    private let queue = DispatchQueue(label: "com.designmyroom.crashlogsink")

    public init(fileURL: URL) {
        self.fileURL = fileURL
        // Created synchronously, once, here — not lazily inside `write`'s async
        // block. Two sink instances (e.g. across an app relaunch) racing to create
        // the same file inside the queue would risk one truncating what the other
        // just wrote; doing it up front removes that window entirely.
        if !FileManager.default.fileExists(atPath: fileURL.path) {
            FileManager.default.createFile(atPath: fileURL.path, contents: nil)
        }
    }

    public func write(_ record: CrashRecord) {
        queue.async { [fileURL] in
            guard let data = try? JSONCoding.encoder.encode(record) else { return }
            var line = data
            line.append(UInt8(ascii: "\n"))
            guard let handle = try? FileHandle(forWritingTo: fileURL) else { return }
            defer { try? handle.close() }
            handle.seekToEndOfFile()
            handle.write(line)
        }
    }

    /// Test-only synchronization point — production code never needs to know when a
    /// write finished.
    func waitForPendingWrites() {
        queue.sync {}
    }
}

/// `NSSetUncaughtExceptionHandler` only accepts a capture-less `@convention(c)`
/// function, so the sink it reports to has to live in process-wide storage rather
/// than being captured by the handler closure.
private nonisolated(unsafe) var installedExceptionSink: CrashLogSink?

/// Installs the process-wide uncaught-exception handler and gives call sites a place
/// to log a handled (non-fatal) error with context, e.g. from a `catch` block.
public final class CrashReporter: @unchecked Sendable {
    private let sink: CrashLogSink

    public init(sink: CrashLogSink) {
        self.sink = sink
    }

    /// Call once at app launch.
    public func install() {
        installedExceptionSink = sink
        NSSetUncaughtExceptionHandler { exception in
            let detail = "\(exception.name.rawValue): \(exception.reason ?? "no reason")\n"
                + exception.callStackSymbols.joined(separator: "\n")
            installedExceptionSink?.write(CrashRecord(timestamp: Date(), kind: .exception, detail: detail))
        }
    }

    /// Call from a `catch` block for an error worth having on record — a render that
    /// failed, a sign-in that didn't go through, an unexpected decode failure.
    public func logHandledError(_ error: Error, context: String) {
        sink.write(CrashRecord(timestamp: Date(), kind: .handledError, detail: "\(context): \(error)"))
    }
}
