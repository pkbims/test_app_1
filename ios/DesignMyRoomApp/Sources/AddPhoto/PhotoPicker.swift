import PhotosUI
import SwiftUI
import UIKit
import UniformTypeIdentifiers

/// Wraps `PHPickerViewController` (library) for `UIViewControllerRepresentable` use.
/// Out-of-process per Apple's design, so no photo-library usage description is
/// needed — only the camera path below requires an Info.plist string.
struct PhotoLibraryPicker: UIViewControllerRepresentable {
    var onPick: (Data) -> Void
    var onCancel: () -> Void

    func makeUIViewController(context: Context) -> PHPickerViewController {
        var config = PHPickerConfiguration()
        config.filter = .images
        config.selectionLimit = 1
        let picker = PHPickerViewController(configuration: config)
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: PHPickerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onPick: onPick, onCancel: onCancel)
    }

    final class Coordinator: NSObject, PHPickerViewControllerDelegate {
        let onPick: (Data) -> Void
        let onCancel: () -> Void

        init(onPick: @escaping (Data) -> Void, onCancel: @escaping () -> Void) {
            self.onPick = onPick
            self.onCancel = onCancel
        }

        /// Loads the *original file bytes*, not a decoded `UIImage` — a decode step
        /// loses the source format (an on-disk HEIC would come back only as pixels),
        /// which would defeat `PhotoFormatConverter`'s already-tested HEIC-vs-JPEG/PNG
        /// detection: every photo would look "already decoded," so nothing would ever
        /// take the passthrough path, and every upload would pay for a needless
        /// re-encode. Preferring HEIC/HEIF's own type identifier over a generic one
        /// keeps that real: an iPhone photo stays HEIC bytes until the converter
        /// deliberately re-encodes it.
        ///
        /// Deliberately does **not** call `picker.dismiss(animated:)` — this picker
        /// is presented via SwiftUI's `.sheet(isPresented:)`, which already owns the
        /// dismissal and drives it from the `showingLibraryPicker = false` in
        /// `onPick`/`onCancel`. Calling `.dismiss()` here too, imperatively, races
        /// that: it desyncs SwiftUI's belief about what's presented from the real
        /// UIKit hierarchy, which can cascade into SwiftUI incorrectly collapsing an
        /// *ancestor* presentation (the whole New Room flow, not just this sheet) —
        /// reproduced and confirmed via DesignMyRoomUITests/AddPhotoFlowUITests.
        func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
            guard let provider = results.first?.itemProvider else {
                onCancel()
                return
            }
            let preferredTypes = [UTType.heic.identifier, UTType.heif.identifier, UTType.jpeg.identifier, UTType.png.identifier]
            guard let typeIdentifier = preferredTypes.first(where: provider.hasItemConformingToTypeIdentifier)
                ?? provider.registeredTypeIdentifiers.first
            else {
                onCancel()
                return
            }
            provider.loadDataRepresentation(forTypeIdentifier: typeIdentifier) { [onPick, onCancel] data, _ in
                guard let data else {
                    DispatchQueue.main.async { onCancel() }
                    return
                }
                DispatchQueue.main.async { onPick(data) }
            }
        }
    }
}

/// Wraps `UIImagePickerController`'s camera source — the "or camera" half of the
/// brief (screen 2). Requires `NSCameraUsageDescription` in Info.plist.
///
/// Unlike the library picker, there's no "original file" to preserve here — a fresh
/// capture only comes back as a decoded `UIImage` — so this re-encodes to JPEG
/// directly. `PhotoFormatConverter` still runs on the result; it just always takes
/// its passthrough path for a camera photo; since a JPEG encode of a `UIImage`
/// is already an accepted format.
struct CameraPicker: UIViewControllerRepresentable {
    var onPick: (Data) -> Void
    var onCancel: () -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onPick: onPick, onCancel: onCancel)
    }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let onPick: (Data) -> Void
        let onCancel: () -> Void

        init(onPick: @escaping (Data) -> Void, onCancel: @escaping () -> Void) {
            self.onPick = onPick
            self.onCancel = onCancel
        }

        // Same reasoning as PhotoLibraryPicker.Coordinator above: presented via
        // .fullScreenCover(isPresented:), which already owns dismissal via
        // showingCameraPicker — no imperative picker.dismiss() here.
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            guard let image = info[.originalImage] as? UIImage, let data = image.jpegData(compressionQuality: 0.92) else {
                onCancel()
                return
            }
            onPick(data)
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            onCancel()
        }
    }
}
