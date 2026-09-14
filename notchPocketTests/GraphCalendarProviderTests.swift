//
//  GraphCalendarProviderTests.swift
//  notchPocketTests
//

import Foundation
import XCTest
@testable import notchPocket
private actor CancelOnThirdTransport: GraphCalendarTransport {
    private(set) var requests: [GraphCalendarRequest] = []

    func response(for request: GraphCalendarRequest) async throws -> GraphCalendarTransportResponse {
        requests.append(request)
        if requests.count == 3 {
            withUnsafeCurrentTask { $0?.cancel() }
            throw URLError(.cancelled)
        }
        return GraphCalendarTransportResponse(
            statusCode: 200, headers: [:], body: Data(#"{"value":[]}"#.utf8)
        )
    }

    func receivedRequests() -> [GraphCalendarRequest] { requests }
}
private enum StubBehavior {
    case events([CalendarCoreEvent])
    case expectedFailure(CalendarCoreExpectedFailure)
    case cancellation
    case unexpectedFailure
}
private enum TestError: Error {
    case unexpected
}
private actor StubProvider: CalendarCoreProviding {
    private let behaviorByAccount: [CalendarAccountID: StubBehavior]

    init(behaviorByAccount: [CalendarAccountID: StubBehavior]) { self.behaviorByAccount = behaviorByAccount }

    func calendars(for account: CalendarAccountID) async throws -> [CalendarCoreCalendar] { [] }

    func events(
        for account: CalendarAccountID,
        calendars: [CalendarIdentity],
        interval: CalendarQueryInterval
    ) async throws -> [CalendarCoreEvent] {
        switch behaviorByAccount[account] {
        case .events(let events):
            return events
        case .expectedFailure(let error):
            throw error
        case .cancellation:
            throw CancellationError()
        case .unexpectedFailure:
            throw TestError.unexpected
        case nil:
            throw GraphCalendarError.notFound
        }
    }
}
final class GraphCalendarProviderTests: XCTestCase {
    private actor RecordingTransport: GraphCalendarTransport {
        private var responses: [GraphCalendarTransportResponse]
        private(set) var requests: [GraphCalendarRequest] = []

        init(responses: [GraphCalendarTransportResponse]) {
            self.responses = responses
        }

        func response(for request: GraphCalendarRequest) async throws -> GraphCalendarTransportResponse {
            requests.append(request)
            guard !responses.isEmpty else { throw GraphCalendarError.transport }
            return responses.removeFirst()
        }

        func receivedRequests() -> [GraphCalendarRequest] {
            requests
        }
    }

    private func account(_ id: String = "account") throws -> CalendarAccountID {
        try CalendarAccountID(provider: CalendarProviderID("graph"), externalID: id)
    }

    private func calendar(account: CalendarAccountID, id: String) throws -> CalendarIdentity {
        try CalendarIdentity(account: account, externalID: id)
    }

    private func interval() throws -> CalendarQueryInterval {
        try CalendarQueryInterval(
            start: Date(timeIntervalSince1970: 1_789_220_700.125),
            end: Date(timeIntervalSince1970: 1_789_227_900.875)
        )
    }

    private func response(_ body: String) -> GraphCalendarTransportResponse {
        GraphCalendarTransportResponse(statusCode: 200, headers: [:], body: Data(body.utf8))
    }

    func testEventRequestScopesCalendarIDAsPathDataAndSerializesExactInstants() async throws {
        let account = try account()
        let calendar = try calendar(account: account, id: "folder/../? #")
        let transport = RecordingTransport(responses: [response(#"{"value":[]}"#)])

        _ = try await GraphCalendarProvider(transport: transport).events(
            for: account,
            calendars: [calendar],
            interval: interval()
        )

        let receivedRequests = await transport.receivedRequests()
        let request = try XCTUnwrap(receivedRequests.first)
        let components = try XCTUnwrap(URLComponents(url: request.url, resolvingAgainstBaseURL: false))
        let query = Dictionary(
            uniqueKeysWithValues: (components.queryItems ?? []).map { ($0.name, $0.value) }
        )

        XCTAssertEqual(
            components.percentEncodedPath,
            "/v1.0/me/calendars/folder%2F..%2F%3F%20%23/calendarView"
        )
        XCTAssertEqual(query["startDateTime"]!, "2026-09-12T13:45:00.125000000Z")
        XCTAssertEqual(query["endDateTime"]!, "2026-09-12T15:45:00.875000000Z")
        XCTAssertEqual(request.account, account)
        XCTAssertEqual(request.headers["Prefer"], #"outlook.timezone="UTC""#)
    }

    func testEventRequestPreservesSubmillisecondEndpointInstants() async throws {
        let account = try account()
        let calendar = try calendar(account: account, id: "calendar")
        let intervals = [
            try CalendarQueryInterval(
                start: Date(timeIntervalSince1970: 1_789_220_700.1251),
                end: Date(timeIntervalSince1970: 1_789_220_700.1252)
            ),
            try CalendarQueryInterval(
                start: Date(timeIntervalSince1970: 1_789_220_700.123456),
                end: Date(timeIntervalSince1970: 1_789_227_900.987654)
            ),
            try CalendarQueryInterval(
                start: Date(timeIntervalSinceReferenceDate: 810_913_500.1250001),
                end: Date(timeIntervalSinceReferenceDate: 810_913_501.1250001)
            ),
            try CalendarQueryInterval(
                start: Date(timeIntervalSinceReferenceDate: -0.0002),
                end: Date(timeIntervalSinceReferenceDate: -0.0001)
            ),
            try CalendarQueryInterval(
                start: Date(timeIntervalSinceReferenceDate: -0.0001),
                end: Date(timeIntervalSinceReferenceDate: 0.0001)
            )
        ]
        let transport = RecordingTransport(
            responses: intervals.map { _ in response(#"{"value":[]}"#) }
        )
        let provider = GraphCalendarProvider(transport: transport)

        for interval in intervals {
            _ = try await provider.events(
                for: account,
                calendars: [calendar],
                interval: interval
            )
        }

        let requests = await transport.receivedRequests()
        XCTAssertEqual(requests.count, intervals.count)
        for (request, interval) in zip(requests, intervals) {
            let components = try XCTUnwrap(
                URLComponents(url: request.url, resolvingAgainstBaseURL: false)
            )
            let query = Dictionary(
                uniqueKeysWithValues: (components.queryItems ?? []).compactMap { item in
                    item.value.map { (item.name, $0) }
                }
            )
            XCTAssertEqual(
                try parsedRequestDate(try XCTUnwrap(query["startDateTime"])),
                interval.start
            )
            XCTAssertEqual(
                try parsedRequestDate(try XCTUnwrap(query["endDateTime"])),
                interval.end
            )
        }
    }

    func testRequestsRejectMismatchedAccountsBeforeTransport() async throws {
        let requestedAccount = try account("requested")
        let otherCalendar = try calendar(account: account("other"), id: "calendar")
        let nonGraphAccount = try CalendarAccountID(
            provider: CalendarProviderID("eventkit"), externalID: "account"
        )
        let nonGraphCalendar = try calendar(account: nonGraphAccount, id: "calendar")
        let transport = RecordingTransport(responses: [])
        let provider = GraphCalendarProvider(transport: transport)
        let interval = try interval()

        let cases: [(GraphCalendarError, () async throws -> Void)] = [
            (
                .calendarAccountMismatch,
                {
                    _ = try await provider.events(
                        for: requestedAccount,
                        calendars: [otherCalendar],
                        interval: interval
                    )
                }
            ),
            (
                .accountProviderMismatch,
                { _ = try await provider.calendars(for: nonGraphAccount) }
            ),
            (
                .accountProviderMismatch,
                {
                    _ = try await provider.events(
                        for: nonGraphAccount,
                        calendars: [nonGraphCalendar],
                        interval: interval
                    )
                }
            )
        ]
        for (expectedError, operation) in cases {
            do {
                _ = try await operation()
                XCTFail("Expected account mismatch")
            } catch {
                XCTAssertEqual(error as? GraphCalendarError, expectedError)
            }
        }
        let requests = await transport.receivedRequests()
        XCTAssertTrue(requests.isEmpty)
    }

    func testEventRequestRejectsStandaloneDotCalendarIDsBeforeTransport() async throws {
        for identifier in [".", ".."] {
            let account = try account()
            let calendar = try calendar(account: account, id: identifier)
            let transport = RecordingTransport(responses: [])

            do {
                _ = try await GraphCalendarProvider(transport: transport).events(
                    for: account,
                    calendars: [calendar],
                    interval: interval()
                )
                XCTFail("Expected path-navigation identifier rejection")
            } catch {
                XCTAssertEqual(error as? GraphCalendarError, .invalidPayload)
            }
            let requests = await transport.receivedRequests()
            XCTAssertTrue(requests.isEmpty)
        }
    }

    func testEventRequestAllowsOrdinaryDottedCalendarID() async throws {
        let account = try account()
        let calendar = try calendar(account: account, id: "calendar.v2")
        let transport = RecordingTransport(responses: [response(#"{"value":[]}"#)])

        _ = try await GraphCalendarProvider(transport: transport).events(
            for: account,
            calendars: [calendar],
            interval: interval()
        )

        let requests = await transport.receivedRequests()
        let request = try XCTUnwrap(requests.first)
        XCTAssertEqual(
            request.url.path,
            "/v1.0/me/calendars/calendar.v2/calendarView"
        )
    }

    func testEventsRetainTheirExactAccountAndCalendarIdentities() async throws {
        let account = try account()
        let first = try calendar(account: account, id: "first")
        let second = try calendar(account: account, id: "second")
        let eventPayload =
            """
            {
              "value": [{
                "id": "same-event",
                "subject": "Event",
                "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
                "isAllDay": false,
                "isCancelled": false
              }]
            }
            """
        let transport = RecordingTransport(responses: [
            response(eventPayload),
            response(eventPayload)
        ])

        let events = try await GraphCalendarProvider(transport: transport).events(
            for: account,
            calendars: [first, second],
            interval: interval()
        )

        XCTAssertEqual(events.map(\.identity.calendar), [first, second])
        XCTAssertNotEqual(events[0].identity, events[1].identity)
    }

    func testCoordinatorIsolatesNonGraphExpectedFailureInOrder() async throws {
        let firstAccount = try account("first")
        let secondAccount = try CalendarAccountID(
            provider: CalendarProviderID("eventkit"), externalID: "second"
        )
        let thirdAccount = try account("third")
        let firstCalendar = try calendar(account: firstAccount, id: "calendar")
        let secondCalendar = try calendar(account: secondAccount, id: "calendar")
        let thirdCalendar = try calendar(account: thirdAccount, id: "calendar")
        let expectedFailure = CalendarCoreExpectedFailure.provider(
            provider: secondAccount.provider, code: "unavailable"
        )
        let event = CalendarCoreEvent(
            identity: try CalendarEventIdentity(calendar: firstCalendar, externalID: "event"),
            title: "Event",
            start: try interval().start,
            end: try interval().end,
            isAllDay: false,
            isCancelled: false,
            location: nil,
            onlineMeetingURL: nil,
            webURL: nil,
            seriesRootExternalID: nil,
            providerType: nil,
            sensitivity: nil,
            availability: nil
        )
        let coordinator = CalendarCoreCoordinator(
            provider: StubProvider(
                behaviorByAccount: [
                    firstAccount: .events([event]),
                    secondAccount: .expectedFailure(expectedFailure),
                    thirdAccount: .events([])
                ]
            )
        )
        let requests = [
            CalendarAccountEventRequest(account: firstAccount, calendars: [firstCalendar]),
            CalendarAccountEventRequest(account: secondAccount, calendars: [secondCalendar]),
            CalendarAccountEventRequest(account: thirdAccount, calendars: [thirdCalendar])
        ]

        let outcomes = try await coordinator.events(for: requests, interval: interval())

        XCTAssertEqual(outcomes.map(\.account), [firstAccount, secondAccount, thirdAccount])
        XCTAssertEqual(outcomes[0], .success(account: firstAccount, events: [event]))
        XCTAssertEqual(outcomes[1], .failure(account: secondAccount, error: expectedFailure))
        XCTAssertEqual(outcomes[2], .success(account: thirdAccount, events: []))
    }

    func testCoordinatorPropagatesCancellation() async throws {
        let account = try account()
        let calendar = try calendar(account: account, id: "calendar")
        let coordinator = CalendarCoreCoordinator(
            provider: StubProvider(behaviorByAccount: [account: .cancellation])
        )

        do {
            _ = try await coordinator.events(
                for: [CalendarAccountEventRequest(account: account, calendars: [calendar])],
                interval: interval()
            )
            XCTFail("Expected cancellation")
        } catch is CancellationError {
        } catch {
            XCTFail("Expected CancellationError, got \(error)")
        }
    }

    func testCoordinatorDoesNotTranslateUnexpectedProviderFailure() async throws {
        let account = try account()
        let calendar = try calendar(account: account, id: "calendar")
        let coordinator = CalendarCoreCoordinator(
            provider: StubProvider(behaviorByAccount: [account: .unexpectedFailure])
        )

        do {
            _ = try await coordinator.events(
                for: [CalendarAccountEventRequest(account: account, calendars: [calendar])],
                interval: interval()
            )
            XCTFail("Expected original provider failure")
        } catch TestError.unexpected {
        } catch {
            XCTFail("Expected original provider failure, got \(error)")
        }
    }

    func testCoordinatorContinuesAfterMalformedMiddleAccountPayload() async throws {
        let firstAccount = try account("first")
        let secondAccount = try account("second")
        let thirdAccount = try account("third")
        let firstCalendar = try calendar(account: firstAccount, id: "calendar")
        let secondCalendar = try calendar(account: secondAccount, id: "calendar")
        let thirdCalendar = try calendar(account: thirdAccount, id: "calendar")
        let transport = RecordingTransport(responses: [
            response(eventPayload(id: "first-event", title: "First")),
            response(eventPayload(id: " ", title: "Invalid")),
            response(eventPayload(id: "third-event", title: "Third"))
        ])
        let coordinator = CalendarCoreCoordinator(
            provider: GraphCalendarProvider(transport: transport)
        )
        let requests = [
            CalendarAccountEventRequest(account: firstAccount, calendars: [firstCalendar]),
            CalendarAccountEventRequest(account: secondAccount, calendars: [secondCalendar]),
            CalendarAccountEventRequest(account: thirdAccount, calendars: [thirdCalendar])
        ]

        let outcomes = try await coordinator.events(for: requests, interval: interval())
        let receivedRequests = await transport.receivedRequests()

        XCTAssertEqual(outcomes.count, 3)
        XCTAssertEqual(outcomes[0].account, firstAccount)
        XCTAssertEqual(
            outcomes[1],
            .failure(account: secondAccount, error: .graph(.invalidPayload))
        )
        XCTAssertEqual(outcomes[2].account, thirdAccount)
        XCTAssertEqual(receivedRequests.map(\.account), [firstAccount, secondAccount, thirdAccount])
    }

    func testCoordinatorPropagatesTransportCancellationFromLastAccount() async throws {
        let firstAccount = try account("first")
        let secondAccount = try account("second")
        let thirdAccount = try account("third")
        let transport = CancelOnThirdTransport()
        let coordinator = CalendarCoreCoordinator(
            provider: GraphCalendarProvider(transport: transport)
        )
        let requests = [
            CalendarAccountEventRequest(
                account: firstAccount,
                calendars: [try calendar(account: firstAccount, id: "calendar")]
            ),
            CalendarAccountEventRequest(
                account: secondAccount,
                calendars: [try calendar(account: secondAccount, id: "calendar")]
            ),
            CalendarAccountEventRequest(
                account: thirdAccount,
                calendars: [try calendar(account: thirdAccount, id: "calendar")]
            )
        ]

        let operation = Task {
            try await coordinator.events(for: requests, interval: interval())
        }

        do {
            _ = try await operation.value
            XCTFail("Expected cancellation")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }
        let receivedRequests = await transport.receivedRequests()
        XCTAssertEqual(receivedRequests.map(\.account), [firstAccount, secondAccount, thirdAccount])
    }
}

private func eventPayload(id: String, title: String) -> String {
    """
    {
      "value": [{
        "id": "\(id)", "subject": "\(title)",
        "start": {"dateTime": "2026-09-12T13:45:00", "timeZone": "UTC"},
        "end": {"dateTime": "2026-09-12T14:00:00", "timeZone": "UTC"},
        "isAllDay": false, "isCancelled": false
      }]
    }
    """
}

private func parsedRequestDate(_ value: String) throws -> Date {
    let fractionalSeparator = try XCTUnwrap(value.lastIndex(of: "."))
    let suffixStart = value.index(after: fractionalSeparator)
    let suffixEnd = value.index(before: value.endIndex)
    let wholeSecondValue = String(value[..<fractionalSeparator]) + "Z"
    let fractionalValue = "0." + value[suffixStart..<suffixEnd]
    let wholeSecond = try Date.ISO8601FormatStyle(includingFractionalSeconds: false)
        .parse(wholeSecondValue)
    let wholeReferenceSeconds = try XCTUnwrap(
        Int64(exactly: wholeSecond.timeIntervalSinceReferenceDate)
    )
    let fraction = try XCTUnwrap(Decimal(
        string: String(fractionalValue), locale: Locale(identifier: "en_US_POSIX")
    ))
    let referenceSeconds = Decimal(wholeReferenceSeconds) + fraction
    let exactSeconds = try XCTUnwrap(Double(NSDecimalNumber(
        decimal: referenceSeconds
    ).stringValue))
    return Date(timeIntervalSinceReferenceDate: exactSeconds)
}
