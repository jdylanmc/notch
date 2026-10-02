//
//  DashboardDefaultsConfigurationDataStore.swift
//  notchPocket
//

import Defaults
import Foundation

struct DefaultsDashboardConfigurationDataStore: DashboardConfigurationDataStore {
    private let key: Defaults.Key<Data?>

    init(key: Defaults.Key<Data?> = .dashboardConfigurationData) {
        self.key = key
    }

    func read() throws -> Data? {
        Defaults[key]
    }

    func write(_ data: Data) throws {
        Defaults[key] = data
    }
}

extension DashboardConfigurationStore {
    static func live() -> Self {
        Self(dataStore: DefaultsDashboardConfigurationDataStore())
    }
}
