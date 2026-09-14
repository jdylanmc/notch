//
//  DashboardConfigurationTests.swift
//  notchPocketTests
//

import Foundation
import XCTest

@testable import notchPocket

final class DashboardConfigurationTests: XCTestCase {
    private final class MemoryDataStore: DashboardConfigurationDataStore {
        private let lock = NSLock()
        private var storedData: Data?

        var data: Data? {
            get { lock.withLock { storedData } }
            set { lock.withLock { storedData = newValue } }
        }

        init(data: Data? = nil) {
            storedData = data
        }

        func read() throws -> Data? {
            lock.withLock { storedData }
        }

        func write(_ data: Data) throws {
            lock.withLock { storedData = data }
        }
    }

    func testMissingConfigurationIsReportedExplicitly() {
        let store = DashboardConfigurationStore(dataStore: MemoryDataStore())

        XCTAssertEqual(store.load(), .missing)
    }

    func testWidgetKindUsesSingleStringPersistenceRepresentation() throws {
        let configuration = DashboardConfiguration(
            revision: 0,
            instances: [
                .shelfSummary(
                    position: .init(column: 0, row: 0),
                    footprint: .init(columns: 1, rows: 1)
                )
            ]
        )

        let encoded = try JSONEncoder().encode(configuration)
        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: encoded) as? [String: Any]
        )
        let instances = try XCTUnwrap(object["instances"] as? [[String: Any]])
        XCTAssertEqual(instances.first?["kind"] as? String, "shelfSummary")

        let futureKind = try JSONDecoder().decode(
            DashboardWidgetKind.self,
            from: Data(#""futureWidget""#.utf8)
        )
        XCTAssertEqual(futureKind.rawValue, "futureWidget")
    }

    func testSaveAdvancesRevisionAndRejectsStaleWriter() throws {
        let dataStore = MemoryDataStore()
        let store = DashboardConfigurationStore(dataStore: dataStore)
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let draft = DashboardConfiguration(revision: 0, instances: [instance])

        let committed = try store.save(draft, expectedRevision: 0)

        XCTAssertEqual(committed.revision, 1)
        XCTAssertEqual(store.load(), .loaded(committed))
        XCTAssertThrowsError(try store.save(draft, expectedRevision: 0)) { error in
            XCTAssertEqual(
                error as? DashboardConfigurationStoreError,
                .revisionConflict(expected: 0, actual: 1)
            )
        }
    }

    func testFutureAndMalformedDataRequireRecoveryWithoutChangingSourceBytes() {
        let futureData = Data(
            #"{"schemaVersion":99,"revision":4,"instances":[]}"#.utf8
        )
        let futureStore = DashboardConfigurationStore(
            dataStore: MemoryDataStore(data: futureData)
        )

        guard case .recoveryRequired(let preservedFuture, .unsupportedSchema(99)) = futureStore.load()
        else {
            return XCTFail("Expected unsupported future schema")
        }
        XCTAssertEqual(preservedFuture, futureData)

        let malformedData = Data(#"{"schemaVersion":"broken"}"#.utf8)
        let malformedStore = DashboardConfigurationStore(
            dataStore: MemoryDataStore(data: malformedData)
        )

        guard case .recoveryRequired(let preservedMalformed, .malformed) = malformedStore.load()
        else {
            return XCTFail("Expected malformed-data recovery state")
        }
        XCTAssertEqual(preservedMalformed, malformedData)
    }

    func testUpdatingKnownShelfSettingPreservesUnknownSettings() throws {
        let source = Data(
            """
            {
              "schemaVersion": 1,
              "revision": 7,
              "instances": [
                {
                  "id": "00000000-0000-0000-0000-000000000001",
                  "kind": "shelfSummary",
                  "position": {"column": 0, "row": 0},
                  "footprint": {"columns": 1, "rows": 1},
                  "settings": {
                    "showsItemCount": true,
                    "futureOption": {"mode": "dense", "limit": 3}
                  }
                }
              ]
            }
            """.utf8
        )
        let dataStore = MemoryDataStore(data: source)
        let store = DashboardConfigurationStore(dataStore: dataStore)
        guard case .loaded(var configuration) = store.load() else {
            return XCTFail("Expected supported configuration")
        }

        configuration.instances[0].setShelfSummarySettings(
            .init(showsItemCount: false)
        )
        _ = try store.save(configuration, expectedRevision: 7)

        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: try XCTUnwrap(dataStore.data)) as? [String: Any]
        )
        let instances = try XCTUnwrap(object["instances"] as? [[String: Any]])
        let settings = try XCTUnwrap(instances.first?["settings"] as? [String: Any])
        XCTAssertEqual(settings["showsItemCount"] as? Bool, false)
        let futureOption = try XCTUnwrap(settings["futureOption"] as? [String: Any])
        XCTAssertEqual(futureOption["mode"] as? String, "dense")
        XCTAssertEqual(futureOption["limit"] as? Int, 3)
    }

    func testUnknownWidgetPayloadSurvivesSupportedSchemaRoundTrip() throws {
        let source = Data(
            """
            {
              "schemaVersion": 1,
              "revision": 2,
              "instances": [
                {
                  "id": "00000000-0000-0000-0000-000000000001",
                  "kind": "futureWidget",
                  "position": {"column": 1, "row": 2},
                  "footprint": {"columns": 2, "rows": 1},
                  "settings": {"theme": "violet"},
                  "payload": {"provider": "future", "options": [1, 2, 3]}
                }
              ]
            }
            """.utf8
        )
        let dataStore = MemoryDataStore(data: source)
        let store = DashboardConfigurationStore(dataStore: dataStore)
        guard case .loaded(let configuration) = store.load() else {
            return XCTFail("Expected supported configuration")
        }

        _ = try store.save(configuration, expectedRevision: 2)

        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: try XCTUnwrap(dataStore.data)) as? [String: Any]
        )
        let instances = try XCTUnwrap(object["instances"] as? [[String: Any]])
        let payload = try XCTUnwrap(instances.first?["payload"] as? [String: Any])
        XCTAssertEqual(payload["provider"] as? String, "future")
        XCTAssertEqual(payload["options"] as? [Int], [1, 2, 3])
    }

    func testLargeUnknownIntegersSurviveNestedSettingsAndPayloadRoundTrip() throws {
        let source = Data(
            """
            {
              "schemaVersion": 1,
              "revision": 4,
              "instances": [
                {
                  "id": "00000000-0000-0000-0000-000000000001",
                  "kind": "futureWidget",
                  "position": {"column": 0, "row": 0},
                  "footprint": {"columns": 1, "rows": 1},
                  "settings": {
                    "nested": {"remoteID": 9007199254740993}
                  },
                  "payload": {
                    "maximumID": 18446744073709551615
                  }
                }
              ]
            }
            """.utf8
        )
        let dataStore = MemoryDataStore(data: source)
        let store = DashboardConfigurationStore(dataStore: dataStore)
        guard case .loaded(let configuration) = store.load() else {
            return XCTFail("Expected supported integer payload")
        }

        _ = try store.save(configuration, expectedRevision: 4)

        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: try XCTUnwrap(dataStore.data)) as? [String: Any]
        )
        let instance = try XCTUnwrap((object["instances"] as? [[String: Any]])?.first)
        let settings = try XCTUnwrap(instance["settings"] as? [String: Any])
        let nested = try XCTUnwrap(settings["nested"] as? [String: Any])
        let payload = try XCTUnwrap(instance["payload"] as? [String: Any])
        XCTAssertEqual((nested["remoteID"] as? NSNumber)?.stringValue, "9007199254740993")
        XCTAssertEqual((payload["maximumID"] as? NSNumber)?.stringValue, "18446744073709551615")
    }

    func testUnsupportedUnknownNumberRequiresRecoveryWithOriginalBytes() {
        let source = Data(
            """
            {
              "schemaVersion": 1,
              "revision": 1,
              "instances": [
                {
                  "id": "00000000-0000-0000-0000-000000000001",
                  "kind": "futureWidget",
                  "position": {"column": 0, "row": 0},
                  "footprint": {"columns": 1, "rows": 1},
                  "settings": {"unsupported": 1e9999}
                }
              ]
            }
            """.utf8
        )
        let store = DashboardConfigurationStore(dataStore: MemoryDataStore(data: source))

        guard case .recoveryRequired(let preserved, .malformed) = store.load() else {
            return XCTFail("Expected unsupported numeric value to require recovery")
        }
        XCTAssertEqual(preserved, source)
    }

    func testDuplicateIDsRequireRecoveryAndCannotBeSaved() {
        let duplicateID = "00000000-0000-0000-0000-000000000001"
        let source = duplicateConfigurationData(id: duplicateID)
        let existingDataStore = MemoryDataStore(data: source)
        let existingStore = DashboardConfigurationStore(dataStore: existingDataStore)
        guard case .recoveryRequired(let preserved, .duplicateInstanceIDs) = existingStore.load()
        else {
            return XCTFail("Expected duplicate IDs to require recovery")
        }

        XCTAssertEqual(preserved, source)
        XCTAssertThrowsError(
            try existingStore.save(
                DashboardConfiguration(revision: 3, instances: []),
                expectedRevision: 3
            )
        ) { error in
            XCTAssertEqual(
                error as? DashboardConfigurationStoreError,
                .recoveryRequired(source, .duplicateInstanceIDs)
            )
        }
        XCTAssertEqual(existingDataStore.data, source)

        let duplicateInstance = DashboardWidgetInstance.shelfSummary(
            id: UUID(uuidString: duplicateID)!,
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let missingDataStore = MemoryDataStore()
        let missingStore = DashboardConfigurationStore(dataStore: missingDataStore)
        XCTAssertThrowsError(
            try missingStore.save(
                DashboardConfiguration(
                    revision: 0,
                    instances: [duplicateInstance, duplicateInstance]
                ),
                expectedRevision: 0
            )
        ) { error in
            XCTAssertEqual(
                error as? DashboardConfigurationStoreError,
                .invalidConfiguration(.duplicateInstanceIDs)
            )
        }
        XCTAssertNil(missingDataStore.data)
    }

    private func duplicateConfigurationData(id: String) -> Data {
        Data(
            """
            {
              "schemaVersion": 1,
              "revision": 3,
              "instances": [
                {
                  "id": "\(id)",
                  "kind": "shelfSummary",
                  "position": {"column": 0, "row": 0},
                  "footprint": {"columns": 1, "rows": 1},
                  "settings": {}
                },
                {
                  "id": "\(id)",
                  "kind": "shelfSummary",
                  "position": {"column": 1, "row": 0},
                  "footprint": {"columns": 1, "rows": 1},
                  "settings": {}
                }
              ]
            }
            """.utf8
        )
    }

    func testRevisionExhaustionPreservesStoredBytes() throws {
        let source = Data(
            """
            {
              "schemaVersion": 1,
              "revision": 18446744073709551615,
              "instances": []
            }
            """.utf8
        )
        let dataStore = MemoryDataStore(data: source)
        let store = DashboardConfigurationStore(dataStore: dataStore)
        guard case .loaded(let configuration) = store.load() else {
            return XCTFail("Expected maximum revision to load")
        }

        XCTAssertThrowsError(
            try store.save(configuration, expectedRevision: UInt64.max)
        ) { error in
            XCTAssertEqual(error as? DashboardConfigurationStoreError, .revisionExhausted)
        }
        XCTAssertEqual(dataStore.data, source)
    }

    func testConcurrentStoresProduceOneCommitAndOneConflict() {
        let dataStore = InterleavingDataStore()
        let stores = [
            DashboardConfigurationStore(dataStore: dataStore),
            DashboardConfigurationStore(dataStore: dataStore)
        ]
        let results = LockedResults()
        let firstRead = dataStore.firstRead
        let releaseFirstRead = dataStore.releaseFirstRead
        let secondRead = dataStore.secondRead
        let secondWorkerStarted = DispatchSemaphore(value: 0)
        let group = DispatchGroup()
        let queue = DispatchQueue(label: "DashboardConfigurationTests.concurrent", attributes: .concurrent)
        let firstDraft = concurrencyDraft(
            id: "00000000-0000-0000-0000-000000000001",
            column: 0
        )
        let secondDraft = concurrencyDraft(
            id: "00000000-0000-0000-0000-000000000002",
            column: 1
        )

        group.enter()
        queue.async {
            defer { group.leave() }
            results.append(Result {
                try stores[0].save(firstDraft, expectedRevision: 0)
            })
        }
        XCTAssertEqual(firstRead.wait(timeout: .now() + 2), .success)

        group.enter()
        queue.async {
            secondWorkerStarted.signal()
            defer { group.leave() }
            results.append(Result {
                try stores[1].save(secondDraft, expectedRevision: 0)
            })
        }
        XCTAssertEqual(secondWorkerStarted.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(secondRead.wait(timeout: .now() + 0.5), .timedOut)
        releaseFirstRead.signal()
        XCTAssertEqual(group.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(secondRead.wait(timeout: .now() + 2), .success)

        let values = results.values
        let successfulConfigurations = values.compactMap(\.successValue)
        XCTAssertEqual(successfulConfigurations.count, 1)
        XCTAssertEqual(values.filter(\.isRevisionConflict).count, 1)
        guard case .loaded(let persisted) = stores[0].load() else {
            return XCTFail("Expected winning commit")
        }
        XCTAssertEqual(persisted.revision, 1)
        XCTAssertEqual(persisted.instances, successfulConfigurations.first?.instances)
        XCTAssertTrue(
            persisted.instances == firstDraft.instances
                || persisted.instances == secondDraft.instances
        )
    }

    private func concurrencyDraft(id: String, column: Int) -> DashboardConfiguration {
        DashboardConfiguration(
            revision: 0,
            instances: [
                .shelfSummary(
                    id: UUID(uuidString: id)!,
                    position: .init(column: column, row: 0),
                    footprint: .init(columns: 1, rows: 1)
                )
            ]
        )
    }
}

private final class InterleavingDataStore: DashboardConfigurationDataStore {
    let firstRead = DispatchSemaphore(value: 0)
    let releaseFirstRead = DispatchSemaphore(value: 0)
    let secondRead = DispatchSemaphore(value: 0)

    private let lock = NSLock()
    private var readCount = 0
    private var data: Data?

    func read() throws -> Data? {
        let (snapshot, readOrdinal) = lock.withLock {
            readCount += 1
            return (data, readCount)
        }
        if readOrdinal == 1 {
            firstRead.signal()
            _ = releaseFirstRead.wait(timeout: .now() + 2)
        } else if readOrdinal == 2 {
            secondRead.signal()
        }
        return snapshot
    }

    func write(_ data: Data) throws {
        lock.withLock { self.data = data }
    }
}

private final class LockedResults {
    private let lock = NSLock()
    private(set) var stored: [Result<DashboardConfiguration, Error>] = []

    var values: [Result<DashboardConfiguration, Error>] {
        lock.withLock { stored }
    }

    func append(_ result: Result<DashboardConfiguration, Error>) {
        lock.withLock { stored.append(result) }
    }
}

private extension Result where Success == DashboardConfiguration, Failure == Error {
    var successValue: DashboardConfiguration? {
        guard case .success(let configuration) = self else { return nil }
        return configuration
    }

    var isSuccess: Bool {
        if case .success = self { return true }
        return false
    }

    var isRevisionConflict: Bool {
        guard case .failure(let error) = self,
              case .revisionConflict = error as? DashboardConfigurationStoreError
        else {
            return false
        }
        return true
    }
}
