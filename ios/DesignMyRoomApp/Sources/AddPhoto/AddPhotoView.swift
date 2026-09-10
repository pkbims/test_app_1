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
        VStack(spacing: Spacing.xl) {
            Spacer()

            VStack(spacing: Spacing.s) {
                Text("Add a photo of your room")
                    .font(.fraunces(20, weight: .medium))
                    .foregroundStyle(Color.ink)
                Text("One photo is all we need. Frame the whole room — anything we can't see, we can't protect.")
                    .font(.system(size: 14))
                    .foregroundStyle(Color.inkSoft)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            dropZone

            Spacer()

            if let conversionError {
                Text(conversionError)
                    .font(.footnote)
                    .foregroundStyle(Color.warn)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            if let bannerMessage = flow.bannerMessage {
                Text(bannerMessage)
                    .font(.footnote)
                    .foregroundStyle(Color.warn)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Button {
                showingSourcePicker = true
            } label: {
                if flow.isBusy {
                    ProgressView()
                        .tint(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                } else {
                    Text("Add a photo")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                }
            }
            .background(Color.accent, in: RoundedRectangle(cornerRadius: Radius.button, style: .continuous))
            .disabled(flow.isBusy)
            .padding(.horizontal, 32)
            .padding(.bottom, 24)
        }
        .background(Color.paper.ignoresSafeArea())
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

    // HANDOFF §2 "Add a photo": the icon-plus-button pairing becomes one large
    // square drop-zone card that's itself a tap target — same confirmationDialog/
    // picker wiring as the "Add a photo" button below, only the empty-state visual
    // changes.
    private var dropZone: some View {
        Button {
            showingSourcePicker = true
        } label: {
            VStack(spacing: Spacing.m) {
                ZStack {
                    Circle()
                        .fill(Color.accentSoft)
                        .frame(width: 64, height: 64)
                    Image(systemName: "camera.fill")
                        .font(.system(size: 24))
                        .foregroundStyle(Color.accentDeep)
                }
                Text("Tap to take or choose a photo")
                    .font(.system(size: 14))
                    .foregroundStyle(Color.inkSoft)
            }
            .frame(width: 220, height: 220)
            .background(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(Color.surface2)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .strokeBorder(Color.line, style: StrokeStyle(lineWidth: 1.5, dash: [6, 5]))
            )
        }
        .buttonStyle(.plain)
        .disabled(flow.isBusy)
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
