//
//  DashboardConfigurationNumericTests.swift
//  notchPocketTests
//

import Foundation
import XCTest

@testable import notchPocket

final class DashboardConfigurationNumericTests: XCTestCase {
    private final class MemoryDataStore: DashboardConfigurationDataStore {
        var data: Data?

        init(data: Data? = nil) {
            self.data = data
        }

        func read() throws -> Data? {
            data
        }

        func write(_ data: Data) throws {
            self.data = data
        }
    }

    func testMinimumSignedIntegerSurvivesNestedSettingsAndPayloadRoundTrip() throws {
        let literal = "-9223372036854775808"
        let source = configurationData(numberLiteral: literal)
        let dataStore = MemoryDataStore(data: source)
        let store = DashboardConfigurationStore(dataStore: dataStore)
        guard case .loaded(let configuration) = store.load() else {
            return XCTFail("Expected minimum signed integer to load")
        }

        _ = try store.save(configuration, expectedRevision: 1)

        try assertNestedNumbers(in: XCTUnwrap(dataStore.data), equal: literal)
    }

    func testFractionalAndUnderflowNumbersRequireRecoveryWithoutWriting() {
        for literal in ["1.5", "1.00000000000000000001", "1e-9999"] {
            assertNumberRequiresRecoveryWithoutWriting(literal)
        }
    }

    func testIntegralExponentIsPreservedExactlyOrRequiresRecoveryWithoutWriting() throws {
        let literal = "9007199254740993e0"
        let expectedInteger = "9007199254740993"
        let source = configurationData(numberLiteral: literal)
        let dataStore = MemoryDataStore(data: source)
        let store = DashboardConfigurationStore(dataStore: dataStore)

        switch store.load() {
        case .loaded(let configuration):
            _ = try store.save(configuration, expectedRevision: 1)
            try assertNestedNumbers(
                in: XCTUnwrap(dataStore.data),
                equal: expectedInteger
            )
        case .recoveryRequired(let preserved, .malformed):
            XCTAssertEqual(preserved, source)
            assertOrdinarySaveIsRejected(store: store, dataStore: dataStore, source: source)
        default:
            XCTFail("Expected exact integer preservation or recovery")
        }
    }

    func testNumberLikeStringsAndEscapesDoNotTriggerNumericRecovery() {
        let source = Data(
            #"""
            {
              "schemaVersion": 1,
              "revision": 1,
              "instances": [
                {
                  "id": "00000000-0000-0000-0000-000000000001",
                  "kind": "futureWidget",
                  "position": {"column": 0, "row": 0},
                  "footprint": {"columns": 1, "rows": 1},
                  "settings": {
                    "fraction": "1.5",
                    "escaped": "value \"1e-9999\""
                  },
                  "payload": {"value": "9007199254740993e0"}
                }
              ]
            }
            """#.utf8
        )
        let store = DashboardConfigurationStore(dataStore: MemoryDataStore(data: source))

        guard case .loaded = store.load() else {
            return XCTFail("Expected number-like string content to remain supported")
        }
    }

    func testNonUTF8EncodingsRequireRecoveryWithoutWriting() throws {
        let source = try XCTUnwrap(
            String(
                bytes: configurationData(numberLiteral: "1.00000000000000000001"),
                encoding: .utf8
            )
        )
        let fixtures: [Data] = [
            encoded(source, as: .utf16LittleEndian, bom: [0xFF, 0xFE]),
            encoded(source, as: .utf16BigEndian, bom: [0xFE, 0xFF]),
            encoded(source, as: .utf32LittleEndian, bom: [0xFF, 0xFE, 0x00, 0x00]),
            encoded(source, as: .utf32BigEndian, bom: [0x00, 0x00, 0xFE, 0xFF]),
            encoded(source, as: .utf16LittleEndian),
            encoded(source, as: .utf16BigEndian),
            encoded(source, as: .utf32LittleEndian),
            encoded(source, as: .utf32BigEndian)
        ]

        for fixture in fixtures {
            let dataStore = MemoryDataStore(data: fixture)
            let store = DashboardConfigurationStore(dataStore: dataStore)
            guard case .recoveryRequired(let preserved, .malformed) = store.load() else {
                XCTFail("Expected non-UTF8 input to require recovery")
                continue
            }
            XCTAssertEqual(preserved, fixture)
            assertOrdinarySaveIsRejected(store: store, dataStore: dataStore, source: fixture)
        }
    }

    func testUTF8NonASCIIAndEscapedControlsRemainSupported() {
        let source = Data(
            #"""
            {
              "schemaVersion": 1,
              "revision": 1,
              "instances": [
                {
                  "id": "00000000-0000-0000-0000-000000000001",
                  "kind": "futureWidget",
                  "position": {"column": 0, "row": 0},
                  "footprint": {"columns": 1, "rows": 1},
                  "settings": {
                    "label": "Café 雪",
                    "escaped": "line\nnul\u0000quote\""
                  },
                  "payload": {"value": 7}
                }
              ]
            }
            """#.utf8
        )
        let store = DashboardConfigurationStore(dataStore: MemoryDataStore(data: source))

        guard case .loaded = store.load() else {
            return XCTFail("Expected valid UTF-8 strings and escapes to remain supported")
        }
    }

    private func configurationData(numberLiteral: String) -> Data {
        Data(
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
                  "settings": {"nested": {"value": \(numberLiteral)}},
                  "payload": {"nested": {"value": \(numberLiteral)}}
                }
              ]
            }
            """.utf8
        )
    }

    private func assertNestedNumbers(in data: Data, equal expected: String) throws {
        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: data) as? [String: Any]
        )
        let instance = try XCTUnwrap((object["instances"] as? [[String: Any]])?.first)
        for field in ["settings", "payload"] {
            let container = try XCTUnwrap(instance[field] as? [String: Any])
            let nested = try XCTUnwrap(container["nested"] as? [String: Any])
            XCTAssertEqual((nested["value"] as? NSNumber)?.stringValue, expected)
        }
    }

    private func assertNumberRequiresRecoveryWithoutWriting(_ literal: String) {
        let source = configurationData(numberLiteral: literal)
        let dataStore = MemoryDataStore(data: source)
        let store = DashboardConfigurationStore(dataStore: dataStore)
        guard case .recoveryRequired(let preserved, .malformed) = store.load() else {
            return XCTFail("Expected \(literal) to require recovery")
        }
        XCTAssertEqual(preserved, source)
        assertOrdinarySaveIsRejected(store: store, dataStore: dataStore, source: source)
    }

    private func assertOrdinarySaveIsRejected(
        store: DashboardConfigurationStore,
        dataStore: MemoryDataStore,
        source: Data
    ) {
        XCTAssertThrowsError(
            try store.save(
                DashboardConfiguration(revision: 1, instances: []),
                expectedRevision: 1
            )
        ) { error in
            XCTAssertEqual(
                error as? DashboardConfigurationStoreError,
                .recoveryRequired(source, .malformed)
            )
        }
        XCTAssertEqual(dataStore.data, source)
    }

    private func encoded(
        _ source: String,
        as encoding: String.Encoding,
        bom: [UInt8] = []
    ) -> Data {
        var data = Data(bom)
        data.append(source.data(using: encoding)!)
        return data
    }
}
