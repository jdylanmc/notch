//
//  CalendarCoreModels.swift
//  notchPocket
//

import Foundation

enum CalendarCoreValidationError: Error, Equatable {
    case emptyIdentifier
    case invalidInterval
}

struct CalendarProviderID: Hashable, Codable, Sendable {
    let rawValue: String

    init(_ rawValue: String) throws {
        self.rawValue = try validatedCalendarIdentifier(rawValue)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(container.decode(String.self, forKey: .rawValue))
    }

    private enum CodingKeys: String, CodingKey {
        case rawValue
    }
}

struct CalendarAccountID: Hashable, Codable, Sendable {
    let provider: CalendarProviderID
    let externalID: String

    init(provider: CalendarProviderID, externalID: String) throws {
        self.provider = provider
        self.externalID = try validatedCalendarIdentifier(externalID)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            provider: container.decode(CalendarProviderID.self, forKey: .provider),
            externalID: container.decode(String.self, forKey: .externalID)
        )
    }

    private enum CodingKeys: String, CodingKey {
        case provider
        case externalID
    }
}

struct CalendarIdentity: Hashable, Codable, Sendable {
    let account: CalendarAccountID
    let externalID: String

    init(account: CalendarAccountID, externalID: String) throws {
        self.account = account
        self.externalID = try validatedCalendarIdentifier(externalID)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            account: container.decode(CalendarAccountID.self, forKey: .account),
            externalID: container.decode(String.self, forKey: .externalID)
        )
    }

    private enum CodingKeys: String, CodingKey {
        case account
        case externalID
    }
}

struct CalendarEventIdentity: Hashable, Codable, Sendable {
    let calendar: CalendarIdentity
    let externalID: String

    init(calendar: CalendarIdentity, externalID: String) throws {
        self.calendar = calendar
        self.externalID = try validatedCalendarIdentifier(externalID)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            calendar: container.decode(CalendarIdentity.self, forKey: .calendar),
            externalID: container.decode(String.self, forKey: .externalID)
        )
    }

    private enum CodingKeys: String, CodingKey {
        case calendar
        case externalID
    }
}

struct CalendarQueryInterval: Hashable, Codable, Sendable {
    let start: Date
    let end: Date

    init(start: Date, end: Date) throws {
        guard start.timeIntervalSinceReferenceDate.isFinite,
              end.timeIntervalSinceReferenceDate.isFinite,
              start < end
        else {
            throw CalendarCoreValidationError.invalidInterval
        }

        self.start = start
        self.end = end
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            start: container.decode(Date.self, forKey: .start),
            end: container.decode(Date.self, forKey: .end)
        )
    }

    private enum CodingKeys: String, CodingKey {
        case start
        case end
    }
}

func validatedCalendarIdentifier(_ value: String) throws -> String {
    guard !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
        throw CalendarCoreValidationError.emptyIdentifier
    }
    return value
}
