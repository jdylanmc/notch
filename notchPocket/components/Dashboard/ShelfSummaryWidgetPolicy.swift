//
//  ShelfSummaryWidgetPolicy.swift
//  notchPocket
//

struct ShelfSummaryWidgetPolicy: Equatable {
    let isShelfEnabled: Bool
    let isEditing: Bool
    let isInternalShelfDrag: Bool

    var isAvailable: Bool { isShelfEnabled }
    var exposesItemCount: Bool { isShelfEnabled }
    var canOpenShelf: Bool { isShelfEnabled && !isEditing }
    var canAcceptDrop: Bool {
        isShelfEnabled && !isEditing && !isInternalShelfDrag
    }
}
