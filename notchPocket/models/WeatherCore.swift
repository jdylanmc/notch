//
//  WeatherCore.swift
//  notchPocket
//

import Foundation

private extension Optional where Wrapped == String {
    var hasNonblankText: Bool {
        guard let value = self else { return false }
        return !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}

enum WeatherUnitSelection: String, CaseIterable, Equatable, Sendable {
    case automatic
    case metric
    case imperial
}

struct WeatherWidgetID: RawRepresentable, Equatable, Hashable, Sendable {
    let rawValue: UUID
}

struct WeatherLocationID: RawRepresentable, Equatable, Hashable, Sendable {
    let rawValue: String
}

struct WeatherLocation: Equatable, Hashable, Sendable {
    let id: WeatherLocationID
    let displayName: String
    let latitude: Double
    let longitude: Double
    let timeZoneIdentifier: String
}

enum WeatherTemperaturePresentation {
    static func value(
        _ temperature: Measurement<UnitTemperature>,
        units: WeatherUnitSelection,
        locale: Locale
    ) -> Measurement<UnitTemperature> {
        let unit: UnitTemperature
        switch units {
        case .automatic:
            unit = locale.measurementSystem == .us ? .fahrenheit : .celsius
        case .metric:
            unit = .celsius
        case .imperial:
            unit = .fahrenheit
        }
        return temperature.converted(to: unit)
    }
}

struct CurrentWeatherRecord: Equatable {
    let providerDate: Date?
    let condition: String?
    let symbolName: String?
    let temperature: Measurement<UnitTemperature>?
    let apparentTemperature: Measurement<UnitTemperature>?
    let highTemperature: Measurement<UnitTemperature>?
    let lowTemperature: Measurement<UnitTemperature>?
    let precipitationChance: Double?

    fileprivate var hasUsableData: Bool {
        condition.hasNonblankText
            || symbolName.hasNonblankText
            || temperature != nil
            || apparentTemperature != nil
            || highTemperature != nil
            || lowTemperature != nil
            || precipitationChance != nil
    }
}

struct HourlyWeatherRecord: Equatable {
    let date: Date
    let condition: String?
    let symbolName: String?
    let temperature: Measurement<UnitTemperature>?
    let precipitationChance: Double?

    fileprivate var hasUsableData: Bool {
        condition.hasNonblankText
            || symbolName.hasNonblankText
            || temperature != nil
            || precipitationChance != nil
    }
}

struct DailyWeatherRecord: Equatable {
    let date: Date
    let condition: String?
    let symbolName: String?
    let highTemperature: Measurement<UnitTemperature>?
    let lowTemperature: Measurement<UnitTemperature>?
    let precipitationChance: Double?

    fileprivate var hasUsableData: Bool {
        condition.hasNonblankText
            || symbolName.hasNonblankText
            || highTemperature != nil
            || lowTemperature != nil
            || precipitationChance != nil
    }
}

struct WeatherSnapshot: Equatable {
    let providerDate: Date?
    let fetchedAt: Date
    let current: CurrentWeatherRecord?
    let hourly: [HourlyWeatherRecord]
    let daily: [DailyWeatherRecord]

    init(
        providerDate: Date?,
        fetchedAt: Date,
        current: CurrentWeatherRecord?,
        hourly: [HourlyWeatherRecord],
        daily: [DailyWeatherRecord]
    ) {
        self.providerDate = providerDate
        self.fetchedAt = fetchedAt
        self.current = current
        self.hourly = Array(hourly.prefix(24))
        self.daily = Array(daily.prefix(7))
    }

    fileprivate var hasUsableData: Bool {
        current?.hasUsableData == true
            || hourly.contains(where: \.hasUsableData)
            || daily.contains(where: \.hasUsableData)
    }
}

struct WeatherWidgetPresentation: Equatable {
    let widgetID: WeatherWidgetID
    let location: WeatherLocation
    let units: WeatherUnitSelection
    let snapshot: WeatherSnapshot?
}

enum WeatherRefreshDecision: Equatable {
    case refresh
    case current
    case invalidInterval
    case invalidTime
}

enum WeatherRefreshPolicy {
    static func decision(
        snapshot: WeatherSnapshot?,
        now: Date,
        refreshInterval: TimeInterval
    ) -> WeatherRefreshDecision {
        guard refreshInterval.isFinite, refreshInterval > 0 else { return .invalidInterval }
        guard let snapshot else { return .refresh }
        guard snapshot.hasUsableData else { return .refresh }
        guard now.timeIntervalSinceReferenceDate.isFinite,
              snapshot.fetchedAt.timeIntervalSinceReferenceDate.isFinite
        else {
            return .invalidTime
        }

        let age = now.timeIntervalSince(snapshot.fetchedAt)
        guard age.isFinite else { return .invalidTime }
        guard age >= 0 else { return .current }
        return age >= refreshInterval ? .refresh : .current
    }
}

enum WeatherSnapshotAvailability: Equatable {
    case available(WeatherSnapshot)
    case stale(WeatherSnapshot)
    case unavailable
    case invalidInterval
    case invalidTime

    static func evaluate(
        snapshot: WeatherSnapshot?,
        refreshFailed: Bool,
        now: Date,
        staleInterval: TimeInterval
    ) -> WeatherSnapshotAvailability {
        guard staleInterval.isFinite, staleInterval > 0 else { return .invalidInterval }
        guard let snapshot else { return .unavailable }
        guard snapshot.hasUsableData else { return .unavailable }
        guard now.timeIntervalSinceReferenceDate.isFinite,
              snapshot.fetchedAt.timeIntervalSinceReferenceDate.isFinite
        else {
            return .invalidTime
        }

        let age = now.timeIntervalSince(snapshot.fetchedAt)
        guard age.isFinite else { return .invalidTime }
        guard refreshFailed else { return .available(snapshot) }

        return max(0, age) <= staleInterval ? .stale(snapshot) : .unavailable
    }
}
