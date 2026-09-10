import XCTest
import DesignMyRoomCore
@testable import DesignMyRoom

/// `HomeViewModel` depends on `RoomListProviding` (a narrow protocol the real
/// `APIClient` conforms to — see `Home/HomeViewModel.swift`) rather than the
/// concrete actor, so these tests use a plain stub instead of standing up a real
/// `APIClient`/`MockTransport` stack — that machinery is already covered by
/// `DesignMyRoomCore`'s own `APIClientTests`; this only needs to prove the view
/// model reacts correctly to what the provider returns.
final class HomeViewModelTests: XCTestCase {

    private struct StubRoomListProvider: RoomListProviding {
        var result: Result<[Room], Error>
        var delayNanos: UInt64 = 0

        func listRooms() async throws -> [Room] {
            if delayNanos > 0 {
                try? await Task.sleep(nanoseconds: delayNanos)
            }
            return try result.get()
        }
    }

    private func makeRoom(id: String, label: String?) -> Room {
        Room(roomId: id, label: label, createdAt: Date(), hasPhoto: true, hasInventory: true)
    }

    @MainActor
    func testLoadRoomsPopulatesRoomsOnSuccess() async {
        let rooms = [makeRoom(id: "rm_1", label: "Bedroom"), makeRoom(id: "rm_2", label: nil)]
        let viewModel = HomeViewModel(
            roomsProvider: StubRoomListProvider(result: .success(rooms)),
            crashReporter: CrashReporter(sink: NoOpCrashLogSink())
        )

        await viewModel.loadRooms()

        XCTAssertEqual(viewModel.rooms, rooms)
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isLoading)
    }

    @MainActor
    func testLoadRoomsSetsErrorMessageOnApiError() async {
        let apiError = ApiError(code: .rateLimited, message: "Slow down.")
        let viewModel = HomeViewModel(
            roomsProvider: StubRoomListProvider(result: .failure(apiError)),
            crashReporter: CrashReporter(sink: NoOpCrashLogSink())
        )

        await viewModel.loadRooms()

        XCTAssertEqual(viewModel.errorMessage, "Slow down.")
        XCTAssertEqual(viewModel.rooms, [])
    }

    @MainActor
    func testLoadRoomsSetsGenericErrorMessageOnUnrecognizedFailure() async {
        let viewModel = HomeViewModel(
            roomsProvider: StubRoomListProvider(result: .failure(URLError(.timedOut))),
            crashReporter: CrashReporter(sink: NoOpCrashLogSink())
        )

        await viewModel.loadRooms()

        XCTAssertNotNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.errorMessage!.isEmpty)
    }

    @MainActor
    func testIsLoadingIsTrueWhileTheRequestIsInFlight() async {
        let viewModel = HomeViewModel(
            roomsProvider: StubRoomListProvider(result: .success([]), delayNanos: 50_000_000),
            crashReporter: CrashReporter(sink: NoOpCrashLogSink())
        )

        XCTAssertFalse(viewModel.isLoading)
        let task = Task { await viewModel.loadRooms() }
        try? await Task.sleep(nanoseconds: 10_000_000) // let loadRooms() start and flip isLoading
        XCTAssertTrue(viewModel.isLoading)
        await task.value
        XCTAssertFalse(viewModel.isLoading)
    }

    @MainActor
    func testLoadRoomsClearsAPreviousErrorOnRetrySuccess() async {
        let viewModel = HomeViewModel(
            roomsProvider: StubRoomListProvider(result: .failure(ApiError(code: .rateLimited, message: "Slow down."))),
            crashReporter: CrashReporter(sink: NoOpCrashLogSink())
        )
        await viewModel.loadRooms()
        XCTAssertNotNil(viewModel.errorMessage)

        // A different provider standing in for "the user pulled to refresh and it worked".
        // `roomsProvider` is `internal`, not `private` — visible here via `@testable import`.
        let room = makeRoom(id: "rm_1", label: "Bedroom")
        viewModel.roomsProvider = StubRoomListProvider(result: .success([room]))
        await viewModel.loadRooms()

        XCTAssertNil(viewModel.errorMessage)
        XCTAssertEqual(viewModel.rooms, [room])
    }
}

/// A `CrashLogSink` that discards everything — tests want `CrashReporter.logHandledError`
/// to be a safe no-op, not a real file write.
struct NoOpCrashLogSink: CrashLogSink {
    func write(_ record: CrashRecord) {}
}
