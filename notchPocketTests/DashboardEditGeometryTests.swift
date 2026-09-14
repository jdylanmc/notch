//
//  DashboardEditGeometryTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class DashboardEditGeometryTests: XCTestCase {
    func testMoveSnapsTranslationAndClampsAtGridOrigin() {
        XCTAssertEqual(
            DashboardEditGeometry.movedPosition(
                from: .init(column: 2, row: 3),
                translation: .init(width: 120, height: -160),
                cellStep: .init(width: 100, height: 100)
            ),
            .init(column: 3, row: 1)
        )
    }

    func testResizeSnapsTranslationAndClampsToWidgetConstraints() {
        XCTAssertEqual(
            DashboardEditGeometry.resizedFootprint(
                from: .init(columns: 1, rows: 1),
                translation: .init(width: 260, height: -100),
                cellStep: .init(width: 100, height: 100),
                constraints: .init(
                    minimum: .init(columns: 1, rows: 1),
                    maximum: .init(columns: 2, rows: 2)
                )
            ),
            .init(columns: 2, rows: 1)
        )
    }

    func testInvalidGeometryPreservesTheExistingDraft() {
        XCTAssertNil(
            DashboardEditGeometry.movedPosition(
                from: .init(column: 1, row: 1),
                translation: .init(width: CGFloat.infinity, height: 0),
                cellStep: .init(width: 100, height: 100)
            )
        )
        XCTAssertNil(
            DashboardEditGeometry.resizedFootprint(
                from: .init(columns: 1, rows: 1),
                translation: .zero,
                cellStep: .init(width: 0, height: 100),
                constraints: .init(
                    minimum: .init(columns: 1, rows: 1),
                    maximum: .init(columns: 2, rows: 2)
                )
            )
        )
    }
}
