//
//  DashboardWidgetEditCommitter.swift
//  notchPocket
//

import Foundation

@MainActor
enum DashboardWidgetEditCommitter {
    static func commitResize(
        controller: DashboardController,
        ownerID: UUID,
        instanceID: UUID,
        resolvedPosition: DashboardGridPosition,
        footprint: DashboardGridFootprint
    ) -> DashboardEditResult {
        if case .recoveryRequired = controller.loadResult {
            return .failure(.recoveryRequired)
        }
        guard let session = controller.editSession,
              session.ownerID == ownerID
        else {
            return .failure(.notEditOwner)
        }
        guard let index = session.draft.instances.firstIndex(where: {
            $0.id == instanceID
        }) else {
            return .failure(.instanceNotFound)
        }
        guard resolvedPosition.column >= 0,
              resolvedPosition.row >= 0,
              footprint.columns > 0,
              footprint.rows > 0
        else {
            return .failure(.invalidConfiguration)
        }

        var moved = session.draft
        moved.instances[index].position = resolvedPosition
        guard isValid(moved) else {
            return .failure(.invalidConfiguration)
        }
        var resized = moved
        resized.instances[index].footprint = footprint
        guard isValid(resized) else {
            return .failure(.invalidConfiguration)
        }

        // Both mutations are prevalidated and run synchronously on MainActor,
        // so the second operation cannot observe an intervening draft change.
        let moveResult = controller.move(
            instanceID: instanceID,
            to: resolvedPosition,
            ownerID: ownerID
        )
        guard moveResult == .success else { return moveResult }
        return controller.resize(
            instanceID: instanceID,
            to: footprint,
            ownerID: ownerID
        )
    }

    private static func isValid(_ configuration: DashboardConfiguration) -> Bool {
        guard configuration.identityValidationError == nil else { return false }
        return configuration.instances.allSatisfy {
            $0.position.column >= 0
                && $0.position.row >= 0
                && $0.footprint.columns > 0
                && $0.footprint.rows > 0
        }
    }
}
