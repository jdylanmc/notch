//
//  DashboardWidgetInteractionTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class DashboardWidgetInteractionTests: XCTestCase {
    private let metrics = DashboardLayoutMetrics(
        minimumCellWidth: 220,
        rowHeight: 96,
        spacing: 10
    )
    private let constraints = DashboardWidgetConstraints(
        minimum: .init(columns: 1, rows: 1),
        maximum: .init(columns: 4, rows: 2)
    )

    func testMoveUsesResolvedPositionAndClampsAtVisibleColumnEdge() throws {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 4, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let layout = try resolvedLayout(for: instance)
        let resolved = try XCTUnwrap(layout.items.first)
        let step = cellStep(for: resolved)

        XCTAssertEqual(resolved.position, .init(column: 1, row: 0))
        XCTAssertEqual(instance.position, .init(column: 4, row: 0))

        let movedLeft = try XCTUnwrap(
            DashboardWidgetInteraction.move(
                resolved: resolved,
                translation: .init(width: -step.width, height: 0),
                cellStep: step,
                columnCount: layout.columnCount
            )
        )
        XCTAssertEqual(movedLeft.targetPosition, .init(column: 0, row: 0))
        XCTAssertEqual(movedLeft.previewOffset, .init(width: -step.width, height: 0))

        let movedRight = try XCTUnwrap(
            DashboardWidgetInteraction.move(
                resolved: resolved,
                translation: .init(width: step.width, height: 0),
                cellStep: step,
                columnCount: layout.columnCount
            )
        )
        XCTAssertEqual(movedRight.targetPosition, resolved.position)
        XCTAssertEqual(movedRight.previewOffset, .zero)
        XCTAssertEqual(instance.position, .init(column: 4, row: 0))
    }

    func testMovePreviewSnapsInsteadOfFollowingRawPixels() throws {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let layout = try resolvedLayout(for: instance)
        let resolved = try XCTUnwrap(layout.items.first)
        let step = cellStep(for: resolved)

        let belowThreshold = try XCTUnwrap(
            DashboardWidgetInteraction.move(
                resolved: resolved,
                translation: .init(width: step.width * 0.49, height: 0),
                cellStep: step,
                columnCount: layout.columnCount
            )
        )
        XCTAssertEqual(belowThreshold.previewOffset, .zero)

        let aboveThreshold = try XCTUnwrap(
            DashboardWidgetInteraction.move(
                resolved: resolved,
                translation: .init(width: step.width * 0.51, height: 0),
                cellStep: step,
                columnCount: layout.columnCount
            )
        )
        XCTAssertEqual(aboveThreshold.previewOffset, .init(width: step.width, height: 0))
    }

    func testResizeUsesResolvedFootprintAndVisibleColumnLimit() throws {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 4, rows: 1)
        )
        let layout = try resolvedLayout(for: instance)
        let resolved = try XCTUnwrap(layout.items.first)
        let step = cellStep(for: resolved)

        XCTAssertEqual(resolved.footprint, .init(columns: 2, rows: 1))
        XCTAssertEqual(instance.footprint, .init(columns: 4, rows: 1))

        let decreased = try XCTUnwrap(
            DashboardWidgetInteraction.resize(
                resolved: resolved,
                translation: .init(width: -step.width, height: 0),
                context: resizeContext(step: step, columnCount: layout.columnCount)
            )
        )
        XCTAssertEqual(decreased.targetFootprint, .init(columns: 1, rows: 1))
        XCTAssertEqual(decreased.previewSize.width, resolved.frame.width - step.width)

        let increased = try XCTUnwrap(
            DashboardWidgetInteraction.resize(
                resolved: resolved,
                translation: .init(width: step.width, height: 0),
                context: resizeContext(step: step, columnCount: layout.columnCount)
            )
        )
        XCTAssertEqual(increased.targetFootprint, resolved.footprint)
        XCTAssertEqual(increased.previewSize, resolved.frame.size)
        XCTAssertEqual(instance.footprint, .init(columns: 4, rows: 1))
    }

    func testResizeAtVisibleRightEdgeDoesNotCreateHiddenWidth() throws {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 1, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let layout = try resolvedLayout(for: instance)
        let resolved = try XCTUnwrap(layout.items.first)
        let step = cellStep(for: resolved)

        let interaction = try XCTUnwrap(
            DashboardWidgetInteraction.resize(
                resolved: resolved,
                translation: .init(width: step.width, height: 0),
                context: resizeContext(step: step, columnCount: layout.columnCount)
            )
        )

        XCTAssertEqual(interaction.targetFootprint, resolved.footprint)
        XCTAssertEqual(interaction.previewSize, resolved.frame.size)
    }

    func testInsertionOverflowFailsInsteadOfChoosingAnotherRow() {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: Int.max),
            footprint: .init(columns: 1, rows: 1)
        )

        XCTAssertThrowsError(
            try DashboardWidgetInteraction.nextInsertionRow(for: [instance])
        ) { error in
            XCTAssertEqual(error as? DashboardWidgetInteractionError, .coordinateOverflow)
        }
    }

    func testInsertionUsesLowestRowAfterExistingFootprints() throws {
        let instances = [
            DashboardWidgetInstance.shelfSummary(
                position: .init(column: 0, row: 2),
                footprint: .init(columns: 1, rows: 2)
            ),
            DashboardWidgetInstance.shelfSummary(
                position: .init(column: 1, row: 1),
                footprint: .init(columns: 1, rows: 1)
            )
        ]

        XCTAssertEqual(
            try DashboardWidgetInteraction.nextInsertionRow(for: instances),
            4
        )
    }

    func testRecoveryControlPolicyKeepsOnlyCancelAvailable() {
        let policy = DashboardEditControlsPolicy(
            isEditOwner: true,
            isRecoveryRequired: true
        )

        XCTAssertFalse(policy.canAdd)
        XCTAssertFalse(policy.canFinish)
        XCTAssertTrue(policy.canCancel)
    }

    func testLayoutResolutionPreservesUnexpectedFailure() {
        struct FixtureError: LocalizedError {
            var errorDescription: String? { "fixture layout failure" }
        }

        let result = DashboardWidgetInteraction.resolveLayout {
            throw FixtureError()
        }

        XCTAssertEqual(result, .failure(.unexpected("fixture layout failure")))
    }

    func testLayoutResolutionPreservesKnownLayoutFailure() {
        let result = DashboardWidgetInteraction.resolveLayout {
            throw DashboardLayoutError.invalidMetrics
        }

        XCTAssertEqual(result, .failure(.layout(.invalidMetrics)))
    }

    func testAlwaysShowTabsKeepsFullNavigationVisible() {
        XCTAssertEqual(
            NotchHeaderNavigationPolicy.presentation(
                alwaysShowTabs: true,
                shelfEnabled: false,
                shelfIsEmpty: true,
                currentView: .dashboard
            ),
            .tabs
        )
    }

    func testHiddenTabsKeepDashboardReachableFromHome() {
        XCTAssertEqual(
            NotchHeaderNavigationPolicy.presentation(
                alwaysShowTabs: false,
                shelfEnabled: true,
                shelfIsEmpty: true,
                currentView: .home
            ),
            .dashboardShortcut
        )
    }

    func testHiddenTabsKeepHomeReachableFromDashboard() {
        XCTAssertEqual(
            NotchHeaderNavigationPolicy.presentation(
                alwaysShowTabs: false,
                shelfEnabled: false,
                shelfIsEmpty: true,
                currentView: .dashboard
            ),
            .homeShortcut
        )
    }

    func testDisabledShelfWithRetainedContentKeepsCompactNavigation() {
        XCTAssertEqual(
            NotchHeaderNavigationPolicy.presentation(
                alwaysShowTabs: false,
                shelfEnabled: false,
                shelfIsEmpty: false,
                currentView: .home
            ),
            .dashboardShortcut
        )
    }

    func testShelfContentPreservesExistingFullNavigationBehavior() {
        XCTAssertEqual(
            NotchHeaderNavigationPolicy.presentation(
                alwaysShowTabs: false,
                shelfEnabled: true,
                shelfIsEmpty: false,
                currentView: .shelf
            ),
            .tabs
        )
    }

    func testShelfSelectedCompactNavigationWithholdsTabAccessibility() {
        XCTAssertFalse(NotchHeaderNavigationPolicy.exposesCompactTabAccessibility(currentView: .shelf))
        XCTAssertTrue(NotchHeaderNavigationPolicy.exposesCompactTabAccessibility(currentView: .home))
        XCTAssertTrue(NotchHeaderNavigationPolicy.exposesCompactTabAccessibility(currentView: .dashboard))
    }

    func testDisablingAlwaysShowTabsDisablesRememberLastTab() {
        XCTAssertFalse(
            NotchTabPreferencePolicy.rememberLastTab(
                whenAlwaysShowTabsChangesTo: false,
                currentValue: true
            )
        )
    }

    func testEnablingRememberLastTabEnablesAlwaysShowTabs() {
        XCTAssertTrue(
            NotchTabPreferencePolicy.alwaysShowTabs(
                whenRememberLastTabChangesTo: true,
                currentValue: false
            )
        )
    }

    func testHidingTabsPreservesShelfSelectionOnlyWhenConfigured() {
        XCTAssertEqual(
            NotchTabPreferencePolicy.currentViewWhenHidingTabs(
                currentView: .shelf,
                shelfIsEmpty: false,
                openShelfByDefault: true
            ),
            .shelf
        )
        XCTAssertEqual(
            NotchTabPreferencePolicy.currentViewWhenHidingTabs(
                currentView: .shelf,
                shelfIsEmpty: false,
                openShelfByDefault: false
            ),
            .home
        )
    }

    private func resolvedLayout(
        for instance: DashboardWidgetInstance
    ) throws -> DashboardResolvedLayout {
        try DashboardLayoutEngine.resolve(
            instances: [instance],
            availableWidth: 640,
            metrics: metrics,
            constraints: [.shelfSummary: constraints]
        )
    }

    private func cellStep(for resolved: DashboardResolvedWidget) -> CGSize {
        CGSize(
            width: (resolved.frame.width + metrics.spacing)
                / CGFloat(resolved.footprint.columns),
            height: metrics.rowHeight + metrics.spacing
        )
    }

    private func resizeContext(
        step: CGSize,
        columnCount: Int
    ) -> DashboardResizeContext {
        DashboardResizeContext(
            cellStep: step,
            metrics: metrics,
            constraints: constraints,
            columnCount: columnCount
        )
    }
}
