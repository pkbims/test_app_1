import SwiftUI

/// Shared section chrome for the confirm and style screens' controls — icon gutter,
/// serif heading, an optional right-hand note (`locked` / `optional` / a live count),
/// a helper line that changes with the selection, and a divider above every section
/// but the first (`options_review/HANDOFF.md` §5.3, mirroring `prototype.html`'s
/// `.opt` block). One place to keep the two screens visually identical.
struct OptionSection<Content: View>: View {
    let icon: String
    let title: String
    var note: String?
    /// An occasional non-text accessory on the heading line — e.g. the plants
    /// switch (HANDOFF §5.2: "heading with a switch on the same line"). Wins over
    /// `note` when both are set.
    var trailingAccessory: AnyView?
    var isFirst: Bool = false
    let helper: String
    @ViewBuilder var content: Content

    private let gutterWidth: CGFloat = 28

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if !isFirst {
                Rectangle()
                    .fill(Color.line)
                    .frame(height: 1)
                    .padding(.bottom, 16)
            }
            HStack(alignment: .top, spacing: 0) {
                Text(icon)
                    .font(.system(size: 17))
                    .frame(width: gutterWidth, alignment: .leading)
                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(title)
                            .font(.fraunces(17, weight: .semibold))
                            .foregroundStyle(Color.ink)
                        Spacer(minLength: 0)
                        if let trailingAccessory {
                            trailingAccessory
                        } else if let note {
                            Text(note)
                                .font(.system(size: 11.5))
                                .foregroundStyle(Color.faint)
                        }
                    }
                    if !helper.isEmpty {
                        Text(helper)
                            .font(.system(size: 12))
                            .foregroundStyle(Color.inkSoft)
                    }
                    content
                }
            }
            .padding(.bottom, 12)
        }
    }
}
