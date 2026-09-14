//
//  DashboardWidgetCard.swift
//  notchPocket
//

import SwiftUI

@MainActor
struct DashboardWidgetCard: View {
    let instance: DashboardWidgetInstance
    let resolved: DashboardResolvedWidget
    let columnCount: Int
    let metrics: DashboardLayoutMetrics
    let constraints: DashboardWidgetConstraints?
    let ownerID: UUID
    let isEditing: Bool
    @ObservedObject var controller: DashboardController
    let dropInteraction: DropInteractionState
    @Binding var editError: DashboardEditError?

    @State private var movePreview: DashboardMoveInteraction?
    @State private var resizePreview: DashboardResizeInteraction?

    private var cellStep: CGSize {
        CGSize(
            width: (resolved.frame.width + metrics.spacing) / CGFloat(resolved.footprint.columns),
            height: metrics.rowHeight + metrics.spacing
        )
    }

    var body: some View {
        widget
            .frame(
                width: resizePreview?.previewSize.width ?? resolved.frame.width,
                height: resizePreview?.previewSize.height ?? resolved.frame.height
            )
            .overlay {
                RoundedRectangle(cornerRadius: 14)
                    .stroke(
                        isEditing ? Color.accentColor.opacity(0.85) : Color.white.opacity(0.1),
                        style: StrokeStyle(
                            lineWidth: isEditing ? 2 : 1,
                            dash: isEditing ? [6, 4] : []
                        )
                    )
                    .allowsHitTesting(false)
            }
            .overlay(alignment: .topLeading) {
                if isEditing {
                    moveHandle
                }
            }
            .overlay(alignment: .topTrailing) {
                if isEditing {
                    editMenu
                }
            }
            .overlay(alignment: .bottomTrailing) {
                if isEditing, constraints != nil {
                    resizeHandle
                }
            }
            .offset(movePreview?.previewOffset ?? .zero)
            .zIndex(movePreview == nil && resizePreview == nil ? 0 : 1)
    }

    @ViewBuilder
    private var widget: some View {
        if instance.kind == .shelfSummary {
            ShelfSummaryWidget(
                settings: instance.shelfSummarySettings ?? .init(showsItemCount: true),
                isEditing: isEditing,
                dropInteraction: dropInteraction
            )
        } else {
            VStack(spacing: 5) {
                Image(systemName: "square.dashed")
                    .accessibilityHidden(true)
                Text("Widget unavailable")
                    .font(.headline)
                Text(instance.kind.rawValue)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.white.opacity(0.04))
            .clipShape(.rect(cornerRadius: 14))
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Unavailable widget: \(instance.kind.rawValue)")
        }
    }

    private var moveHandle: some View {
        Image(systemName: "arrow.up.and.down.and.arrow.left.and.right")
            .font(.caption.weight(.semibold))
            .padding(7)
            .background(.black.opacity(0.75), in: Circle())
            .contentShape(Circle())
            .offset(x: 5, y: 5)
            .gesture(
                DragGesture(
                    minimumDistance: 3,
                    coordinateSpace: .named(instance.id)
                )
                    .onChanged { value in
                        movePreview = moveInteraction(for: value.translation)
                    }
                    .onEnded { value in
                        let interaction = moveInteraction(for: value.translation)
                        movePreview = nil
                        guard let interaction else {
                            editError = .invalidConfiguration
                            return
                        }
                        handle(controller.move(
                            instanceID: instance.id,
                            to: interaction.targetPosition,
                            ownerID: ownerID
                        ))
                    }
            )
            .accessibilityLabel("Move widget")
            .accessibilityHint("Drag to move the widget between grid cells.")
            .accessibilityAddTraits(.isButton)
    }

    private var resizeHandle: some View {
        Image(systemName: "arrow.down.right.and.arrow.up.left")
            .font(.caption.weight(.semibold))
            .padding(7)
            .background(.black.opacity(0.75), in: Circle())
            .contentShape(Circle())
            .offset(x: -5, y: -5)
            .gesture(
                DragGesture(
                    minimumDistance: 3,
                    coordinateSpace: .named(instance.id)
                )
                    .onChanged { value in
                        resizePreview = resizeInteraction(for: value.translation)
                    }
                    .onEnded { value in
                        let interaction = resizeInteraction(for: value.translation)
                        resizePreview = nil
                        guard let interaction else {
                            editError = .invalidConfiguration
                            return
                        }
                        commitResize(interaction)
                    }
            )
            .accessibilityLabel("Resize widget")
            .accessibilityHint("Drag to resize the widget by grid cells.")
            .accessibilityAddTraits(.isButton)
    }

    private var editMenu: some View {
        Menu {
            Button("Move Left", systemImage: "arrow.left") {
                move(columns: -1, rows: 0)
            }
            Button("Move Right", systemImage: "arrow.right") {
                move(columns: 1, rows: 0)
            }
            Button("Move Up", systemImage: "arrow.up") {
                move(columns: 0, rows: -1)
            }
            Button("Move Down", systemImage: "arrow.down") {
                move(columns: 0, rows: 1)
            }

            if constraints != nil {
                Divider()
                Button("Increase Width", systemImage: "arrow.left.and.right") {
                    resize(columns: 1, rows: 0)
                }
                Button("Decrease Width", systemImage: "arrow.right.and.left") {
                    resize(columns: -1, rows: 0)
                }
                Button("Increase Height", systemImage: "arrow.up.and.down") {
                    resize(columns: 0, rows: 1)
                }
                Button("Decrease Height", systemImage: "arrow.down.and.up") {
                    resize(columns: 0, rows: -1)
                }
            }

            if let settings = instance.shelfSummarySettings {
                Divider()
                if settings.showsItemCount {
                    Button("Hide Item Count", systemImage: "number.slash") {
                        setShowsItemCount(false)
                    }
                } else {
                    Button("Show Item Count", systemImage: "number") {
                        setShowsItemCount(true)
                    }
                }
            }

            Divider()
            Button("Remove Widget", systemImage: "trash", role: .destructive) {
                handle(controller.remove(instanceID: instance.id, ownerID: ownerID))
            }
        } label: {
            Image(systemName: "ellipsis.circle.fill")
                .font(.title3)
                .symbolRenderingMode(.hierarchical)
                .padding(5)
        }
        .menuStyle(.borderlessButton)
        .fixedSize()
        .offset(x: -3, y: 3)
        .accessibilityLabel("Widget actions")
    }

    private func move(columns: Int, rows: Int) {
        guard let interaction = moveInteraction(
            for: .init(
                width: CGFloat(columns) * cellStep.width,
                height: CGFloat(rows) * cellStep.height
            )
        ) else {
            editError = .invalidConfiguration
            return
        }
        handle(controller.move(
            instanceID: instance.id,
            to: interaction.targetPosition,
            ownerID: ownerID
        ))
    }

    private func resize(columns: Int, rows: Int) {
        guard let interaction = resizeInteraction(
            for: .init(
                width: CGFloat(columns) * cellStep.width,
                height: CGFloat(rows) * cellStep.height
            )
        ) else {
            editError = .invalidConfiguration
            return
        }
        commitResize(interaction)
    }

    private func moveInteraction(for translation: CGSize) -> DashboardMoveInteraction? {
        DashboardWidgetInteraction.move(
            resolved: resolved,
            translation: translation,
            cellStep: cellStep,
            columnCount: columnCount
        )
    }

    private func resizeInteraction(
        for translation: CGSize
    ) -> DashboardResizeInteraction? {
        guard let constraints else { return nil }
        return DashboardWidgetInteraction.resize(
            resolved: resolved,
            translation: translation,
            context: DashboardResizeContext(
                cellStep: cellStep,
                metrics: metrics,
                constraints: constraints,
                columnCount: columnCount
            )
        )
    }

    private func setShowsItemCount(_ showsItemCount: Bool) {
        handle(controller.setSetting(
            .bool(showsItemCount),
            forKey: "showsItemCount",
            instanceID: instance.id,
            ownerID: ownerID
        ))
    }

    private func commitResize(_ interaction: DashboardResizeInteraction) {
        handle(DashboardWidgetEditCommitter.commitResize(
            controller: controller,
            ownerID: ownerID,
            instanceID: instance.id,
            resolvedPosition: resolved.position,
            footprint: interaction.targetFootprint
        ))
    }

    private func handle(_ result: DashboardEditResult) {
        switch result {
        case .success:
            editError = nil
        case .failure(let error):
            editError = error
        }
    }
}
