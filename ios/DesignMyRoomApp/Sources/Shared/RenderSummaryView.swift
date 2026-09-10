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
        VStack(alignment: .leading, spacing: Spacing.m) {
            labelledImage(title: "Before", urlString: render.beforeUrl)
            labelledImage(title: "After", urlString: render.afterUrl)

            if let rate = render.preservationRate {
                fidelityCard(rate: rate)
            }

            if let missing = render.missingItems, !missing.isEmpty {
                missingItemsBanner(missing)
            }
        }
    }

    // HANDOFF §2 "Compare": before/after get a small uppercase tag chip overlaid
    // top-left instead of a separate label row above each image.
    @ViewBuilder
    private func labelledImage(title: String, urlString: String?) -> some View {
        if let urlString, let url = URL(string: urlString) {
            ZStack(alignment: .topLeading) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image.resizable().aspectRatio(contentMode: .fit)
                    case .failure:
                        Color.surface2
                    default:
                        ProgressView()
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(minHeight: 180)
                .clipShape(RoundedRectangle(cornerRadius: Radius.beforeAfterImage, style: .continuous))
                .cardShadow()

                Text(title.uppercased())
                    .font(.system(size: 10.5, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.black.opacity(0.55), in: Capsule())
                    .padding(8)
            }
        }
    }

    // HANDOFF §2/§3: fidelity is the headline metric (PRD §9), so it gets a
    // dedicated card rather than a plain row — the number in Fraunces SemiBold next
    // to a two-line description of what it means.
    private func fidelityCard(rate: Double) -> some View {
        HStack(alignment: .top, spacing: Spacing.m) {
            Text("\(Int((rate * 100).rounded()))%")
                .font(.fraunces(30, weight: .semibold))
                .foregroundStyle(Color.accentDeep)
            Text("Preservation — how much of your room's structure survived the restyle.")
                .font(.system(size: 13))
                .foregroundStyle(Color.inkSoft)
        }
        .padding(Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.surface2)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(Color.line, lineWidth: 1)
        )
    }

    // The `warnSoft` low-confidence banner from HANDOFF §1's color table.
    private func missingItemsBanner(_ missing: [String]) -> some View {
        HStack(alignment: .top, spacing: Spacing.s) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 13))
                .foregroundStyle(Color.warn)
            Text("Not found in the result: \(missing.joined(separator: ", "))")
                .font(.system(size: 12.5))
                .foregroundStyle(Color.warn)
        }
        .padding(Spacing.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color.warnSoft)
        )
    }
}
