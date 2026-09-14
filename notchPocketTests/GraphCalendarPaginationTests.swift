//
//  GraphCalendarPaginationTests.swift
//  notchPocketTests
//

import Foundation
import XCTest

@testable import notchPocket

final class GraphCalendarPaginationTests: XCTestCase {
    private actor ScriptedTransport: GraphCalendarTransport {
        private var results: [Result<GraphCalendarTransportResponse, Error>]
        private(set) var requests: [GraphCalendarRequest] = []

        init(_ results: [Result<GraphCalendarTransportResponse, Error>]) {
            self.results = results
        }

        func response(for request: GraphCalendarRequest) async throws -> GraphCalendarTransportResponse {
            requests.append(request)
            guard !results.isEmpty else { throw TestError.exhausted }
            return try results.removeFirst().get()
        }

        func receivedRequests() -> [GraphCalendarRequest] {
            requests
        }
    }

    private enum TestError: Error {
        case exhausted
        case transport
    }

    private func account() throws -> CalendarAccountID {
        try CalendarAccountID(provider: CalendarProviderID("graph"), externalID: "account")
    }

    private func response(
        status: Int = 200,
        headers: [String: String] = [:],
        body: String
    ) -> Result<GraphCalendarTransportResponse, Error> {
        .success(
            GraphCalendarTransportResponse(
                statusCode: status,
                headers: headers,
                body: Data(body.utf8)
            )
        )
    }

    func testPaginationFollowsOpaqueNextLinksAndPreservesPageOrder() async throws {
        let firstNext = "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=first%2Fopaque"
        let secondNext = "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=second%2Bopaque"
        let transport = ScriptedTransport([
            response(
                body:
                    #"{"value":[{"id":"one","name":"One","isDefaultCalendar":true}],"@odata.nextLink":"\#(firstNext)"}"#
            ),
            response(
                body:
                    #"{"value":[{"id":"two","name":"Two","isDefaultCalendar":false}],"@odata.nextLink":"\#(secondNext)"}"#
            ),
            response(
                body:
                    #"{"value":[{"id":"three","name":"Three","isDefaultCalendar":false}]}"#
            )
        ])
        let provider = GraphCalendarProvider(transport: transport)

        let calendars = try await provider.calendars(for: account())
        let requests = await transport.receivedRequests()

        XCTAssertEqual(calendars.map(\.name), ["One", "Two", "Three"])
        XCTAssertEqual(requests.count, 3)
        XCTAssertEqual(requests[1].url.absoluteString, firstNext)
        XCTAssertEqual(requests[2].url.absoluteString, secondNext)
    }

    func testPaginationRejectsUntrustedContinuationBeforeTransport() async throws {
        let untrustedLinks = [
            "http://graph.microsoft.com/v1.0/me/calendars?$skiptoken=x",
            "https://graph.microsoft.com.evil.example/v1.0/me/calendars?$skiptoken=x",
            "https://user@graph.microsoft.com/v1.0/me/calendars?$skiptoken=x",
            "https://graph.microsoft.com:444/v1.0/me/calendars?$skiptoken=x",
            "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=x#fragment",
            "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=%ZZ",
            "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=raw space"
        ]

        for link in untrustedLinks {
            let transport = ScriptedTransport([
                response(
                    body:
                        #"{"value":[],"@odata.nextLink":"\#(link)"}"#
                )
            ])
            let provider = GraphCalendarProvider(transport: transport)

            do {
                _ = try await provider.calendars(for: account())
                XCTFail("Expected invalid continuation: \(link)")
            } catch {
                XCTAssertEqual(error as? GraphCalendarError, .invalidNextPageURL)
            }
            let requestCount = await transport.receivedRequests().count
            XCTAssertEqual(requestCount, 1)
        }
    }

    func testPaginationDetectsCyclesAndUniquePageLimit() async throws {
        let repeated = "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=repeat"
        let cycleTransport = ScriptedTransport([
            response(body: #"{"value":[],"@odata.nextLink":"\#(repeated)"}"#),
            response(body: #"{"value":[],"@odata.nextLink":"\#(repeated)"}"#)
        ])

        do {
            _ = try await GraphCalendarProvider(transport: cycleTransport)
                .calendars(for: account())
            XCTFail("Expected pagination cycle")
        } catch {
            XCTAssertEqual(error as? GraphCalendarError, .paginationCycle)
        }

        let pageTwo = "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=two"
        let pageThree = "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=three"
        let boundedTransport = ScriptedTransport([
            response(body: #"{"value":[],"@odata.nextLink":"\#(pageTwo)"}"#),
            response(body: #"{"value":[],"@odata.nextLink":"\#(pageThree)"}"#)
        ])

        do {
            _ = try await GraphCalendarProvider(transport: boundedTransport, maxPages: 2)
                .calendars(for: account())
            XCTFail("Expected page limit")
        } catch {
            XCTAssertEqual(error as? GraphCalendarError, .pageLimitExceeded)
        }
        let boundedRequestCount = await boundedTransport.receivedRequests().count
        XCTAssertEqual(boundedRequestCount, 2)
    }

    func testLaterPageFailureNeverReturnsPartialSuccess() async throws {
        let next = "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=next"
        let transport = ScriptedTransport([
            response(
                body:
                    #"{"value":[{"id":"one","name":"One","isDefaultCalendar":true}],"@odata.nextLink":"\#(next)"}"#
            ),
            .failure(TestError.transport)
        ])

        do {
            _ = try await GraphCalendarProvider(transport: transport).calendars(for: account())
            XCTFail("Expected transport failure")
        } catch {
            XCTAssertEqual(error as? GraphCalendarError, .transport)
        }
    }

    func testHTTPAndBodyFailuresRemainTyped() async throws {
        let cases: [(Result<GraphCalendarTransportResponse, Error>, GraphCalendarError)] = [
            (response(status: 401, body: "{}"), .unauthorized),
            (response(status: 403, body: "{}"), .forbidden),
            (response(status: 404, body: "{}"), .notFound),
            (
                response(status: 429, headers: ["Retry-After": "120"], body: "{}"),
                .throttled(retryAfter: .seconds(120))
            ),
            (response(status: 503, body: "{}"), .httpStatus(503)),
            (response(body: "123456"), .responseTooLarge(limit: 5)),
            (response(body: "x"), .decoding)
        ]

        for (result, expected) in cases {
            let provider = GraphCalendarProvider(
                transport: ScriptedTransport([result]),
                maxResponseBytes: 5
            )
            do {
                _ = try await provider.calendars(for: account())
                XCTFail("Expected \(expected)")
            } catch {
                XCTAssertEqual(error as? GraphCalendarError, expected)
            }
        }
    }

    func testHTTPDateRetryAfterIsPreserved() async throws {
        let transport = ScriptedTransport([
            response(
                status: 429,
                headers: ["retry-after": "Sun, 06 Nov 1994 08:49:37 GMT"],
                body: "{}"
            )
        ])

        do {
            _ = try await GraphCalendarProvider(transport: transport).calendars(for: account())
            XCTFail("Expected throttling")
        } catch GraphCalendarError.throttled(let retryAfter) {
            guard case .date(let date) = retryAfter else {
                return XCTFail("Expected HTTP-date Retry-After")
            }
            XCTAssertEqual(date.timeIntervalSince1970, 784_111_777, accuracy: 0.001)
        }
    }

    func testCancellationPropagatesWithoutErrorTranslation() async throws {
        let transport = ScriptedTransport([.failure(CancellationError())])

        do {
            _ = try await GraphCalendarProvider(transport: transport).calendars(for: account())
            XCTFail("Expected cancellation")
        } catch is CancellationError {
        } catch {
            XCTFail("Expected CancellationError, got \(error)")
        }
    }
}
