//
//  DropInteractionState.swift
//  notchPocket
//

import Foundation
import Observation

@Observable
final class DropInteractionState {
    var dragDetectorTargeting = false
    var generalDropTargeting = false
    var dropZoneTargeting = false
    var dropEvent = false
    private var widgetDropTargetSources: Set<UUID> = []

    var widgetDropTargeting: Bool {
        !widgetDropTargetSources.isEmpty
    }

    var anyDropZoneTargeting: Bool {
        dragDetectorTargeting || generalDropTargeting || dropZoneTargeting || widgetDropTargeting
    }

    func setWidgetDropTargeting(_ isTargeted: Bool, sourceID: UUID) {
        if isTargeted {
            widgetDropTargetSources.insert(sourceID)
        } else {
            widgetDropTargetSources.remove(sourceID)
        }
    }
}
