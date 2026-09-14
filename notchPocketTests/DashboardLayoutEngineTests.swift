//
//  DashboardLayoutEngineTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class DashboardLayoutEngineTests: XCTestCase {
    private let metrics = DashboardLayoutMetrics(
        minimumCellWidth: 100,
        rowHeight: 60,
        spacing: 10
    )
    private let constraints: [DashboardWidgetKind: DashboardWidgetConstraints] = [
        .shelfSummary: .init(
            minimum: .init(columns: 1, rows: 1),
            maximum: .init(columns: 2, rows: 2)
        )
    ]

    func testCollisionMovesToNearestAvailableSnappedCell() throws {
        let first = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 2, rows: 1)
        )
        let second = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            position: .init(column: 1, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )

        let layout = try DashboardLayoutEngine.resolve(
            instances: [first, second],
            availableWidth: 320,
            metrics: metrics,
            constraints: constraints
        )

        XCTAssertEqual(layout.columnCount, 3)
        XCTAssertEqual(layout.items[0].position, .init(column: 0, row: 0))
        XCTAssertEqual(layout.items[1].position, .init(column: 2, row: 0))
        XCTAssertEqual(layout.items[1].frame.origin.x, 220, accuracy: 0.001)
    }

    func testNarrowLayoutReflowsWithoutMutatingCanonicalInstances() throws {
        let first = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let second = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            position: .init(column: 2, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let canonical = [first, second]

        let layout = try DashboardLayoutEngine.resolve(
            instances: canonical,
            availableWidth: 100,
            metrics: metrics,
            constraints: constraints
        )

        XCTAssertEqual(layout.columnCount, 1)
        XCTAssertEqual(layout.items.map(\.position), [
            .init(column: 0, row: 0),
            .init(column: 0, row: 1)
        ])
        XCTAssertEqual(canonical[1].position, .init(column: 2, row: 0))
        XCTAssertEqual(layout.contentHeight, 130, accuracy: 0.001)
    }

    func testFootprintIsClampedToWidgetAndAvailableWidthConstraints() throws {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: -4, row: -2),
            footprint: .init(columns: 5, rows: 0)
        )

        let layout = try DashboardLayoutEngine.resolve(
            instances: [instance],
            availableWidth: 320,
            metrics: metrics,
            constraints: constraints
        )

        XCTAssertEqual(layout.items[0].position, .init(column: 0, row: 0))
        XCTAssertEqual(layout.items[0].footprint, .init(columns: 2, rows: 1))
        XCTAssertEqual(layout.items[0].frame.size.width, 210, accuracy: 0.001)
        XCTAssertEqual(layout.items[0].frame.size.height, 60, accuracy: 0.001)
    }

    func testOversizedFootprintIsRejectedWithinWorkBudget() {
        let instance = DashboardWidgetInstance(
            id: UUID(),
            kind: DashboardWidgetKind(rawValue: "futureWidget"),
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 65),
            settings: [:]
        )

        XCTAssertThrowsError(
            try DashboardLayoutEngine.resolve(
                instances: [instance],
                availableWidth: 100,
                metrics: metrics,
                constraints: [:],
                workBudget: .init(maxCandidateChecks: 64, maximumFootprintSpan: 64)
            )
        ) { error in
            XCTAssertEqual(
                error as? DashboardLayoutError,
                .footprintExceedsWorkBudget(instanceID: instance.id)
            )
        }
    }

    func testBillionRowCollisionResolvesWithBoundedWorkAndPreservesInput() throws {
        let first = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            position: .init(column: 0, row: 1_000_000_000),
            footprint: .init(columns: 1, rows: 1)
        )
        let second = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            position: .init(column: 0, row: 1_000_000_000),
            footprint: .init(columns: 1, rows: 1)
        )
        let canonical = [first, second]

        let layout = try DashboardLayoutEngine.resolve(
            instances: canonical,
            availableWidth: 100,
            metrics: metrics,
            constraints: constraints,
            workBudget: .init(maxCandidateChecks: 64, maximumFootprintSpan: 64)
        )

        XCTAssertEqual(layout.items.map(\.position), [
            .init(column: 0, row: 1_000_000_000),
            .init(column: 0, row: 999_999_999)
        ])
        XCTAssertEqual(canonical, [first, second])
        XCTAssertTrue(layout.contentHeight.isFinite)
    }

    func testMaximumRowIsRejectedWithoutChangingCanonicalInput() {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: Int.max),
            footprint: .init(columns: 1, rows: 1)
        )
        let canonical = [instance]

        XCTAssertThrowsError(
            try DashboardLayoutEngine.resolve(
                instances: canonical,
                availableWidth: 100,
                metrics: metrics,
                constraints: constraints,
                workBudget: .init(maxCandidateChecks: 64, maximumFootprintSpan: 64)
            )
        ) { error in
            XCTAssertEqual(
                error as? DashboardLayoutError,
                .coordinateOverflow(instanceID: instance.id)
            )
        }
        XCTAssertEqual(canonical, [instance])
    }

    func testMaximumUnknownFootprintIsRejectedWithoutEnumeratingCells() {
        let instance = DashboardWidgetInstance(
            id: UUID(),
            kind: DashboardWidgetKind(rawValue: "futureWidget"),
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: Int.max),
            settings: [:]
        )

        XCTAssertThrowsError(
            try DashboardLayoutEngine.resolve(
                instances: [instance],
                availableWidth: 100,
                metrics: metrics,
                constraints: [:],
                workBudget: .init(maxCandidateChecks: 64, maximumFootprintSpan: 64)
            )
        ) { error in
            XCTAssertEqual(
                error as? DashboardLayoutError,
                .footprintExceedsWorkBudget(instanceID: instance.id)
            )
        }
    }

    func testPrecisionCollapsedPixelFramesAreRejectedWithoutChangingCanonicalInput() {
        let row = 18_014_398_509_481_984
        let first = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            position: .init(column: 0, row: row),
            footprint: .init(columns: 1, rows: 1)
        )
        let second = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            position: .init(column: 0, row: row),
            footprint: .init(columns: 1, rows: 1)
        )
        let canonical = [first, second]

        XCTAssertThrowsError(
            try DashboardLayoutEngine.resolve(
                instances: canonical,
                availableWidth: 100,
                metrics: metrics,
                constraints: constraints,
                workBudget: .init(maxCandidateChecks: 64, maximumFootprintSpan: 64)
            )
        ) { error in
            XCTAssertEqual(
                error as? DashboardLayoutError,
                .unrepresentableGeometry(instanceID: first.id)
            )
        }
        XCTAssertEqual(canonical, [first, second])
    }

    func testNonFiniteFinalFrameEdgeIsRejectedWithoutChangingCanonicalInput() {
        let availableWidth = CGFloat.greatestFiniteMagnitude
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 2, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let canonical = [instance]

        XCTAssertThrowsError(
            try DashboardLayoutEngine.resolve(
                instances: canonical,
                availableWidth: availableWidth,
                metrics: .init(
                    minimumCellWidth: availableWidth / 3,
                    rowHeight: 60,
                    spacing: 0
                ),
                constraints: constraints,
                workBudget: .init(maxCandidateChecks: 64, maximumFootprintSpan: 64)
            )
        ) { error in
            XCTAssertEqual(
                error as? DashboardLayoutError,
                .nonFiniteGeometry(instanceID: instance.id)
            )
        }
        XCTAssertEqual(canonical, [instance])
    }
}
