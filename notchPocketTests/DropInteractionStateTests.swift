//
//  DropInteractionStateTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class DropInteractionStateTests: XCTestCase {
    func testWidgetTargetParticipatesInAggregateTargeting() {
        let state = DropInteractionState()
        let source = UUID()

        state.setWidgetDropTargeting(true, sourceID: source)

        XCTAssertTrue(state.widgetDropTargeting)
        XCTAssertTrue(state.anyDropZoneTargeting)
    }

    func testOverlappingWidgetTargetsRemainActiveUntilEverySourceClears() {
        let state = DropInteractionState()
        let first = UUID()
        let second = UUID()

        state.setWidgetDropTargeting(true, sourceID: first)
        state.setWidgetDropTargeting(true, sourceID: second)
        state.setWidgetDropTargeting(false, sourceID: first)

        XCTAssertTrue(state.widgetDropTargeting)
        XCTAssertTrue(state.anyDropZoneTargeting)

        state.setWidgetDropTargeting(false, sourceID: second)

        XCTAssertFalse(state.widgetDropTargeting)
        XCTAssertFalse(state.anyDropZoneTargeting)
    }

    func testWidgetCleanupDoesNotTrampleOtherDropSources() {
        let state = DropInteractionState()
        let source = UUID()
        state.generalDropTargeting = true
        state.setWidgetDropTargeting(true, sourceID: source)

        state.setWidgetDropTargeting(false, sourceID: source)

        XCTAssertFalse(state.widgetDropTargeting)
        XCTAssertTrue(state.anyDropZoneTargeting)
    }

    func testRepeatedTransitionsAndCleanupAreIdempotent() {
        let state = DropInteractionState()
        let source = UUID()

        state.setWidgetDropTargeting(true, sourceID: source)
        state.setWidgetDropTargeting(true, sourceID: source)
        state.setWidgetDropTargeting(false, sourceID: source)
        state.setWidgetDropTargeting(false, sourceID: source)

        XCTAssertFalse(state.widgetDropTargeting)
        XCTAssertFalse(state.anyDropZoneTargeting)
    }
}
