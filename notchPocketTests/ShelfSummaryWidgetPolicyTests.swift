//
//  ShelfSummaryWidgetPolicyTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class ShelfSummaryWidgetPolicyTests: XCTestCase {
    func testEnabledNormalModeExposesCountAndAllowsShelfActions() {
        let policy = ShelfSummaryWidgetPolicy(
            isShelfEnabled: true,
            isEditing: false,
            isInternalShelfDrag: false
        )

        XCTAssertTrue(policy.isAvailable)
        XCTAssertTrue(policy.exposesItemCount)
        XCTAssertTrue(policy.canOpenShelf)
        XCTAssertTrue(policy.canAcceptDrop)
    }

    func testDisabledShelfExposesNoCountOrActions() {
        let policy = ShelfSummaryWidgetPolicy(
            isShelfEnabled: false,
            isEditing: false,
            isInternalShelfDrag: false
        )

        XCTAssertFalse(policy.isAvailable)
        XCTAssertFalse(policy.exposesItemCount)
        XCTAssertFalse(policy.canOpenShelf)
        XCTAssertFalse(policy.canAcceptDrop)
    }

    func testEditingDisablesFeatureActionsWithoutHidingEnabledPresentation() {
        let policy = ShelfSummaryWidgetPolicy(
            isShelfEnabled: true,
            isEditing: true,
            isInternalShelfDrag: false
        )

        XCTAssertTrue(policy.isAvailable)
        XCTAssertTrue(policy.exposesItemCount)
        XCTAssertFalse(policy.canOpenShelf)
        XCTAssertFalse(policy.canAcceptDrop)
    }

    func testInternalShelfDragRejectsDropWithoutDisablingOpenAction() {
        let policy = ShelfSummaryWidgetPolicy(
            isShelfEnabled: true,
            isEditing: false,
            isInternalShelfDrag: true
        )

        XCTAssertTrue(policy.canOpenShelf)
        XCTAssertFalse(policy.canAcceptDrop)
    }
}
