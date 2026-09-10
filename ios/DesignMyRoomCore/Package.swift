// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "DesignMyRoomCore",
    platforms: [.iOS(.v17), .macOS(.v13)],
    products: [
        .library(name: "DesignMyRoomCore", targets: ["DesignMyRoomCore"])
    ],
    targets: [
        .target(name: "DesignMyRoomCore"),
        .testTarget(name: "DesignMyRoomCoreTests", dependencies: ["DesignMyRoomCore"])
    ]
)
