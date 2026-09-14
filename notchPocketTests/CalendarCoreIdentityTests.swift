//
//  CalendarCoreIdentityTests.swift
//  notchPocketTests
//

import Foundation
import XCTest

@testable import notchPocket

final class CalendarCoreIdentityTests: XCTestCase {
    func testIdentityHierarchyScopesProviderValues() throws {
        let graph = try CalendarProviderID("graph")
        let eventKit = try CalendarProviderID("eventkit")
        let graphAccount = try CalendarAccountID(provider: graph, externalID: "account")
        let otherProviderAccount = try CalendarAccountID(provider: eventKit, externalID: "account")
        let otherGraphAccount = try CalendarAccountID(provider: graph, externalID: "other-account")
        let graphCalendar = try CalendarIdentity(account: graphAccount, externalID: "calendar")
        let otherProviderCalendar = try CalendarIdentity(account: otherProviderAccount, externalID: "calendar")
        let otherAccountCalendar = try CalendarIdentity(account: otherGraphAccount, externalID: "calendar")

        XCTAssertNotEqual(graphAccount, otherProviderAccount)
        XCTAssertNotEqual(graphCalendar, otherProviderCalendar)
        XCTAssertNotEqual(graphCalendar, otherAccountCalendar)
        XCTAssertNotEqual(
            try CalendarEventIdentity(calendar: graphCalendar, externalID: "event"),
            try CalendarEventIdentity(calendar: otherAccountCalendar, externalID: "event")
        )
    }

    func testIdentityHierarchyRoundTripsThroughCodable() throws {
        let identity = try CalendarEventIdentity(
            calendar: CalendarIdentity(
                account: CalendarAccountID(
                    provider: CalendarProviderID("graph"),
                    externalID: "account"
                ),
                externalID: "calendar"
            ),
            externalID: "event"
        )

        let data = try JSONEncoder().encode(identity)

        XCTAssertEqual(try JSONDecoder().decode(CalendarEventIdentity.self, from: data), identity)
    }

    func testIdentityInitializersRejectEmptyValues() throws {
        XCTAssertThrowsError(try CalendarProviderID(" \n "))
        XCTAssertThrowsError(
            try CalendarAccountID(provider: CalendarProviderID("graph"), externalID: "")
        )
        XCTAssertThrowsError(
            try CalendarIdentity(
                account: CalendarAccountID(
                    provider: CalendarProviderID("graph"),
                    externalID: "account"
                ),
                externalID: "\t"
            )
        )
    }

    func testIdentityDecodingRejectsEmptyValues() {
        let invalidPayloads: [(Data, any Decodable.Type)] = [
            (Data(#"{"rawValue":"  "}"#.utf8), CalendarProviderID.self),
            (
                Data(#"{"provider":{"rawValue":"graph"},"externalID":" "}"#.utf8),
                CalendarAccountID.self
            ),
            (
                Data(
                    #"{"account":{"provider":{"rawValue":"graph"},"externalID":"account"},"externalID":""}"#.utf8
                ),
                CalendarIdentity.self
            ),
            (
                Data(
                    #"{"calendar":{"account":{"provider":{"rawValue":"graph"},"externalID":"account"},"externalID":"calendar"},"externalID":"\n"}"#.utf8
                ),
                CalendarEventIdentity.self
            )
        ]

        for (data, type) in invalidPayloads {
            XCTAssertThrowsError(try decode(type, from: data))
        }
    }

    func testIntervalPreservesExactInstants() throws {
        let start = Date(timeIntervalSinceReferenceDate: 123.456)
        let end = Date(timeIntervalSinceReferenceDate: 789.012)

        let interval = try CalendarQueryInterval(start: start, end: end)

        XCTAssertEqual(interval.start, start)
        XCTAssertEqual(interval.end, end)
    }

    func testIntervalRejectsInvalidOrderingAndNonFiniteDates() {
        let instant = Date(timeIntervalSinceReferenceDate: 100)

        XCTAssertThrowsError(try CalendarQueryInterval(start: instant, end: instant))
        XCTAssertThrowsError(
            try CalendarQueryInterval(
                start: Date(timeIntervalSinceReferenceDate: 200),
                end: Date(timeIntervalSinceReferenceDate: 100)
            )
        )
        XCTAssertThrowsError(
            try CalendarQueryInterval(
                start: Date(timeIntervalSinceReferenceDate: .infinity),
                end: instant
            )
        )
        XCTAssertThrowsError(
            try CalendarQueryInterval(
                start: instant,
                end: Date(timeIntervalSinceReferenceDate: .nan)
            )
        )
    }

    func testIntervalDecodingRevalidatesValues() {
        let equalBounds = Data(#"{"start":100,"end":100}"#.utf8)

        XCTAssertThrowsError(try JSONDecoder().decode(CalendarQueryInterval.self, from: equalBounds))
    }

    private func decode(_ type: any Decodable.Type, from data: Data) throws -> Any {
        try JSONDecoder().decode(type, from: data)
    }
}
