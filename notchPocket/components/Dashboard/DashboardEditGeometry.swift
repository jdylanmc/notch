//
//  DashboardEditGeometry.swift
//  notchPocket
//

import CoreGraphics
import Foundation

enum DashboardEditGeometry {
    static func movedPosition(
        from position: DashboardGridPosition,
        translation: CGSize,
        cellStep: CGSize
    ) -> DashboardGridPosition? {
        guard position.column >= 0,
              position.row >= 0,
              let columnDelta = snappedDelta(translation.width, step: cellStep.width),
              let rowDelta = snappedDelta(translation.height, step: cellStep.height)
        else {
            return nil
        }
        let (column, columnOverflow) = position.column.addingReportingOverflow(columnDelta)
        let (row, rowOverflow) = position.row.addingReportingOverflow(rowDelta)
        guard !columnOverflow, !rowOverflow else { return nil }
        return DashboardGridPosition(column: max(0, column), row: max(0, row))
    }

    static func resizedFootprint(
        from footprint: DashboardGridFootprint,
        translation: CGSize,
        cellStep: CGSize,
        constraints: DashboardWidgetConstraints
    ) -> DashboardGridFootprint? {
        guard footprint.columns > 0,
              footprint.rows > 0,
              constraints.minimum.columns > 0,
              constraints.minimum.rows > 0,
              constraints.maximum.columns >= constraints.minimum.columns,
              constraints.maximum.rows >= constraints.minimum.rows,
              let columnDelta = snappedDelta(translation.width, step: cellStep.width),
              let rowDelta = snappedDelta(translation.height, step: cellStep.height)
        else {
            return nil
        }
        let (columns, columnOverflow) = footprint.columns.addingReportingOverflow(columnDelta)
        let (rows, rowOverflow) = footprint.rows.addingReportingOverflow(rowDelta)
        guard !columnOverflow, !rowOverflow else { return nil }
        return DashboardGridFootprint(
            columns: min(
                max(columns, constraints.minimum.columns),
                constraints.maximum.columns
            ),
            rows: min(
                max(rows, constraints.minimum.rows),
                constraints.maximum.rows
            )
        )
    }

    private static func snappedDelta(_ translation: CGFloat, step: CGFloat) -> Int? {
        guard translation.isFinite, step.isFinite, step > 0 else { return nil }
        return Int(exactly: (translation / step).rounded())
    }
}
