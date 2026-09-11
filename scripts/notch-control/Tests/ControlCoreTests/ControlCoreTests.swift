import ControlCore
import Foundation
import XCTest

final class ControlCoreTests: XCTestCase {
    private let app = AppIdentity(pid: 42, path: "/Applications/notch-pocket.app",
                                  launchedAt: Date(timeIntervalSince1970: 100))

    private func assertFailure(
        _ expected: FailureCode,
        file: StaticString = #filePath,
        line: UInt = #line,
        _ operation: () throws -> Void
    ) {
        XCTAssertThrowsError(try operation(), file: file, line: line) { error in
            XCTAssertEqual((error as? ControlFailure)?.code, expected, file: file, line: line)
        }
    }

    func testValidCommands() throws {
        XCTAssertEqual(try Options.parse(["inspect"]).command, .inspect)
        XCTAssertEqual(try Options.parse(["help"]).command, .help)
        for pane in ["open", "general", "about"] {
            let options = try Options.parse(["settings", pane, "--app-path", app.path, "--timeout", "2"])
            XCTAssertEqual(options.pane, pane)
            XCTAssertEqual(options.appPath, app.path)
            XCTAssertEqual(options.timeout, 2)
        }
        let capture = try Options.parse(["capture", "--window", "99", "--output", "/owned/image.png"])
        XCTAssertEqual(capture.windowID, 99)
        XCTAssertEqual(capture.output, "/owned/image.png")
    }

    func testInvalidInputMatrix() {
        let invalid: [[String]] = [
            [], ["other"], ["--help"], ["help", "--timeout", "2"],
            ["settings"], ["settings", "close"], ["settings", "General"],
            ["inspect", "--window", "1"], ["inspect", "--output", "/owned/file.png"],
            ["inspect", "--unknown", "1"], ["inspect", "--timeout"],
            ["inspect", "--timeout", "1", "--timeout", "2"],
            ["inspect", "--timeout", "nan"], ["inspect", "--timeout", "inf"],
            ["inspect", "--timeout", "0"], ["inspect", "--timeout", "16"],
            ["inspect", "--app-path", "relative.app"], ["inspect", "--app-path", "/file"],
            ["capture"], ["capture", "--window", "-1", "--output", "/owned/a.png"],
            ["capture", "--window", "0", "--output", "/owned/a.png"],
            ["capture", "--window", "4294967296", "--output", "/owned/a.png"],
            ["capture", "--window", "1.5", "--output", "/owned/a.png"],
            ["capture", "--window", "1;echo", "--output", "/owned/a.png"],
            ["capture", "--window", "1", "--output", "relative.png"],
            ["capture", "--window", "1", "--output", "/owned/a.jpg"],
            ["capture", "--window", "1", "--output", "/owned/../a.png"],
            ["capture", "--window", "1", "--output", "/owned//a.png"],
            ["capture", "--window", "1", "--output", "/owned/a\n.png"],
            ["capture", "--window", "1", "--output", "/owned/a\0.png"]
        ]
        for arguments in invalid {
            assertFailure(.invalidInput) { _ = try Options.parse(arguments) }
        }
    }

    func testNoFirstInstanceOrPathBasedAmbiguityBypass() throws {
        XCTAssertEqual(try selectApp([app], expectedPath: app.path), app)
        assertFailure(.appMissing) { _ = try selectApp([], expectedPath: nil) }
        assertFailure(.ambiguousApp) { _ = try selectApp([app, app], expectedPath: app.path) }
        assertFailure(.appPathMismatch) { _ = try selectApp([app], expectedPath: "/Other.app") }
        let relaunched = AppIdentity(pid: app.pid, path: app.path, launchedAt: app.launchedAt.addingTimeInterval(1))
        assertFailure(.staleTarget) { try requireSameApp(app, relaunched) }
        let moved = AppIdentity(pid: app.pid, path: "/Other.app", launchedAt: app.launchedAt)
        assertFailure(.staleTarget) { try requireSameApp(app, moved) }
        try requireSameApp(app, app)
    }

    func testCaptureOwnershipAndExclusion() throws {
        let visible = WindowInfo(id: 5, ownerPID: app.pid, onScreen: true, sharingAllowed: true, layer: 0)
        XCTAssertEqual(try captureWindow([visible], id: 5, pid: app.pid), visible)
        assertFailure(.windowMissing) { _ = try captureWindow([visible], id: 6, pid: app.pid) }
        assertFailure(.windowMissing) { _ = try captureWindow([visible], id: 5, pid: 43) }
        assertFailure(.windowMissing) { _ = try captureWindow([visible, visible], id: 5, pid: app.pid) }
        let excluded = WindowInfo(id: 5, ownerPID: app.pid, onScreen: true, sharingAllowed: false, layer: 0)
        assertFailure(.windowExcluded) { _ = try captureWindow([excluded], id: 5, pid: app.pid) }
        let hidden = WindowInfo(id: 5, ownerPID: app.pid, onScreen: false, sharingAllowed: true, layer: 0)
        assertFailure(.unsupportedWindow) { _ = try captureWindow([hidden], id: 5, pid: app.pid) }
    }

    private func menuItem(
        roots: [String],
        descendants: [String: [String]] = [:],
        labels: [String: String] = [:]
    ) throws -> String {
        try selectSettingsMenuItem(
            immediateChildren: roots,
            role: { element in
                if element.hasPrefix("bar") { return "AXMenuBar" }
                return element.hasPrefix("item") ? "AXMenuItem" : "AXWindow"
            },
            children: { element in
                XCTAssertNotEqual(element, "window", "Must not traverse non-menu app children")
                return descendants[element] ?? []
            },
            title: { labels[$0] }
        )
    }

    func testSettingsUsesSecondImmediateMenuBarOnly() throws {
        let selected = try menuItem(
            roots: ["barMain", "window", "barExtra"],
            descendants: ["barMain": ["itemOther"], "barExtra": ["itemSettings"], "window": ["itemDecoy"]],
            labels: ["itemOther": "About", "itemSettings": "Settings…", "itemDecoy": "Settings"]
        )
        XCTAssertEqual(selected, "itemSettings")
    }

    func testSettingsMissingMenuOrEnglishItemFails() {
        for roots in [[], ["window"], ["barMain"]] {
            assertFailure(.unsupportedControl) { _ = try menuItem(roots: roots) }
        }
        assertFailure(.unsupportedControl) {
            _ = try menuItem(roots: ["barMain"], descendants: ["barMain": ["itemSettings"]],
                             labels: ["itemSettings": "Réglages"])
        }
    }

    func testSettingsDeduplicatesRootsButRefusesDistinctCandidates() throws {
        for label in ["Settings", "Settings…", "Settings..."] {
            XCTAssertEqual(try menuItem(
                roots: Array(repeating: "barMain", count: 600),
                descendants: ["barMain": ["itemSettings"]],
                labels: ["itemSettings": label]
            ), "itemSettings")
        }
        assertFailure(.unsupportedControl) {
            _ = try menuItem(
                roots: ["barMain", "barExtra"],
                descendants: ["barMain": ["itemFirst"], "barExtra": ["itemSecond"]],
                labels: ["itemFirst": "Settings", "itemSecond": "Settings…"]
            )
        }
    }

    func testSettingsMenuSearchIsBounded() {
        assertFailure(.unsupportedControl) {
            _ = try menuItem(roots: Array(repeating: "barMain", count: 601))
        }
        assertFailure(.unsupportedControl) {
            _ = try menuItem(roots: ["barMain"], descendants: ["barMain": Array(repeating: "itemOther", count: 601)])
        }
        assertFailure(.unsupportedControl) {
            _ = try menuItem(roots: ["barMain"], descendants: ["barMain": ["barMain"]])
        }
        assertFailure(.unsupportedControl) {
            _ = try menuItem(roots: ["barMain", "barExtra"], descendants: [
                "barMain": Array(repeating: "itemOther", count: 300),
                "barExtra": Array(repeating: "itemOther", count: 300)
            ])
        }
    }

    func testSettingsMenuReadFailurePropagates() {
        assertFailure(.accessibilityFailed) {
            _ = try selectSettingsMenuItem(
                immediateChildren: ["barMain"],
                role: { _ in "AXMenuBar" },
                children: { _ in throw ControlFailure(.accessibilityFailed, "Synthetic AX failure.") },
                title: { _ in nil }
            )
        }
    }

    func testWaitRequiresObservationAndUsesOneDeadline() throws {
        var now: TimeInterval = 10
        var probes = 0
        let budget = PollBudget(timeout: 1, now: { now })
        try budget.until(pause: { now += $0 }, condition: {
            probes += 1
            return probes == 3
        })
        XCTAssertEqual(probes, 3)
        XCTAssertEqual(now, 10.2, accuracy: 0.001)
        now = 11
        assertFailure(.timeout) {
            try budget.until(pause: { _ in XCTFail("Must not sleep past deadline") }, condition: {
                XCTFail("Expired budget must not probe")
                return true
            })
        }
    }

    func testNeverObservedConditionTimesOut() {
        var now: TimeInterval = 0
        let budget = PollBudget(timeout: 0.5, now: { now })
        assertFailure(.timeout) {
            try budget.until(pause: { now += $0 }, condition: { false })
        }
        XCTAssertEqual(now, 0.5, accuracy: 0.001)
    }

    func testWaitPropagatesFailureInsteadOfTreatingItAsAbsence() {
        let budget = PollBudget(timeout: 1, now: { 0 })
        assertFailure(.accessibilityFailed) {
            try budget.until(pause: { _ in XCTFail("Must propagate read failure") }, condition: {
                throw ControlFailure(.accessibilityFailed, "Synthetic AX failure.")
            })
        }
    }

    func testErrorWireFormatAndNonzeroStatuses() throws {
        let contract: [String: Int32] = [
            "invalid_input": 2,
            "app_missing": 3, "ambiguous_app": 3, "app_path_mismatch": 3, "stale_target": 3,
            "permission_denied": 4,
            "unsupported_control": 5, "accessibility_failed": 5,
            "window_missing": 6, "window_excluded": 6, "unsupported_window": 6,
            "timeout": 7, "capture_failed": 8,
            "output_exists": 9, "unsafe_output": 9, "output_failed": 9,
            "internal_error": 10
        ]
        XCTAssertEqual(Set(FailureCode.allCases.map(\.rawValue)), Set(contract.keys))
        for (literal, status) in contract {
            let code = try XCTUnwrap(FailureCode(rawValue: literal))
            XCTAssertEqual(code.exitStatus, status, literal)
            let data = try JSONEncoder().encode(ControlFailure(code, "Bounded diagnostic."))
            let decoded = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: String])
            XCTAssertEqual(decoded, ["code": literal, "message": "Bounded diagnostic."])
        }
    }

    func testInvalidInputExecutableWireContract() throws {
        let executable = try XCTUnwrap(ProcessInfo.processInfo.environment["NOTCH_CONTROL_TEST_EXECUTABLE"],
                                       "Use bash scripts/notch-control/control.sh test.")
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = ["settings", "close"]
        let output = Pipe()
        let errors = Pipe()
        process.standardOutput = output
        process.standardError = errors
        let finished = expectation(description: "Invalid input exits without app discovery")
        process.terminationHandler = { _ in finished.fulfill() }
        try process.run()
        defer { if process.isRunning { process.terminate() } }
        wait(for: [finished], timeout: 5)
        guard !process.isRunning else { return }
        XCTAssertEqual(process.terminationReason, .exit)
        XCTAssertEqual(process.terminationStatus, 2)
        let data = output.fileHandleForReading.readDataToEndOfFile()
        XCTAssertEqual(data.filter { $0 == 10 }.count, 1)
        XCTAssertEqual(data.last, 10)
        let decoded = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? NSDictionary)
        XCTAssertEqual(decoded, [
            "ok": false,
            "error": ["code": "invalid_input", "message": "settings requires open, general, or about."]
        ] as NSDictionary)
        XCTAssertTrue(errors.fileHandleForReading.readDataToEndOfFile().isEmpty)
    }

    func testSecureOutputRefusesOverwriteAndSymlinks() throws {
        let root = try XCTUnwrap(ProcessInfo.processInfo.environment["NOTCH_CONTROL_TEST_ROOT"],
                                 "Use bash scripts/notch-control/control.sh test for worktree-local filesystem tests.")
        try validateAbsolutePath(root)
        let manager = FileManager.default
        let directory = URL(fileURLWithPath: root).appendingPathComponent("output-tests-\(UUID().uuidString)")
        try manager.createDirectory(at: directory, withIntermediateDirectories: false)
        defer { try? manager.removeItem(at: directory) }
        let path = directory.appendingPathComponent("image.png").path
        let payload = Data([1, 2, 3])
        try SecureOutput.write(payload, to: path)
        XCTAssertEqual(try Data(contentsOf: URL(fileURLWithPath: path)), payload)
        let attributes = try manager.attributesOfItem(atPath: path)
        XCTAssertEqual((attributes[.posixPermissions] as? NSNumber)?.intValue, 0o600)
        assertFailure(.outputExists) { try SecureOutput.write(Data([4]), to: path) }
        XCTAssertEqual(try Data(contentsOf: URL(fileURLWithPath: path)), payload)
        let link = directory.appendingPathComponent("link.png")
        try manager.createSymbolicLink(atPath: link.path, withDestinationPath: path)
        assertFailure(.outputExists) { try SecureOutput.write(payload, to: link.path) }
        let parentLink = directory.appendingPathComponent("redirect")
        try manager.createSymbolicLink(atPath: parentLink.path, withDestinationPath: directory.path)
        assertFailure(.unsafeOutput) {
            try SecureOutput.write(payload, to: parentLink.appendingPathComponent("other.png").path)
        }
        XCTAssertFalse(manager.fileExists(atPath: directory.appendingPathComponent("other.png").path))
        assertFailure(.unsafeOutput) {
            try SecureOutput.write(payload, to: directory.appendingPathComponent("missing/image.png").path)
        }
        let empty = directory.appendingPathComponent("empty.png")
        assertFailure(.outputFailed) { try SecureOutput.write(Data(), to: empty.path) }
        XCTAssertFalse(manager.fileExists(atPath: empty.path))
    }
}
