//
//  GraphCalendarCore.swift
//  notchPocket
//

import Foundation

struct CalendarProviderColor: Equatable, Sendable {
    let name: String?
    let hex: String?
}

struct CalendarCoreCalendar: Equatable, Sendable {
    let identity: CalendarIdentity
    let name: String
    let isDefault: Bool
    let color: CalendarProviderColor?
}

struct CalendarCoreEvent: Equatable, Sendable {
    let identity: CalendarEventIdentity
    let title: String
    let start: Date
    let end: Date
    let isAllDay: Bool
    let isCancelled: Bool
    let location: String?
    let onlineMeetingURL: URL?
    let webURL: URL?
    let seriesRootExternalID: String?
    let providerType: String?
    let sensitivity: String?
    let availability: String?
}

struct GraphCalendarPage<Item: Sendable>: Sendable {
    let items: [Item]
    let nextLink: String?
}

enum GraphCalendarError: Error, Equatable, Sendable {
    case invalidPayload
    case decoding
    case transport
    case unauthorized
    case forbidden
    case notFound
    case throttled(retryAfter: GraphRetryAfter?)
    case httpStatus(Int)
    case responseTooLarge(limit: Int)
    case accountProviderMismatch
    case calendarAccountMismatch
    case invalidNextPageURL
    case paginationCycle
    case pageLimitExceeded
}

enum GraphRetryAfter: Equatable, Sendable {
    case seconds(Int)
    case date(Date)
}

struct GraphCalendarRequest: Equatable, Sendable {
    let account: CalendarAccountID
    let url: URL
    let headers: [String: String]
}

struct GraphCalendarTransportResponse: Sendable {
    let statusCode: Int
    let headers: [String: String]
    let body: Data
}

protocol GraphCalendarTransport: Sendable {
    func response(for request: GraphCalendarRequest) async throws -> GraphCalendarTransportResponse
}

protocol CalendarCoreProviding: Sendable {
    func calendars(for account: CalendarAccountID) async throws -> [CalendarCoreCalendar]
    func events(
        for account: CalendarAccountID,
        calendars: [CalendarIdentity],
        interval: CalendarQueryInterval
    ) async throws -> [CalendarCoreEvent]
}

struct CalendarAccountEventRequest: Equatable, Sendable {
    let account: CalendarAccountID
    let calendars: [CalendarIdentity]
}

enum CalendarCoreExpectedFailure: Error, Equatable, Sendable {
    case graph(GraphCalendarError)
    case provider(provider: CalendarProviderID, code: String)
}

enum CalendarAccountEventOutcome: Equatable, Sendable {
    case success(account: CalendarAccountID, events: [CalendarCoreEvent])
    case failure(account: CalendarAccountID, error: CalendarCoreExpectedFailure)

    var account: CalendarAccountID {
        switch self {
        case .success(let account, _), .failure(let account, _):
            return account
        }
    }
}

struct CalendarCoreCoordinator: Sendable {
    private let provider: any CalendarCoreProviding

    init(provider: any CalendarCoreProviding) {
        self.provider = provider
    }

    func events(
        for requests: [CalendarAccountEventRequest],
        interval: CalendarQueryInterval
    ) async throws -> [CalendarAccountEventOutcome] {
        var outcomes: [CalendarAccountEventOutcome] = []
        outcomes.reserveCapacity(requests.count)

        for request in requests {
            try Task.checkCancellation()
            do {
                let events = try await provider.events(
                    for: request.account,
                    calendars: request.calendars,
                    interval: interval
                )
                outcomes.append(.success(account: request.account, events: events))
            } catch is CancellationError {
                throw CancellationError()
            } catch let error as CalendarCoreExpectedFailure {
                outcomes.append(.failure(account: request.account, error: error))
            } catch let error as GraphCalendarError {
                outcomes.append(.failure(account: request.account, error: .graph(error)))
            }
        }

        return outcomes
    }
}

struct GraphCalendarProvider: CalendarCoreProviding, Sendable {
    private static let providerID = "graph"
    private static let graphHost = "graph.microsoft.com"
    private static let calendarFields = "id,name,isDefaultCalendar,color,hexColor"
    private static let eventFields = [
        "id",
        "subject",
        "start",
        "end",
        "isAllDay",
        "isCancelled",
        "location",
        "onlineMeeting",
        "webLink",
        "seriesMasterId",
        "type",
        "sensitivity",
        "showAs"
    ].joined(separator: ",")

    private let transport: any GraphCalendarTransport
    private let payloadDecoder = GraphCalendarPayloadDecoder()
    private let maxPages: Int
    private let maxResponseBytes: Int

    init(
        transport: any GraphCalendarTransport,
        maxPages: Int = 100,
        maxResponseBytes: Int = 5 * 1_024 * 1_024
    ) {
        precondition(maxPages > 0)
        precondition(maxResponseBytes > 0)
        self.transport = transport
        self.maxPages = maxPages
        self.maxResponseBytes = maxResponseBytes
    }

    func calendars(for account: CalendarAccountID) async throws -> [CalendarCoreCalendar] {
        try validateProvider(for: account)

        var components = URLComponents()
        components.scheme = "https"
        components.host = Self.graphHost
        components.path = "/v1.0/me/calendars"
        components.queryItems = [
            URLQueryItem(name: "$select", value: Self.calendarFields)
        ]
        guard let url = components.url else {
            throw GraphCalendarError.invalidPayload
        }

        return try await loadPages(account: account, initialURL: url) { data in
            try payloadDecoder.decodeCalendars(data, account: account)
        }
    }

    func events(
        for account: CalendarAccountID,
        calendars: [CalendarIdentity],
        interval: CalendarQueryInterval
    ) async throws -> [CalendarCoreEvent] {
        try validateProvider(for: account)
        guard calendars.allSatisfy({ $0.account == account }) else {
            throw GraphCalendarError.calendarAccountMismatch
        }

        var events: [CalendarCoreEvent] = []
        for calendar in calendars {
            try Task.checkCancellation()
            let url = try eventURL(calendarID: calendar.externalID, interval: interval)
            let calendarEvents = try await loadPages(account: account, initialURL: url) { data in
                try payloadDecoder.decodeEvents(data, calendar: calendar)
            }
            events.append(contentsOf: calendarEvents)
        }
        return events
    }

    private func validateProvider(for account: CalendarAccountID) throws {
        guard account.provider.rawValue == Self.providerID else {
            throw GraphCalendarError.accountProviderMismatch
        }
    }

    private func loadPages<Item: Sendable>(
        account: CalendarAccountID,
        initialURL: URL,
        decode: (Data) throws -> GraphCalendarPage<Item>
    ) async throws -> [Item] {
        var currentURL = initialURL
        var visitedURLs: Set<String> = []
        var items: [Item] = []
        var loadedPages = 0

        while true {
            try Task.checkCancellation()
            guard visitedURLs.insert(currentURL.absoluteString).inserted else {
                throw GraphCalendarError.paginationCycle
            }

            let response: GraphCalendarTransportResponse
            do {
                response = try await transport.response(
                    for: GraphCalendarRequest(
                        account: account,
                        url: currentURL,
                        headers: ["Prefer": #"outlook.timezone="UTC""#]
                    )
                )
            } catch is CancellationError {
                throw CancellationError()
            } catch {
                try Task.checkCancellation()
                throw GraphCalendarError.transport
            }

            try Task.checkCancellation()
            try validate(response)
            let page = try decode(response.body)
            items.append(contentsOf: page.items)
            loadedPages += 1

            guard let nextLink = page.nextLink else {
                return items
            }
            guard loadedPages < maxPages else {
                throw GraphCalendarError.pageLimitExceeded
            }
            currentURL = try validatedNextPageURL(nextLink)
        }
    }

    private func validate(_ response: GraphCalendarTransportResponse) throws {
        guard response.body.count <= maxResponseBytes else {
            throw GraphCalendarError.responseTooLarge(limit: maxResponseBytes)
        }

        switch response.statusCode {
        case 200..<300:
            break
        case 401:
            throw GraphCalendarError.unauthorized
        case 403:
            throw GraphCalendarError.forbidden
        case 404:
            throw GraphCalendarError.notFound
        case 429:
            throw GraphCalendarError.throttled(
                retryAfter: Self.retryAfter(from: response.headers)
            )
        default:
            throw GraphCalendarError.httpStatus(response.statusCode)
        }
    }

    private func validatedNextPageURL(_ value: String) throws -> URL {
        guard let components = URLComponents(
            string: value,
            encodingInvalidCharacters: false
        ),
              components.scheme?.lowercased() == "https",
              components.host?.lowercased() == Self.graphHost,
              components.user == nil,
              components.password == nil,
              components.port == nil,
              components.fragment == nil,
              let url = components.url
        else {
            throw GraphCalendarError.invalidNextPageURL
        }
        return url
    }

    private func eventURL(
        calendarID: String,
        interval: CalendarQueryInterval
    ) throws -> URL {
        guard calendarID != ".",
              calendarID != "..",
              let encodedCalendarID = Self.encodedPathSegment(calendarID)
        else {
            throw GraphCalendarError.invalidPayload
        }

        var components = URLComponents()
        components.scheme = "https"
        components.host = Self.graphHost
        components.percentEncodedPath =
            "/v1.0/me/calendars/\(encodedCalendarID)/calendarView"
        components.queryItems = [
            URLQueryItem(
                name: "startDateTime",
                value: try Self.requestDateString(interval.start)
            ),
            URLQueryItem(
                name: "endDateTime",
                value: try Self.requestDateString(interval.end)
            ),
            URLQueryItem(name: "$select", value: Self.eventFields)
        ]
        guard let url = components.url else {
            throw GraphCalendarError.invalidPayload
        }
        return url
    }

    private static func encodedPathSegment(_ value: String) -> String? {
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "-._~")
        return value.addingPercentEncoding(withAllowedCharacters: allowed)
    }

    private static func retryAfter(from headers: [String: String]) -> GraphRetryAfter? {
        guard let value = headers.first(where: {
            $0.key.caseInsensitiveCompare("Retry-After") == .orderedSame
        })?.value else {
            return nil
        }
        if let seconds = Int(value), seconds >= 0 {
            return .seconds(seconds)
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "EEE',' dd MMM yyyy HH':'mm':'ss z"
        if let date = formatter.date(from: value) {
            return .date(date)
        }
        return nil
    }

    private static func requestDateString(_ date: Date) throws -> String {
        let referenceSeconds = date.timeIntervalSinceReferenceDate
        guard var wholeSeconds = Int64(exactly: floor(referenceSeconds)) else {
            throw GraphCalendarError.invalidPayload
        }
        var nanoseconds = Int64(
            ((referenceSeconds - Double(wholeSeconds)) * 1_000_000_000).rounded()
        )
        if nanoseconds == 1_000_000_000 {
            guard wholeSeconds < .max else {
                throw GraphCalendarError.invalidPayload
            }
            wholeSeconds += 1
            nanoseconds = 0
        }

        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        let wholeSecondValue = formatter.string(
            from: Date(timeIntervalSinceReferenceDate: Double(wholeSeconds))
        )
        let fractionalValue = String(
            format: ".%09lld",
            locale: Locale(identifier: "en_US_POSIX"),
            nanoseconds
        )
        let value = wholeSecondValue + fractionalValue + "Z"

        let wholeSecondParser = Date.ISO8601FormatStyle(includingFractionalSeconds: false)
        guard let parsedWholeSecond = try? wholeSecondParser.parse(wholeSecondValue + "Z"),
              parsedWholeSecond.timeIntervalSinceReferenceDate == Double(wholeSeconds),
              let fraction = Decimal(
                  string: "0" + fractionalValue,
                  locale: Locale(identifier: "en_US_POSIX")
              ),
              let reconstructedSeconds = Double(
                  NSDecimalNumber(
                      decimal: Decimal(wholeSeconds) + fraction
                  ).stringValue
              ),
              Date(timeIntervalSinceReferenceDate: reconstructedSeconds) == date
        else {
            throw GraphCalendarError.invalidPayload
        }
        return value
    }
}
