//
//  DashboardWidgetEditCommitterTests.swift
//  notchPocketTests
//

import Foundation
import XCTest

@testable import notchPocket

@MainActor
final class DashboardWidgetEditCommitterTests: XCTestCase {
    private final class MemoryDataStore: DashboardConfigurationDataStore {
        var data: Data?

        func read() throws -> Data? {
            data
        }

        func write(_ data: Data) throws {
            self.data = data
        }
    }

    private let owner = UUID(uuidString: "00000000-0000-0000-0000-00000000000A")!
    private let otherOwner = UUID(uuidString: "00000000-0000-0000-0000-00000000000B")!
    private let metrics = DashboardLayoutMetrics(
        minimumCellWidth: 220,
        rowHeight: 96,
        spacing: 10
    )
    private let constraints: [DashboardWidgetKind: DashboardWidgetConstraints] = [
        .shelfSummary: .init(
            minimum: .init(columns: 1, rows: 1),
            maximum: .init(columns: 2, rows: 2)
        )
    ]

    func testResizeCommitPinsResolvedOriginFromReachableCollisionSequence() throws {
        let (controller, second) = makeCollisionFixture()
        let before = try resolvedLayout(controller: controller)
        let resolved = try XCTUnwrap(before.items.first(where: { $0.id == second.id }))
        XCTAssertEqual(resolved.position, .init(column: 0, row: 1))
        XCTAssertEqual(resolved.footprint, .init(columns: 2, rows: 1))

        let interaction = try XCTUnwrap(
            DashboardWidgetInteraction.resize(
                resolved: resolved,
                translation: .init(width: -cellStep(for: resolved).width, height: 0),
                context: .init(
                    cellStep: cellStep(for: resolved),
                    metrics: metrics,
                    constraints: constraints[.shelfSummary]!,
                    columnCount: before.columnCount
                )
            )
        )
        XCTAssertEqual(
            DashboardWidgetEditCommitter.commitResize(
                controller: controller,
                ownerID: owner,
                instanceID: second.id,
                resolvedPosition: resolved.position,
                footprint: interaction.targetFootprint
            ),
            .success
        )

        let draft = try XCTUnwrap(
            controller.configuration(for: owner)?.instances.first(where: {
                $0.id == second.id
            })
        )
        XCTAssertEqual(draft.position, .init(column: 0, row: 1))
        XCTAssertEqual(draft.footprint, .init(columns: 1, rows: 1))

        let after = try resolvedLayout(controller: controller)
        XCTAssertEqual(
            after.items.first(where: { $0.id == second.id })?.position,
            .init(column: 0, row: 1)
        )
    }

    func testStaleOwnerCannotPartiallyApplyResize() throws {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let controller = makeController(instances: [instance])
        XCTAssertEqual(controller.beginEditing(ownerID: owner), .success)
        let before = controller.configuration(for: owner)

        XCTAssertEqual(
            DashboardWidgetEditCommitter.commitResize(
                controller: controller,
                ownerID: otherOwner,
                instanceID: instance.id,
                resolvedPosition: .init(column: 1, row: 1),
                footprint: .init(columns: 2, rows: 1)
            ),
            .failure(.notEditOwner)
        )
        XCTAssertEqual(controller.configuration(for: owner), before)
    }

    func testMissingInstanceCannotPartiallyApplyResize() {
        let controller = makeController()
        XCTAssertEqual(controller.beginEditing(ownerID: owner), .success)
        let before = controller.configuration(for: owner)

        XCTAssertEqual(
            DashboardWidgetEditCommitter.commitResize(
                controller: controller,
                ownerID: owner,
                instanceID: UUID(),
                resolvedPosition: .init(column: 1, row: 1),
                footprint: .init(columns: 2, rows: 1)
            ),
            .failure(.instanceNotFound)
        )
        XCTAssertEqual(controller.configuration(for: owner), before)
    }

    func testInvalidPositionIsRejectedBeforeFootprintMutation() {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let controller = makeController(instances: [instance])
        XCTAssertEqual(controller.beginEditing(ownerID: owner), .success)
        let before = controller.configuration(for: owner)

        XCTAssertEqual(
            DashboardWidgetEditCommitter.commitResize(
                controller: controller,
                ownerID: owner,
                instanceID: instance.id,
                resolvedPosition: .init(column: -1, row: 0),
                footprint: .init(columns: 2, rows: 1)
            ),
            .failure(.invalidConfiguration)
        )
        XCTAssertEqual(controller.configuration(for: owner), before)
    }

    func testInvalidFootprintIsRejectedBeforePositionMutation() {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let controller = makeController(instances: [instance])
        XCTAssertEqual(controller.beginEditing(ownerID: owner), .success)
        let before = controller.configuration(for: owner)

        XCTAssertEqual(
            DashboardWidgetEditCommitter.commitResize(
                controller: controller,
                ownerID: owner,
                instanceID: instance.id,
                resolvedPosition: .init(column: 1, row: 1),
                footprint: .init(columns: 0, rows: 1)
            ),
            .failure(.invalidConfiguration)
        )
        XCTAssertEqual(controller.configuration(for: owner), before)
    }

    private func makeController(
        instances: [DashboardWidgetInstance] = []
    ) -> DashboardController {
        DashboardController(
            store: DashboardConfigurationStore(dataStore: MemoryDataStore()),
            seed: DashboardConfiguration(revision: 0, instances: instances)
        )
    }

    private func makeCollisionFixture() -> (
        controller: DashboardController,
        second: DashboardWidgetInstance
    ) {
        let first = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let second = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            position: .init(column: 0, row: 1),
            footprint: .init(columns: 1, rows: 1)
        )
        let controller = makeController(instances: [first, second])
        XCTAssertEqual(controller.beginEditing(ownerID: owner), .success)
        XCTAssertEqual(
            controller.resize(
                instanceID: second.id,
                to: .init(columns: 2, rows: 1),
                ownerID: owner
            ),
            .success
        )
        XCTAssertEqual(
            controller.move(
                instanceID: second.id,
                to: .init(column: 0, row: 0),
                ownerID: owner
            ),
            .success
        )
        return (controller, second)
    }

    private func resolvedLayout(
        controller: DashboardController
    ) throws -> DashboardResolvedLayout {
        let configuration = try XCTUnwrap(controller.configuration(for: owner))
        return try DashboardLayoutEngine.resolve(
            instances: configuration.instances,
            availableWidth: 640,
            metrics: metrics,
            constraints: constraints
        )
    }

    private func cellStep(for resolved: DashboardResolvedWidget) -> CGSize {
        CGSize(
            width: (resolved.frame.width + metrics.spacing)
                / CGFloat(resolved.footprint.columns),
            height: metrics.rowHeight + metrics.spacing
        )
    }
}
