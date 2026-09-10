import SwiftUI

@main
struct DesignMyRoomApp: App {
    @State private var environment = AppEnvironment()

    var body: some Scene {
        WindowGroup {
            RootView(environment: environment)
        }
    }
}
