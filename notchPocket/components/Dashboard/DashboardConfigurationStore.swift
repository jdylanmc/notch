//
//  DashboardConfigurationStore.swift
//  notchPocket
//

import Foundation

protocol DashboardConfigurationDataStore {
    func read() throws -> Data?
    func write(_ data: Data) throws
}

enum DashboardConfigurationRecoveryError: Error, Equatable {
    case unsupportedSchema(Int)
    case malformed
    case duplicateInstanceIDs
}

enum DashboardConfigurationLoadResult: Equatable {
    case missing
    case loaded(DashboardConfiguration)
    case recoveryRequired(Data, DashboardConfigurationRecoveryError)
    case storageFailure(String)
}

enum DashboardConfigurationStoreError: Error, Equatable {
    case revisionConflict(expected: UInt64, actual: UInt64)
    case revisionExhausted
    case invalidConfiguration(DashboardConfigurationValidationError)
    case recoveryRequired(Data, DashboardConfigurationRecoveryError)
    case storageFailure(String)
}

struct DashboardConfigurationStore {
    private static let transactionLock = NSLock()

    private let dataStore: any DashboardConfigurationDataStore
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    init(dataStore: any DashboardConfigurationDataStore) {
        self.dataStore = dataStore
        encoder.outputFormatting = [.sortedKeys]
    }

    func load() -> DashboardConfigurationLoadResult {
        Self.transactionLock.withLock {
            loadWithoutLock()
        }
    }

    func loadOrSeed(_ seed: DashboardConfiguration) -> DashboardConfigurationLoadResult {
        Self.transactionLock.withLock {
            let result = loadWithoutLock()
            guard case .missing = result else {
                return result
            }
            guard seed.identityValidationError == nil else {
                return .storageFailure("The default Dashboard configuration is invalid.")
            }

            var storedSeed = seed
            storedSeed.schemaVersion = DashboardConfiguration.currentSchemaVersion
            do {
                try dataStore.write(encoder.encode(storedSeed))
                return .loaded(storedSeed)
            } catch {
                return .storageFailure(error.localizedDescription)
            }
        }
    }

    func save(
        _ configuration: DashboardConfiguration,
        expectedRevision: UInt64
    ) throws -> DashboardConfiguration {
        try Self.transactionLock.withLock {
            try saveWithoutLock(configuration, expectedRevision: expectedRevision)
        }
    }

    private func loadWithoutLock() -> DashboardConfigurationLoadResult {
        let data: Data
        do {
            guard let storedData = try dataStore.read() else {
                return .missing
            }
            data = storedData
        } catch {
            return .storageFailure(error.localizedDescription)
        }

        return decode(data)
    }

    private func saveWithoutLock(
        _ configuration: DashboardConfiguration,
        expectedRevision: UInt64
    ) throws -> DashboardConfiguration {
        if let validationError = configuration.identityValidationError {
            throw DashboardConfigurationStoreError.invalidConfiguration(validationError)
        }

        let actualRevision: UInt64
        switch loadWithoutLock() {
        case .missing:
            actualRevision = 0
        case .loaded(let current):
            actualRevision = current.revision
        case .recoveryRequired(let data, let error):
            throw DashboardConfigurationStoreError.recoveryRequired(data, error)
        case .storageFailure(let message):
            throw DashboardConfigurationStoreError.storageFailure(message)
        }

        guard actualRevision == expectedRevision else {
            throw DashboardConfigurationStoreError.revisionConflict(
                expected: expectedRevision,
                actual: actualRevision
            )
        }

        let (nextRevision, overflow) = expectedRevision.addingReportingOverflow(1)
        guard !overflow else {
            throw DashboardConfigurationStoreError.revisionExhausted
        }

        var committed = configuration
        committed.schemaVersion = DashboardConfiguration.currentSchemaVersion
        committed.revision = nextRevision

        do {
            try dataStore.write(encoder.encode(committed))
        } catch {
            throw DashboardConfigurationStoreError.storageFailure(error.localizedDescription)
        }
        return committed
    }

    private func decode(_ data: Data) -> DashboardConfigurationLoadResult {
        guard JSONIntegerTokenValidator.accepts(data) else {
            return .recoveryRequired(data, .malformed)
        }

        let schemaVersion: Int
        do {
            let probe = try JSONDecoder().decode(SchemaVersionProbe.self, from: data)
            schemaVersion = probe.schemaVersion
        } catch {
            return .recoveryRequired(data, .malformed)
        }

        guard schemaVersion == DashboardConfiguration.currentSchemaVersion else {
            return .recoveryRequired(data, .unsupportedSchema(schemaVersion))
        }

        do {
            let configuration = try decoder.decode(DashboardConfiguration.self, from: data)
            if configuration.identityValidationError == .duplicateInstanceIDs {
                return .recoveryRequired(data, .duplicateInstanceIDs)
            }
            return .loaded(configuration)
        } catch {
            return .recoveryRequired(data, .malformed)
        }
    }
}

private struct SchemaVersionProbe: Decodable {
    let schemaVersion: Int
}

private enum JSONIntegerTokenValidator {
    private static let quote = UInt8(ascii: "\"")
    private static let escape = UInt8(ascii: "\\")

    static func accepts(_ data: Data) -> Bool {
        guard !data.contains(0), String(data: data, encoding: .utf8) != nil else {
            return false
        }

        let bytes = Array(data)
        var index = 0

        while index < bytes.count {
            if bytes[index] == quote {
                guard let nextIndex = endOfString(in: bytes, startingAt: index) else {
                    return false
                }
                index = nextIndex
            } else if isNumberStart(bytes[index]) {
                let endIndex = endOfNumber(in: bytes, startingAt: index)
                guard isSupportedInteger(bytes[index..<endIndex]) else {
                    return false
                }
                index = endIndex
            } else {
                index += 1
            }
        }
        return true
    }

    private static func endOfString(in bytes: [UInt8], startingAt start: Int) -> Int? {
        var index = start + 1
        while index < bytes.count {
            if bytes[index] == escape {
                index += 2
            } else if bytes[index] == quote {
                return index + 1
            } else {
                index += 1
            }
        }
        return nil
    }

    private static func endOfNumber(in bytes: [UInt8], startingAt start: Int) -> Int {
        var index = start
        while index < bytes.count, isNumberCharacter(bytes[index]) {
            index += 1
        }
        return index
    }

    private static func isSupportedInteger(_ bytes: ArraySlice<UInt8>) -> Bool {
        guard let token = String(bytes: bytes, encoding: .utf8),
              !token.contains("."),
              !token.contains("e"),
              !token.contains("E")
        else {
            return false
        }
        if token.first == "-" {
            return Int64(token) != nil
        }
        return UInt64(token) != nil
    }

    private static func isNumberStart(_ byte: UInt8) -> Bool {
        byte == UInt8(ascii: "-") || byte >= UInt8(ascii: "0") && byte <= UInt8(ascii: "9")
    }

    private static func isNumberCharacter(_ byte: UInt8) -> Bool {
        isNumberStart(byte)
            || byte == UInt8(ascii: "+")
            || byte == UInt8(ascii: ".")
            || byte == UInt8(ascii: "e")
            || byte == UInt8(ascii: "E")
    }
}
