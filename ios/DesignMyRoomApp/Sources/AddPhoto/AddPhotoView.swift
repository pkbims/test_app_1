import DesignMyRoomCore
import SwiftUI
import UIKit

/// Screen 2 (AGENT.md): one photo, asked once, silently (U1) — no "add another"
/// prompt. HEIC->JPEG conversion and the 12MB check both happen here, before the
/// photo ever reaches `RoomFlowViewModel`/the network.
struct AddPhotoView: View {
    @Bindable var flow: RoomFlowViewModel

    @State private var showingSourcePicker = false
    @State private var showingLibraryPicker = false
    @State private var showingCameraPicker = false
    @State private var conversionError: String?

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            Image(systemName: "camera.on.rectangle")
                .font(.system(size: 56))
                .foregroundStyle(.secondary)
            Text("Add a photo of your room")
                .font(.title2.weight(.semibold))
            Text("One photo is all we need. Frame the whole room — anything we can't see, we can't protect.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Spacer()

            if let conversionError {
                Text(conversionError)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            if let bannerMessage = flow.bannerMessage {
                Text(bannerMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Button {
                showingSourcePicker = true
            } label: {
                if flow.isBusy {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                } else {
                    Text("Add a photo")
                        .frame(maxWidth: .infinity)
                }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(flow.isBusy)
            .padding(.horizontal, 32)
            .padding(.bottom, 24)
        }
        .confirmationDialog("Add a photo", isPresented: $showingSourcePicker) {
            // UIImagePickerController crashes if asked for a camera source that
            // doesn't exist — true of every Simulator, and some devices/contexts.
            if UIImagePickerController.isSourceTypeAvailable(.camera) {
                Button("Take Photo") { showingCameraPicker = true }
            }
            Button("Choose from Library") { showingLibraryPicker = true }
            Button("Cancel", role: .cancel) {}
        }
        .sheet(isPresented: $showingLibraryPicker) {
            PhotoLibraryPicker(onPick: handlePicked, onCancel: { showingLibraryPicker = false })
        }
        .fullScreenCover(isPresented: $showingCameraPicker) {
            CameraPicker(onPick: handlePicked, onCancel: { showingCameraPicker = false })
                .ignoresSafeArea()
        }
    }

    private func handlePicked(_ rawData: Data) {
        showingLibraryPicker = false
        showingCameraPicker = false
        conversionError = nil

        do {
            let converted = try PhotoFormatConverter.convertToAcceptedFormatIfNeeded(rawData)
            guard PhotoValidation.isWithinSizeLimit(converted) else {
                conversionError = ErrorCopy.message(for: .photoTooLarge)
                return
            }
            Task {
                await flow.submitPhoto(data: converted, filename: "room.jpg", mimeType: "image/jpeg")
            }
        } catch {
            conversionError = ErrorCopy.message(for: .photoUnsupported)
        }
    }
}
