import Defaults
import EventKit
import Foundation
import XCTest

@testable import notchPocket

@MainActor
final class CalendarManagerIsolationTests: XCTestCase {
    private enum FixtureError: Error {
        case occupiedDomain
        case accessFailed
    }

    private struct Query: Equatable {
        let start: Date
        let end: Date
        let calendarIDs: [String]
    }

    private final class Service: CalendarServiceProviding {
        var eventStatus: EKAuthorizationStatus = .notDetermined
        var reminderStatus: EKAuthorizationStatus = .notDetermined
        var accessResult: Result<Bool, FixtureError> = .success(true)
        var calendarValues: [CalendarModel] = []
        var eventValues: [EventModel] = []
        var requests: [EKEntityType] = []
        var calendarReads = 0
        var queries: [Query] = []
        var completions: [(String, Bool)] = []
        var operations: [String] = []

        func authorizationStatus(for type: EKEntityType) -> EKAuthorizationStatus {
            type == .event ? eventStatus : reminderStatus
        }

        @MainActor
        func requestAccess(to type: EKEntityType) async throws -> Bool {
            requests.append(type)
            return try accessResult.get()
        }

        func calendars() async -> [CalendarModel] {
            calendarReads += 1
            return calendarValues
        }

        func events(from start: Date, to end: Date, calendars: [String]) async -> [EventModel] {
            queries.append(Query(start: start, end: end, calendarIDs: calendars))
            operations.append("events")
            return eventValues.filter { calendars.isEmpty || calendars.contains($0.calendar.id) }
        }

        func setReminderCompleted(reminderID: String, completed: Bool) async {
            completions.append((reminderID, completed))
            operations.append("complete")
        }
    }

    private struct Fixture {
        let service: Service
        let manager: CalendarManager
        let key: Defaults.Key<CalendarSelectionState>
    }

    private let date = Date(timeIntervalSince1970: 1_789_220_700)

    private func calendar(_ id: String, reminder: Bool = false) -> CalendarModel {
        CalendarModel(id: id, account: "Synthetic account", title: id, color: .blue,
                      isSubscribed: false, isReminder: reminder)
    }

    private func fixture() throws -> Fixture {
        let name = "com.jdylanmc.notchpocket.tests.calendar.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: name))
        guard defaults.persistentDomain(forName: name) == nil else { throw FixtureError.occupiedDomain }
        addTeardownBlock {
            let owned = try XCTUnwrap(UserDefaults(suiteName: name))
            owned.removePersistentDomain(forName: name)
            XCTAssertTrue(owned.persistentDomain(forName: name)?.isEmpty ?? true)
        }
        let key = Defaults.Key<CalendarSelectionState>("calendarSelectionState", default: .all, suite: defaults)
        XCTAssertTrue(key.suite === defaults)
        XCTAssertFalse(key.suite === UserDefaults.standard)
        let service = Service()
        service.calendarValues = [calendar("a"), calendar("b"), calendar("reminders", reminder: true)]
        let manager = CalendarManager(service: service, selectionKey: key, initialDate: date)
        return Fixture(service: service, manager: manager, key: key)
    }

    private func event(in calendar: CalendarModel) -> EventModel {
        EventModel(id: "fixture-event-\(calendar.id)", start: date, end: date.addingTimeInterval(3_600),
                   title: "Synthetic event", location: nil, notes: nil, url: nil, isAllDay: false,
                   type: .event(.accepted), calendar: calendar, participants: [], timeZone: nil,
                   hasRecurrenceRules: false, priority: nil, meetingLink: nil)
    }

    private func drainMainQueue() async {
        await withCheckedContinuation { continuation in
            DispatchQueue.main.async { continuation.resume() }
        }
    }

    func testInjectedConstructionDoesNotStartProviderWork() throws {
        XCTAssertTrue(Defaults.Keys.calendarSelectionState.suite === UserDefaults.standard)
        let fixture = try fixture()
        XCTAssertEqual(fixture.service.calendarReads, 0)
        XCTAssertTrue(fixture.service.requests.isEmpty)
        XCTAssertTrue(fixture.service.queries.isEmpty)
        XCTAssertTrue(fixture.manager.allCalendars.isEmpty)
        XCTAssertEqual(fixture.manager.currentWeekStartDate, Calendar.current.startOfDay(for: date))
    }

    func testReloadPartitionsCalendarsAndRemindersWithAllSelection() async throws {
        let fixture = try fixture()

        await fixture.manager.reloadCalendarAndReminderLists()

        XCTAssertEqual(fixture.service.calendarReads, 1)
        XCTAssertEqual(fixture.manager.eventCalendars.map(\.id), ["a", "b"])
        XCTAssertEqual(fixture.manager.reminderLists.map(\.id), ["reminders"])
        XCTAssertEqual(fixture.manager.selectedCalendarIDs, ["a", "b", "reminders"])
        XCTAssertTrue(fixture.service.queries.isEmpty)
    }

    func testStoredSelectionScopesQueriesToItsOwnedPreferenceSuite() async throws {
        let fixture = try fixture()
        Defaults[fixture.key] = .selected(["b"])
        await fixture.manager.reloadCalendarAndReminderLists()
        let value = event(in: fixture.service.calendarValues[1])
        fixture.service.eventValues = [event(in: fixture.service.calendarValues[0]), value]

        await fixture.manager.updateCurrentDate(date)

        let query = try XCTUnwrap(fixture.service.queries.last)
        let start = Calendar.current.startOfDay(for: date)
        XCTAssertEqual(query.start, start)
        XCTAssertEqual(query.end, try XCTUnwrap(Calendar.current.date(byAdding: .day, value: 1, to: start)))
        XCTAssertEqual(query.calendarIDs, ["b"])
        XCTAssertEqual(fixture.manager.events, [value])
        XCTAssertFalse(fixture.manager.getCalendarSelected(fixture.service.calendarValues[0]))
    }

    func testSelectionWritesDoNotAffectAnotherFixtureSuite() async throws {
        let first = try fixture()
        let second = try fixture()
        Defaults[second.key] = .selected(["a"])
        await first.manager.reloadCalendarAndReminderLists()

        await first.manager.setCalendarSelected(first.service.calendarValues[0], isSelected: false)

        guard case .selected(let firstIDs) = Defaults[first.key],
              case .selected(let secondIDs) = Defaults[second.key] else {
            return XCTFail("Expected independent stored selections")
        }
        XCTAssertEqual(firstIDs, ["b", "reminders"])
        XCTAssertEqual(secondIDs, ["a"])
        XCTAssertEqual(first.service.queries.last?.calendarIDs, ["b", "reminders"])
    }

    func testRemovingTheLastExplicitSelectionPreservesExistingAllFallback() async throws {
        let fixture = try fixture()
        Defaults[fixture.key] = .selected(["a"])
        await fixture.manager.reloadCalendarAndReminderLists()

        await fixture.manager.setCalendarSelected(fixture.service.calendarValues[0], isSelected: false)

        guard case .all = Defaults[fixture.key] else { return XCTFail("Expected the existing all-calendars fallback") }
        XCTAssertEqual(fixture.manager.selectedCalendarIDs, ["a", "b", "reminders"])
        XCTAssertEqual(fixture.service.queries.last?.calendarIDs, ["a", "b", "reminders"])
    }

    func testImmediateCalendarGrantKeepsFinalStatusAfterQueuedWork() async throws {
        let fixture = try fixture()
        fixture.service.eventValues = [event(in: fixture.service.calendarValues[0])]

        await fixture.manager.checkCalendarAuthorization()
        await drainMainQueue()

        XCTAssertEqual(fixture.service.requests, [.event])
        XCTAssertEqual(fixture.manager.calendarAuthorizationStatus, .fullAccess)
        XCTAssertEqual(fixture.service.calendarReads, 1)
        XCTAssertEqual(fixture.manager.events, fixture.service.eventValues)
    }

    func testDeniedRestrictedAndWriteOnlyCalendarNeverRequestOrReadData() async throws {
        for status in [EKAuthorizationStatus.denied, .restricted, .writeOnly] {
            let fixture = try fixture()
            fixture.service.eventStatus = status

            await fixture.manager.checkCalendarAuthorization()
            await drainMainQueue()

            XCTAssertEqual(fixture.manager.calendarAuthorizationStatus, status)
            XCTAssertTrue(fixture.service.requests.isEmpty)
            XCTAssertEqual(fixture.service.calendarReads, 0)
            XCTAssertTrue(fixture.service.queries.isEmpty)
        }
    }

    func testCalendarRequestDenialOrErrorDoesNotBecomeAccessOrFetch() async throws {
        for result: Result<Bool, FixtureError> in [.success(false), .failure(.accessFailed)] {
            let fixture = try fixture()
            fixture.service.accessResult = result

            await fixture.manager.checkCalendarAuthorization()
            await drainMainQueue()

            switch result {
            case .success: XCTAssertEqual(fixture.manager.calendarAuthorizationStatus, .denied)
            case .failure: XCTAssertEqual(fixture.manager.calendarAuthorizationStatus, .notDetermined)
            }
            XCTAssertEqual(fixture.service.requests, [.event])
            XCTAssertEqual(fixture.service.calendarReads, 0)
            XCTAssertTrue(fixture.service.queries.isEmpty)
        }
    }

    func testExistingCalendarAccessFetchesWithoutRequestingAgain() async throws {
        let fixture = try fixture()
        fixture.service.eventStatus = .fullAccess

        await fixture.manager.checkCalendarAuthorization()

        XCTAssertTrue(fixture.service.requests.isEmpty)
        XCTAssertEqual(fixture.service.calendarReads, 1)
        XCTAssertEqual(fixture.service.queries.count, 1)
    }

    func testImmediateReminderGrantRetainsStatusWithoutFetchingEvents() async throws {
        let fixture = try fixture()

        await fixture.manager.checkReminderAuthorization()
        await drainMainQueue()

        XCTAssertEqual(fixture.service.requests, [.reminder])
        XCTAssertEqual(fixture.manager.reminderAuthorizationStatus, .fullAccess)
        XCTAssertEqual(fixture.service.calendarReads, 1)
        XCTAssertTrue(fixture.service.queries.isEmpty)
    }

    func testDeniedReminderAccessDoesNotRequestOrReload() async throws {
        let fixture = try fixture()
        fixture.service.reminderStatus = .denied

        await fixture.manager.checkReminderAuthorization()
        await drainMainQueue()

        XCTAssertEqual(fixture.manager.reminderAuthorizationStatus, .denied)
        XCTAssertTrue(fixture.service.requests.isEmpty)
        XCTAssertEqual(fixture.service.calendarReads, 0)
    }

    func testReminderRequestDenialOrErrorDoesNotBecomeAccessOrReload() async throws {
        for result: Result<Bool, FixtureError> in [.success(false), .failure(.accessFailed)] {
            let fixture = try fixture()
            fixture.service.accessResult = result

            await fixture.manager.checkReminderAuthorization()
            await drainMainQueue()

            switch result {
            case .success: XCTAssertEqual(fixture.manager.reminderAuthorizationStatus, .denied)
            case .failure: XCTAssertEqual(fixture.manager.reminderAuthorizationStatus, .notDetermined)
            }
            XCTAssertEqual(fixture.service.requests, [.reminder])
            XCTAssertEqual(fixture.service.calendarReads, 0)
            XCTAssertTrue(fixture.service.queries.isEmpty)
        }
    }

    func testExistingReminderAccessReloadsWithoutRequestingOrFetchingEvents() async throws {
        let fixture = try fixture()
        fixture.service.reminderStatus = .fullAccess

        await fixture.manager.checkReminderAuthorization()

        XCTAssertTrue(fixture.service.requests.isEmpty)
        XCTAssertEqual(fixture.service.calendarReads, 1)
        XCTAssertTrue(fixture.service.queries.isEmpty)
        XCTAssertEqual(fixture.manager.reminderLists.map(\.id), ["reminders"])
    }

    func testReminderCompletionReachesOnlyTheInjectedServiceThenRefreshes() async throws {
        let fixture = try fixture()
        await fixture.manager.reloadCalendarAndReminderLists()
        fixture.service.eventValues = [event(in: fixture.service.calendarValues[0])]

        await fixture.manager.setReminderCompleted(reminderID: "fixture-reminder", completed: true)

        XCTAssertEqual(fixture.service.completions.count, 1)
        XCTAssertEqual(fixture.service.completions.first?.0, "fixture-reminder")
        XCTAssertEqual(fixture.service.completions.first?.1, true)
        XCTAssertEqual(fixture.service.operations, ["complete", "events"])
        XCTAssertEqual(fixture.manager.events, fixture.service.eventValues)
    }

    func testFirstDateQueryResolvesStoredSelectionBeforeFetchingEvents() async throws {
        let fixture = try fixture()
        Defaults[fixture.key] = .selected(["b"])
        let expected = event(in: fixture.service.calendarValues[1])
        fixture.service.eventValues = [event(in: fixture.service.calendarValues[0]), expected]

        await fixture.manager.updateCurrentDate(date)

        XCTAssertEqual(fixture.service.calendarReads, 1)
        XCTAssertEqual(fixture.service.queries.last?.calendarIDs, ["b"])
        XCTAssertEqual(fixture.manager.events, [expected])
    }

    func testFirstSelectionChangeLoadsListsBeforeComputingDeselection() async throws {
        let fixture = try fixture()

        await fixture.manager.setCalendarSelected(fixture.service.calendarValues[0], isSelected: false)

        XCTAssertEqual(fixture.service.calendarReads, 1)
        XCTAssertEqual(fixture.manager.selectedCalendarIDs, ["b", "reminders"])
        XCTAssertEqual(fixture.service.queries.last?.calendarIDs, ["b", "reminders"])
    }

    func testUnavailableExplicitSelectionDoesNotBroadenToEveryCalendar() async throws {
        let fixture = try fixture()
        Defaults[fixture.key] = .selected(["removed-calendar"])
        fixture.service.eventValues = [event(in: fixture.service.calendarValues[0])]

        await fixture.manager.updateCurrentDate(date)

        XCTAssertEqual(fixture.manager.selectedCalendarIDs, ["removed-calendar"])
        XCTAssertTrue(fixture.service.queries.isEmpty)
        XCTAssertTrue(fixture.manager.events.isEmpty)
    }

    func testStaleSelectionIDsDoNotEnableUnselectedListsByMatchingCount() async throws {
        let fixture = try fixture()
        Defaults[fixture.key] = .selected(["a", "removed-calendar"])
        await fixture.manager.reloadCalendarAndReminderLists()

        await fixture.manager.setCalendarSelected(fixture.service.calendarValues[1], isSelected: true)

        guard case .selected(let identifiers) = Defaults[fixture.key] else {
            return XCTFail("Unknown IDs must not silently convert an explicit selection into all calendars")
        }
        XCTAssertEqual(identifiers, ["a", "b", "removed-calendar"])
        XCTAssertEqual(fixture.service.queries.last?.calendarIDs, ["a", "b"])
        XCTAssertFalse(fixture.manager.getCalendarSelected(fixture.service.calendarValues[2]))
    }
}
