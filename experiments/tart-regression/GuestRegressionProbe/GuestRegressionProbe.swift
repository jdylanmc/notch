import AppKit
import CoreGraphics
import CryptoKit
import Darwin
import Foundation
import Vision
import XCTest

final class GuestRegressionProbe: XCTestCase {
    private enum Blocked: Error {
        case reason(String)
    }

    @MainActor
    private final class RunState {
        var verdict = "BLOCKED"
        var reason = "preconditions_not_established"
        var cleanup = "not_needed"
        var screenshotHash: String?
        var candidateVerified = false
        var nativeError: [String: Any]?
        var observed: [String: Bool] = [:]
        var window: XCUIElement?
        var app: XCUIApplication?
        var originalPID: pid_t?
        var needsRestoration = false
        var originalPane: String?
        var originalBuildVisible: Bool?
        var buildLabel = ""
        var attemptedSettingsOpen = false
        var openedSettings = false
        var pointerReturn: XCUICoordinate?
        var discovery: [String: Any] = [:]
        var appearanceContentFrame: CGRect?
        var appearanceControls: [String: Bool] = [:]
        var settingsCaptures: [[String: Any]] = []
        var originalGeneralScroll: [CGRect]?
    }

    private let candidate = URL(fileURLWithPath: "/Applications/notch-pocket.app")
    private var expectedHash: String {
        ProcessInfo.processInfo.environment["NOTCH_VM_EXPECTED_SHA256"] ?? ""
    }

    private func require(_ condition: Bool, _ reason: String) throws {
        guard condition else { throw Blocked.reason(reason) }
    }

    private func hardwareModel() throws -> String {
        var size = 0
        try require(sysctlbyname("hw.model", nil, &size, nil, 0) == 0, "hardware_model_unavailable")
        var bytes = [CChar](repeating: 0, count: size)
        try require(sysctlbyname("hw.model", &bytes, &size, nil, 0) == 0, "hardware_model_unavailable")
        return String(cString: bytes)
    }

    private func candidateHash() throws -> String {
        let data = try Data(contentsOf: candidate.appendingPathComponent("Contents/MacOS/notch-pocket"))
        return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    private func currentCandidatePID() -> pid_t? {
        let running = NSRunningApplication.runningApplications(withBundleIdentifier: "com.jdylanmc.notchpocket")
        guard running.count == 1, running[0].bundleURL == candidate else { return nil }
        return running[0].processIdentifier
    }

    @MainActor
    private func waitHittable(_ element: XCUIElement) -> Bool {
        let ready = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "exists == true AND hittable == true"), object: element
        )
        return XCTWaiter.wait(for: [ready], timeout: 5) == .completed
    }

    @MainActor
    private func restore(_ state: RunState) {
        state.cleanup = state.needsRestoration || state.attemptedSettingsOpen ? "pending" : "not_needed"
        state.pointerReturn?.hover()
        if state.needsRestoration, let settings = state.window {
            let targetPane = state.openedSettings ? "General" : state.originalPane
            guard let targetPane else {
                state.cleanup = "blocked"
                return
            }
            guard currentCandidatePID() == state.originalPID && settings.exists else {
                state.cleanup = "blocked"
                return
            }
            let row = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: targetPane).firstMatch
            let control = row.staticTexts[targetPane]
            let alreadySelected = row.exists && row.isSelected
            state.discovery["restorationPaneAlreadySelected"] = alreadySelected
            if !alreadySelected {
                guard waitHittable(control) else {
                    state.cleanup = "blocked"
                    return
                }
                control.click()
            }
            let selected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "selected == true"), object: row)
            guard XCTWaiter.wait(for: [selected], timeout: 5) == .completed else {
                state.cleanup = "blocked"
                return
            }
            if let original = state.originalGeneralScroll {
                do {
                    let form = try settingsForm(settings, scenario: .general)
                    let current = try form.snapshot().children
                        .filter { $0.elementType != .scrollBar && !$0.frame.isEmpty }.map(\.frame)
                    guard let first = current.first, let target = original.first else {
                        state.cleanup = "blocked"
                        return
                    }
                    form.scroll(byDeltaX: 0, deltaY: target.minY - first.minY)
                    let restored = try form.snapshot().children
                        .filter { $0.elementType != .scrollBar && !$0.frame.isEmpty }.map(\.frame)
                    state.discovery["generalScrollRestored"] = restored == original
                    guard restored == original else {
                        state.cleanup = "blocked"
                        return
                    }
                } catch {
                    state.cleanup = "blocked"
                    return
                }
            }
            if state.openedSettings {
                let close = settings.buttons[XCUIIdentifierCloseWindow]
                guard waitHittable(close) else {
                    state.cleanup = "blocked"
                    return
                }
                close.click()
                let closed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: settings)
                state.cleanup = XCTWaiter.wait(for: [closed], timeout: 5) == .completed ? "restored_closed_settings" : "blocked"
            } else {
                if let originalBuildVisible = state.originalBuildVisible {
                    let build = settings.staticTexts[state.buildLabel]
                    if build.exists != originalBuildVisible {
                        let version = settings.staticTexts["Version"]
                        guard waitHittable(version) else {
                            state.cleanup = "blocked"
                            return
                        }
                        version.click()
                    }
                    let restored = XCTNSPredicateExpectation(
                        predicate: NSPredicate(format: "exists == %@", NSNumber(value: originalBuildVisible)), object: build
                    )
                    guard XCTWaiter.wait(for: [restored], timeout: 5) == .completed else {
                        state.cleanup = "blocked"
                        return
                    }
                }
                state.cleanup = "restored_original_state"
            }
        } else if state.attemptedSettingsOpen {
            state.cleanup = "blocked"
        }
    }

    @MainActor
    private func finish(_ state: RunState, runID: String, mode: String, testName: String) {
        let primaryVerdict = state.verdict
        let primaryReason = state.reason
        let nativeFailures = testRun?.failureCount ?? 0
        if nativeFailures > 0 && state.reason == "preconditions_not_established" {
            state.reason = "native_interaction_aborted"
        }
        if state.cleanup == "pending" || state.cleanup == "blocked" {
            state.verdict = "BLOCKED"
            state.reason = "restoration_unverified"
        }
        if state.needsRestoration {
            do {
                try require(try candidateHash() == expectedHash, "candidate_integrity_changed")
            } catch {
                state.verdict = "BLOCKED"
                state.reason = "candidate_integrity_unverified"
            }
        }
        var receipt: [String: Any] = [
            "runID": runID, "scenario": mode, "verdict": state.verdict, "reason": state.reason,
            "testIdentifier": "GuestRegressionProbe/GuestRegressionProbe/\(testName)",
            "cleanup": state.cleanup, "expectedCandidateSHA256": expectedHash,
            "candidateVerified": state.candidateVerified, "observedPublicText": state.observed,
            "openedSettings": state.openedSettings, "discovery": state.discovery,
            "originalPane": state.originalPane ?? "closed",
            "primaryVerdict": primaryVerdict, "primaryReason": primaryReason,
            "nativeFailureCountBeforeReport": nativeFailures
        ]
        if let hash = state.screenshotHash { receipt["screenshotSHA256"] = hash }
        if !state.settingsCaptures.isEmpty, let scenario = SettingsRemovalScenario(rawValue: mode) {
            receipt[scenario.captureVersionKey] = 1
            receipt["captures"] = state.settingsCaptures
        }
        if let error = state.nativeError { receipt["nativeError"] = error }
        do {
            let data = try JSONSerialization.data(withJSONObject: receipt, options: [.sortedKeys])
            print("NOTCH_VM_RESULT " + String(decoding: data, as: UTF8.self))
        } catch {
            XCTFail("BLOCKED: result_serialization_failed")
            return
        }
        if state.verdict != "PASS" && nativeFailures == 0 { XCTFail("\(state.verdict): \(state.reason)") }
    }

    @MainActor
    func testInstalledAboutOutput() {
        runInstalledSettingsOutput(testName: "testInstalledAboutOutput", modes: [
            "visual-pass", "visual-fail", "stale-evidence", "visual-no-reveal",
            "native-abort-after-open", "native-abort-after-about"
        ])
    }

    @MainActor
    func testInstalledAppearanceWithoutIdleFace() {
        runInstalledSettingsOutput(testName: "testInstalledAppearanceWithoutIdleFace",
                                   modes: ["appearance-idle-face-removed"])
    }

    @MainActor
    func testInstalledNotificationsWithoutAIReplies() {
        runInstalledSettingsOutput(testName: "testInstalledNotificationsWithoutAIReplies",
                                   modes: ["notifications-ai-replies-removed"])
    }

    @MainActor
    func testInstalledGeneralWithoutHaptics() {
        runInstalledSettingsOutput(testName: "testInstalledGeneralWithoutHaptics",
                                   modes: ["general-haptics-removed"])
    }

    @MainActor
    func testInstalledGeneralWithoutPanelSwipes() {
        runInstalledSettingsOutput(testName: "testInstalledGeneralWithoutPanelSwipes",
                                   modes: ["general-panel-swipes-removed"])
    }

    @MainActor
    func testInstalledGeneralWithoutCompactMode() {
        runInstalledSettingsOutput(testName: "testInstalledGeneralWithoutCompactMode",
                                   modes: ["general-compact-mode-removed"])
    }

    @MainActor
    private func settingsForm(_ settings: XCUIElement, scenario: SettingsRemovalScenario) throws -> XCUIElement {
        let scrollViews = settings.scrollViews.allElementsBoundByIndex
        let sidebars = scrollViews.filter { $0.outlines.count == 1 }
        let forms = scrollViews.filter { $0.outlines.count == 0 }
        try require(sidebars.count == 1 && forms.count == 1, "\(scenario.prefix)_form_ambiguous")
        let form = forms[0]
        try require(form.frame.minX >= sidebars[0].frame.maxX && settings.frame.contains(form.frame),
                    "\(scenario.prefix)_form_mapping_unverified")
        return form
    }

    @MainActor
    private func inspectScrollableSettings(
        _ settings: XCUIElement, scenario: SettingsRemovalScenario, state: RunState, runID: String
    ) throws {
        let prefix = scenario.prefix
        if scenario.pane == "General" {
            if state.originalPane == "General" {
                let originalForm = try settingsForm(settings, scenario: .general)
                let frames = try originalForm.snapshot().children
                    .filter { $0.elementType != .scrollBar && !$0.frame.isEmpty }.map(\.frame)
                try require(!frames.isEmpty, "general_original_scroll_unavailable")
                state.originalGeneralScroll = frames
            }
            let aboutRow = settings.descendants(matching: .outlineRow)
                .containing(.staticText, identifier: "About").firstMatch
            let about = aboutRow.staticTexts["About"]
            try require(waitHittable(about), "general_navigation_control_unavailable")
            about.click()
            let away = XCTNSPredicateExpectation(predicate: NSPredicate(format: "selected == true"), object: aboutRow)
            try require(XCTWaiter.wait(for: [away], timeout: 5) == .completed, "general_navigation_not_observed")
            state.discovery["generalNavigationObserved"] = true
        }
        let row = settings.descendants(matching: .outlineRow)
            .containing(.staticText, identifier: scenario.pane).firstMatch
        let pane = row.staticTexts[scenario.pane]
        try require(waitHittable(pane), "\(prefix)_control_unavailable")
        pane.click()
        let selected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "selected == true"), object: row)
        try require(XCTWaiter.wait(for: [selected], timeout: 5) == .completed, "\(prefix)_selection_not_observed")
        state.discovery[prefix + "PaneSelected"] = row.isSelected
        try require(settings.frame.width >= 700 && settings.frame.height >= 600, "\(prefix)_window_too_small")
        let form = try settingsForm(settings, scenario: scenario)
        state.discovery[prefix + "FormMapped"] = true

        let windowFrame = settings.frame
        let formFrame = form.frame
        try require(NSScreen.screens.count == 1, "\(prefix)_single_display_required")
        let display = CGDisplayBounds(CGMainDisplayID())
        try require(display.contains(windowFrame), "\(prefix)_window_offscreen")
        func windowID() throws -> Int {
            try require(currentCandidatePID() == state.originalPID && row.isSelected
                        && settings.frame == windowFrame && form.frame == formFrame,
                        "\(prefix)_capture_identity_changed")
            let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                                     kCGNullWindowID) as? [[String: Any]] ?? []
            let matches = windows.filter {
                guard $0[kCGWindowOwnerPID as String] as? Int == Int(state.originalPID ?? -1),
                      let bounds = $0[kCGWindowBounds as String] as? NSDictionary,
                      let frame = CGRect(dictionaryRepresentation: bounds) else { return false }
                return frame == windowFrame
            }
            try require(matches.count == 1, "\(prefix)_native_window_ambiguous")
            guard let identifier = matches[0][kCGWindowNumber as String] as? Int else {
                throw Blocked.reason("\(prefix)_native_window_unavailable")
            }
            return identifier
        }
        let identifier = try windowID()
        func content() throws -> [XCUIElementSnapshot] {
            let snapshot = try form.snapshot()
            let items = snapshot.children.filter { $0.elementType != .scrollBar && !$0.frame.isEmpty }
            try require(snapshot.frame == formFrame && !items.isEmpty && items.count <= 100
                        && items.allSatisfy {
                            $0.frame.minX >= formFrame.minX && $0.frame.maxX <= formFrame.maxX
                                && $0.frame.minY.isFinite && $0.frame.maxY.isFinite
                        }, "\(prefix)_content_geometry_unavailable")
            return items
        }
        func rect(_ frame: CGRect) -> [String: CGFloat] {
            ["x": frame.minX, "y": frame.minY, "width": frame.width, "height": frame.height]
        }
        func normalized(_ frame: CGRect) -> CGRect {
            CGRect(x: (frame.minX - windowFrame.minX) / windowFrame.width,
                   y: (windowFrame.maxY - frame.maxY) / windowFrame.height,
                   width: frame.width / windowFrame.width, height: frame.height / windowFrame.height)
        }
        var endpointContent: [[XCUIElementSnapshot]] = []
        var outputs: [[String: Bool]] = []
        for (role, delta) in [("top", 10_000.0), ("bottom", -10_000.0)] {
            form.scroll(byDeltaX: 0, deltaY: delta)
            let first = try content()
            form.scroll(byDeltaX: 0, deltaY: delta)
            let confirmed = try content()
            try require(first.map(\.frame) == confirmed.map(\.frame)
                        && first.map(\.elementType) == confirmed.map(\.elementType),
                        "\(prefix)_scroll_endpoint_unverified")
            let frames = confirmed.map(\.frame)
            try require(role == "top" ? frames.allSatisfy { $0.minY >= formFrame.minY }
                        : frames.allSatisfy { $0.maxY <= formFrame.maxY },
                        "\(prefix)_scroll_endpoint_incomplete")
            try require(try windowID() == identifier, "\(prefix)_capture_identity_changed")

            // General's Launch at login/Remember last tab also expose static-text AXValue, not checkbox titles.
            // Disabled text can still render. Interaction eligibility is not presence.
            var controls: [String: Bool] = [:]
            var labelFrames: [String: CGRect] = [:]
            for label in scenario.retainedLabels {
                let matches = form.staticTexts.matching(identifier: label)
                let visible = matches.count == 1 && !matches.firstMatch.frame.isEmpty
                    && formFrame.contains(matches.firstMatch.frame)
                controls[label] = visible
                if visible { labelFrames[label] = normalized(matches.firstMatch.frame) }
            }
            controls[scenario.absenceKey] = scenario.removedLabelsAbsent { form.staticTexts[$0].exists }
            let capture = settings.screenshot()
            try require(try windowID() == identifier, "\(prefix)_capture_identity_changed")
            let after = try content()
            try require(after.map(\.frame) == frames
                        && after.map(\.elementType) == confirmed.map(\.elementType),
                        "\(prefix)_capture_content_changed")
            guard let image = capture.image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
                throw Blocked.reason("capture_pixels_unavailable")
            }
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.recognitionLanguages = ["en-US"]
            request.usesLanguageCorrection = false
            try VNImageRequestHandler(cgImage: image).perform([request])
            let observations = (request.results ?? []).compactMap { observation -> AboutOutputOracle.Observation? in
                guard let text = observation.topCandidates(1).first?.string else { return nil }
                return AboutOutputOracle.Observation(text: text, frame: observation.boundingBox)
            }
            try require(!observations.isEmpty, "ocr_unavailable")
            let observed = SettingsRemovalOutputOracle.evaluate(
                observations, scenario: scenario, contentFrame: normalized(formFrame),
                controls: controls, labelFrames: labelFrames, pixelWidth: image.width,
                windowWidthPoints: windowFrame.width
            )
            let name = "guest-public-\(prefix)-\(runID)-\(role)"
            let hash = SHA256.hash(data: capture.pngRepresentation).map { String(format: "%02x", $0) }.joined()
            let attachment = XCTAttachment(screenshot: capture)
            attachment.name = name
            attachment.lifetime = .keepAlways
            add(attachment)
            state.settingsCaptures.append([
                "role": role, "name": name, "sha256": hash, "runID": runID,
                "scenario": scenario.rawValue,
                "testIdentifier": "GuestRegressionProbe/GuestRegressionProbe/\(scenario.testName)",
                "candidateSHA256": expectedHash, "candidatePID": Int(state.originalPID ?? -1),
                "appPath": candidate.path,
                "windowID": identifier, "windowMarker": "NotchPocketSettingsWindow", "pane": scenario.pane,
                "windowFrame": rect(windowFrame), "formFrame": rect(formFrame),
                "contentFrames": frames.map(rect), "endpointFrames": first.map { rect($0.frame) },
                "contentTypes": confirmed.map { $0.elementType.rawValue },
                "labelFrames": labelFrames.mapValues(rect), "observedPublicText": observed,
                "pixelWidth": image.width, "pixelHeight": image.height
            ])
            endpointContent.append(confirmed)
            outputs.append(observed)
        }
        let head = endpointContent[0]
        let tail = endpointContent[1]
        let offset = head[0].frame.minY - tail[0].frame.minY
        let overlap = formFrame.height - offset
        try require(head.count == tail.count && offset >= 0 && overlap >= 64
                    && zip(head, tail).allSatisfy {
                        $0.elementType == $1.elementType
                            && $0.frame.offsetBy(dx: 0, dy: -offset) == $1.frame
                    }, "\(prefix)_scroll_coverage_incomplete")
        state.discovery[prefix + "ScrollComplete"] = true
        state.discovery[prefix + "ScrollOffsetPoints"] = offset
        state.discovery[prefix + "OverlapPoints"] = overlap
        state.observed = SettingsRemovalOutputOracle.combine(outputs, scenario: scenario)
    }

    @MainActor
    private func inspectAppearance(_ settings: XCUIElement, state: RunState) throws {
        let row = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: "Appearance").firstMatch
        let appearance = row.staticTexts["Appearance"]
        try require(waitHittable(appearance), "appearance_control_unavailable")
        appearance.click()
        let selected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "selected == true"), object: row)
        try require(XCTWaiter.wait(for: [selected], timeout: 5) == .completed, "appearance_selection_not_observed")
        state.discovery["appearancePaneSelected"] = row.isSelected
        try require(settings.frame.width >= 700 && settings.frame.height >= 600, "appearance_window_too_small")
        let scrollViews = settings.scrollViews.allElementsBoundByIndex
        let sidebars = scrollViews.filter { $0.outlines.count == 1 }
        let forms = scrollViews.filter { $0.outlines.count == 0 }
        try require(sidebars.count == 1 && forms.count == 1, "appearance_form_ambiguous")
        let form = forms[0]
        try require(form.frame.minX >= sidebars[0].frame.maxX && settings.frame.contains(form.frame),
                    "appearance_form_mapping_unverified")
        state.discovery["appearanceFormMapped"] = true

        // SwiftUI row text uses AXValue; section headers use AXLabel on the same static-text class.
        func header(_ title: String) -> XCUIElementQuery {
            form.staticTexts.matching(NSPredicate(format: "label == %@", title))
        }
        try require(header("General").count == 1 && header("Media").count == 1,
                    "appearance_section_header_class_unverified")
        state.discovery["appearanceSectionHeaderClassVerified"] = true

        // One capture is valid only when the whole form fits at both native scroll endpoints.
        // This guard uses container geometry, never the controls whose presence is under test.
        func contentFrames() throws -> [CGRect] {
            let snapshot = try form.snapshot()
            let content = snapshot.children.filter { $0.elementType != .scrollBar && !$0.frame.isEmpty }
            try require(!content.isEmpty && content.allSatisfy { snapshot.frame.contains($0.frame) },
                        "appearance_full_form_not_visible")
            return content.map(\.frame)
        }
        form.scroll(byDeltaX: 0, deltaY: 10_000)
        let headFrames = try contentFrames()
        form.scroll(byDeltaX: 0, deltaY: -10_000)
        let tailFrames = try contentFrames()
        try require(headFrames == tailFrames, "appearance_full_form_not_visible")
        state.discovery["appearanceFullFormVisible"] = true
        let frame = form.frame
        let windowFrame = settings.frame
        state.appearanceContentFrame = CGRect(
            x: (frame.minX - windowFrame.minX) / windowFrame.width,
            y: (windowFrame.maxY - frame.maxY) / windowFrame.height,
            width: frame.width / windowFrame.width, height: frame.height / windowFrame.height
        )
        state.appearanceControls = Dictionary(uniqueKeysWithValues: AppearanceOutputOracle.retainedLabels.map {
            let controls = form.staticTexts.matching(identifier: $0)
            return ($0, controls.count == 1 && controls.firstMatch.isHittable)
        })
        state.appearanceControls["faceControlAbsent"] =
            !form.staticTexts[AppearanceOutputOracle.faceLabel].exists
        state.appearanceControls["additionalFeaturesAbsent"] = header("Additional features").count == 0
    }

    @MainActor
    private func runInstalledSettingsOutput(testName: String, modes: [String]) {
        continueAfterFailure = false
        let state = RunState()
        let environment = ProcessInfo.processInfo.environment
        let runID = environment["NOTCH_VM_RUN_ID"] ?? ""
        let mode = environment["NOTCH_VM_SCENARIO"] ?? ""
        let expectedVersion = environment["NOTCH_VM_EXPECTED_VERSION"] ?? ""
        let expectedBuild = environment["NOTCH_VM_EXPECTED_BUILD"] ?? ""
        let buildLabel = "(\(expectedBuild))"
        state.buildLabel = buildLabel

        // Teardown is LIFO: emit even if native XCTest unwinding aborts restoration.
        addTeardownBlock { @MainActor in self.finish(state, runID: runID, mode: mode, testName: testName) }
        addTeardownBlock { @MainActor in self.restore(state) }

        do {
            try require(try hardwareModel().hasPrefix("VirtualMac"), "host_execution_refused")
            guard let session = CGSessionCopyCurrentDictionary() as? [String: Any] else {
                throw Blocked.reason("guest_session_unavailable")
            }
            try require(session["CGSSessionScreenIsLocked"] as? Bool != true, "guest_locked")
            try require(session[kCGSessionOnConsoleKey as String] as? Bool == true
                        && session[kCGSessionLoginDoneKey as String] as? Bool == true, "guest_graphical_session_unavailable")
            try require(UUID(uuidString: runID) != nil, "run_identity_missing")
            try require(expectedHash.range(of: "^[a-f0-9]{64}$", options: .regularExpression) != nil
                        && !expectedVersion.isEmpty && !expectedBuild.isEmpty, "candidate_expectations_missing")
            try require(Set(["Release name", "Notch Pocket", "Version", expectedVersion, buildLabel]).count == 5,
                        "candidate_expectations_ambiguous")
            try require(modes.contains(mode), "scenario_invalid")
            try require(try candidateHash() == expectedHash, "candidate_hash_mismatch")
            let bundle = Bundle(url: candidate)
            try require(bundle?.bundleIdentifier == "com.jdylanmc.notchpocket"
                        && bundle?.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String == expectedVersion
                        && bundle?.object(forInfoDictionaryKey: "CFBundleVersion") as? String == expectedBuild,
                        "candidate_metadata_mismatch")
            state.candidateVerified = true
            state.originalPID = currentCandidatePID()
            try require(state.originalPID != nil, "exact_running_candidate_required")

            let application = XCUIApplication(url: candidate)
            state.app = application
            application.activate()
            let matches = application.descendants(matching: .any).matching(identifier: "NotchPocketSettingsWindow")
            state.discovery = ["initialSettingsMarkerCount": matches.count]
            let settings = matches.firstMatch
            state.window = settings
            if !settings.exists {
                state.attemptedSettingsOpen = true
                let panels = application.dialogs.matching(
                    NSPredicate(format: "identifier BEGINSWITH %@", "com.jdylanmc.notchpocket.notch.v1.window.")
                )
                try require(panels.count == 1, "exact_notch_panel_required")
                let panel = panels.firstMatch
                let frame = panel.frame
                guard let pointer = CGEvent(source: nil)?.location else {
                    throw Blocked.reason("guest_pointer_unavailable")
                }
                let origin = panel.coordinate(withNormalizedOffset: .zero)
                state.pointerReturn = origin.withOffset(CGVector(dx: pointer.x - frame.minX, dy: pointer.y - frame.minY))
                origin.withOffset(CGVector(dx: frame.width / 2, dy: 5)).hover()
                let gear = panel.buttons.matching(NSPredicate(format: "label IN %@ OR identifier IN %@", ["Settings", "gear"], ["Settings", "gear"]))
                let visible = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: gear.firstMatch)
                let ready = XCTWaiter.wait(for: [visible], timeout: 5) == .completed
                try require(gear.count == 1 && ready, "notch_settings_gear_unavailable")
                gear.firstMatch.click()
                try require(settings.waitForExistence(timeout: 5), "settings_open_not_observed")
                state.openedSettings = true
                state.needsRestoration = true
                state.pointerReturn?.hover()
                state.pointerReturn = nil
            }
            try require(matches.count == 1, "settings_marker_ambiguous")
            let generalRow = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: "General").firstMatch
            if !state.openedSettings {
                let aboutRow = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: "About").firstMatch
                if generalRow.exists && generalRow.isSelected {
                    state.originalPane = "General"
                } else if aboutRow.exists && aboutRow.isSelected {
                    state.originalPane = "About"
                    state.originalBuildVisible = settings.staticTexts[buildLabel].exists
                } else {
                    throw Blocked.reason("unsupported_original_settings_pane")
                }
            }
            state.needsRestoration = true
            if mode == "native-abort-after-open" {
                state.reason = "native_interaction_aborted"
                XCTFail("Controlled native XCTest failure after Settings opened")
                return
            }
            if generalRow.exists && !generalRow.isSelected {
                let general = generalRow.staticTexts["General"]
                try require(waitHittable(general), "general_control_unavailable")
                general.click()
                let selected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "selected == true"), object: generalRow)
                try require(XCTWaiter.wait(for: [selected], timeout: 5) == .completed, "general_selection_not_observed")
            }
            try require(generalRow.exists && generalRow.isSelected, "prepared_general_pane_required")
            if mode == "appearance-idle-face-removed" {
                try inspectAppearance(settings, state: state)
            } else if let scenario = SettingsRemovalScenario(rawValue: mode) {
                try inspectScrollableSettings(settings, scenario: scenario, state: state, runID: runID)
                state.verdict = state.observed.values.allSatisfy { $0 } ? "PASS" : "FAIL"
                state.reason = state.verdict == "PASS" ? "rendered_output_verified" : "rendered_output_mismatch"
                return
            } else {
                let about = settings.descendants(matching: .outlineRow)
                    .containing(.staticText, identifier: "About").firstMatch.staticTexts["About"]
                try require(waitHittable(about), "about_control_unavailable")
                about.click()
                let version = settings.staticTexts["Version"]
                try require(waitHittable(version), "version_control_unavailable")
                if mode == "native-abort-after-about" {
                    state.reason = "native_interaction_aborted"
                    XCTFail("Controlled native XCTest failure after About selected")
                    return
                }
                let revealed = settings.staticTexts[buildLabel]
                if mode != "visual-no-reveal" { version.click() }
                let buildObserved = mode != "visual-no-reveal" && revealed.waitForExistence(timeout: 3)
                state.discovery["buildRevealObserved"] = buildObserved
                if mode == "visual-fail" {
                    try require(buildObserved, "negative_control_prerequisite_missing")
                    version.click()
                    let hidden = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: revealed)
                    _ = XCTWaiter.wait(for: [hidden], timeout: 3)
                }
            }

            try require(currentCandidatePID() == state.originalPID, "candidate_process_changed")
            let capture = settings.screenshot()
            let capturedRunID = mode == "stale-evidence" ? "deliberately-wrong-run" : runID
            try require(capturedRunID == runID, "capture_identity_mismatch")
            state.screenshotHash = SHA256.hash(data: capture.pngRepresentation).map { String(format: "%02x", $0) }.joined()
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.recognitionLanguages = ["en-US"]
            request.usesLanguageCorrection = false
            guard let image = capture.image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
                throw Blocked.reason("capture_pixels_unavailable")
            }
            try VNImageRequestHandler(cgImage: image).perform([request])
            let observations = (request.results ?? []).compactMap { observation -> AboutOutputOracle.Observation? in
                guard let text = observation.topCandidates(1).first?.string else { return nil }
                return AboutOutputOracle.Observation(text: text, frame: observation.boundingBox)
            }
            try require(!observations.isEmpty, "ocr_unavailable")
            if mode == "appearance-idle-face-removed" {
                guard let contentFrame = state.appearanceContentFrame else {
                    throw Blocked.reason("appearance_content_frame_unavailable")
                }
                state.observed = AppearanceOutputOracle.evaluate(
                    observations, contentFrame: contentFrame, controls: state.appearanceControls
                )
            } else {
                state.observed = AboutOutputOracle.evaluate(observations, version: expectedVersion, build: expectedBuild)
            }
            let attachment = XCTAttachment(screenshot: capture)
            let pane: String
            switch mode {
            case "appearance-idle-face-removed": pane = "appearance"
            default: pane = "about"
            }
            attachment.name = "guest-public-\(pane)-\(runID)"
            attachment.lifetime = .keepAlways
            add(attachment)
            state.verdict = state.observed.values.allSatisfy { $0 } ? "PASS" : "FAIL"
            state.reason = state.verdict == "PASS" ? "rendered_output_verified" : "rendered_output_mismatch"
        } catch Blocked.reason(let reason) {
            state.reason = reason
        } catch {
            state.reason = "native_or_evidence_error"
            let error = error as NSError
            state.nativeError = ["domain": error.domain, "code": error.code]
        }
    }
}
