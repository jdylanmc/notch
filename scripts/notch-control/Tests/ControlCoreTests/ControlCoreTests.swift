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

    func testWaitRequiresObservationAndUsesOneDeadline() throws {
        var now: TimeInterval = 10
        var probes = 0
        let budget = PollBudget(timeout: 1, now: { now })
        try budget.until(pause: { now += $0 }) {
            probes += 1
            return probes == 3
        }
        XCTAssertEqual(probes, 3)
        XCTAssertEqual(now, 10.2, accuracy: 0.001)
        now = 11
        assertFailure(.timeout) {
            try budget.until(pause: { _ in XCTFail("Must not sleep past deadline") }) {
                XCTFail("Expired budget must not probe")
                return true
            }
        }
    }

    func testNeverObservedConditionTimesOut() {
        var now: TimeInterval = 0
        let budget = PollBudget(timeout: 0.5, now: { now })
        assertFailure(.timeout) {
            try budget.until(pause: { now += $0 }) { false }
        }
        XCTAssertEqual(now, 0.5, accuracy: 0.001)
    }

    func testWaitPropagatesFailureInsteadOfTreatingItAsAbsence() {
        let budget = PollBudget(timeout: 1, now: { 0 })
        assertFailure(.accessibilityFailed) {
            try budget.until(pause: { _ in XCTFail("Must propagate read failure") }) {
                throw ControlFailure(.accessibilityFailed, "Synthetic AX failure.")
            }
        }
    }

    func testErrorWireFormatAndNonzeroStatuses() throws {
        for code in FailureCode.allCases {
            XCTAssertGreaterThan(code.exitStatus, 0)
            let data = try JSONEncoder().encode(ControlFailure(code, "Bounded diagnostic."))
            let decoded = try JSONDecoder().decode(ControlFailure.self, from: data)
            XCTAssertEqual(decoded.code, code)
            XCTAssertEqual(decoded.message, "Bounded diagnostic.")
        }
        XCTAssertEqual(FailureCode.invalidInput.exitStatus, 2)
        XCTAssertEqual(FailureCode.permissionDenied.exitStatus, 4)
        XCTAssertEqual(FailureCode.timeout.exitStatus, 7)
    }

    func testSecureOutputRefusesOverwriteAndSymlinks() throws {
        guard let root = ProcessInfo.processInfo.environment["NOTCH_CONTROL_TEST_ROOT"] else {
            throw XCTSkip("Use bash scripts/notch-control/control.sh test for worktree-local filesystem tests.")
        }
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
