import Defaults
import Foundation
import XCTest

@testable import notchPocket

@MainActor
final class DashboardDefaultsIsolationTests: XCTestCase {
    private enum FixtureError: Error {
        case preexistingDomain
    }

    @MainActor
    private struct Fixture {
        let name: String
        let defaults: UserDefaults

        func store() -> DashboardConfigurationStore {
            let key = Defaults.Key<Data?>("dashboardConfigurationData", default: nil, suite: defaults)
            XCTAssertTrue(key.suite === defaults)
            XCTAssertFalse(key.suite === UserDefaults.standard)
            return DashboardConfigurationStore(dataStore: DefaultsDashboardConfigurationDataStore(
                key: key
            ))
        }

        func controller() -> DashboardController {
            DashboardController(store: store(), seed: .init(revision: 0, instances: []))
        }
    }

    private func fixture() throws -> Fixture {
        let name = "com.jdylanmc.notchpocket.tests.dashboard.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: name))
        guard defaults.persistentDomain(forName: name) == nil else {
            throw FixtureError.preexistingDomain
        }
        addTeardownBlock {
            let ownedDefaults = try XCTUnwrap(UserDefaults(suiteName: name))
            ownedDefaults.removePersistentDomain(forName: name)
            XCTAssertNil(ownedDefaults.persistentDomain(forName: name))
        }
        return Fixture(name: name, defaults: defaults)
    }

    private func instance(column: Int = 0) -> DashboardWidgetInstance {
        .shelfSummary(position: .init(column: column, row: 0), footprint: .init(columns: 1, rows: 1))
    }

    func testIndependentSuitesKeepTheSameProductionKeyIsolated() throws {
        XCTAssertEqual(Defaults.Keys.dashboardConfigurationData.name, "dashboardConfigurationData")
        XCTAssertTrue(Defaults.Keys.dashboardConfigurationData.suite === UserDefaults.standard)
        let first = try fixture()
        let second = try fixture()
        let stored = Data(#"{"schemaVersion":99,"revision":1,"instances":[]}"#.utf8)
        second.defaults.set(stored, forKey: "dashboardConfigurationData")

        let controller = first.controller()

        XCTAssertEqual(controller.committedConfiguration, .init(revision: 0, instances: []))
        XCTAssertNotNil(first.defaults.data(forKey: "dashboardConfigurationData"))
        XCTAssertEqual(second.defaults.data(forKey: "dashboardConfigurationData"), stored)
    }

    func testDonePersistsCommittedFieldsForAReconstructedController() throws {
        let fixture = try fixture()
        let controller = fixture.controller()
        let owner = UUID()
        let widget = instance(column: 2)
        XCTAssertEqual(controller.beginEditing(ownerID: owner), .success)
        XCTAssertEqual(controller.add(widget, ownerID: owner), .success)
        XCTAssertEqual(controller.setSetting(.bool(false), forKey: "showsItemCount",
                                             instanceID: widget.id, ownerID: owner), .success)

        XCTAssertEqual(controller.done(ownerID: owner), .success)

        let bytes = try XCTUnwrap(fixture.defaults.data(forKey: "dashboardConfigurationData"))
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: bytes) as? [String: Any])
        let storedWidget = try XCTUnwrap((object["instances"] as? [[String: Any]])?.first)
        XCTAssertEqual(object["revision"] as? Int, 1)
        XCTAssertEqual(storedWidget["id"] as? String, widget.id.uuidString)
        XCTAssertEqual((storedWidget["position"] as? [String: Int])?["column"], 2)
        XCTAssertEqual((storedWidget["settings"] as? [String: Bool])?["showsItemCount"], false)

        let reader = Fixture(name: fixture.name, defaults: try XCTUnwrap(UserDefaults(suiteName: fixture.name)))
        let reconstructed = reader.controller()
        XCTAssertEqual(reconstructed.committedConfiguration?.revision, 1)
        XCTAssertEqual(reconstructed.committedConfiguration?.instances.first?.id, widget.id)
        XCTAssertEqual(reconstructed.committedConfiguration?.instances.first?.shelfSummarySettings?.showsItemCount, false)
        XCTAssertNil(reconstructed.editSession)
    }

    func testCancelPreservesExactStoredBytesAndUnrelatedFixturePreferences() throws {
        let fixture = try fixture()
        let controller = fixture.controller()
        let before = try XCTUnwrap(fixture.defaults.data(forKey: "dashboardConfigurationData"))
        fixture.defaults.set("fixture-only", forKey: "sentinel")
        let owner = UUID()
        XCTAssertEqual(controller.beginEditing(ownerID: owner), .success)
        XCTAssertEqual(controller.add(instance(), ownerID: owner), .success)
        XCTAssertEqual(fixture.defaults.data(forKey: "dashboardConfigurationData"), before)

        XCTAssertEqual(controller.cancel(ownerID: owner), .success)

        XCTAssertEqual(fixture.defaults.data(forKey: "dashboardConfigurationData"), before)
        XCTAssertEqual(fixture.defaults.string(forKey: "sentinel"), "fixture-only")
        XCTAssertEqual(fixture.controller().committedConfiguration?.instances, [])
    }

    func testFutureAndMalformedFixtureBytesAreNeverSeededOrOverwritten() throws {
        for (text, reason) in [
            (#"{"schemaVersion":99,"revision":4,"instances":[]}"#, DashboardConfigurationRecoveryError.unsupportedSchema(99)),
            (#"{"schemaVersion":"broken"}"#, .malformed)
        ] {
            let fixture = try fixture()
            let bytes = Data(text.utf8)
            fixture.defaults.set(bytes, forKey: "dashboardConfigurationData")
            let controller = fixture.controller()

            XCTAssertEqual(controller.loadResult, .recoveryRequired(bytes, reason))
            XCTAssertEqual(controller.beginEditing(ownerID: UUID()), .failure(.recoveryRequired))
            XCTAssertThrowsError(try fixture.store().save(.init(revision: 4, instances: []), expectedRevision: 4)) { error in
                XCTAssertEqual(error as? DashboardConfigurationStoreError, .recoveryRequired(bytes, reason))
            }
            XCTAssertEqual(fixture.defaults.data(forKey: "dashboardConfigurationData"), bytes)
        }
    }

    func testDefaultSeedKeepsItsIdentityAcrossIndependentDefaultsStores() throws {
        let fixture = try fixture()
        let first = DashboardController(store: fixture.store())
        let originalID = try XCTUnwrap(first.committedConfiguration?.instances.first?.id)
        let before = try XCTUnwrap(fixture.defaults.data(forKey: "dashboardConfigurationData"))
        let reader = Fixture(name: fixture.name, defaults: try XCTUnwrap(UserDefaults(suiteName: fixture.name)))

        let reconstructed = DashboardController(store: reader.store())

        XCTAssertEqual(reconstructed.committedConfiguration?.instances.first?.id, originalID)
        XCTAssertEqual(reader.defaults.data(forKey: "dashboardConfigurationData"), before)
    }

    func testStaleControllerCannotOverwriteAnotherControllerCommitInTheSameSuite() throws {
        let fixture = try fixture()
        let first = fixture.controller()
        let stale = fixture.controller()
        let firstOwner = UUID()
        let staleOwner = UUID()
        let savedWidget = instance()
        let staleWidget = instance(column: 1)
        XCTAssertEqual(first.beginEditing(ownerID: firstOwner), .success)
        XCTAssertEqual(stale.beginEditing(ownerID: staleOwner), .success)
        XCTAssertEqual(first.add(savedWidget, ownerID: firstOwner), .success)
        XCTAssertEqual(stale.add(staleWidget, ownerID: staleOwner), .success)
        XCTAssertEqual(first.done(ownerID: firstOwner), .success)
        let saved = try XCTUnwrap(fixture.defaults.data(forKey: "dashboardConfigurationData"))

        XCTAssertEqual(stale.done(ownerID: staleOwner), .failure(.revisionConflict(expected: 0, actual: 1)))

        XCTAssertEqual(stale.editSession?.draft.instances, [staleWidget])
        XCTAssertEqual(fixture.defaults.data(forKey: "dashboardConfigurationData"), saved)
        XCTAssertEqual(fixture.controller().committedConfiguration?.instances, [savedWidget])
    }

    func testOwnerTeardownDiscardsOnlyDraftAndPreservesStoredConfiguration() throws {
        let fixture = try fixture()
        let controller = fixture.controller()
        let stored = try XCTUnwrap(fixture.defaults.data(forKey: "dashboardConfigurationData"))
        let owner = UUID()
        XCTAssertEqual(controller.beginEditing(ownerID: owner), .success)
        XCTAssertEqual(controller.add(instance(), ownerID: owner), .success)

        controller.handleOwnerLifecycleEvent(.ownerDidTearDown, ownerID: owner)

        XCTAssertNil(controller.editSession)
        XCTAssertEqual(fixture.defaults.data(forKey: "dashboardConfigurationData"), stored)
        XCTAssertEqual(controller.beginEditing(ownerID: UUID()), .success)
    }
}
