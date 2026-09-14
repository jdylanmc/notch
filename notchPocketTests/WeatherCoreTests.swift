//
//  WeatherCoreTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class WeatherCoreTests: XCTestCase {
    func testSnapshotLimitsForecastHorizonsAndPreservesOrder() {
        let start = Date(timeIntervalSince1970: 1_700_000_000)
        let hourly = (0..<30).map { offset in
            HourlyWeatherRecord(
                date: start.addingTimeInterval(TimeInterval(offset * 3_600)),
                condition: nil,
                symbolName: nil,
                temperature: nil,
                precipitationChance: nil
            )
        }
        let daily = (0..<10).map { offset in
            DailyWeatherRecord(
                date: start.addingTimeInterval(TimeInterval(offset * 86_400)),
                condition: nil,
                symbolName: nil,
                highTemperature: nil,
                lowTemperature: nil,
                precipitationChance: nil
            )
        }

        let snapshot = WeatherSnapshot(
            providerDate: nil,
            fetchedAt: start,
            current: nil,
            hourly: hourly,
            daily: daily
        )

        XCTAssertEqual(snapshot.hourly.count, 24)
        XCTAssertEqual(snapshot.hourly.first?.date, start)
        XCTAssertEqual(snapshot.hourly.last?.date, start.addingTimeInterval(23 * 3_600))
        XCTAssertEqual(snapshot.daily.count, 7)
        XCTAssertEqual(snapshot.daily.first?.date, start)
        XCTAssertEqual(snapshot.daily.last?.date, start.addingTimeInterval(6 * 86_400))
    }

    func testTemperaturePresentationConvertsWithoutChangingSourceValue() {
        let source = Measurement(value: 0, unit: UnitTemperature.celsius)

        let metric = WeatherTemperaturePresentation.value(
            source,
            units: .metric,
            locale: Locale(identifier: "en_US")
        )
        let imperial = WeatherTemperaturePresentation.value(
            source,
            units: .imperial,
            locale: Locale(identifier: "en_GB")
        )

        XCTAssertEqual(metric.unit, .celsius)
        XCTAssertEqual(metric.value, 0, accuracy: 0.001)
        XCTAssertEqual(imperial.unit, .fahrenheit)
        XCTAssertEqual(imperial.value, 32, accuracy: 0.001)
        XCTAssertEqual(source.unit, .celsius)
        XCTAssertEqual(source.value, 0, accuracy: 0.001)
    }

    func testAutomaticTemperatureUnitsFollowLocaleMeasurementSystem() {
        let source = Measurement(value: 20, unit: UnitTemperature.celsius)

        let unitedStates = WeatherTemperaturePresentation.value(
            source,
            units: .automatic,
            locale: Locale(identifier: "en_US")
        )
        let unitedKingdom = WeatherTemperaturePresentation.value(
            source,
            units: .automatic,
            locale: Locale(identifier: "en_GB")
        )

        XCTAssertEqual(unitedStates.unit, .fahrenheit)
        XCTAssertEqual(unitedKingdom.unit, .celsius)
    }

    func testRepeatedWidgetsKeepIndependentIdentityForTheSameLocation() throws {
        let location = WeatherLocation(
            id: WeatherLocationID(rawValue: "manual:seattle-wa-us"),
            displayName: "Seattle, WA",
            latitude: 47.6062,
            longitude: -122.3321,
            timeZoneIdentifier: "America/Los_Angeles"
        )
        let firstID = WeatherWidgetID(
            rawValue: try XCTUnwrap(UUID(uuidString: "11111111-1111-1111-1111-111111111111"))
        )
        let secondID = WeatherWidgetID(
            rawValue: try XCTUnwrap(UUID(uuidString: "22222222-2222-2222-2222-222222222222"))
        )

        let first = WeatherWidgetPresentation(
            widgetID: firstID,
            location: location,
            units: .metric,
            snapshot: nil
        )
        let second = WeatherWidgetPresentation(
            widgetID: secondID,
            location: location,
            units: .metric,
            snapshot: nil
        )

        XCTAssertNotEqual(first, second)
        XCTAssertEqual(first.location.id.rawValue, "manual:seattle-wa-us")
        XCTAssertEqual(second.location, first.location)
    }

    func testRefreshDecisionUsesInjectedTimeAndInterval() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let current = makeSnapshot(fetchedAt: now.addingTimeInterval(-1_799))
        let due = makeSnapshot(fetchedAt: now.addingTimeInterval(-1_800))
        let future = makeSnapshot(fetchedAt: now.addingTimeInterval(60))

        XCTAssertEqual(
            WeatherRefreshPolicy.decision(snapshot: nil, now: now, refreshInterval: 1_800),
            .refresh
        )
        XCTAssertEqual(
            WeatherRefreshPolicy.decision(snapshot: current, now: now, refreshInterval: 1_800),
            .current
        )
        XCTAssertEqual(
            WeatherRefreshPolicy.decision(snapshot: due, now: now, refreshInterval: 1_800),
            .refresh
        )
        XCTAssertEqual(
            WeatherRefreshPolicy.decision(snapshot: future, now: now, refreshInterval: 1_800),
            .current
        )
        XCTAssertEqual(
            WeatherRefreshPolicy.decision(snapshot: current, now: now, refreshInterval: 0),
            .invalidInterval
        )
    }

    func testRefreshDecisionRejectsEveryNonfiniteInterval() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let snapshot = makeSnapshot(fetchedAt: now)

        for interval in [Double.infinity, -Double.infinity, Double.nan] {
            XCTAssertEqual(
                WeatherRefreshPolicy.decision(snapshot: nil, now: now, refreshInterval: interval),
                .invalidInterval
            )
            XCTAssertEqual(
                WeatherRefreshPolicy.decision(snapshot: snapshot, now: now, refreshInterval: interval),
                .invalidInterval
            )
        }
    }

    func testFailedRefreshUsesInjectedStaleInterval() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let atLimit = makeSnapshot(fetchedAt: now.addingTimeInterval(-21_600))
        let expired = makeSnapshot(fetchedAt: now.addingTimeInterval(-21_601))

        XCTAssertEqual(
            WeatherSnapshotAvailability.evaluate(
                snapshot: atLimit,
                refreshFailed: true,
                now: now,
                staleInterval: 21_600
            ),
            .stale(atLimit)
        )
        XCTAssertEqual(
            WeatherSnapshotAvailability.evaluate(
                snapshot: expired,
                refreshFailed: true,
                now: now,
                staleInterval: 21_600
            ),
            .unavailable
        )
        XCTAssertEqual(
            WeatherSnapshotAvailability.evaluate(
                snapshot: expired,
                refreshFailed: false,
                now: now,
                staleInterval: 21_600
            ),
            .available(expired)
        )
        XCTAssertEqual(
            WeatherSnapshotAvailability.evaluate(
                snapshot: nil,
                refreshFailed: true,
                now: now,
                staleInterval: 21_600
            ),
            .unavailable
        )
        XCTAssertEqual(
            WeatherSnapshotAvailability.evaluate(
                snapshot: atLimit,
                refreshFailed: true,
                now: now,
                staleInterval: 0
            ),
            .invalidInterval
        )
    }

    func testStalePolicyRejectsEveryNonfiniteInterval() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let snapshot = makeSnapshot(fetchedAt: now)

        for interval in [Double.infinity, -Double.infinity, Double.nan] {
            XCTAssertEqual(
                WeatherSnapshotAvailability.evaluate(
                    snapshot: snapshot,
                    refreshFailed: true,
                    now: now,
                    staleInterval: interval
                ),
                .invalidInterval
            )
        }
    }

    func testEmptySnapshotIsNeverCurrentAvailableOrStale() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let empty = WeatherSnapshot(
            providerDate: now,
            fetchedAt: now,
            current: nil,
            hourly: [],
            daily: []
        )

        XCTAssertEqual(
            WeatherRefreshPolicy.decision(snapshot: empty, now: now, refreshInterval: 1_800),
            .refresh
        )
        XCTAssertEqual(
            WeatherSnapshotAvailability.evaluate(
                snapshot: empty,
                refreshFailed: false,
                now: now,
                staleInterval: 21_600
            ),
            .unavailable
        )
        XCTAssertEqual(
            WeatherSnapshotAvailability.evaluate(
                snapshot: empty,
                refreshFailed: true,
                now: now,
                staleInterval: 21_600
            ),
            .unavailable
        )
    }

    func testAnySupportedPartialForecastRemainsUsable() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let currentOnly = makeSnapshot(fetchedAt: now)
        let hourlyOnly = WeatherSnapshot(
            providerDate: now,
            fetchedAt: now,
            current: nil,
            hourly: [
                HourlyWeatherRecord(
                    date: now,
                    condition: nil,
                    symbolName: nil,
                    temperature: Measurement(value: 13, unit: .celsius),
                    precipitationChance: nil
                )
            ],
            daily: []
        )
        let dailyOnly = WeatherSnapshot(
            providerDate: now,
            fetchedAt: now,
            current: nil,
            hourly: [],
            daily: [
                DailyWeatherRecord(
                    date: now,
                    condition: nil,
                    symbolName: nil,
                    highTemperature: Measurement(value: 15, unit: .celsius),
                    lowTemperature: nil,
                    precipitationChance: nil
                )
            ]
        )

        for snapshot in [currentOnly, hourlyOnly, dailyOnly] {
            XCTAssertEqual(
                WeatherRefreshPolicy.decision(snapshot: snapshot, now: now, refreshInterval: 1_800),
                .current
            )
            XCTAssertEqual(
                WeatherSnapshotAvailability.evaluate(
                    snapshot: snapshot,
                    refreshFailed: false,
                    now: now,
                    staleInterval: 21_600
                ),
                .available(snapshot)
            )
        }
    }

    func testFreshnessPoliciesRejectNonfiniteDatesAndAges() {
        let validNow = Date(timeIntervalSince1970: 1_700_000_000)
        let validSnapshot = makeSnapshot(fetchedAt: validNow)

        for invalidTime in [Double.nan, Double.infinity, -Double.infinity] {
            let invalidDate = Date(timeIntervalSinceReferenceDate: invalidTime)
            let invalidSnapshot = makeSnapshot(fetchedAt: invalidDate)

            assertInvalidTime(snapshot: invalidSnapshot, now: validNow)
            assertInvalidTime(snapshot: validSnapshot, now: invalidDate)
        }

        let overflowSnapshot = makeSnapshot(
            fetchedAt: Date(timeIntervalSinceReferenceDate: -Double.greatestFiniteMagnitude)
        )
        let overflowNow = Date(timeIntervalSinceReferenceDate: Double.greatestFiniteMagnitude)

        assertInvalidTime(snapshot: overflowSnapshot, now: overflowNow)
    }

    func testMissingProviderValuesRemainExplicit() {
        let current = CurrentWeatherRecord(
            providerDate: nil,
            condition: nil,
            symbolName: nil,
            temperature: nil,
            apparentTemperature: nil,
            highTemperature: nil,
            lowTemperature: nil,
            precipitationChance: nil
        )

        XCTAssertNil(current.providerDate)
        XCTAssertNil(current.condition)
        XCTAssertNil(current.symbolName)
        XCTAssertNil(current.temperature)
        XCTAssertNil(current.apparentTemperature)
        XCTAssertNil(current.highTemperature)
        XCTAssertNil(current.lowTemperature)
        XCTAssertNil(current.precipitationChance)
    }

    private func makeSnapshot(fetchedAt: Date) -> WeatherSnapshot {
        WeatherSnapshot(
            providerDate: nil,
            fetchedAt: fetchedAt,
            current: CurrentWeatherRecord(
                providerDate: nil,
                condition: "Clear",
                symbolName: "sun.max",
                temperature: Measurement(value: 20, unit: .celsius),
                apparentTemperature: nil,
                highTemperature: nil,
                lowTemperature: nil,
                precipitationChance: nil
            ),
            hourly: [],
            daily: []
        )
    }

    private func assertInvalidTime(
        snapshot: WeatherSnapshot,
        now: Date,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertEqual(
            WeatherRefreshPolicy.decision(
                snapshot: snapshot,
                now: now,
                refreshInterval: 1_800
            ),
            .invalidTime,
            file: file,
            line: line
        )
        XCTAssertEqual(
            WeatherSnapshotAvailability.evaluate(
                snapshot: snapshot,
                refreshFailed: true,
                now: now,
                staleInterval: 21_600
            ),
            .invalidTime,
            file: file,
            line: line
        )
    }
}

final class WeatherCoreInvariantTests: XCTestCase {
    func testFiniteNegativeIntervalsAreInvalidForMissingAndExistingSnapshots() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let snapshots: [WeatherSnapshot?] = [nil, makeUsableSnapshot(fetchedAt: now)]

        for snapshot in snapshots {
            XCTAssertEqual(
                WeatherRefreshPolicy.decision(snapshot: snapshot, now: now, refreshInterval: -1),
                .invalidInterval
            )
            XCTAssertEqual(
                WeatherSnapshotAvailability.evaluate(
                    snapshot: snapshot, refreshFailed: true, now: now, staleInterval: -1
                ),
                .invalidInterval
            )
        }
    }

    func testSnapshotsWithOnlyUnusableRecordsRequireRefreshAndRemainUnavailable() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let current = CurrentWeatherRecord(
            providerDate: now, condition: nil, symbolName: nil, temperature: nil,
            apparentTemperature: nil, highTemperature: nil, lowTemperature: nil,
            precipitationChance: nil
        )
        let hourly = HourlyWeatherRecord(
            date: now, condition: nil, symbolName: nil, temperature: nil, precipitationChance: nil
        )
        let daily = DailyWeatherRecord(
            date: now, condition: nil, symbolName: nil, highTemperature: nil,
            lowTemperature: nil, precipitationChance: nil
        )
        let snapshots = [
            WeatherSnapshot(providerDate: now, fetchedAt: now, current: current, hourly: [], daily: []),
            WeatherSnapshot(providerDate: now, fetchedAt: now, current: nil, hourly: [hourly], daily: []),
            WeatherSnapshot(providerDate: now, fetchedAt: now, current: nil, hourly: [], daily: [daily]),
            WeatherSnapshot(
                providerDate: now, fetchedAt: now, current: current, hourly: [hourly], daily: [daily]
            )
        ]

        for snapshot in snapshots {
            assertUnusable(snapshot, now: now)
        }
    }

    private func makeUsableSnapshot(fetchedAt: Date) -> WeatherSnapshot {
        WeatherSnapshot(
            providerDate: nil, fetchedAt: fetchedAt,
            current: CurrentWeatherRecord(
                providerDate: nil, condition: "Clear", symbolName: nil, temperature: nil,
                apparentTemperature: nil, highTemperature: nil, lowTemperature: nil,
                precipitationChance: nil
            ),
            hourly: [], daily: []
        )
    }

    private func assertUnusable(
        _ snapshot: WeatherSnapshot,
        now: Date,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertEqual(
            WeatherRefreshPolicy.decision(snapshot: snapshot, now: now, refreshInterval: 1_800),
            .refresh,
            file: file,
            line: line
        )
        for refreshFailed in [false, true] {
            XCTAssertEqual(
                WeatherSnapshotAvailability.evaluate(
                    snapshot: snapshot, refreshFailed: refreshFailed, now: now, staleInterval: 21_600
                ),
                .unavailable,
                file: file,
                line: line
            )
        }
    }
}
