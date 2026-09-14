//
//  ShelfSummaryWidget.swift
//  notchPocket
//

import Defaults
import SwiftUI
import UniformTypeIdentifiers

@MainActor
struct ShelfSummaryWidget: View {
    let settings: ShelfSummaryWidgetSettings
    let isEditing: Bool
    let dropInteraction: DropInteractionState

    @Default(.notchPocketShelf) private var shelfEnabled
    @StateObject private var shelfState = ShelfStateViewModel.shared
    @ObservedObject private var coordinator = NotchPocketViewCoordinator.shared
    @State private var isDropTargeted = false
    @State private var dropTargetSourceID = UUID()

    private let supportedDropTypes: [UTType] = [
        .fileURL,
        .url,
        .utf8PlainText,
        .plainText,
        .data
    ]

    var body: some View {
        Group {
            if !policy.isAvailable {
                unavailableCard
            } else if isEditing {
                card
            } else {
                Button {
                    guard currentPolicy.canOpenShelf else { return }
                    coordinator.currentView = .shelf
                } label: {
                    card
                }
                .buttonStyle(.plain)
                .onDrop(of: supportedDropTypes, isTargeted: dropTargetBinding) { providers in
                    guard currentPolicy.canAcceptDrop else {
                        clearDropTarget()
                        return false
                    }
                    dropInteraction.dropEvent = true
                    shelfState.load(providers)
                    clearDropTarget()
                    return true
                }
                .accessibilityHint(
                    "Opens the full Shelf. You can also drop supported items here."
                )
            }
        }
        .onChange(of: shelfEnabled) {
            if !shelfEnabled {
                clearDropTarget()
            }
        }
        .onChange(of: isEditing) {
            if isEditing {
                clearDropTarget()
            }
        }
        .onDisappear(perform: clearDropTarget)
    }

    private var policy: ShelfSummaryWidgetPolicy {
        ShelfSummaryWidgetPolicy(
            isShelfEnabled: shelfEnabled,
            isEditing: isEditing,
            isInternalShelfDrag: false
        )
    }

    private var currentPolicy: ShelfSummaryWidgetPolicy {
        ShelfSummaryWidgetPolicy(
            isShelfEnabled: shelfEnabled,
            isEditing: isEditing,
            isInternalShelfDrag: ShelfSelectionModel.shared.isDragging
        )
    }

    private var dropTargetBinding: Binding<Bool> {
        Binding(
            get: { isDropTargeted },
            set: { isTargeted in
                isDropTargeted = isTargeted
                dropInteraction.setWidgetDropTargeting(
                    isTargeted,
                    sourceID: dropTargetSourceID
                )
            }
        )
    }

    private var card: some View {
        HStack(spacing: 12) {
            Image(systemName: isDropTargeted ? "tray.and.arrow.down.fill" : "tray.fill")
                .font(.title2)
                .foregroundStyle(isDropTargeted ? Color.accentColor : .white)
                .frame(width: 34, height: 34)
                .background(Color.white.opacity(0.08), in: Circle())
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 3) {
                Text("Shelf")
                    .font(.headline)

                if policy.exposesItemCount && settings.showsItemCount {
                    Text("\(shelfState.items.count) shelf items")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } else {
                    Text("Open full Shelf")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer(minLength: 4)

            if !isEditing {
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .accessibilityHidden(true)
            }
        }
        .padding(.horizontal, 14)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            isDropTargeted ? Color.accentColor.opacity(0.12) : Color.white.opacity(0.04)
        )
        .clipShape(.rect(cornerRadius: 14))
        .contentShape(.rect)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
    }

    private var unavailableCard: some View {
        HStack(spacing: 12) {
            Image(systemName: "tray")
                .font(.title2)
                .foregroundStyle(.secondary)
                .frame(width: 34, height: 34)
                .background(Color.white.opacity(0.05), in: Circle())
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 3) {
                Text("Shelf is disabled")
                    .font(.headline)
                Text("Enable Shelf in Settings to use this widget.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer(minLength: 4)
        }
        .padding(.horizontal, 14)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.white.opacity(0.03))
        .clipShape(.rect(cornerRadius: 14))
        .accessibilityElement(children: .combine)
    }

    private var accessibilityLabel: Text {
        if policy.exposesItemCount && settings.showsItemCount {
            Text("Shelf, \(shelfState.items.count) items")
        } else {
            Text("Shelf")
        }
    }

    private func clearDropTarget() {
        isDropTargeted = false
        dropInteraction.setWidgetDropTargeting(false, sourceID: dropTargetSourceID)
    }
}
