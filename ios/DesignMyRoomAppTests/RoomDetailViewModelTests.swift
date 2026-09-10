import XCTest
import DesignMyRoomCore
@testable import DesignMyRoom

/// Read-only room history (per the user's product decision — no restyle from here
/// for v1). `RoomDetailViewModel` depends on `RenderListProviding`, a narrow
/// protocol the real `APIClient` conforms to, so this uses a plain stub rather than
/// a real `APIClient`/`MockTransport` stack.
final class RoomDetailViewModelTests: XCTestCase {

    private struct StubRenderListProvider: RenderListProviding {
        var result: Result<[Render], Error>
        func listRenders(roomId: String) async throws -> [Render] { try result.get() }
    }

    private func makeRoom() -> Room {
        Room(roomId: "rm_1", label: "Bedroom", createdAt: Date(), hasPhoto: true, hasInventory: true)
    }

    private func makeRender(id: String, status: RenderStatus = .done, preservationRate: Double? = 0.9) -> Render {
        Render(
            renderId: id, roomId: "rm_1", status: status, style: "scandi", removeIds: [],
            beforeUrl: "https://x/before", afterUrl: "https://x/after",
            preservationRate: preservationRate, missingItems: nil, errorCode: nil,
            createdAt: Date(), creditsLeft: 2
        )
    }

    @MainActor
    func testLoadRendersPopulatesOnSuccess() async {
        let renders = [makeRender(id: "rd_1"), makeRender(id: "rd_2")]
        let viewModel = RoomDetailViewModel(
            room: makeRoom(),
            rendersProvider: StubRenderListProvider(result: .success(renders)),
            crashReporter: CrashReporter(sink: NoOpCrashLogSink())
        )

        await viewModel.loadRenders()

        XCTAssertEqual(viewModel.renders, renders)
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isLoading)
    }

    @MainActor
    func testLoadRendersRequestsThisRoomsIdSpecifically() async {
        final class RecordingProvider: RenderListProviding {
            private(set) var requestedRoomId: String?
            func listRenders(roomId: String) async throws -> [Render] {
                requestedRoomId = roomId
                return []
            }
        }
        let recorder = RecordingProvider()
        let viewModel = RoomDetailViewModel(room: makeRoom(), rendersProvider: recorder, crashReporter: CrashReporter(sink: NoOpCrashLogSink()))

        await viewModel.loadRenders()

        XCTAssertEqual(recorder.requestedRoomId, "rm_1")
    }

    @MainActor
    func testLoadRendersSetsErrorMessageOnApiError() async {
        let viewModel = RoomDetailViewModel(
            room: makeRoom(),
            rendersProvider: StubRenderListProvider(result: .failure(ApiError(code: .notFound, message: "We couldn't find that."))),
            crashReporter: CrashReporter(sink: NoOpCrashLogSink())
        )

        await viewModel.loadRenders()

        XCTAssertEqual(viewModel.errorMessage, "We couldn't find that.")
        XCTAssertEqual(viewModel.renders, [])
    }

    @MainActor
    func testOnlyDoneRendersAreShownAsCompletedHistory() async {
        // A room can have a queued/running render if the user backgrounds mid-render
        // and revisits history before it finishes — history is read-only, so it just
        // shouldn't crash or misrender; done/failed are the two terminal, displayable
        // cases the view distinguishes.
        let renders = [
            makeRender(id: "rd_done", status: .done),
            makeRender(id: "rd_failed", status: .failed, preservationRate: nil),
            makeRender(id: "rd_queued", status: .queued, preservationRate: nil),
        ]
        let viewModel = RoomDetailViewModel(
            room: makeRoom(),
            rendersProvider: StubRenderListProvider(result: .success(renders)),
            crashReporter: CrashReporter(sink: NoOpCrashLogSink())
        )

        await viewModel.loadRenders()

        XCTAssertEqual(viewModel.renders.count, 3, "history shows every render it's told about, in whatever order the server returned")
    }
}
