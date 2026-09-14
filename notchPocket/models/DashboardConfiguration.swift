//
//  DashboardConfiguration.swift
//  notchPocket
//

import Foundation

struct DashboardConfiguration: Codable, Equatable, Sendable {
    static let currentSchemaVersion = 1

    var schemaVersion: Int
    var revision: UInt64
    var instances: [DashboardWidgetInstance]

    init(
        schemaVersion: Int = Self.currentSchemaVersion,
        revision: UInt64,
        instances: [DashboardWidgetInstance]
    ) {
        self.schemaVersion = schemaVersion
        self.revision = revision
        self.instances = instances
    }

    var identityValidationError: DashboardConfigurationValidationError? {
        let ids = instances.map(\.id)
        return ids.count == Set(ids).count ? nil : .duplicateInstanceIDs
    }
}

enum DashboardConfigurationValidationError: Error, Equatable {
    case duplicateInstanceIDs
}

struct DashboardWidgetKind: RawRepresentable, Codable, Equatable, Hashable, Sendable {
    static let shelfSummary = DashboardWidgetKind(rawValue: "shelfSummary")

    let rawValue: String
}

struct DashboardGridPosition: Codable, Equatable, Sendable {
    var column: Int
    var row: Int
}

struct DashboardGridFootprint: Codable, Equatable, Sendable {
    var columns: Int
    var rows: Int
}

struct ShelfSummaryWidgetSettings: Equatable, Sendable {
    var showsItemCount: Bool
}

struct DashboardWidgetInstance: Codable, Equatable, Identifiable, Sendable {
    var id: UUID
    var kind: DashboardWidgetKind
    var position: DashboardGridPosition
    var footprint: DashboardGridFootprint
    var settings: [String: JSONValue]
    var extraFields: [String: JSONValue]

    init(
        id: UUID,
        kind: DashboardWidgetKind,
        position: DashboardGridPosition,
        footprint: DashboardGridFootprint,
        settings: [String: JSONValue],
        extraFields: [String: JSONValue] = [:]
    ) {
        self.id = id
        self.kind = kind
        self.position = position
        self.footprint = footprint
        self.settings = settings
        self.extraFields = extraFields
    }

    static func shelfSummary(
        id: UUID = UUID(),
        position: DashboardGridPosition,
        footprint: DashboardGridFootprint,
        settings: ShelfSummaryWidgetSettings = .init(showsItemCount: true)
    ) -> Self {
        var instance = Self(
            id: id,
            kind: .shelfSummary,
            position: position,
            footprint: footprint,
            settings: [:]
        )
        instance.setShelfSummarySettings(settings)
        return instance
    }

    var shelfSummarySettings: ShelfSummaryWidgetSettings? {
        guard kind == .shelfSummary else { return nil }
        return ShelfSummaryWidgetSettings(
            showsItemCount: settings["showsItemCount"]?.boolValue ?? true
        )
    }

    mutating func setShelfSummarySettings(_ value: ShelfSummaryWidgetSettings) {
        guard kind == .shelfSummary else { return }
        settings["showsItemCount"] = .bool(value.showsItemCount)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: DashboardCodingKey.self)
        id = try container.decode(UUID.self, forKey: .init("id"))
        kind = try container.decode(DashboardWidgetKind.self, forKey: .init("kind"))
        position = try container.decode(DashboardGridPosition.self, forKey: .init("position"))
        footprint = try container.decode(DashboardGridFootprint.self, forKey: .init("footprint"))
        settings = try container.decodeIfPresent(
            [String: JSONValue].self,
            forKey: .init("settings")
        ) ?? [:]

        let knownKeys = Set(["id", "kind", "position", "footprint", "settings"])
        extraFields = try container.allKeys.reduce(into: [:]) { result, key in
            guard !knownKeys.contains(key.stringValue) else { return }
            result[key.stringValue] = try container.decode(JSONValue.self, forKey: key)
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: DashboardCodingKey.self)
        try container.encode(id, forKey: .init("id"))
        try container.encode(kind, forKey: .init("kind"))
        try container.encode(position, forKey: .init("position"))
        try container.encode(footprint, forKey: .init("footprint"))
        try container.encode(settings, forKey: .init("settings"))
        for (key, value) in extraFields {
            try container.encode(value, forKey: .init(key))
        }
    }
}

enum JSONValue: Codable, Equatable, Sendable {
    case null
    case bool(Bool)
    case number(JSONNumber)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    var boolValue: Bool? {
        guard case .bool(let value) = self else { return nil }
        return value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Int64.self) {
            self = .number(.signed(value))
        } else if let value = try? container.decode(UInt64.self) {
            self = .number(.unsigned(value))
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            self = .object(try container.decode([String: JSONValue].self))
        }
    }

    enum JSONNumber: Codable, Equatable, Sendable {
        case signed(Int64)
        case unsigned(UInt64)

        init(from decoder: Decoder) throws {
            let container = try decoder.singleValueContainer()
            if let value = try? container.decode(Int64.self) {
                self = .signed(value)
            } else if let value = try? container.decode(UInt64.self) {
                self = .unsigned(value)
            } else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "Only exactly representable JSON integers are supported"
                )
            }
        }

        func encode(to encoder: Encoder) throws {
            var container = encoder.singleValueContainer()
            switch self {
            case .signed(let value):
                try container.encode(value)
            case .unsigned(let value):
                try container.encode(value)
            }
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null:
            try container.encodeNil()
        case .bool(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        case .string(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        }
    }
}

private struct DashboardCodingKey: CodingKey, Hashable {
    let stringValue: String
    let intValue: Int?

    init(_ stringValue: String) {
        self.stringValue = stringValue
        intValue = nil
    }

    init?(stringValue: String) {
        self.init(stringValue)
    }

    init?(intValue: Int) {
        stringValue = String(intValue)
        self.intValue = intValue
    }
}
