//
//  DashboardWidgetInteraction.swift
//  notchPocket
//

import CoreGraphics
import Foundation

struct DashboardMoveInteraction: Equatable {
    var targetPosition: DashboardGridPosition
    var previewOffset: CGSize
}

struct DashboardResizeInteraction: Equatable {
    var targetFootprint: DashboardGridFootprint
    var previewSize: CGSize
}

struct DashboardResizeContext: Equatable {
    var cellStep: CGSize
    var metrics: DashboardLayoutMetrics
    var constraints: DashboardWidgetConstraints
    var columnCount: Int
}

enum DashboardWidgetInteractionError: Error, Equatable {
    case coordinateOverflow
}

enum DashboardLayoutPresentationError: Error, Equatable {
    case layout(DashboardLayoutError)
    case unexpected(String)

    var diagnosticDescription: String {
        switch self {
        case .layout(let error):
            String(describing: error)
        case .unexpected(let message):
            message
        }
    }
}

struct DashboardEditControlsPolicy: Equatable {
    let isEditOwner: Bool
    let isRecoveryRequired: Bool

    var canAdd: Bool { isEditOwner && !isRecoveryRequired }
    var canFinish: Bool { isEditOwner && !isRecoveryRequired }
    var canCancel: Bool { isEditOwner }
}

enum DashboardWidgetInteraction {
    static func move(
        resolved: DashboardResolvedWidget,
        translation: CGSize,
        cellStep: CGSize,
        columnCount: Int
    ) -> DashboardMoveInteraction? {
        guard columnCount > 0,
              resolved.footprint.columns > 0,
              resolved.footprint.columns <= columnCount,
              let proposed = DashboardEditGeometry.movedPosition(
                from: resolved.position,
                translation: translation,
                cellStep: cellStep
              )
        else {
            return nil
        }
        let maximumColumn = columnCount - resolved.footprint.columns
        let target = DashboardGridPosition(
            column: min(proposed.column, maximumColumn),
            row: proposed.row
        )
        guard let previewOffset = previewOffset(
            from: resolved.position,
            to: target,
            cellStep: cellStep
        ) else {
            return nil
        }
        return DashboardMoveInteraction(
            targetPosition: target,
            previewOffset: previewOffset
        )
    }

    static func resize(
        resolved: DashboardResolvedWidget,
        translation: CGSize,
        context: DashboardResizeContext
    ) -> DashboardResizeInteraction? {
        guard context.columnCount > 0,
              resolved.position.column >= 0,
              resolved.position.column < context.columnCount
        else {
            return nil
        }
        let availableColumns = context.columnCount - resolved.position.column
        let maximumColumns = min(
            max(1, context.constraints.maximum.columns),
            availableColumns
        )
        let visibleConstraints = DashboardWidgetConstraints(
            minimum: .init(
                columns: min(max(1, context.constraints.minimum.columns), maximumColumns),
                rows: max(1, context.constraints.minimum.rows)
            ),
            maximum: .init(
                columns: maximumColumns,
                rows: max(1, context.constraints.maximum.rows)
            )
        )
        guard visibleConstraints.minimum.rows <= visibleConstraints.maximum.rows,
              let footprint = DashboardEditGeometry.resizedFootprint(
                from: resolved.footprint,
                translation: translation,
                cellStep: context.cellStep,
                constraints: visibleConstraints
              ),
              let previewSize = previewSize(
                for: footprint,
                cellStep: context.cellStep,
                metrics: context.metrics
              )
        else {
            return nil
        }
        return DashboardResizeInteraction(
            targetFootprint: footprint,
            previewSize: previewSize
        )
    }

    static func nextInsertionRow(
        for instances: [DashboardWidgetInstance]
    ) throws -> Int {
        var nextRow = 0
        for instance in instances {
            let (bottom, overflow) = instance.position.row.addingReportingOverflow(
                instance.footprint.rows
            )
            guard !overflow else {
                throw DashboardWidgetInteractionError.coordinateOverflow
            }
            nextRow = max(nextRow, bottom)
        }
        return nextRow
    }

    static func resolveLayout(
        _ operation: () throws -> DashboardResolvedLayout
    ) -> Result<DashboardResolvedLayout, DashboardLayoutPresentationError> {
        do {
            return .success(try operation())
        } catch let error as DashboardLayoutError {
            return .failure(.layout(error))
        } catch {
            return .failure(.unexpected(error.localizedDescription))
        }
    }

    private static func previewOffset(
        from current: DashboardGridPosition,
        to target: DashboardGridPosition,
        cellStep: CGSize
    ) -> CGSize? {
        let (columnDelta, columnOverflow) = target.column.subtractingReportingOverflow(
            current.column
        )
        let (rowDelta, rowOverflow) = target.row.subtractingReportingOverflow(current.row)
        guard !columnOverflow, !rowOverflow else { return nil }
        let offset = CGSize(
            width: CGFloat(columnDelta) * cellStep.width,
            height: CGFloat(rowDelta) * cellStep.height
        )
        guard offset.width.isFinite, offset.height.isFinite else { return nil }
        return offset
    }

    private static func previewSize(
        for footprint: DashboardGridFootprint,
        cellStep: CGSize,
        metrics: DashboardLayoutMetrics
    ) -> CGSize? {
        guard cellStep.width.isFinite,
              cellStep.height.isFinite,
              metrics.spacing.isFinite,
              metrics.rowHeight.isFinite
        else {
            return nil
        }
        let cellWidth = cellStep.width - metrics.spacing
        let width = CGFloat(footprint.columns) * cellWidth
            + CGFloat(footprint.columns - 1) * metrics.spacing
        let height = CGFloat(footprint.rows) * metrics.rowHeight
            + CGFloat(footprint.rows - 1) * metrics.spacing
        guard width.isFinite, height.isFinite, width > 0, height > 0 else {
            return nil
        }
        return CGSize(width: width, height: height)
    }
}
