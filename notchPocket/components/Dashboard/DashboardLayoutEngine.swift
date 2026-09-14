//
//  DashboardLayoutEngine.swift
//  notchPocket
//

import CoreGraphics
import Foundation

struct DashboardWidgetConstraints: Equatable, Sendable {
    var minimum: DashboardGridFootprint
    var maximum: DashboardGridFootprint
}

struct DashboardLayoutMetrics: Equatable, Sendable {
    var minimumCellWidth: CGFloat
    var rowHeight: CGFloat
    var spacing: CGFloat
}

struct DashboardLayoutWorkBudget: Equatable, Sendable {
    static let standard = DashboardLayoutWorkBudget(
        maxCandidateChecks: 50_000,
        maximumFootprintSpan: 4_096
    )

    var maxCandidateChecks: Int
    var maximumFootprintSpan: Int
}

enum DashboardLayoutError: Error, Equatable {
    case invalidMetrics
    case footprintExceedsWorkBudget(instanceID: UUID)
    case coordinateOverflow(instanceID: UUID)
    case candidateWorkBudgetExceeded
    case nonFiniteGeometry(instanceID: UUID)
    case unrepresentableGeometry(instanceID: UUID)
}

struct DashboardResolvedLayout: Equatable, Sendable {
    var columnCount: Int
    var items: [DashboardResolvedWidget]
    var contentHeight: CGFloat
}

struct DashboardResolvedWidget: Equatable, Identifiable, Sendable {
    var id: UUID
    var position: DashboardGridPosition
    var footprint: DashboardGridFootprint
    var frame: CGRect
}

enum DashboardLayoutEngine {
    static func resolve(
        instances: [DashboardWidgetInstance],
        availableWidth: CGFloat,
        metrics: DashboardLayoutMetrics,
        constraints: [DashboardWidgetKind: DashboardWidgetConstraints],
        workBudget: DashboardLayoutWorkBudget = .standard
    ) throws -> DashboardResolvedLayout {
        let columnCount = try resolvedColumnCount(
            availableWidth: availableWidth,
            metrics: metrics
        )
        guard workBudget.maxCandidateChecks > 0, workBudget.maximumFootprintSpan > 0 else {
            throw DashboardLayoutError.invalidMetrics
        }

        let cellWidth = (availableWidth - CGFloat(columnCount - 1) * metrics.spacing)
            / CGFloat(columnCount)
        guard cellWidth.isFinite, cellWidth >= 0 else {
            throw DashboardLayoutError.invalidMetrics
        }

        let context = DashboardLayoutResolutionContext(
            columnCount: columnCount,
            cellWidth: cellWidth,
            metrics: metrics,
            constraints: constraints,
            workBudget: workBudget
        )
        var state = DashboardLayoutResolutionState(remainingWork: workBudget.maxCandidateChecks)
        for instance in instances {
            try appendResolved(instance, context: context, state: &state)
        }

        let contentHeight = state.resolved.map(\.frame.maxY).max() ?? 0
        guard contentHeight.isFinite else {
            throw DashboardLayoutError.invalidMetrics
        }
        return DashboardResolvedLayout(
            columnCount: columnCount,
            items: state.resolved,
            contentHeight: contentHeight
        )
    }

    private static func appendResolved(
        _ instance: DashboardWidgetInstance,
        context: DashboardLayoutResolutionContext,
        state: inout DashboardLayoutResolutionState
    ) throws {
        try consumeWork(&state.remainingWork)
        let footprint = try clampedFootprint(
            instance,
            columnCount: context.columnCount,
            constraints: context.constraints,
            workBudget: context.workBudget
        )
        let requested = DashboardGridPosition(
            column: min(
                max(0, instance.position.column),
                context.columnCount - footprint.columns
            ),
            row: max(0, instance.position.row)
        )
        let placementContext = DashboardPlacementContext(
            instanceID: instance.id,
            footprint: footprint,
            columnCount: context.columnCount,
            occupied: state.occupied,
            workBudget: context.workBudget
        )
        let position = try nearestAvailablePosition(
            requested: requested,
            context: placementContext,
            remainingWork: &state.remainingWork
        )
        let rectangle = try DashboardGridRectangle(
            instanceID: instance.id,
            position: position,
            footprint: footprint
        )
        let frame = try resolvedFrame(
            instanceID: instance.id,
            position: position,
            footprint: footprint,
            context: context
        )
        guard state.resolved.allSatisfy({ !$0.frame.intersects(frame) }) else {
            throw DashboardLayoutError.unrepresentableGeometry(instanceID: instance.id)
        }
        state.occupied.append(rectangle)
        state.resolved.append(
            DashboardResolvedWidget(
                id: instance.id,
                position: position,
                footprint: footprint,
                frame: frame
            )
        )
    }

    private static func resolvedFrame(
        instanceID: UUID,
        position: DashboardGridPosition,
        footprint: DashboardGridFootprint,
        context: DashboardLayoutResolutionContext
    ) throws -> CGRect {
        let width = CGFloat(footprint.columns) * context.cellWidth
            + CGFloat(footprint.columns - 1) * context.metrics.spacing
        let height = CGFloat(footprint.rows) * context.metrics.rowHeight
            + CGFloat(footprint.rows - 1) * context.metrics.spacing
        let origin = CGPoint(
            x: CGFloat(position.column) * (context.cellWidth + context.metrics.spacing),
            y: CGFloat(position.row) * (context.metrics.rowHeight + context.metrics.spacing)
        )
        let frame = CGRect(origin: origin, size: CGSize(width: width, height: height))
        guard frame.origin.x.isFinite,
              frame.origin.y.isFinite,
              frame.width.isFinite,
              frame.height.isFinite,
              frame.minX.isFinite,
              frame.minY.isFinite,
              frame.maxX.isFinite,
              frame.maxY.isFinite
        else {
            throw DashboardLayoutError.nonFiniteGeometry(instanceID: instanceID)
        }
        guard frame.minX < frame.maxX, frame.minY < frame.maxY else {
            throw DashboardLayoutError.unrepresentableGeometry(instanceID: instanceID)
        }
        return frame
    }

    private static func resolvedColumnCount(
        availableWidth: CGFloat,
        metrics: DashboardLayoutMetrics
    ) throws -> Int {
        guard availableWidth.isFinite,
              availableWidth >= 0,
              metrics.minimumCellWidth.isFinite,
              metrics.minimumCellWidth > 0,
              metrics.rowHeight.isFinite,
              metrics.rowHeight > 0,
              metrics.spacing.isFinite,
              metrics.spacing >= 0
        else {
            throw DashboardLayoutError.invalidMetrics
        }
        let divisor = metrics.minimumCellWidth + metrics.spacing
        let quotient = (availableWidth + metrics.spacing) / divisor
        guard quotient.isFinite, quotient < CGFloat(Int.max) else {
            throw DashboardLayoutError.invalidMetrics
        }
        return max(1, Int(quotient))
    }

    private static func clampedFootprint(
        _ instance: DashboardWidgetInstance,
        columnCount: Int,
        constraints: [DashboardWidgetKind: DashboardWidgetConstraints],
        workBudget: DashboardLayoutWorkBudget
    ) throws -> DashboardGridFootprint {
        let explicitConstraint = constraints[instance.kind]
        let exceedsUnconstrainedBudget = explicitConstraint == nil
            && (instance.footprint.columns > workBudget.maximumFootprintSpan
                || instance.footprint.rows > workBudget.maximumFootprintSpan)
        if exceedsUnconstrainedBudget {
            throw DashboardLayoutError.footprintExceedsWorkBudget(instanceID: instance.id)
        }
        let constraint = explicitConstraint ?? DashboardWidgetConstraints(
            minimum: .init(columns: 1, rows: 1),
            maximum: .init(
                columns: min(columnCount, workBudget.maximumFootprintSpan),
                rows: workBudget.maximumFootprintSpan
            )
        )
        let maximumColumns = min(max(1, constraint.maximum.columns), columnCount)
        let minimumColumns = min(max(1, constraint.minimum.columns), maximumColumns)
        let maximumRows = max(1, constraint.maximum.rows)
        let minimumRows = min(max(1, constraint.minimum.rows), maximumRows)
        let footprint = DashboardGridFootprint(
            columns: min(max(instance.footprint.columns, minimumColumns), maximumColumns),
            rows: min(max(instance.footprint.rows, minimumRows), maximumRows)
        )
        guard footprint.columns <= workBudget.maximumFootprintSpan,
              footprint.rows <= workBudget.maximumFootprintSpan
        else {
            throw DashboardLayoutError.footprintExceedsWorkBudget(instanceID: instance.id)
        }
        return footprint
    }

    private static func nearestAvailablePosition(
        requested: DashboardGridPosition,
        context: DashboardPlacementContext,
        remainingWork: inout Int
    ) throws -> DashboardGridPosition {
        let requestedRectangle = try DashboardGridRectangle(
            instanceID: context.instanceID,
            position: requested,
            footprint: context.footprint
        )
        if try isAvailable(
            requestedRectangle,
            occupied: context.occupied,
            remainingWork: &remainingWork
        ) {
            return requested
        }

        let (candidateColumns, candidateRows) = try candidateAxes(
            requested: requested,
            context: context,
            remainingWork: &remainingWork
        )
        let (candidateCount, overflow) = candidateColumns.count.multipliedReportingOverflow(
            by: candidateRows.count
        )
        guard !overflow, candidateCount <= context.workBudget.maxCandidateChecks else {
            throw DashboardLayoutError.candidateWorkBudgetExceeded
        }

        var best: DashboardGridPosition?
        var bestDistance: UInt?
        for row in candidateRows {
            for column in candidateColumns {
                let candidate = DashboardGridPosition(column: column, row: row)
                let rectangle = try DashboardGridRectangle(
                    instanceID: context.instanceID,
                    position: candidate,
                    footprint: context.footprint
                )
                guard try isAvailable(
                    rectangle,
                    occupied: context.occupied,
                    remainingWork: &remainingWork
                ) else {
                    continue
                }
                let distance = gridDistance(from: requested, to: candidate)
                if isBetterCandidate(
                    candidate,
                    distance: distance,
                    than: best,
                    bestDistance: bestDistance
                ) {
                    best = candidate
                    bestDistance = distance
                }
            }
        }

        guard let best else {
            throw DashboardLayoutError.candidateWorkBudgetExceeded
        }
        return best
    }

    private static func candidateAxes(
        requested: DashboardGridPosition,
        context: DashboardPlacementContext,
        remainingWork: inout Int
    ) throws -> (columns: Set<Int>, rows: Set<Int>) {
        let maxColumn = context.columnCount - context.footprint.columns
        var columns: Set<Int> = [0, maxColumn, requested.column]
        var rows: Set<Int> = [0, requested.row]
        var globalBottom = 0

        for rectangle in context.occupied {
            try consumeWork(&remainingWork)
            globalBottom = max(globalBottom, rectangle.maxRow)
            if rectangle.maxColumn <= maxColumn {
                columns.insert(rectangle.maxColumn)
            }
            if rectangle.minColumn >= context.footprint.columns {
                columns.insert(rectangle.minColumn - context.footprint.columns)
            }
            rows.insert(rectangle.maxRow)
            if rectangle.minRow >= context.footprint.rows {
                rows.insert(rectangle.minRow - context.footprint.rows)
            }
        }
        rows.insert(globalBottom)
        return (columns, rows)
    }

    private static func isBetterCandidate(
        _ candidate: DashboardGridPosition,
        distance: UInt,
        than best: DashboardGridPosition?,
        bestDistance: UInt?
    ) -> Bool {
        guard let best, let bestDistance else { return true }
        if distance != bestDistance {
            return distance < bestDistance
        }
        return (candidate.row, candidate.column) < (best.row, best.column)
    }

    private static func isAvailable(
        _ candidate: DashboardGridRectangle,
        occupied: [DashboardGridRectangle],
        remainingWork: inout Int
    ) throws -> Bool {
        for rectangle in occupied {
            try consumeWork(&remainingWork)
            if rectangle.intersects(candidate) {
                return false
            }
        }
        return true
    }

    private static func consumeWork(_ remainingWork: inout Int) throws {
        guard remainingWork > 0 else {
            throw DashboardLayoutError.candidateWorkBudgetExceeded
        }
        remainingWork -= 1
    }

    private static func gridDistance(
        from first: DashboardGridPosition,
        to second: DashboardGridPosition
    ) -> UInt {
        let columnDistance = UInt(max(first.column, second.column) - min(first.column, second.column))
        let rowDistance = UInt(max(first.row, second.row) - min(first.row, second.row))
        let (distance, overflow) = columnDistance.addingReportingOverflow(rowDistance)
        return overflow ? UInt.max : distance
    }
}

private struct DashboardLayoutResolutionContext {
    let columnCount: Int
    let cellWidth: CGFloat
    let metrics: DashboardLayoutMetrics
    let constraints: [DashboardWidgetKind: DashboardWidgetConstraints]
    let workBudget: DashboardLayoutWorkBudget
}

private struct DashboardLayoutResolutionState {
    var occupied: [DashboardGridRectangle] = []
    var resolved: [DashboardResolvedWidget] = []
    var remainingWork: Int
}

private struct DashboardPlacementContext {
    let instanceID: UUID
    let footprint: DashboardGridFootprint
    let columnCount: Int
    let occupied: [DashboardGridRectangle]
    let workBudget: DashboardLayoutWorkBudget
}

private struct DashboardGridRectangle {
    let minColumn: Int
    let minRow: Int
    let maxColumn: Int
    let maxRow: Int

    init(
        instanceID: UUID,
        position: DashboardGridPosition,
        footprint: DashboardGridFootprint
    ) throws {
        let (maxColumn, columnOverflow) = position.column.addingReportingOverflow(
            footprint.columns
        )
        let (maxRow, rowOverflow) = position.row.addingReportingOverflow(footprint.rows)
        guard !columnOverflow, !rowOverflow else {
            throw DashboardLayoutError.coordinateOverflow(instanceID: instanceID)
        }
        minColumn = position.column
        minRow = position.row
        self.maxColumn = maxColumn
        self.maxRow = maxRow
    }

    func intersects(_ other: Self) -> Bool {
        minColumn < other.maxColumn
            && maxColumn > other.minColumn
            && minRow < other.maxRow
            && maxRow > other.minRow
    }
}
