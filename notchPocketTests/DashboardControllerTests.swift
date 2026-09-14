//
//  DashboardControllerTests.swift
//  notchPocketTests
//

import Foundation
import XCTest

@testable import notchPocket

@MainActor
final class DashboardControllerTests: XCTestCase {
    private final class MemoryDataStore: DashboardConfigurationDataStore {
        var data: Data?

        func read() throws -> Data? {
            data
        }

        func write(_ data: Data) throws {
            self.data = data
        }
    }

    private let ownerA = UUID(uuidString: "00000000-0000-0000-0000-00000000000A")!
    private let ownerB = UUID(uuidString: "00000000-0000-0000-0000-00000000000B")!

    func testMissingConfigurationPersistsStableSeedAcrossControllers() {
        let dataStore = MemoryDataStore()
        let store = DashboardConfigurationStore(dataStore: dataStore)
        let firstController = DashboardController(store: store)
        let firstConfiguration = firstController.committedConfiguration

        let secondController = DashboardController(store: store)

        XCTAssertNotNil(dataStore.data)
        let expectedLoadResult = firstConfiguration.map(DashboardConfigurationLoadResult.loaded)
        XCTAssertEqual(firstController.loadResult, expectedLoadResult)
        XCTAssertEqual(secondController.loadResult, expectedLoadResult)
        XCTAssertEqual(secondController.committedConfiguration, firstConfiguration)
        XCTAssertEqual(firstConfiguration?.revision, 0)
        XCTAssertEqual(firstConfiguration?.instances.count, 1)
    }

    func testOnlyOwnerSeesDraftAndCanCommitIt() {
        let controller = makeController()
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )

        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)
        XCTAssertEqual(controller.beginEditing(ownerID: ownerB), .failure(.editInProgress))
        XCTAssertEqual(controller.add(instance, ownerID: ownerA), .success)
        XCTAssertEqual(controller.configuration(for: ownerA)?.instances.count, 1)
        XCTAssertEqual(controller.configuration(for: ownerB)?.instances.count, 0)
        XCTAssertEqual(controller.done(ownerID: ownerB), .failure(.notEditOwner))

        XCTAssertEqual(controller.done(ownerID: ownerA), .success)
        XCTAssertEqual(controller.committedConfiguration?.revision, 1)
        XCTAssertEqual(controller.committedConfiguration?.instances, [instance])
        XCTAssertNil(controller.editSession)
    }

    func testCancelDiscardsOnlyDashboardDraft() {
        let controller = makeController()
        let featureState = FeatureState(value: 1)
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )

        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)
        XCTAssertEqual(controller.add(instance, ownerID: ownerA), .success)
        featureState.value = 2

        XCTAssertEqual(controller.cancel(ownerID: ownerA), .success)
        XCTAssertEqual(controller.committedConfiguration?.instances, [])
        XCTAssertEqual(featureState.value, 2)
    }

    func testSharedTabChangeDoesNotReleaseOwnerDraft() {
        let controller = makeController()
        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)

        controller.handleOwnerLifecycleEvent(.contentDidDisappear, ownerID: ownerA)

        XCTAssertEqual(controller.editSession?.ownerID, ownerA)
    }

    func testOwnerTeardownReleasesDraft() {
        let controller = makeController()
        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)

        controller.handleOwnerLifecycleEvent(.ownerDidTearDown, ownerID: ownerA)

        XCTAssertNil(controller.editSession)
        XCTAssertEqual(controller.beginEditing(ownerID: ownerB), .success)
    }

    func testInvalidMutationLeavesPriorDraftUnchanged() {
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let controller = makeController(instances: [instance])
        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)

        XCTAssertEqual(
            controller.move(
                instanceID: instance.id,
                to: .init(column: -1, row: 0),
                ownerID: ownerA
            ),
            .failure(.invalidConfiguration)
        )
        XCTAssertEqual(
            controller.configuration(for: ownerA)?.instances.first?.position,
            .init(column: 0, row: 0)
        )
    }

    func testSettingMutationPreservesUnrelatedSettings() {
        var instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        instance.settings["futureOption"] = .string("preserve")
        let controller = makeController(instances: [instance])
        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)

        XCTAssertEqual(
            controller.setSetting(
                .bool(false),
                forKey: "showsItemCount",
                instanceID: instance.id,
                ownerID: ownerA
            ),
            .success
        )

        let settings = controller.configuration(for: ownerA)?.instances.first?.settings
        XCTAssertEqual(settings?["showsItemCount"], .bool(false))
        XCTAssertEqual(settings?["futureOption"], .string("preserve"))
    }

    func testRevisionConflictPreservesNewerCommitAndOwnerDraft() throws {
        let dataStore = MemoryDataStore()
        let store = DashboardConfigurationStore(dataStore: dataStore)
        let controller = makeController(store: store)
        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)
        let draftInstance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        XCTAssertEqual(controller.add(draftInstance, ownerID: ownerA), .success)

        let externalInstance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 1, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        let external = try store.save(
            DashboardConfiguration(revision: 0, instances: [externalInstance]),
            expectedRevision: 0
        )

        XCTAssertEqual(
            controller.done(ownerID: ownerA),
            .failure(.revisionConflict(expected: 0, actual: 1))
        )
        XCTAssertEqual(controller.editSession?.draft.instances, [draftInstance])
        XCTAssertEqual(controller.editSession?.baseRevision, 0)
        XCTAssertEqual(controller.committedConfiguration, external)
        guard case .loaded(let stored) = store.load() else {
            return XCTFail("Expected external commit")
        }
        XCTAssertEqual(stored, external)
    }

    func testRecoveryRequiredStateCannotStartEditing() {
        let dataStore = MemoryDataStore()
        dataStore.data = Data(#"{"schemaVersion":99,"revision":1,"instances":[]}"#.utf8)
        let controller = DashboardController(
            store: DashboardConfigurationStore(dataStore: dataStore)
        )

        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .failure(.recoveryRequired))
        XCTAssertNil(controller.committedConfiguration)
    }

    func testBackendRecoveryDuringDonePublishesStateAndBlocksFurtherEditing() {
        let dataStore = MemoryDataStore()
        let controller = makeController(
            store: DashboardConfigurationStore(dataStore: dataStore)
        )
        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        XCTAssertEqual(controller.add(instance, ownerID: ownerA), .success)
        let futureData = Data(#"{"schemaVersion":99,"revision":1,"instances":[]}"#.utf8)
        dataStore.data = futureData

        XCTAssertEqual(controller.done(ownerID: ownerA), .failure(.recoveryRequired))
        XCTAssertEqual(
            controller.loadResult,
            .recoveryRequired(futureData, .unsupportedSchema(99))
        )
        XCTAssertNil(controller.committedConfiguration)
        XCTAssertEqual(controller.editSession?.draft.instances, [instance])
        XCTAssertEqual(
            controller.move(
                instanceID: instance.id,
                to: .init(column: 1, row: 0),
                ownerID: ownerA
            ),
            .failure(.recoveryRequired)
        )
        XCTAssertEqual(controller.cancel(ownerID: ownerA), .success)
        XCTAssertEqual(controller.beginEditing(ownerID: ownerB), .failure(.recoveryRequired))
        XCTAssertEqual(dataStore.data, futureData)
    }

    func testRevisionExhaustionPreservesOwnerDraftAndStoredBytes() {
        let source = Data(
            """
            {
              "schemaVersion": 1,
              "revision": 18446744073709551615,
              "instances": []
            }
            """.utf8
        )
        let dataStore = MemoryDataStore()
        dataStore.data = source
        let controller = DashboardController(
            store: DashboardConfigurationStore(dataStore: dataStore)
        )
        XCTAssertEqual(controller.beginEditing(ownerID: ownerA), .success)
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: 0),
            footprint: .init(columns: 1, rows: 1)
        )
        XCTAssertEqual(controller.add(instance, ownerID: ownerA), .success)

        XCTAssertEqual(controller.done(ownerID: ownerA), .failure(.revisionExhausted))
        XCTAssertEqual(controller.editSession?.draft.instances, [instance])
        XCTAssertEqual(controller.editSession?.baseRevision, UInt64.max)
        XCTAssertEqual(dataStore.data, source)
    }

    private func makeController(
        store: DashboardConfigurationStore? = nil,
        instances: [DashboardWidgetInstance] = []
    ) -> DashboardController {
        DashboardController(
            store: store ?? DashboardConfigurationStore(dataStore: MemoryDataStore()),
            seed: DashboardConfiguration(revision: 0, instances: instances)
        )
    }
}

private final class FeatureState {
    var value: Int

    init(value: Int) {
        self.value = value
    }
}
