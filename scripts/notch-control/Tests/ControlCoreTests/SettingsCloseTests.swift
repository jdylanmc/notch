import ControlCore
import Foundation
import XCTest

extension ControlCoreTests {
    func testSettingsPaneWaitObservesSelectionWithoutDependingOnWindowTitle() throws {
        var now: TimeInterval = 0
        var observations = 0
        try waitForSettingsPane("about", budget: PollBudget(timeout: 1, now: { now }), pause: { now += $0 }) {
            observations += 1
            return (true, observations < 3 ? "general" : "about")
        }
        XCTAssertEqual(observations, 3)
        XCTAssertGreaterThan(now, 0)
    }

    func testSettingsPaneWaitRejectsReplacedWindowAndLateSelection() {
        assertFailure(.staleTarget) {
            try waitForSettingsPane("general", budget: PollBudget(timeout: 1), pause: { _ in }) {
                (false, "general")
            }
        }
        var now: TimeInterval = 0
        assertFailure(.timeout) {
            try waitForSettingsPane("about", budget: PollBudget(timeout: 1, now: { now }), pause: { _ in }) {
                now = 2
                return (true, "about")
            }
        }
    }

    func testSettingsPaneWaitTimesOutPropagatesErrorsAndRejectsInvalidDestination() {
        var now: TimeInterval = 0
        assertFailure(.timeout) {
            try waitForSettingsPane("about", budget: PollBudget(timeout: 0.5, now: { now }), pause: { now += $0 }) {
                (true, nil)
            }
        }
        assertFailure(.permissionDenied) {
            try waitForSettingsPane("general", budget: PollBudget(timeout: 1), pause: { _ in }) {
                throw ControlFailure(.permissionDenied, "fixture")
            }
        }
        assertFailure(.invalidInput) {
            try waitForSettingsPane("close", budget: PollBudget(timeout: 1), pause: { _ in }) {
                XCTFail("Closing must not enter pane navigation")
                return nil
            }
        }
    }

    func testSettingsCloseRequiresItsOwnExplicitWindowSelector() throws {
        let options = try Options.parse(["settings", "close", "--window", "17", "--app-path", app.path])
        XCTAssertEqual(options.command, .settings)
        XCTAssertEqual(options.pane, "close")
        XCTAssertEqual(options.windowID, 17)
        XCTAssertEqual(options.appPath, app.path)
        XCTAssertNil(options.output)
    }

    func testSettingsCloseRejectsInvalidOrUnrelatedSelectors() {
        for raw in ["0", "-1", "+1", "01", "1.5", "4294967296", "1;echo", " 1"] {
            assertFailure(.invalidInput) { _ = try Options.parse(["settings", "close", "--window", raw]) }
        }
        for arguments in [
            ["settings", "close"],
            ["settings", "close", "--window", "1", "--output", "/owned/image.png"],
            ["settings", "general", "--window", "1"],
            ["settings", "open", "--window", "1"],
            ["settings", "close", "--window", "1", "--window", "2"]
        ] {
            assertFailure(.invalidInput) { _ = try Options.parse(arguments) }
        }
    }

    func testSettingsCloseObservesCompletionAfterOneExactPress() throws {
        var observations = 0
        var actions: [String] = []
        let result = try closeSettingsWindow(
            windowID: 17, budget: PollBudget(timeout: 1), pause: { _ in },
            transport: SettingsCloseTransport(
                observe: { observations += 1; return observations <= 2 ? 17 : nil },
                actionNames: { ["AXPress"] },
                perform: { actions.append($0) }
            )
        )
        XCTAssertEqual(actions, ["AXPress"])
        XCTAssertEqual(observations, 3)
        XCTAssertEqual(result.windowID, 17)
        let encoded = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(result)) as? [String: Any])
        XCTAssertEqual(encoded["windowID"] as? Int, 17)
        XCTAssertEqual(encoded["outcome"] as? String, "closed")
    }

    func testSettingsCloseWaitsWithoutRepeatingTheAction() throws {
        var now: TimeInterval = 0
        var observations = 0
        var actions = 0
        _ = try closeSettingsWindow(
            windowID: 17, budget: PollBudget(timeout: 1, now: { now }), pause: { now += $0 },
            transport: SettingsCloseTransport(
                observe: { observations += 1; return observations < 5 ? 17 : nil },
                actionNames: { ["AXPress"] }, perform: { _ in actions += 1 }
            )
        )
        XCTAssertEqual(actions, 1)
        XCTAssertEqual(observations, 5)
        XCTAssertGreaterThan(now, 0)
    }

    func testSettingsCloseRefusesMissingOrDifferentInitialWindow() {
        for observed: UInt32? in [nil, 18] {
            assertFailure(.staleTarget) {
                _ = try closeSettingsWindow(
                    windowID: 17, budget: PollBudget(timeout: 1), pause: { _ in },
                    transport: SettingsCloseTransport(
                        observe: { observed }, actionNames: { XCTFail("No action discovery"); return [] },
                        perform: { _ in XCTFail("No close action") }
                    )
                )
            }
        }
    }

    func testSettingsCloseRequiresOneAdvertisedNativePress() {
        for names in [[], ["AXRaise"], ["AXPress", "AXPress"], Array(repeating: "AXPress", count: 601)] {
            assertFailure(.unsupportedControl) {
                _ = try closeSettingsWindow(
                    windowID: 17, budget: PollBudget(timeout: 1), pause: { _ in },
                    transport: SettingsCloseTransport(
                        observe: { 17 }, actionNames: { names }, perform: { _ in XCTFail("No close action") }
                    )
                )
            }
        }
    }

    func testSettingsCloseRechecksIdentityBeforeDispatchAndDuringWait() {
        for changeAt in [2, 3] {
            var observations = 0
            var actions = 0
            assertFailure(.staleTarget) {
                _ = try closeSettingsWindow(
                    windowID: 17, budget: PollBudget(timeout: 1), pause: { _ in },
                    transport: SettingsCloseTransport(
                        observe: { observations += 1; return observations >= changeAt ? 18 : 17 },
                        actionNames: { ["AXPress"] }, perform: { _ in actions += 1 }
                    )
                )
            }
            XCTAssertEqual(actions, changeAt == 2 ? 0 : 1)
        }
    }

    func testSettingsCloseDoesNotRetryFailedNativeDispatch() {
        var observations = 0
        var actions = 0
        assertFailure(.accessibilityFailed) {
            _ = try closeSettingsWindow(
                windowID: 17, budget: PollBudget(timeout: 1), pause: { _ in },
                transport: SettingsCloseTransport(
                    observe: { observations += 1; return 17 }, actionNames: { ["AXPress"] },
                    perform: { _ in actions += 1; throw ControlFailure(.accessibilityFailed, "fixture") }
                )
            )
        }
        XCTAssertEqual(actions, 1)
        XCTAssertEqual(observations, 2)
    }

    func testSettingsCloseRefusedWindowTimesOutWithoutFalseSuccess() {
        var now: TimeInterval = 0
        var actions = 0
        assertFailure(.timeout) {
            _ = try closeSettingsWindow(
                windowID: 17, budget: PollBudget(timeout: 0.5, now: { now }), pause: { now += $0 },
                transport: SettingsCloseTransport(
                    observe: { 17 }, actionNames: { ["AXPress"] }, perform: { _ in actions += 1 }
                )
            )
        }
        XCTAssertEqual(actions, 1)
    }

    func testSettingsCloseLateReadsDiscoveryAndDispatchNeverSucceed() {
        for phase in ["firstRead", "discovery", "dispatch", "finalRead"] {
            var now: TimeInterval = 0
            var observations = 0
            var actions = 0
            assertFailure(.timeout) {
                _ = try closeSettingsWindow(
                    windowID: 17, budget: PollBudget(timeout: 0.5, now: { now }), pause: { now += $0 },
                    transport: SettingsCloseTransport(
                        observe: {
                            observations += 1
                            if phase == "firstRead" || (phase == "finalRead" && observations == 3) { now = 1 }
                            return observations < 3 ? 17 : nil
                        },
                        actionNames: { if phase == "discovery" { now = 1 }; return ["AXPress"] },
                        perform: { _ in actions += 1; if phase == "dispatch" { now = 1 } }
                    )
                )
            }
            XCTAssertEqual(actions, ["dispatch", "finalRead"].contains(phase) ? 1 : 0)
        }
    }

    func testSettingsClosePropagatesPermissionLossAndRejectsZeroID() {
        var observations = 0
        assertFailure(.permissionDenied) {
            _ = try closeSettingsWindow(
                windowID: 17, budget: PollBudget(timeout: 1), pause: { _ in },
                transport: SettingsCloseTransport(
                    observe: {
                        observations += 1
                        if observations == 3 { throw ControlFailure(.permissionDenied, "fixture") }
                        return 17
                    },
                    actionNames: { ["AXPress"] }, perform: { _ in }
                )
            )
        }
        assertFailure(.invalidInput) {
            _ = try closeSettingsWindow(
                windowID: 0, budget: PollBudget(timeout: 1), pause: { _ in },
                transport: SettingsCloseTransport(
                    observe: { XCTFail("No observation"); return nil },
                    actionNames: { [] }, perform: { _ in XCTFail("No close action") }
                )
            )
        }
    }
}
