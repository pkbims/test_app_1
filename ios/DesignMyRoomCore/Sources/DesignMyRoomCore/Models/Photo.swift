import Foundation

/// Mirrors `components/schemas/Photo`. `url` is a fully-formed signed read URL — per
/// the client brief, load it as-is and never construct, parse, or cache-key it; it
/// expires in ~24h and gets reissued by the server.
public struct Photo: Codable, Equatable, Sendable {
    public let photoId: String
    public let roomId: String
    public let width: Int
    public let height: Int
    public let url: String

    public init(photoId: String, roomId: String, width: Int, height: Int, url: String) {
        self.photoId = photoId
        self.roomId = roomId
        self.width = width
        self.height = height
        self.url = url
    }
}
