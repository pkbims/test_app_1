import SwiftUI

/// A 2–3 way segmented choice — surface-2 track, white selected segment with the
/// small shadow (`options_review/HANDOFF.md` §5.3, `prototype.html`'s `.seg`).
struct OptionSegmentedControl<Value: Hashable>: View {
    let options: [(value: Value, label: String)]
    @Binding var selection: Value

    var body: some View {
        HStack(spacing: 3) {
            ForEach(options, id: \.value) { option in
                Button {
                    selection = option.value
                } label: {
                    Text(option.label)
                        .font(.system(size: 12.5, weight: selection == option.value ? .semibold : .medium))
                        .foregroundStyle(selection == option.value ? Color.ink : Color.inkSoft)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 4)
                        .background {
                            if selection == option.value {
                                RoundedRectangle(cornerRadius: 9, style: .continuous)
                                    .fill(Color.surface)
                                    .shadow(color: .black.opacity(0.08), radius: 2, x: 0, y: 1)
                            }
                        }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color.surface2)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Color.line, lineWidth: 1)
        )
    }
}

/// One faint pill in a chip row — single- or multi-select, selected state fills
/// accent-soft with an accent border (`.chip.faint` / `.chip.faint.on` in the
/// prototype).
struct OptionChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 12.5, weight: isSelected ? .semibold : .medium))
                .foregroundStyle(isSelected ? Color.accentDeep : Color.inkSoft)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Capsule().fill(isSelected ? Color.accentSoft : Color.surface2))
                .overlay(Capsule().stroke(isSelected ? Color.accent : Color.line, lineWidth: 1))
        }
        .buttonStyle(.plain)
    }
}

/// Keep | Remove — the two-state control on each object row in "Your things"
/// (HANDOFF §5.1, replacing whatever remove-toggle existed before).
struct KeepRemoveControl: View {
    @Binding var isRemoving: Bool

    var body: some View {
        HStack(spacing: 2) {
            segment(title: "Keep", isOn: !isRemoving) { isRemoving = false }
            segment(title: "Remove", isOn: isRemoving) { isRemoving = true }
        }
        .padding(2)
        .background(
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .fill(Color.surface2)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .stroke(Color.line, lineWidth: 1)
        )
    }

    private func segment(title: String, isOn: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 11.5, weight: isOn ? .semibold : .medium))
                .foregroundStyle(isOn ? (isRemoving ? Color.accentDeep : Color.ink) : Color.inkSoft)
                .padding(.horizontal, 9)
                .padding(.vertical, 5)
                .background {
                    if isOn {
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .fill(isRemoving ? Color.accentSoft : Color.surface)
                            .shadow(color: .black.opacity(isRemoving ? 0 : 0.06), radius: 2, x: 0, y: 1)
                    }
                }
        }
        .buttonStyle(.plain)
    }
}
