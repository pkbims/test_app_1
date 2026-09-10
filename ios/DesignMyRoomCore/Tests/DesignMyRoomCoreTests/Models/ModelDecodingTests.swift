import XCTest
@testable import DesignMyRoomCore

/// Decodes fixtures shaped exactly like `contract/openapi.json` component schemas.
/// If the backend or the contract ever drifts, these are the first tests to fail.
final class ModelDecodingTests: XCTestCase {

    func testDecodeTokens() throws {
        let json = """
        {"access_token":"abc123","refresh_token":"r-abc","expires_in":900}
        """.data(using: .utf8)!
        let tokens = try JSONCoding.decoder.decode(Tokens.self, from: json)
        XCTAssertEqual(tokens.accessToken, "abc123")
        XCTAssertEqual(tokens.refreshToken, "r-abc")
        XCTAssertEqual(tokens.expiresIn, 900)
    }

    func testDecodeTokensWithNullRefreshToken() throws {
        let json = """
        {"access_token":"abc123","expires_in":900}
        """.data(using: .utf8)!
        let tokens = try JSONCoding.decoder.decode(Tokens.self, from: json)
        XCTAssertNil(tokens.refreshToken)
    }

    func testDecodeMe() throws {
        let json = """
        {"user_id":"u_1","credits_left":3}
        """.data(using: .utf8)!
        let me = try JSONCoding.decoder.decode(Me.self, from: json)
        XCTAssertEqual(me.userId, "u_1")
        XCTAssertEqual(me.creditsLeft, 3)
    }

    func testDecodeRoom() throws {
        let json = """
        {"room_id":"rm_1","label":"Living room","created_at":"2026-09-09T20:20:00Z","has_photo":true,"has_inventory":false}
        """.data(using: .utf8)!
        let room = try JSONCoding.decoder.decode(Room.self, from: json)
        XCTAssertEqual(room.roomId, "rm_1")
        XCTAssertEqual(room.label, "Living room")
        XCTAssertTrue(room.hasPhoto)
        XCTAssertFalse(room.hasInventory)
        var expectedComponents = DateComponents()
        expectedComponents.year = 2026
        expectedComponents.month = 9
        expectedComponents.day = 9
        expectedComponents.hour = 20
        expectedComponents.minute = 20
        expectedComponents.second = 0
        var utcCalendar = Calendar(identifier: .gregorian)
        utcCalendar.timeZone = TimeZone(identifier: "UTC")!
        let expectedDate = utcCalendar.date(from: expectedComponents)!
        XCTAssertEqual(room.createdAt.timeIntervalSince1970, expectedDate.timeIntervalSince1970, accuracy: 1)
    }

    func testDecodeRoomWithNullLabel() throws {
        let json = """
        {"room_id":"rm_1","created_at":"2026-09-09T20:20:00Z","has_photo":false,"has_inventory":false}
        """.data(using: .utf8)!
        let room = try JSONCoding.decoder.decode(Room.self, from: json)
        XCTAssertNil(room.label)
        XCTAssertNil(room.thumbnailUrl)
    }

    func testDecodeRoomWithThumbnailUrl() throws {
        let json = """
        {"room_id":"rm_1","label":"Living room","created_at":"2026-09-09T20:20:00Z","has_photo":true,
         "has_inventory":true,"thumbnail_url":"https://example.com/files/renders/rd_1?exp=1&sig=x"}
        """.data(using: .utf8)!
        let room = try JSONCoding.decoder.decode(Room.self, from: json)
        XCTAssertEqual(room.thumbnailUrl, "https://example.com/files/renders/rd_1?exp=1&sig=x")
    }

    func testDecodeRoomWithNullThumbnailUrl() throws {
        let json = """
        {"room_id":"rm_1","label":"Living room","created_at":"2026-09-09T20:20:00Z","has_photo":false,
         "has_inventory":false,"thumbnail_url":null}
        """.data(using: .utf8)!
        let room = try JSONCoding.decoder.decode(Room.self, from: json)
        XCTAssertNil(room.thumbnailUrl)
    }

    func testDecodePhoto() throws {
        let json = """
        {"photo_id":"ph_1","room_id":"rm_1","width":3024,"height":4032,"url":"https://example.com/files/photos/ph_1?exp=1&sig=x"}
        """.data(using: .utf8)!
        let photo = try JSONCoding.decoder.decode(Photo.self, from: json)
        XCTAssertEqual(photo.photoId, "ph_1")
        XCTAssertEqual(photo.width, 3024)
        XCTAssertEqual(photo.height, 4032)
        XCTAssertEqual(photo.url, "https://example.com/files/photos/ph_1?exp=1&sig=x")
    }

    func testDecodeInventoryItemArchitecture() throws {
        let json = """
        {"id":"A","kind":"architecture","name":"Fireplace","description":"Brick fireplace centred on the back wall.","removable":false}
        """.data(using: .utf8)!
        let item = try JSONCoding.decoder.decode(InventoryItem.self, from: json)
        XCTAssertEqual(item.id, "A")
        XCTAssertEqual(item.kind, .architecture)
        XCTAssertEqual(item.name, "Fireplace")
        XCTAssertFalse(item.removable)
    }

    func testDecodeInventoryItemObject() throws {
        let json = """
        {"id":"H","kind":"object","name":"Blue sofa","description":"Blue three-seat sofa facing the fireplace.","removable":true}
        """.data(using: .utf8)!
        let item = try JSONCoding.decoder.decode(InventoryItem.self, from: json)
        XCTAssertEqual(item.kind, .object)
        XCTAssertTrue(item.removable)
    }

    func testDecodeInventory() throws {
        let json = """
        {"room_id":"rm_1","items":[
          {"id":"A","kind":"architecture","name":"Fireplace","description":"d","removable":false},
          {"id":"H","kind":"object","name":"Sofa","description":"d","removable":true}
        ],"created_at":"2026-09-09T20:20:00Z"}
        """.data(using: .utf8)!
        let inventory = try JSONCoding.decoder.decode(Inventory.self, from: json)
        XCTAssertEqual(inventory.roomId, "rm_1")
        XCTAssertEqual(inventory.items.count, 2)
    }

    func testDecodeRenderQueued() throws {
        let json = """
        {"render_id":"rd_1","room_id":"rm_1","status":"queued","style":"warm-minimal",
         "remove_ids":["H"],"before_url":null,"after_url":null,"preservation_rate":null,
         "missing_items":null,"error_code":null,"created_at":"2026-09-09T20:20:00Z","credits_left":2}
        """.data(using: .utf8)!
        let render = try JSONCoding.decoder.decode(Render.self, from: json)
        XCTAssertEqual(render.status, .queued)
        XCTAssertEqual(render.removeIds, ["H"])
        XCTAssertNil(render.beforeUrl)
        XCTAssertEqual(render.creditsLeft, 2)
    }

    func testDecodeRenderDone() throws {
        let json = """
        {"render_id":"rd_1","room_id":"rm_1","status":"done","style":"scandi",
         "remove_ids":[],"before_url":"https://x/before","after_url":"https://x/after",
         "preservation_rate":0.92,"missing_items":[],"error_code":null,
         "created_at":"2026-09-09T20:20:00Z","credits_left":1}
        """.data(using: .utf8)!
        let render = try JSONCoding.decoder.decode(Render.self, from: json)
        XCTAssertEqual(render.status, .done)
        XCTAssertEqual(render.preservationRate, 0.92)
        XCTAssertEqual(render.beforeUrl, "https://x/before")
        XCTAssertEqual(render.missingItems, [])
    }

    func testDecodeRenderFailedWithMissingItems() throws {
        let json = """
        {"render_id":"rd_1","room_id":"rm_1","status":"failed","style":"scandi",
         "remove_ids":[],"before_url":null,"after_url":null,
         "preservation_rate":0.4,"missing_items":["A","C"],"error_code":"render_failed",
         "created_at":"2026-09-09T20:20:00Z","credits_left":null}
        """.data(using: .utf8)!
        let render = try JSONCoding.decoder.decode(Render.self, from: json)
        XCTAssertEqual(render.status, .failed)
        XCTAssertEqual(render.missingItems, ["A", "C"])
        XCTAssertEqual(render.errorCode, "render_failed")
        XCTAssertNil(render.creditsLeft)
    }

    func testDecodeApiError() throws {
        let json = """
        {"code":"no_credits","message":"You're out of credits."}
        """.data(using: .utf8)!
        let error = try JSONCoding.decoder.decode(ApiError.self, from: json)
        XCTAssertEqual(error.code, .noCredits)
        XCTAssertEqual(error.message, "You're out of credits.")
    }

    func testDecodeApiErrorNotFound() throws {
        let json = """
        {"code":"not_found","message":"Not found."}
        """.data(using: .utf8)!
        let error = try JSONCoding.decoder.decode(ApiError.self, from: json)
        XCTAssertEqual(error.code, .notFound)
    }

    func testAllErrorCodesRoundTrip() throws {
        // Every value in the frozen ErrorCode enum, verbatim.
        let raw = [
            "apple_token_invalid", "token_expired", "no_credits", "rate_limited",
            "photo_too_large", "photo_unsupported", "no_photos", "no_inventory",
            "inventory_failed", "render_failed", "not_found",
        ]
        for value in raw {
            let json = "{\"code\":\"\(value)\",\"message\":\"m\"}".data(using: .utf8)!
            let error = try JSONCoding.decoder.decode(ApiError.self, from: json)
            XCTAssertEqual(error.code.rawValue, value)
        }
    }

    func testEncodeRenderCreate() throws {
        let body = RenderCreate(
            style: "warm-minimal",
            prompt: "cozy and bright",
            removeIds: ["H", "K"],
            idempotencyKey: "11111111-1111-1111-1111-111111111111"
        )
        let data = try JSONCoding.encoder.encode(body)
        let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertEqual(obj?["style"] as? String, "warm-minimal")
        XCTAssertEqual(obj?["prompt"] as? String, "cozy and bright")
        XCTAssertEqual(obj?["remove_ids"] as? [String], ["H", "K"])
        XCTAssertEqual(obj?["idempotency_key"] as? String, "11111111-1111-1111-1111-111111111111")
    }

    func testEncodeRenderCreateOmitsNilPromptAsNull() throws {
        let body = RenderCreate(style: "scandi", prompt: nil, removeIds: [], idempotencyKey: "k")
        let data = try JSONCoding.encoder.encode(body)
        let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertTrue(obj?["prompt"] is NSNull)
    }

    func testEncodeAppleSignIn() throws {
        let body = AppleSignIn(identityToken: "tok")
        let data = try JSONCoding.encoder.encode(body)
        let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertEqual(obj?["identity_token"] as? String, "tok")
    }

    func testEncodeRoomCreate() throws {
        let body = RoomCreate(label: "Living room")
        let data = try JSONCoding.encoder.encode(body)
        let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertEqual(obj?["label"] as? String, "Living room")
    }
}
