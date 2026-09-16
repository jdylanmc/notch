import ApplicationServices
import ControlCore
import Foundation
import XCTest

extension ControlCoreTests {
    private final class NotchActionFixture {
        var now: TimeInterval = 0
        var metadata = [NotchPanelMetadata(identifier: "com.jdylanmc.notchpocket.notch.v1.window.15", value: "closed")]
        var windows = [WindowInfo(id: 15, ownerPID: 42, onScreen: false, sharingAllowed: false, layer: 27)]
        var names = [kAXShowAlternateUIAction, kAXShowDefaultUIAction]
        var attempts: [String] = []
        var reads = 0
        var beforeRead: ((Int) throws -> Void)?
        var onDiscovery: (() throws -> Void)?
        var onPerform: (() throws -> Void)?

        func run(_ action: NotchAction = .open, windowID: UInt32 = 15) throws -> NotchActionResult {
            let budget = PollBudget(timeout: 0.5, now: { self.now })
            let transport = NotchActionTransport(
                observe: {
                    self.reads += 1
                    try self.beforeRead?(self.reads)
                    return try observeNotchPanels(self.metadata, windows: self.windows, pid: 42)
                },
                actionNames: {
                    try self.onDiscovery?()
                    return self.names
                },
                perform: {
                    self.attempts.append($0)
                    try self.onPerform?()
                }
            )
            return try changeNotchState(
                windowID: windowID, action: action, budget: budget,
                pause: { self.now += $0 }, transport: transport
            )
        }
    }

    func testNotchActionParsingAndNativeNames() throws {
        for (verb, target, name) in [
            ("open", "open", kAXShowAlternateUIAction),
            ("close", "closed", kAXShowDefaultUIAction)
        ] {
            let options = try Options.parse(["notch", verb, "--window", "15", "--app-path", app.path, "--timeout", "0.5"])
            XCTAssertEqual(options.command, .notch)
            XCTAssertEqual(options.windowID, 15)
            XCTAssertNil(options.pane)
            XCTAssertNil(options.output)
            XCTAssertEqual(options.notchAction?.rawValue, verb)
            XCTAssertEqual(options.notchAction?.targetState.rawValue, target)
            XCTAssertEqual(options.notchAction?.nativeName, name)
            XCTAssertEqual(options.appPath, app.path)
            XCTAssertEqual(options.timeout, 0.5)
        }
    }

    func testNotchActionInvalidInputMatrix() {
        var invalid = [
            ["notch"], ["notch", "toggle"], ["notch", "Open"], ["notch", "open"],
            ["notch", "close", "--window"], ["notch", "close", "--window", "15", "--window", "16"],
            ["notch", "open", "--window", "15", "--output", "/owned/new.png"],
            ["notch", "open", "--window", "15", "--timeout", "nan"],
            ["notch", "open", "--window", "15", "--app-path", "/Other/../app.app"]
        ]
        invalid += ["0", "-1", "+15", "015", " 15", "15 ", "15.0", "4294967296", "15;open", ""].map {
            ["notch", "open", "--window", $0]
        }
        for arguments in invalid {
            assertFailure(.invalidInput) { _ = try Options.parse(arguments) }
        }
    }

    func testNotchActionRoutesOneAttemptAndObservesSelectedPanel() throws {
        for action in NotchAction.allCases {
            let fixture = NotchActionFixture()
            let initial = action == .open ? "closed" : "open"
            let expected = action == .open ? "open" : "closed"
            fixture.metadata = [notchMetadata("80", expected), notchMetadata("15", initial)]
            fixture.windows = [notchWindow(80), notchWindow(15)]
            fixture.onPerform = {
                fixture.metadata = [self.notchMetadata("80", expected), self.notchMetadata("15", expected)]
            }
            let result = try fixture.run(action)
            XCTAssertEqual(result.windowID, 15)
            XCTAssertEqual(result.state.rawValue, expected)
            XCTAssertEqual(result.outcome.rawValue, "changed")
            XCTAssertEqual(fixture.attempts, [action == .open ? kAXShowAlternateUIAction : kAXShowDefaultUIAction])
            XCTAssertEqual(fixture.reads, 3)
        }
    }

    func testNotchActionAlreadyAtTargetDoesNotDispatch() throws {
        for action in NotchAction.allCases {
            let fixture = NotchActionFixture()
            fixture.metadata = [notchMetadata("15", action == .open ? "open" : "closed")]
            fixture.onPerform = { XCTFail("No model side effects for a no-op") }
            let result = try fixture.run(action)
            XCTAssertEqual(result.outcome.rawValue, "already_at_target")
            XCTAssertTrue(fixture.attempts.isEmpty)
            XCTAssertEqual(fixture.reads, 2)
        }
    }

    func testNotchActionRequiresAdvertisedExactNameEvenForNoOp() {
        for names in [
            [], ["AXPress"], ["Open Notch"], ["com.jdylanmc.notchpocket.notch.v2.open"],
            ["com.jdylanmc.notchpocket.notch.v1.open"], [kAXShowDefaultUIAction],
            Array(repeating: kAXShowAlternateUIAction, count: 2),
            Array(repeating: "other", count: 601)
        ] {
            let fixture = NotchActionFixture()
            fixture.metadata = [notchMetadata("15", "open")]
            fixture.names = names
            assertFailure(.unsupportedControl) { _ = try fixture.run() }
            XCTAssertTrue(fixture.attempts.isEmpty)
        }
    }

    func testNotchActionUnsupportedStaleAndForeignPanelsNeverDispatch() {
        for stage in [1, 2] {
            for failure in [FailureCode.unsupportedControl, .staleTarget] {
                let fixture = NotchActionFixture()
                fixture.beforeRead = { read in
                    if read == stage {
                        if failure == .unsupportedControl { fixture.metadata = [] } else { fixture.windows = [] }
                    }
                }
                assertFailure(failure) { _ = try fixture.run() }
                XCTAssertTrue(fixture.attempts.isEmpty)
            }
        }
        let foreign = NotchActionFixture()
        foreign.windows = [notchWindow(15, pid: 43)]
        assertFailure(.staleTarget) { _ = try foreign.run() }
        XCTAssertTrue(foreign.attempts.isEmpty)
        let unmarked = NotchActionFixture()
        unmarked.windows.append(notchWindow(16))
        assertFailure(.staleTarget) { _ = try unmarked.run(windowID: 16) }
        XCTAssertTrue(unmarked.attempts.isEmpty)
    }

    func testNotchActionRefusedModelTimesOutWithoutRetry() {
        for action in NotchAction.allCases {
            let fixture = NotchActionFixture()
            fixture.metadata = [notchMetadata("15", action == .open ? "closed" : "open")]
            assertFailure(.timeout) { _ = try fixture.run(action) }
            XCTAssertEqual(fixture.attempts.count, 1)
            XCTAssertEqual(fixture.now, 0.5, accuracy: 0.001)
            XCTAssertGreaterThan(fixture.reads, 2)
        }
    }

    func testNotchActionNativeFailureDoesNotRetryOrObserveSuccess() {
        for nativeError in [AXError.cannotComplete, .attributeUnsupported, .actionUnsupported] {
            let fixture = NotchActionFixture()
            fixture.onPerform = {
                fixture.metadata = [self.notchMetadata("15", "open")]
                throw ControlFailure(.accessibilityFailed,
                                     "Notch action dispatch failed (AX \(nativeError.rawValue)); not retried.")
            }
            assertFailure(.accessibilityFailed) { _ = try fixture.run() }
            XCTAssertEqual(fixture.attempts.count, 1)
            XCTAssertEqual(fixture.reads, 2)
            XCTAssertEqual(fixture.now, 0)
        }
    }

    func testNotchActionLateReadsDiscoveryAndDispatchCannotSucceed() {
        for stage in ["initial", "discovery", "beforeAction", "dispatch", "postcondition"] {
            let fixture = NotchActionFixture()
            fixture.onDiscovery = { if stage == "discovery" { fixture.now = 0.5 } }
            fixture.beforeRead = { read in
                if (stage == "initial" && read == 1) || (stage == "beforeAction" && read == 2) ||
                    (stage == "postcondition" && read == 3) {
                    fixture.now = 0.5
                    fixture.metadata = [self.notchMetadata("15", "open")]
                }
            }
            fixture.onPerform = {
                fixture.metadata = [self.notchMetadata("15", "open")]
                if stage == "dispatch" { fixture.now = 0.5 }
            }
            assertFailure(.timeout) { _ = try fixture.run() }
            XCTAssertEqual(fixture.attempts.count, ["dispatch", "postcondition"].contains(stage) ? 1 : 0)
        }
    }

    func testNotchActionObservationLosesIdentityOrPermissionAfterDispatch() {
        for failure in [FailureCode.staleTarget, .permissionDenied, .accessibilityFailed, .unsupportedControl] {
            let fixture = NotchActionFixture()
            fixture.beforeRead = { read in
                if read == 3 { throw ControlFailure(failure, "Post-action observation failed.") }
            }
            assertFailure(failure) { _ = try fixture.run() }
            XCTAssertEqual(fixture.attempts.count, 1)
        }
    }

    func testNotchActionPollingWaitsForTargetWithoutRepeatingAction() throws {
        let fixture = NotchActionFixture()
        fixture.beforeRead = { read in
            if read == 5 { fixture.metadata = [self.notchMetadata("15", "open")] }
        }
        let result = try fixture.run()
        XCTAssertEqual(result.outcome.rawValue, "changed")
        XCTAssertEqual(fixture.reads, 5)
        XCTAssertEqual(fixture.attempts.count, 1)
        XCTAssertEqual(fixture.now, 0.2, accuracy: 0.001)
    }

    func testNotchActionWireContract() throws {
        for (initial, outcome) in [("closed", "changed"), ("open", "already_at_target")] {
            let fixture = NotchActionFixture()
            fixture.metadata = [notchMetadata("15", initial)]
            fixture.onPerform = { fixture.metadata = [self.notchMetadata("15", "open")] }
            let encoder = JSONEncoder()
            encoder.outputFormatting = .sortedKeys
            XCTAssertEqual(String(data: try encoder.encode(fixture.run()), encoding: .utf8),
                           "{\"action\":\"open\",\"outcome\":\"\(outcome)\",\"state\":\"open\",\"windowID\":15}")
        }
    }
}

extension ControlCoreTests {
        private final class TabSelectionFixture {
            var now: TimeInterval = 0
            var metadata = [
                TabControlMetadata(identifier: "com.jdylanmc.notchpocket.notch.v1.tab.dashboard",
                                   value: "unselected", enabled: true),
                TabControlMetadata(identifier: "com.jdylanmc.notchpocket.notch.v1.tab.home",
                                   value: "selected", enabled: true),
                TabControlMetadata(identifier: "com.jdylanmc.notchpocket.notch.v1.tab.shelf",
                                   value: "unselected", enabled: true)
            ]
            var names = [kAXPressAction]
            var attempts: [String] = []
            var reads = 0
            var beforeRead: ((Int) throws -> Void)?
            var onPerform: (() throws -> Void)?

            func run(_ tab: TabTarget = .dashboard) throws -> TabSelectionResult {
                let budget = PollBudget(timeout: 0.5, now: { self.now })
                let transport = TabSelectionTransport(
                    observe: {
                        self.reads += 1
                        try self.beforeRead?(self.reads)
                        return try observeTabSelection(self.metadata, windowID: 15)
                    },
                    actionNames: { self.names },
                    perform: {
                        self.attempts.append($0)
                        try self.onPerform?()
                    }
                )
                return try selectTab(
                    windowID: 15, tab: tab, budget: budget,
                    pause: { self.now += $0 }, transport: transport
                )
            }

            func select(_ tab: TabTarget) {
                metadata = metadata.map {
                    TabControlMetadata(
                        identifier: $0.identifier,
                        value: $0.identifier.hasSuffix(".\(tab.rawValue)") ? "selected" : "unselected",
                        enabled: $0.enabled
                    )
                }
            }
        }

        func testTabSelectionParsingAndExactIdentifiers() throws {
            for tab in TabTarget.allCases {
                let options = try Options.parse([
                    "select-tab", tab.rawValue, "--window", "15",
                    "--app-path", app.path, "--timeout", "0.5"
                ])
                XCTAssertEqual(options.command, .selectTab)
                XCTAssertEqual(options.tabTarget, tab)
                XCTAssertEqual(options.windowID, 15)
                XCTAssertNil(options.notchAction)
                XCTAssertEqual(tab.accessibilityIdentifier,
                               "com.jdylanmc.notchpocket.notch.v1.tab.\(tab.rawValue)")
            }
        }

        func testTabSelectionInvalidInputMatrix() {
            var invalid = [
                ["select-tab"], ["select-tab", "music"], ["select-tab", "Home"],
                ["select-tab", "home"], ["select-tab", "home", "--window", "0"],
                ["select-tab", "home", "--window", "015"],
                ["select-tab", "home", "--window", "15", "--output", "/owned/new.png"]
            ]
            invalid += ["-1", "+15", " 15", "15 ", "15.0", "4294967296", ""].map {
                ["select-tab", "home", "--window", $0]
            }
            for arguments in invalid {
                assertFailure(.invalidInput) { _ = try Options.parse(arguments) }
            }
        }

        func testTabSelectionDispatchesOneExactPressAndObservesSelection() throws {
            for tab in TabTarget.allCases {
                let fixture = TabSelectionFixture()
                fixture.select(tab == .home ? .dashboard : .home)
                fixture.onPerform = { fixture.select(tab) }
                let result = try fixture.run(tab)
                XCTAssertEqual(result.windowID, 15)
                XCTAssertEqual(result.tab, tab)
                XCTAssertEqual(result.state, "selected")
                XCTAssertEqual(result.outcome, .changed)
                XCTAssertEqual(fixture.attempts, [kAXPressAction])
                XCTAssertEqual(fixture.reads, 3)
            }
        }

        func testCompactTabSelectionWithShelfDisabledOrEmptyPressesDashboard() throws {
            let fixture = TabSelectionFixture()
            fixture.metadata = [
                TabControlMetadata(
                    identifier: TabTarget.dashboard.accessibilityIdentifier,
                    value: "unselected",
                    enabled: true
                )
            ]
            fixture.onPerform = {
                fixture.metadata = [
                    TabControlMetadata(
                        identifier: TabTarget.home.accessibilityIdentifier,
                        value: "unselected",
                        enabled: true
                    )
                ]
            }

            let result = try fixture.run(.dashboard)

            XCTAssertEqual(result.outcome, .changed)
            XCTAssertEqual(result.tab, .dashboard)
            XCTAssertEqual(fixture.attempts, [kAXPressAction])
            XCTAssertEqual(fixture.reads, 3)
        }

        func testCompactTabSelectionWithShelfDisabledOrEmptyPressesHome() throws {
            let fixture = TabSelectionFixture()
            fixture.metadata = [
                TabControlMetadata(
                    identifier: TabTarget.home.accessibilityIdentifier,
                    value: "unselected",
                    enabled: true
                )
            ]
            fixture.onPerform = {
                fixture.metadata = [
                    TabControlMetadata(
                        identifier: TabTarget.dashboard.accessibilityIdentifier,
                        value: "unselected",
                        enabled: true
                    )
                ]
            }

            let result = try fixture.run(.home)

            XCTAssertEqual(result.outcome, .changed)
            XCTAssertEqual(result.tab, .home)
            XCTAssertEqual(fixture.attempts, [kAXPressAction])
            XCTAssertEqual(fixture.reads, 3)
        }

        func testTabSelectionAlreadySelectedDoesNotDispatch() throws {
            let fixture = TabSelectionFixture()
            fixture.names = []
            let result = try fixture.run(.home)
            XCTAssertEqual(result.outcome, .alreadySelected)
            XCTAssertTrue(fixture.attempts.isEmpty)
            XCTAssertEqual(fixture.reads, 1)
        }

        func testCompactTabSelectionWithShelfDisabledOrEmptyPreservesNoOp() throws {
            let fixture = TabSelectionFixture()
            fixture.metadata = [
                TabControlMetadata(
                    identifier: TabTarget.dashboard.accessibilityIdentifier,
                    value: "unselected",
                    enabled: true
                )
            ]
            fixture.names = []

            let result = try fixture.run(.home)

            XCTAssertEqual(result.outcome, .alreadySelected)
            XCTAssertEqual(result.tab, .home)
            XCTAssertTrue(fixture.attempts.isEmpty)
            XCTAssertEqual(fixture.reads, 1)
        }

        func testShelfSelectedCompactMetadataIsUnsupportedWithoutFalseHomeNoOp() {
            let fixture = TabSelectionFixture()
            fixture.metadata = []
            fixture.names = []

            assertFailure(.unsupportedControl) { _ = try fixture.run(.home) }

            XCTAssertTrue(fixture.attempts.isEmpty)
            XCTAssertEqual(fixture.reads, 1)
        }

        func testTabSelectionRejectsStaleMappingWithoutDispatch() {
            for stage in [1, 2] {
                let fixture = TabSelectionFixture()
                fixture.beforeRead = { read in
                    if read == stage {
                        throw ControlFailure(.staleTarget, "Selected tab mapping changed; inspect again.")
                    }
                }
                assertFailure(.staleTarget) { _ = try fixture.run() }
                XCTAssertTrue(fixture.attempts.isEmpty)
            }
        }

        func testTabSelectionRejectsUnavailableOrDisabledShelfWithoutChangingSettings() {
            let unavailable = TabSelectionFixture()
            unavailable.metadata.removeAll { $0.identifier.hasSuffix(".shelf") }
            assertFailure(.unsupportedControl) { _ = try unavailable.run(.shelf) }
            XCTAssertTrue(unavailable.attempts.isEmpty)

            let disabled = TabSelectionFixture()
            disabled.metadata = disabled.metadata.map {
                TabControlMetadata(identifier: $0.identifier, value: $0.value,
                                   enabled: $0.identifier.hasSuffix(".shelf") ? false : $0.enabled)
            }
            assertFailure(.unsupportedControl) { _ = try disabled.run(.shelf) }
            XCTAssertTrue(disabled.attempts.isEmpty)
        }

        func testTabSelectionRequiresExactPressAndValidSelectedState() {
            for names in [[], ["Press"], ["AXShowAlternateUI"], [kAXPressAction, kAXPressAction]] {
                let fixture = TabSelectionFixture()
                fixture.names = names
                assertFailure(.unsupportedControl) { _ = try fixture.run() }
                XCTAssertTrue(fixture.attempts.isEmpty)
            }

            for values in [
                ["selected", "selected", "unselected"],
                ["unselected", "unselected", "unselected"],
                ["home", "unselected", "unselected"]
            ] {
                let fixture = TabSelectionFixture()
                fixture.metadata = zip(fixture.metadata, values).map {
                    TabControlMetadata(identifier: $0.0.identifier, value: $0.1, enabled: $0.0.enabled)
                }
                assertFailure(.unsupportedControl) { _ = try fixture.run() }
                XCTAssertTrue(fixture.attempts.isEmpty)
            }
        }

        func testTabSelectionNativeFailureDoesNotRetryOrReportSuccess() {
            let fixture = TabSelectionFixture()
            fixture.onPerform = {
                fixture.select(.dashboard)
                throw ControlFailure(.accessibilityFailed, "Tab press failed; not retried.")
            }
            assertFailure(.accessibilityFailed) { _ = try fixture.run() }
            XCTAssertEqual(fixture.attempts, [kAXPressAction])
            XCTAssertEqual(fixture.reads, 2)
        }

        func testTabSelectionTimeoutDoesNotRetryPress() {
            let fixture = TabSelectionFixture()
            assertFailure(.timeout) { _ = try fixture.run() }
            XCTAssertEqual(fixture.attempts, [kAXPressAction])
            XCTAssertEqual(fixture.now, 0.5, accuracy: 0.001)
            XCTAssertGreaterThan(fixture.reads, 2)
        }

        func testTabSelectionWireContract() throws {
            let fixture = TabSelectionFixture()
            fixture.onPerform = { fixture.select(.dashboard) }
            let encoder = JSONEncoder()
            encoder.outputFormatting = .sortedKeys
            XCTAssertEqual(String(data: try encoder.encode(fixture.run()), encoding: .utf8),
                           "{\"outcome\":\"changed\",\"state\":\"selected\",\"tab\":\"dashboard\",\"windowID\":15}")
        }
    }
