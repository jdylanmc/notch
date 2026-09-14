//
//  GraphCalendarDecodingTests.swift
//  notchPocketTests
//

import Foundation
import XCTest

@testable import notchPocket

final class GraphCalendarDecodingTests: XCTestCase {
    private let decoder = GraphCalendarPayloadDecoder()

    private func account() throws -> CalendarAccountID {
        try CalendarAccountID(provider: CalendarProviderID("graph"), externalID: "account-1")
    }

    private func calendar() throws -> CalendarIdentity {
        try CalendarIdentity(account: account(), externalID: "calendar-1")
    }

    func testCalendarPageDecodesNarrowFieldsAndIgnoresUnknownFields() throws {
        let data = Data(
            """
            {
              "value": [{
                "id": "calendar-1",
                "name": "Personal",
                "isDefaultCalendar": true,
                "color": "lightBlue",
                "hexColor": "#336699",
                "unexpected": {"nested": true}
              }],
              "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=next"
            }
            """.utf8
        )

        let page = try decoder.decodeCalendars(data, account: account())

        XCTAssertEqual(
            page.items,
            [
                CalendarCoreCalendar(
                    identity: try calendar(),
                    name: "Personal",
                    isDefault: true,
                    color: CalendarProviderColor(name: "lightBlue", hex: "#336699")
                )
            ]
        )
        XCTAssertEqual(
            page.nextLink,
            "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=next"
        )
    }

    func testPersonalAppointmentWithoutMeetingMetadataDecodes() throws {
        let data = Data(
            """
            {
              "value": [{
                "id": "event-1",
                "subject": "Dentist",
                "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-09-12T14:30:00.1234567", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false,
                "type": "singleInstance",
                "sensitivity": "personal",
                "showAs": "busy"
              }]
            }
            """.utf8
        )

        let page = try decoder.decodeEvents(data, calendar: calendar())
        let event = try XCTUnwrap(page.items.first)

        XCTAssertEqual(event.identity.externalID, "event-1")
        XCTAssertEqual(event.title, "Dentist")
        XCTAssertEqual(event.start, Date(timeIntervalSince1970: 1_789_220_700))
        XCTAssertEqual(event.end.timeIntervalSince1970, 1_789_223_400.1234567, accuracy: 0.001)
        XCTAssertFalse(event.isAllDay)
        XCTAssertFalse(event.isCancelled)
        XCTAssertNil(event.location)
        XCTAssertNil(event.onlineMeetingURL)
        XCTAssertNil(event.webURL)
        XCTAssertEqual(event.providerType, "singleInstance")
        XCTAssertEqual(event.sensitivity, "personal")
        XCTAssertEqual(event.availability, "busy")
    }

    func testEventPreservesFlagsLinksAndUnknownProviderValues() throws {
        let data = Data(
            """
            {
              "value": [{
                "id": "event-2",
                "subject": "Cancelled event",
                "start": {"dateTime": "2026-09-12T00:00:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-09-13T00:00:00", "timeZone": "UTC"},
                "isAllDay": true,
                "isCancelled": true,
                "location": {"displayName": "Room 1"},
                "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/meetup-join/example"},
                "webLink": "https://outlook.office.com/calendar/item/example",
                "seriesMasterId": "series-1",
                "type": "futureType",
                "sensitivity": "futureSensitivity",
                "showAs": "futureAvailability"
              }]
            }
            """.utf8
        )

        let event = try XCTUnwrap(decoder.decodeEvents(data, calendar: calendar()).items.first)

        XCTAssertTrue(event.isAllDay)
        XCTAssertTrue(event.isCancelled)
        XCTAssertEqual(event.location, "Room 1")
        XCTAssertEqual(event.onlineMeetingURL?.host(), "teams.microsoft.com")
        XCTAssertEqual(event.webURL?.host(), "outlook.office.com")
        XCTAssertEqual(event.seriesRootExternalID, "series-1")
        XCTAssertEqual(event.providerType, "futureType")
        XCTAssertEqual(event.sensitivity, "futureSensitivity")
        XCTAssertEqual(event.availability, "futureAvailability")
    }

    func testMissingRequiredCalendarOrEventFieldsFail() throws {
        let missingCalendarID = Data(
            #"{"value":[{"name":"Personal","isDefaultCalendar":true}]}"#.utf8
        )
        let missingEventEnd = Data(
            """
            {
              "value": [{
                "id": "event-1",
                "subject": "Incomplete",
                "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false
              }]
            }
            """.utf8
        )

        XCTAssertThrowsError(try decoder.decodeCalendars(missingCalendarID, account: account()))
        XCTAssertThrowsError(try decoder.decodeEvents(missingEventEnd, calendar: calendar()))
    }

    func testInvalidRecordIdentifiersMapToInvalidPayload() throws {
        let invalidCalendar = Data(
            #"{"value":[{"id":" ","name":"Personal","isDefaultCalendar":true}]}"#.utf8
        )
        let invalidEvent = Data(
            """
            {
              "value": [{
                "id": " ",
                "subject": "Bad event",
                "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false
              }]
            }
            """.utf8
        )
        let invalidSeries = Data(
            """
            {
              "value": [{
                "id": "event",
                "subject": "Bad series",
                "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false,
                "seriesMasterId": " "
              }]
            }
            """.utf8
        )

        XCTAssertThrowsError(try decoder.decodeCalendars(invalidCalendar, account: account())) {
            XCTAssertEqual($0 as? GraphCalendarError, .invalidPayload)
        }
        for payload in [invalidEvent, invalidSeries] {
            XCTAssertThrowsError(try decoder.decodeEvents(payload, calendar: calendar())) {
                XCTAssertEqual($0 as? GraphCalendarError, .invalidPayload)
            }
        }
    }

    func testInvalidIdentifiersTimestampsTimeZonesAndURLsFail() throws {
        let payloads = [
            """
            {
              "value": [{
                "id": " ",
                "subject": "Bad",
                "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false
              }]
            }
            """,
            """
            {
              "value": [{
                "id": "event",
                "subject": "Bad",
                "start": {"dateTime": "not-a-date", "timeZone": "UTC"},
                "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false
              }]
            }
            """,
            """
            {
              "value": [{
                "id": "event",
                "subject": "Bad",
                "start": {
                  "dateTime": "2026-09-12T13:45:00",
                  "timeZone": "Pacific Standard Time"
                },
                "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false
              }]
            }
            """,
            """
            {
              "value": [{
                "id": "event",
                "subject": "Bad",
                "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false,
                "onlineMeeting": {"joinUrl": "not a url"}
              }]
            }
            """
        ]

        for payload in payloads {
            XCTAssertThrowsError(
                try decoder.decodeEvents(Data(payload.utf8), calendar: calendar()),
                "Expected payload to fail: \(payload)"
            )
        }
    }

    func testMalformedOptionalEventURLsMapToInvalidPayload() throws {
        for link in [
            "https://teams.microsoft.com/l/meetup%ZZ",
            "https://outlook.office.com/calendar/raw space"
        ] {
            let payload =
                """
                {
                  "value": [{
                    "id": "event",
                    "subject": "Bad link",
                    "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
                    "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
                    "isAllDay": false,
                    "isCancelled": false,
                    "webLink": "\(link)"
                  }]
                }
                """

            XCTAssertThrowsError(
                try decoder.decodeEvents(Data(payload.utf8), calendar: calendar())
            ) {
                XCTAssertEqual($0 as? GraphCalendarError, .invalidPayload)
            }
        }
    }
}
