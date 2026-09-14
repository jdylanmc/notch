//
//  DashboardDefaultsConfigurationDataStore.swift
//  notchPocket
//

import Defaults
import Foundation

struct DefaultsDashboardConfigurationDataStore: DashboardConfigurationDataStore {
    func read() throws -> Data? {
        Defaults[.dashboardConfigurationData]
    }

    func write(_ data: Data) throws {
        Defaults[.dashboardConfigurationData] = data
    }
}

extension DashboardConfigurationStore {
    static func live() -> Self {
        Self(dataStore: DefaultsDashboardConfigurationDataStore())
    }
}
