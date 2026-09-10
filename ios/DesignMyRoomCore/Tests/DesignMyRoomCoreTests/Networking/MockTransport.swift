import Foundation
@testable import DesignMyRoomCore

/// Test double for `HTTPTransport`. Responses are queued and handed out in order,
/// one per `send(_:)` call; every request that arrives is recorded so tests can
/// assert on method, path, headers and body.
final actor MockTransport: HTTPTransport {
    enum QueuedResult {
        case success(status: Int, body: Data, headers: [String: String] = [:])
        case failure(Error)
    }

    private(set) var recordedRequests: [URLRequest] = []
    private var queue: [QueuedResult] = []

    func enqueue(_ result: QueuedResult) {
        queue.append(result)
    }

    func enqueueJSON(status: Int, json: String) {
        queue.append(.success(status: status, body: Data(json.utf8)))
    }

    func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        recordedRequests.append(request)
        guard !queue.isEmpty else {
            fatalError("MockTransport ran out of queued responses for \(request.url?.absoluteString ?? "?")")
        }
        let next = queue.removeFirst()
        switch next {
        case let .success(status, body, headers):
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: status,
                httpVersion: "HTTP/1.1",
                headerFields: headers
            )!
            return (body, response)
        case let .failure(error):
            throw error
        }
    }

    var requestCount: Int { recordedRequests.count }
}
