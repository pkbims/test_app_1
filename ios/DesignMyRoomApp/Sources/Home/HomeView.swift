import DesignMyRoomCore
import SwiftUI

/// The home/history screen (product decision: the app lands here after sign-in, not
/// straight into a fresh room). Gallery grid per `ui_design_v2/HANDOFF.md` §3 — restyle
/// only, still drives the same `HomeViewModel`; `RoomCard` replaces the old text-only
/// `RoomRow` and tapping one still pushes the existing read-only `RoomDetailView` via
/// `NavigationLink(value: room)`. "New Room" is a separate entry point into the existing
/// add-photo flow, presented modally by whatever hosts this view.
struct HomeView: View {
    var viewModel: HomeViewModel
    var creditsLeft: Int
    var onNewRoom: () -> Void
    var onSignOut: () -> Void

    private let columns = [
        GridItem(.flexible(), spacing: Spacing.m),
        GridItem(.flexible(), spacing: Spacing.m),
    ]

    var body: some View {
        // Card width is computed once here (from the screen width, screen-edge padding,
        // and the one inter-column gap) and threaded into `RoomCard` as a fixed value,
        // rather than each card measuring itself — `.aspectRatio`/`GeometryReader` used
        // per grid cell both proved unreliable here (oversized/overlapping cards, or a
        // card whose label text renders outside its own clipped bounds).
        GeometryReader { proxy in
            let cardWidth = (proxy.size.width - 2 * Spacing.screenEdge - Spacing.m) / 2

            ScrollView {
                // `gridCellColumns` only spans multiple columns inside `Grid`, not
                // `LazyVGrid` — the header and empty state live outside the grid
                // entirely (as plain VStack siblings) rather than as grid items, so
                // they don't end up sharing a row with the first room card.
                VStack(alignment: .leading, spacing: Spacing.m) {
                    header

                    if let errorMessage = viewModel.errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 13))
                            .foregroundStyle(Color.warn)
                    }

                    if viewModel.rooms.isEmpty, !viewModel.isLoading, viewModel.errorMessage == nil {
                        emptyState
                    } else {
                        LazyVGrid(columns: columns, spacing: Spacing.m) {
                            ForEach(viewModel.rooms) { room in
                                NavigationLink(value: room) {
                                    RoomCard(room: room, width: cardWidth)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                .padding(Spacing.screenEdge)
            }
            .background(Color.paper.ignoresSafeArea(edges: .top))
            .toolbar(.hidden, for: .navigationBar)
            .overlay {
                if viewModel.isLoading, viewModel.rooms.isEmpty {
                    ProgressView()
                }
            }
            .refreshable {
                await viewModel.loadRooms()
            }
            .safeAreaInset(edge: .bottom) {
                Button(action: onNewRoom) {
                    Text("+ Decorate a New Room")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                }
                .background(Color.accent, in: RoundedRectangle(cornerRadius: Radius.button, style: .continuous))
                .ctaShadow()
                .padding(.horizontal, Spacing.screenEdge)
                .padding(.vertical, Spacing.m)
                .background(Color.paper)
            }
            .task {
                await viewModel.loadRooms()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            Text("My Latest Decors")
                .font(.fraunces(24, weight: .medium))
                .foregroundStyle(Color.ink)
            Spacer()
            HStack(spacing: 10) {
                Text("\(creditsLeft) LEFT")
                    .font(.system(size: 11, design: .monospaced).weight(.semibold))
                    .foregroundStyle(Color.accentDeep)
                    .lineLimit(1)
                    .fixedSize()
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(Capsule().fill(Color.accentSoft))
                Button(action: onSignOut) {
                    Text("Sign out")
                        .font(.system(size: 12.5))
                        .underline()
                        .foregroundStyle(Color.faint)
                }
            }
        }
        .padding(.bottom, Spacing.s)
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.s) {
            Text("🖼️")
                .font(.system(size: 40))
            Text("No rooms yet")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Color.ink)
            Text("Tap \u{201C}Decorate a New Room\u{201D} to restyle your first one — it\u{2019}s free.")
                .font(.system(size: 13.5))
                .foregroundStyle(Color.inkSoft)
                .multilineTextAlignment(.center)
        }
        .padding(.vertical, 36)
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: Radius.dashedCard, style: .continuous)
                .fill(Color.surface)
        )
        .overlay(
            RoundedRectangle(cornerRadius: Radius.dashedCard, style: .continuous)
                .strokeBorder(Color.line, style: StrokeStyle(lineWidth: 1, dash: [5, 4]))
        )
    }
}

/// Image-first grid card — HANDOFF §3. `thumbnailUrl` resolves to the room's latest
/// done render, its original photo, or nil (rendered as the `surface2` placeholder,
/// same color while `AsyncImage` is still loading or the load failed — never a broken-
/// image glyph).
private struct RoomCard: View {
    let room: Room
    let width: CGFloat

    var body: some View {
        thumbnail
            .frame(width: width, height: width * 4 / 3)
            .overlay(alignment: .bottom) { scrim }
            .overlay(alignment: .bottomLeading) { labels }
            .clipShape(RoundedRectangle(cornerRadius: Radius.gridCard, style: .continuous))
            .cardShadow()
    }

    @ViewBuilder
    private var thumbnail: some View {
        if let urlString = room.thumbnailUrl, let url = URL(string: urlString) {
            AsyncImage(url: url) { phase in
                if case .success(let image) = phase {
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .clipped()
                } else {
                    Color.surface2
                }
            }
        } else {
            Color.surface2
        }
    }

    private var scrim: some View {
        LinearGradient(
            colors: [Color.black.opacity(0.78), Color.black.opacity(0)],
            startPoint: .bottom,
            endPoint: UnitPoint(x: 0.5, y: 0.32)
        )
    }

    private var labels: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(room.label ?? "Room")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(.white)
                .lineLimit(1)
            Text(room.createdAt.formatted(date: .abbreviated, time: .omitted))
                .font(.system(size: 11))
                .foregroundStyle(.white.opacity(0.82))
        }
        .padding(.horizontal, 12)
        .padding(.bottom, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
