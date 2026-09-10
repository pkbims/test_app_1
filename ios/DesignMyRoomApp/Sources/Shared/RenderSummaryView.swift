import DesignMyRoomCore
import SwiftUI

/// Stacked before/after (U3 — never a slider, output isn't pixel-aligned with
/// input), preservation rate, and missing items for one finished `Render`. Shared
/// between the live flow's `CompareView` (the render that just finished) and
/// `RoomDetailView` (every past render for a room, read-only) so the two never
/// drift into showing this differently.
struct RenderSummaryView: View {
    let render: Render

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            labelledImage(title: "Before", urlString: render.beforeUrl)
            labelledImage(title: "After", urlString: render.afterUrl)

            if let rate = render.preservationRate {
                HStack {
                    Text("Preservation")
                        .font(.subheadline.weight(.medium))
                    Spacer()
                    Text("\(Int((rate * 100).rounded()))%")
                        .font(.subheadline.weight(.semibold))
                }
            }

            if let missing = render.missingItems, !missing.isEmpty {
                Text("Not found in the result: \(missing.joined(separator: ", "))")
                    .font(.footnote)
                    .foregroundStyle(.orange)
            }
        }
    }

    @ViewBuilder
    private func labelledImage(title: String, urlString: String?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased())
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            if let urlString, let url = URL(string: urlString) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image.resizable().aspectRatio(contentMode: .fit)
                    case .failure:
                        Color.secondary.opacity(0.15)
                    default:
                        ProgressView()
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(minHeight: 180)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }
}
