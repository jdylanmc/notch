//
//  CompactMusicHoverPolicyTests.swift
//  notchPocketTests
//

import CoreGraphics
import XCTest

@testable import notchPocket

final class CompactMusicHoverPolicyTests: XCTestCase {
    private let bounds = CGRect(x: 10, y: 20, width: 100, height: 50)
    private lazy var insidePoint = CGPoint(x: 50, y: 40)
    private lazy var outsidePoint = CGPoint(x: 5, y: 40)

    private func hoverState(
        bounds: CGRect? = nil,
        point: CGPoint,
        isHidden: Bool = false,
        previous: Bool?
    ) -> Bool? {
        CompactMusicHoverPolicy.hoverState(
            bounds: bounds ?? self.bounds,
            pointInView: point,
            isHidden: isHidden,
            previous: previous
        )
    }

    // MARK: - Degenerate bounds

    func testZeroSizedBoundsReportNoState() {
        let empty = CGRect(x: 10, y: 20, width: 0, height: 0)

        XCTAssertNil(hoverState(bounds: empty, point: insidePoint, previous: nil))
        XCTAssertNil(hoverState(bounds: empty, point: insidePoint, previous: true))
        XCTAssertNil(hoverState(bounds: empty, point: insidePoint, previous: false))
    }

    func testCollapsedSingleAxisBoundsReportNoState() {
        let zeroWidth = CGRect(x: 10, y: 20, width: 0, height: 50)
        let zeroHeight = CGRect(x: 10, y: 20, width: 100, height: 0)

        XCTAssertNil(hoverState(bounds: zeroWidth, point: insidePoint, previous: nil))
        XCTAssertNil(hoverState(bounds: zeroHeight, point: insidePoint, previous: nil))
    }

    func testNegativeBoundsReportNoStateRegardlessOfPointerOrHiding() {
        let negative = CGRect(x: 10, y: 20, width: -100, height: -50)

        XCTAssertNil(hoverState(bounds: negative, point: insidePoint, previous: nil))
        XCTAssertNil(hoverState(bounds: negative, point: outsidePoint, previous: true))
        XCTAssertNil(hoverState(bounds: negative, point: insidePoint, isHidden: true, previous: false))
    }

    // MARK: - Visible section

    func testPointerInsideBeginsHoverFromUnknownState() {
        XCTAssertEqual(hoverState(point: insidePoint, previous: nil), true)
    }

    func testPointerInsideBeginsHoverFromNotHovering() {
        XCTAssertEqual(hoverState(point: insidePoint, previous: false), true)
    }

    func testPointerOutsideEndsHoverFromHovering() {
        XCTAssertEqual(hoverState(point: outsidePoint, previous: true), false)
    }

    func testPointerOutsideReportsNotHoveringFromUnknownState() {
        XCTAssertEqual(hoverState(point: outsidePoint, previous: nil), false)
    }

    // MARK: - Hidden section

    func testHiddenSectionEndsHoverEvenWithPointerInside() {
        XCTAssertEqual(hoverState(point: insidePoint, isHidden: true, previous: true), false)
    }

    func testHiddenSectionReportsNotHoveringFromUnknownState() {
        XCTAssertEqual(hoverState(point: insidePoint, isHidden: true, previous: nil), false)
    }

    // MARK: - Unchanged state

    func testUnchangedHoverReportsNoState() {
        XCTAssertNil(hoverState(point: insidePoint, previous: true))
    }

    func testUnchangedNonHoverReportsNoState() {
        XCTAssertNil(hoverState(point: outsidePoint, previous: false))
    }

    func testUnchangedHiddenNonHoverReportsNoState() {
        XCTAssertNil(hoverState(point: insidePoint, isHidden: true, previous: false))
    }

    // MARK: - Boundary semantics

    func testOriginCornerCountsAsInside() {
        let origin = CGPoint(x: bounds.minX, y: bounds.minY)

        XCTAssertEqual(hoverState(point: origin, previous: nil), true)
    }

    func testFarEdgesCountAsOutside() {
        let farCorner = CGPoint(x: bounds.maxX, y: bounds.maxY)
        let farEdge = CGPoint(x: bounds.maxX, y: bounds.midY)

        XCTAssertEqual(hoverState(point: farCorner, previous: true), false)
        XCTAssertEqual(hoverState(point: farEdge, previous: true), false)
    }

    func testPointJustInsideFarEdgeCountsAsInside() {
        let justInside = CGPoint(x: bounds.maxX - 0.5, y: bounds.maxY - 0.5)

        XCTAssertEqual(hoverState(point: justInside, previous: nil), true)
    }

    func testBoundsOriginIsRespectedRatherThanSizeAlone() {
        let leftOfOrigin = CGPoint(x: bounds.minX - 1, y: bounds.midY)
        let aboveOrigin = CGPoint(x: bounds.midX, y: bounds.minY - 1)

        XCTAssertEqual(hoverState(point: leftOfOrigin, previous: true), false)
        XCTAssertEqual(hoverState(point: aboveOrigin, previous: true), false)
    }
}
