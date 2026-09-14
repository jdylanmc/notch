//
//  DashboardController.swift
//  notchPocket
//

import Combine
import Foundation

struct DashboardEditSession: Equatable {
    let ownerID: UUID
    let baseRevision: UInt64
    var draft: DashboardConfiguration
}

enum DashboardEditError: Error, Equatable {
    case editInProgress
    case notEditOwner
    case recoveryRequired
    case configurationUnavailable
    case instanceNotFound
    case invalidConfiguration
    case revisionConflict(expected: UInt64, actual: UInt64)
    case revisionExhausted
    case persistenceFailure(String)
}

enum DashboardEditResult: Equatable {
    case success
    case failure(DashboardEditError)
}

@MainActor
final class DashboardController: ObservableObject {
    @Published private(set) var committedConfiguration: DashboardConfiguration?
    @Published private(set) var editSession: DashboardEditSession?
    @Published private(set) var loadResult: DashboardConfigurationLoadResult

    private let store: DashboardConfigurationStore

    init(
        store: DashboardConfigurationStore,
        seed: DashboardConfiguration = DashboardConfiguration(
            revision: 0,
            instances: [
                .shelfSummary(
                    position: .init(column: 0, row: 0),
                    footprint: .init(columns: 1, rows: 1)
                )
            ]
        )
    ) {
        self.store = store
        let result = store.loadOrSeed(seed)
        loadResult = result
        switch result {
        case .missing:
            committedConfiguration = nil
        case .loaded(let configuration):
            committedConfiguration = configuration
        case .recoveryRequired, .storageFailure:
            committedConfiguration = nil
        }
    }

    func configuration(for ownerID: UUID) -> DashboardConfiguration? {
        if editSession?.ownerID == ownerID {
            return editSession?.draft
        }
        return committedConfiguration
    }

    func beginEditing(ownerID: UUID) -> DashboardEditResult {
        if case .recoveryRequired = loadResult {
            return .failure(.recoveryRequired)
        }
        guard committedConfiguration != nil else {
            return .failure(.configurationUnavailable)
        }
        guard editSession == nil else {
            return editSession?.ownerID == ownerID ? .success : .failure(.editInProgress)
        }
        guard let committedConfiguration else {
            return .failure(.configurationUnavailable)
        }
        editSession = DashboardEditSession(
            ownerID: ownerID,
            baseRevision: committedConfiguration.revision,
            draft: committedConfiguration
        )
        return .success
    }

    func add(_ instance: DashboardWidgetInstance, ownerID: UUID) -> DashboardEditResult {
        mutate(ownerID: ownerID) { configuration in
            configuration.instances.append(instance)
            return true
        }
    }

    func remove(instanceID: UUID, ownerID: UUID) -> DashboardEditResult {
        mutate(ownerID: ownerID) { configuration in
            guard let index = configuration.instances.firstIndex(where: { $0.id == instanceID }) else {
                return false
            }
            configuration.instances.remove(at: index)
            return true
        }
    }

    func move(
        instanceID: UUID,
        to position: DashboardGridPosition,
        ownerID: UUID
    ) -> DashboardEditResult {
        mutate(ownerID: ownerID) { configuration in
            guard let index = configuration.instances.firstIndex(where: { $0.id == instanceID }) else {
                return false
            }
            configuration.instances[index].position = position
            return true
        }
    }

    func resize(
        instanceID: UUID,
        to footprint: DashboardGridFootprint,
        ownerID: UUID
    ) -> DashboardEditResult {
        mutate(ownerID: ownerID) { configuration in
            guard let index = configuration.instances.firstIndex(where: { $0.id == instanceID }) else {
                return false
            }
            configuration.instances[index].footprint = footprint
            return true
        }
    }

    func setSetting(
        _ value: JSONValue?,
        forKey key: String,
        instanceID: UUID,
        ownerID: UUID
    ) -> DashboardEditResult {
        mutate(ownerID: ownerID) { configuration in
            guard let index = configuration.instances.firstIndex(where: { $0.id == instanceID }) else {
                return false
            }
            configuration.instances[index].settings[key] = value
            return true
        }
    }

    func cancel(ownerID: UUID) -> DashboardEditResult {
        guard let editSession else {
            return .failure(.notEditOwner)
        }
        guard editSession.ownerID == ownerID else {
            return .failure(.notEditOwner)
        }
        self.editSession = nil
        return .success
    }

    func done(ownerID: UUID) -> DashboardEditResult {
        guard let editSession, editSession.ownerID == ownerID else {
            return .failure(.notEditOwner)
        }
        guard Self.isValid(editSession.draft) else {
            return .failure(.invalidConfiguration)
        }

        do {
            let committed = try store.save(
                editSession.draft,
                expectedRevision: editSession.baseRevision
            )
            committedConfiguration = committed
            loadResult = .loaded(committed)
            self.editSession = nil
            return .success
        } catch let error as DashboardConfigurationStoreError {
            switch error {
            case .revisionConflict(let expected, let actual):
                let latest = store.load()
                loadResult = latest
                if case .loaded(let configuration) = latest {
                    committedConfiguration = configuration
                }
                return .failure(.revisionConflict(expected: expected, actual: actual))
            case .revisionExhausted:
                return .failure(.revisionExhausted)
            case .invalidConfiguration:
                return .failure(.invalidConfiguration)
            case .recoveryRequired(let data, let recoveryError):
                loadResult = .recoveryRequired(data, recoveryError)
                committedConfiguration = nil
                return .failure(.recoveryRequired)
            case .storageFailure(let message):
                return .failure(.persistenceFailure(message))
            }
        } catch {
            return .failure(.persistenceFailure(error.localizedDescription))
        }
    }

    func ownerDidDisappear(ownerID: UUID) {
        if editSession?.ownerID == ownerID {
            editSession = nil
        }
    }

    private func mutate(
        ownerID: UUID,
        mutation: (inout DashboardConfiguration) -> Bool
    ) -> DashboardEditResult {
        if case .recoveryRequired = loadResult {
            return .failure(.recoveryRequired)
        }
        guard var session = editSession, session.ownerID == ownerID else {
            return .failure(.notEditOwner)
        }
        var candidate = session.draft
        guard mutation(&candidate) else {
            return .failure(.instanceNotFound)
        }
        guard Self.isValid(candidate) else {
            return .failure(.invalidConfiguration)
        }
        session.draft = candidate
        editSession = session
        return .success
    }

    private static func isValid(_ configuration: DashboardConfiguration) -> Bool {
        let ids = configuration.instances.map(\.id)
        guard ids.count == Set(ids).count else { return false }
        return configuration.instances.allSatisfy {
            $0.position.column >= 0
                && $0.position.row >= 0
                && $0.footprint.columns > 0
                && $0.footprint.rows > 0
        }
    }
}
