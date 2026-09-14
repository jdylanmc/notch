//
//  GraphCalendarPayloadDecoder.swift
//  notchPocket
//

import Foundation

struct GraphCalendarPayloadDecoder: Sendable {
    func decodeCalendars(
        _ data: Data,
        account: CalendarAccountID
    ) throws -> GraphCalendarPage<CalendarCoreCalendar> {
        let page: CalendarPagePayload = try decode(data)
        do {
            let calendars = try page.value.map { payload in
                let color = payload.color == nil && payload.hexColor == nil
                    ? nil
                    : CalendarProviderColor(name: payload.color, hex: payload.hexColor)
                return CalendarCoreCalendar(
                    identity: try CalendarIdentity(account: account, externalID: payload.id),
                    name: payload.name,
                    isDefault: payload.isDefaultCalendar,
                    color: color
                )
            }
            return GraphCalendarPage(items: calendars, nextLink: page.nextLink)
        } catch is CalendarCoreValidationError {
            throw GraphCalendarError.invalidPayload
        }
    }

    func decodeEvents(
        _ data: Data,
        calendar: CalendarIdentity
    ) throws -> GraphCalendarPage<CalendarCoreEvent> {
        let page: EventPagePayload = try decode(data)
        do {
            let events = try page.value.map { payload in
                CalendarCoreEvent(
                    identity: try CalendarEventIdentity(
                        calendar: calendar,
                        externalID: payload.id
                    ),
                    title: payload.subject,
                    start: try payload.start.date(),
                    end: try payload.end.date(),
                    isAllDay: payload.isAllDay,
                    isCancelled: payload.isCancelled,
                    location: payload.location?.displayName,
                    onlineMeetingURL: try validatedHTTPSURL(payload.onlineMeeting?.joinURL),
                    webURL: try validatedHTTPSURL(payload.webLink),
                    seriesRootExternalID: try payload.seriesRootID.map {
                        try validatedCalendarIdentifier($0)
                    },
                    providerType: payload.type,
                    sensitivity: payload.sensitivity,
                    availability: payload.showAs
                )
            }
            return GraphCalendarPage(items: events, nextLink: page.nextLink)
        } catch is CalendarCoreValidationError {
            throw GraphCalendarError.invalidPayload
        }
    }

    private func decode<Payload: Decodable>(_ data: Data) throws -> Payload {
        do {
            return try JSONDecoder().decode(Payload.self, from: data)
        } catch let error as GraphCalendarError {
            throw error
        } catch {
            throw GraphCalendarError.decoding
        }
    }
}

private struct CalendarPagePayload: Decodable {
    let value: [CalendarPayload]
    let nextLink: String?

    private enum CodingKeys: String, CodingKey {
        case value
        case nextLink = "@odata.nextLink"
    }
}

private struct CalendarPayload: Decodable {
    let id: String
    let name: String
    let isDefaultCalendar: Bool
    let color: String?
    let hexColor: String?
}

private struct EventPagePayload: Decodable {
    let value: [EventPayload]
    let nextLink: String?

    private enum CodingKeys: String, CodingKey {
        case value
        case nextLink = "@odata.nextLink"
    }
}

private struct EventPayload: Decodable {
    let id: String
    let subject: String
    let start: DateTimePayload
    let end: DateTimePayload
    let isAllDay: Bool
    let isCancelled: Bool
    let location: LocationPayload?
    let onlineMeeting: OnlineMeetingPayload?
    let webLink: String?
    let seriesRootID: String?
    let type: String?
    let sensitivity: String?
    let showAs: String?

    private enum CodingKeys: String, CodingKey {
        case id
        case subject
        case start
        case end
        case isAllDay
        case isCancelled
        case location
        case onlineMeeting
        case webLink
        case seriesRootID = "seriesMasterId"
        case type
        case sensitivity
        case showAs
    }
}

private struct DateTimePayload: Decodable {
    let dateTime: String
    let timeZone: String

    func date() throws -> Date {
        guard timeZone == "UTC" || timeZone == "Etc/UTC" else {
            throw GraphCalendarError.invalidPayload
        }

        let value = dateTime.hasSuffix("Z") ? dateTime : dateTime + "Z"
        let fractionalFormatter = ISO8601DateFormatter()
        fractionalFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let wholeSecondFormatter = ISO8601DateFormatter()
        if let date = fractionalFormatter.date(from: value)
            ?? wholeSecondFormatter.date(from: value) {
            return date
        }
        throw GraphCalendarError.invalidPayload
    }
}

private struct LocationPayload: Decodable {
    let displayName: String?
}

private struct OnlineMeetingPayload: Decodable {
    let joinURL: String?

    private enum CodingKeys: String, CodingKey {
        case joinURL = "joinUrl"
    }
}

private func validatedHTTPSURL(_ value: String?) throws -> URL? {
    guard let value else { return nil }
    guard let components = URLComponents(
        string: value,
        encodingInvalidCharacters: false
    ),
          components.scheme?.lowercased() == "https",
          components.host != nil,
          components.user == nil,
          components.password == nil,
          let url = components.url
    else {
        throw GraphCalendarError.invalidPayload
    }
    return url
}
