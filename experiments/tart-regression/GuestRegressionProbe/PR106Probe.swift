// Test-only native supplement. Bounded control/capture patterns adapted from the
// unaccepted PanelNavigationProbe prior art; no product imports or fixture hooks.
import AppKit
import ApplicationServices
import CoreGraphics
import CryptoKit
import Darwin
import Vision
import XCTest

final class PR106Probe: XCTestCase {
    private enum Refusal: Error { case reason(String) }
    private let candidate = URL(fileURLWithPath: "/Applications/notch-pocket.app")
    private let marker = "com.jdylanmc.notchpocket.notch.v1."
    private let producerID = "com.jdylanmc.notchpocket.regression.mediafixture"
    private var environment: [String: String] { ProcessInfo.processInfo.environment }
    private var expectedHash: String { environment["NOTCH_VM_EXPECTED_SHA256"] ?? "" }

    @MainActor
    private final class Journey {
        var app: XCUIApplication?
        var panel: XCUIElement?
        var settings: XCUIElement?
        var pid: pid_t = -1
        var windowID = 0
        var frame = CGRect.zero
        var pointer = CGPoint.zero
        var foreground: NSRunningApplication?
        var touched = false
        var openedSettings = false
        var openedSettingsPane: String?
        var originalTab: String?
        var originalHover: Bool?
        var changedHover = false
        var preferences: [String: Bool] = [:]
        var scroll: [String: [CGRect]] = [:]
        var fixture: [String: Any] = [:]
        var producer: XCUIApplication?
        var producerPID: pid_t = -1
        var producerTouched = false
        var transport: [String: CGRect] = [:]
        var captures: [[String: Any]] = []
        var observed: [String: Bool] = [:]
        var transitions: [String: Bool] = [:]
        var engineSamples: [[String: Any]] = []
        var restoration: [String: Bool] = [:]
        var discovery: [String: Any] = [:]
        var errors: [String: String] = [:]
        var verdict = "BLOCKED"
        var reason = "preconditions_not_established"
    }

    @MainActor func testPanel() { run(media: false) }
    @MainActor func testMedia() { run(media: true) }

    private func require(_ value: Bool, _ reason: String) throws {
        if !value { throw Refusal.reason(reason) }
    }

    private func hash(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    private func fileHash(_ url: URL) throws -> String { hash(try Data(contentsOf: url)) }

    private func running(_ url: URL, identifier: String) -> pid_t? {
        let matches = NSRunningApplication.runningApplications(withBundleIdentifier: identifier)
        guard matches.count == 1, matches[0].bundleURL == url else { return nil }
        return matches[0].processIdentifier
    }

    @MainActor
    private func wait(_ seconds: TimeInterval = 3, _ condition: @escaping () -> Bool) -> Bool {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in condition() }, object: nil)
        return XCTWaiter.wait(for: [expectation], timeout: seconds) == .completed
    }

    @MainActor
    private func run(media: Bool) {
        continueAfterFailure = false
        let journey = Journey()
        // Report is a separate LIFO teardown: native aborts still leave an explicit restoration receipt.
        addTeardownBlock { @MainActor in self.finish(journey, media: media) }
        addTeardownBlock { @MainActor in self.restore(journey) }
        do {
            try setup(journey, media: media)
            if media { try mediaJourney(journey) } else { try panelJourney(journey) }
            journey.verdict = journey.observed.values.allSatisfy { $0 } ? "PASS" : "FAIL"
            journey.reason = journey.verdict == "PASS" ? "rendered_output_verified" : "rendered_output_mismatch"
        } catch Refusal.reason(let reason) {
            if journey.verdict != "FAIL" { journey.reason = reason }
            journey.errors["primary"] = reason
        } catch {
            let native = error as NSError
            if journey.verdict != "FAIL" { journey.reason = "native_or_evidence_error" }
            journey.errors["primary"] = "\(native.domain):\(native.code)"
        }
    }

    @MainActor
    private func setup(_ journey: Journey, media: Bool) throws {
        var size = 0
        try require(sysctlbyname("hw.model", nil, &size, nil, 0) == 0 && size > 0 && size < 256,
                    "hardware_model_unavailable")
        var model = [CChar](repeating: 0, count: size)
        try require(sysctlbyname("hw.model", &model, &size, nil, 0) == 0
                    && String(cString: model).hasPrefix("VirtualMac"), "host_execution_refused")
        try require(NSUserName() == "notch" && NSScreen.screens.count == 1
                    && CGDisplayBounds(CGMainDisplayID()) == CGRect(x: 0, y: 0, width: 1440, height: 900),
                    "synthetic_guest_display_required")
        guard let session = CGSessionCopyCurrentDictionary() as? [String: Any] else {
            throw Refusal.reason("guest_session_unavailable")
        }
        try require(session["CGSSessionScreenIsLocked"] as? Bool != true
                    && session[kCGSessionOnConsoleKey as String] as? Bool == true
                    && session[kCGSessionLoginDoneKey as String] as? Bool == true, "guest_session_unavailable")
        try require(CGPreflightScreenCaptureAccess() && AXIsProcessTrusted(), "existing_capture_and_accessibility_grants_required")
        let modes = media ? ["pr106-media", "pr106-media-wrong-direction", "pr106-media-wrong-pulse"]
            : ["pr106-panel", "pr106-panel-wrong-tab"]
        try require(UUID(uuidString: environment["NOTCH_VM_RUN_ID"] ?? "") != nil
                    && modes.contains(environment["NOTCH_VM_SCENARIO"] ?? "")
                    && environment["NOTCH_VM_PREPARED_INTERACTIONS"] == "1", "prepared_invocation_required")
        let bundle = Bundle(url: candidate)
        try require(try fileHash(candidate.appendingPathComponent("Contents/MacOS/notch-pocket")) == expectedHash
                    && bundle?.bundleIdentifier == "com.jdylanmc.notchpocket"
                    && bundle?.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
                        == environment["NOTCH_VM_EXPECTED_VERSION"]
                    && bundle?.object(forInfoDictionaryKey: "CFBundleVersion") as? String
                        == environment["NOTCH_VM_EXPECTED_BUILD"], "candidate_identity_mismatch")
        guard let data = environment["NOTCH_VM_INTERACTION_FIXTURE"]?.data(using: .utf8),
              let fixture = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              fixture["profile"] as? String == "synthetic-empty-light-v1",
              fixture["candidateSHA256"] as? String == expectedHash,
              fixture["guestUser"] as? String == "notch",
              fixture["ownerID"] as? String == environment["NOTCH_VM_INTERACTION_WORKER"],
              fixture["restorationPlan"] as? String == "parent-restore-owned-snapshot-after-media",
              UUID(uuidString: fixture["fixtureID"] as? String ?? "") != nil,
              UUID(uuidString: fixture["snapshotID"] as? String ?? "") != nil else {
            throw Refusal.reason("owned_synthetic_profile_attestation_required")
        }
        journey.fixture = fixture
        guard let pid = running(candidate, identifier: "com.jdylanmc.notchpocket"),
              let pointer = CGEvent(source: nil)?.location,
              let foreground = NSWorkspace.shared.frontmostApplication else {
            throw Refusal.reason("original_running_ui_required")
        }
        journey.pid = pid
        journey.pointer = pointer
        journey.foreground = foreground
        let app = XCUIApplication(url: candidate)
        journey.app = app
        let settings = app.descendants(matching: .any).matching(identifier: "NotchPocketSettingsWindow")
        try require(settings.count == 0, "closed_settings_fixture_required")
        journey.settings = settings.firstMatch
        let panels = app.dialogs.matching(NSPredicate(format: "identifier BEGINSWITH %@", marker + "window."))
        try require(panels.count == 1, "exact_marked_panel_required")
        let panel = panels.firstMatch
        journey.panel = panel
        journey.windowID = Int(panel.identifier.replacingOccurrences(of: marker + "window.", with: "")) ?? 0
        journey.frame = panel.frame
        try qualify(journey)
        try require(panel.value as? String == "closed" && !panel.frame.contains(pointer), "closed_panel_pointer_fixture_required")
        journey.touched = true
        app.activate()
        try clickOpen(journey)
        journey.originalTab = try tabs(journey).first { $0.value == "selected" }?.key
        try require(journey.originalTab == "home", "original_home_fixture_required")
        try openSettings(journey)
        _ = try form(journey, pane: "General")
        journey.originalHover = try preference(journey, pane: "General", label: "Open notch on hover")
        try require(journey.originalHover == true, "enabled_hover_fixture_required")
        try require(try preference(journey, pane: "General", label: "Compact mode") == false,
                    "standard_layout_fixture_required")
        _ = try preference(journey, pane: "General", label: "Remember last tab")
        try require(try preference(journey, pane: "Appearance", label: "Always show tabs"), "visible_tabs_fixture_required")
        try require(try preference(journey, pane: "Shelf", label: "Enable shelf"), "enabled_empty_shelf_fixture_required")
        if media {
            try require(try preference(journey, pane: "General", label: "Enable media gestures"), "media_gestures_fixture_required")
            try require(try preference(journey, pane: "General", label: "Change media with horizontal gestures"),
                        "horizontal_gestures_fixture_required")
            let mediaForm = try form(journey, pane: "Media")
            mediaForm.scroll(byDeltaX: 0, deltaY: 10_000)
            let sources = mediaForm.popUpButtons.allElementsBoundByIndex.filter {
                $0.value as? String == "Now Playing" || $0.label == "Now Playing"
            }
            try require(sources.count == 1 && mediaForm.frame.contains(sources[0].frame), "actual_now_playing_source_required")
            journey.discovery["musicSource"] = "Now Playing"
            try require(try preference(journey, pane: "Media", label: "Show music live activity"), "live_music_fixture_required")
            try require(try preference(journey, pane: "Media", label: "Show sneak peek on playback changes") == false,
                        "no_sneak_peek_fixture_required")
            try require(try preference(journey, pane: "Advanced", label: "Normalize gesture direction") == false,
                        "unnormalized_scroll_fixture_required")
            try prepareProducer(journey)
        } else {
            let shortcutForm = try form(journey, pane: "Shortcuts")
            let labels = shortcutForm.staticTexts.matching(identifier: "Toggle Notch Open:")
            try require(labels.count == 1, "shortcut_label_required")
            let label = labels.firstMatch.frame
            let keys = shortcutForm.descendants(matching: .any).allElementsBoundByIndex.filter {
                !$0.frame.isEmpty && shortcutForm.frame.contains($0.frame)
                    && $0.frame.minX >= label.maxX && abs($0.frame.midY - label.midY) < 8
            }.flatMap { [$0.label, $0.value as? String ?? ""] }
            let accepted = ["\u{21e7}\u{2318}I", "\u{2318}\u{21e7}I"]
            try require(keys.contains { accepted.contains($0.replacingOccurrences(of: " ", with: "")) },
                        "observed_command_shift_i_required")
            journey.discovery["keyboardShortcut"] = "command-shift-i"
        }
        try closeSettings(journey)
        if journey.panel?.value as? String != "open" { try clickOpen(journey) }
        try selectTab(journey, "home")
        try exitPanel(journey)
        journey.discovery["originalPreferences"] = journey.preferences
        journey.discovery["setupQualified"] = true
    }

    @MainActor
    private func qualify(_ journey: Journey) throws {
        guard let panel = journey.panel else { throw Refusal.reason("panel_unavailable") }
        try require(running(candidate, identifier: "com.jdylanmc.notchpocket") == journey.pid
                    && panel.identifier == marker + "window.\(journey.windowID)" && journey.windowID > 0
                    && panel.frame == journey.frame
                    && CGDisplayBounds(CGMainDisplayID()).contains(panel.frame), "panel_identity_changed")
        try require(journey.app?.dialogs.matching(NSPredicate(
            format: "identifier BEGINSWITH %@", marker + "window.")).count == 1, "exact_marked_panel_required")
        guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                                      kCGNullWindowID) as? [[String: Any]] else {
            throw Refusal.reason("native_window_observation_unavailable")
        }
        let selected = windows.filter { $0[kCGWindowNumber as String] as? Int == journey.windowID }
        guard selected.count == 1, let row = selected.first,
              row[kCGWindowOwnerPID as String] as? Int == Int(journey.pid),
              let sharing = row[kCGWindowSharingState as String] as? Int, sharing != 0,
              let bounds = row[kCGWindowBounds as String] as? NSDictionary,
              CGRect(dictionaryRepresentation: bounds) == journey.frame else {
            throw Refusal.reason("fresh_owned_shareable_panel_required")
        }
    }

    @MainActor
    private func at(_ journey: Journey, _ point: CGPoint) throws -> XCUICoordinate {
        try qualify(journey)
        guard let panel = journey.panel else { throw Refusal.reason("panel_unavailable") }
        return panel.coordinate(withNormalizedOffset: .zero)
            .withOffset(CGVector(dx: point.x - journey.frame.minX, dy: point.y - journey.frame.minY))
    }

    @MainActor
    private func top(_ journey: Journey) -> CGPoint {
        CGPoint(x: journey.frame.midX, y: journey.frame.minY + 5)
    }

    @MainActor
    private func panelState(_ journey: Journey, _ expected: String) -> Bool {
        wait { journey.panel?.value as? String == expected }
    }

    @MainActor
    private func clickOpen(_ journey: Journey) throws {
        try at(journey, top(journey)).click()
        try require(panelState(journey, "open"), "panel_open_not_observed")
        Thread.sleep(forTimeInterval: 0.5)
    }

    @MainActor
    private func exitPanel(_ journey: Journey) throws {
        try at(journey, journey.pointer).hover()
        try require(panelState(journey, "closed"), "panel_close_not_observed")
        Thread.sleep(forTimeInterval: 0.5)
    }

    @MainActor
    private func tabs(_ journey: Journey) throws -> [String: String] {
        guard let panel = journey.panel else { throw Refusal.reason("panel_unavailable") }
        var values: [String: String] = [:]
        for tab in ["home", "dashboard", "shelf"] {
            let matches = panel.buttons.matching(identifier: marker + "tab." + tab)
            if matches.count == 1, let value = matches.firstMatch.value as? String,
               ["selected", "unselected"].contains(value) { values[tab] = value }
        }
        return values
    }

    @MainActor
    private func selectTab(_ journey: Journey, _ name: String) throws {
        guard let panel = journey.panel else { throw Refusal.reason("panel_unavailable") }
        let button = panel.buttons[marker + "tab." + name]
        try require(button.exists && button.isHittable, "native_tab_control_required")
        button.click()
        Thread.sleep(forTimeInterval: 0.5)
    }

    @MainActor
    private func openSettings(_ journey: Journey) throws {
        guard let panel = journey.panel, let settings = journey.settings else { throw Refusal.reason("panel_unavailable") }
        if settings.exists { return }
        let gear = panel.buttons.matching(NSPredicate(format: "label IN %@ OR identifier IN %@",
                                                      ["Settings", "gear"], ["Settings", "gear"]))
        try require(gear.count == 1 && gear.firstMatch.isHittable, "settings_gear_required")
        journey.openedSettings = true
        gear.firstMatch.click()
        try require(settings.waitForExistence(timeout: 3), "settings_open_not_observed")
        if journey.openedSettingsPane == nil {
            let known = ["General", "Appearance", "Media", "Notifications", "Shelf", "Shortcuts", "Advanced", "About"]
            let selected = known.filter {
                let rows = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: $0)
                return rows.count == 1 && rows.firstMatch.isSelected
            }
            try require(selected.count == 1, "original_settings_pane_unavailable")
            journey.openedSettingsPane = selected[0]
        }
        let general = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: "General")
        try require(general.count == 1 && general.firstMatch.isSelected, "closed_general_settings_fixture_required")
    }

    @MainActor
    private func form(_ journey: Journey, pane: String) throws -> XCUIElement {
        guard let settings = journey.settings, settings.exists,
              running(candidate, identifier: "com.jdylanmc.notchpocket") == journey.pid else {
            throw Refusal.reason("settings_identity_changed")
        }
        let row = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: pane).firstMatch
        try require(row.exists && row.staticTexts[pane].isHittable, "settings_pane_required")
        if !row.isSelected { row.staticTexts[pane].click() }
        try require(wait { row.isSelected }, "settings_selection_not_observed")
        let forms = settings.scrollViews.allElementsBoundByIndex.filter { $0.outlines.count == 0 }
        try require(forms.count == 1 && settings.frame.contains(forms[0].frame), "settings_form_required")
        if journey.scroll[pane] == nil {
            let frames = try scrollFrames(forms[0])
            try require(!frames.isEmpty && frames.count <= 100, "original_scroll_required")
            journey.scroll[pane] = frames
        }
        return forms[0]
    }

    @MainActor
    private func scrollFrames(_ form: XCUIElement) throws -> [CGRect] {
        try form.snapshot().children.filter { $0.elementType != .scrollBar && !$0.frame.isEmpty }.map(\.frame)
    }

    private func toggleValue(_ value: Any?) -> Bool? {
        if let string = value as? String { return string == "1" ? true : string == "0" ? false : nil }
        if let number = value as? NSNumber { return number == 1 ? true : number == 0 ? false : nil }
        return nil
    }

    @MainActor
    private func toggle(_ journey: Journey, pane: String, label: String) throws -> XCUIElement {
        let content = try form(journey, pane: pane)
        for delta in [10_000.0, -10_000.0] {
            content.scroll(byDeltaX: 0, deltaY: CGFloat(delta))
            let labels = content.staticTexts.matching(identifier: label)
            if labels.count == 1 && content.frame.contains(labels.firstMatch.frame) && !labels.firstMatch.frame.isEmpty {
                let controls = content.checkBoxes.allElementsBoundByIndex + content.switches.allElementsBoundByIndex
                try require(controls.count <= 50, "bounded_toggle_inventory_required")
                let matches = controls.filter {
                    !$0.frame.isEmpty && content.frame.contains($0.frame)
                        && abs($0.frame.midY - labels.firstMatch.frame.midY) < 5
                }
                try require(matches.count == 1 && matches[0].isHittable, "unique_toggle_required")
                return matches[0]
            }
        }
        throw Refusal.reason("visible_preference_required")
    }

    @MainActor
    private func preference(_ journey: Journey, pane: String, label: String) throws -> Bool {
        let control = try toggle(journey, pane: pane, label: label)
        guard let value = toggleValue(control.value) else { throw Refusal.reason("actual_toggle_value_required") }
        journey.preferences[pane + ":" + label] = value
        return value
    }

    @MainActor
    private func setHover(_ journey: Journey, _ enabled: Bool) throws {
        let control = try toggle(journey, pane: "General", label: "Open notch on hover")
        guard let actual = toggleValue(control.value), journey.originalHover != nil else {
            throw Refusal.reason("original_hover_value_required")
        }
        if actual != enabled { journey.changedHover = true; control.click() }
        try require(wait { self.toggleValue(control.value) == enabled }, "hover_change_not_observed")
    }

    @MainActor
    private func closeSettings(_ journey: Journey) throws {
        guard let settings = journey.settings, settings.exists else { throw Refusal.reason("settings_required") }
        for pane in journey.scroll.keys.sorted() {
            let content = try form(journey, pane: pane)
            let current = try scrollFrames(content)
            guard let original = journey.scroll[pane], let target = original.first, let first = current.first else {
                throw Refusal.reason("original_scroll_required")
            }
            if current != original { content.scroll(byDeltaX: 0, deltaY: target.minY - first.minY) }
            try require(try scrollFrames(content) == original, "settings_scroll_restoration_unverified")
        }
        guard let originalPane = journey.openedSettingsPane else {
            throw Refusal.reason("original_settings_pane_unavailable")
        }
        // Unsupported initial panes are closed on their original pane without changing their form.
        let row = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: originalPane).firstMatch
        if !row.isSelected {
            try require(row.staticTexts[originalPane].isHittable, "original_settings_pane_unavailable")
            row.staticTexts[originalPane].click()
            try require(wait { row.isSelected }, "settings_pane_restoration_unverified")
        }
        let close = settings.buttons[XCUIIdentifierCloseWindow]
        try require(close.isHittable, "settings_close_control_required")
        close.click()
        try require(wait { !settings.exists }, "settings_close_not_observed")
    }

    @MainActor
    private func observe(_ journey: Journey, _ key: String, _ value: Bool) {
        journey.observed[key] = value
        if !value { journey.verdict = "FAIL"; journey.reason = "rendered_output_mismatch" }
    }

    @MainActor
    private func panelJourney(_ journey: Journey) throws {
        try at(journey, top(journey)).hover()
        journey.transitions["hoverOpened"] = panelState(journey, "open")
        try selectTab(journey, "dashboard")
        try capture(journey, role: "hover", expected: "dashboard")
        try exitPanel(journey)
        journey.transitions["exitClosed"] = journey.panel?.value as? String == "closed"
        try clickOpen(journey)
        try openSettings(journey)
        try setHover(journey, false)
        try closeSettings(journey)
        try exitPanel(journey)
        try at(journey, top(journey)).hover()
        // Above the entire supported UI hover-delay range, without changing that slider.
        Thread.sleep(forTimeInterval: 2)
        journey.transitions["disabledHoverClosed"] = journey.panel?.value as? String == "closed"
        try clickOpen(journey)
        journey.transitions["clickOpened"] = journey.panel?.value as? String == "open"
        try selectTab(journey, "shelf")
        try capture(journey, role: "click", expected: "shelf")
        try exitPanel(journey)
        guard let app = journey.app else { throw Refusal.reason("candidate_required") }
        app.typeKey("i", modifierFlags: [.command, .shift])
        journey.transitions["keyboardOpened"] = panelState(journey, "open")
        app.typeKey("i", modifierFlags: [.command, .shift])
        journey.transitions["keyboardClosed"] = panelState(journey, "closed")
        try clickOpen(journey)
        try selectTab(journey, "dashboard")
        if environment["NOTCH_VM_SCENARIO"] == "pr106-panel-wrong-tab" {
            try require(journey.observed.values.allSatisfy { $0 } && journey.transitions.values.allSatisfy { $0 },
                        "negative_control_prerequisite_missing")
            try selectTab(journey, "shelf")
        }
        try capture(journey, role: "challenge", expected: "dashboard")
        for (key, value) in journey.transitions { observe(journey, key, value) }
        journey.discovery["transitions"] = journey.transitions
    }

    @MainActor
    private func prepareProducer(_ journey: Journey) throws {
        guard let path = journey.fixture["producerPath"] as? String,
              let pin = journey.fixture["producerSHA256"] as? String else { throw Refusal.reason("producer_pin_required") }
        let url = URL(fileURLWithPath: path)
        try require(url.resolvingSymlinksInPath() == url && path.hasPrefix("/Users/notch/"),
                    "guest_owned_producer_path_required")
        let bundle = Bundle(url: url)
        try require(bundle?.bundleIdentifier == producerID
                    && bundle?.object(forInfoDictionaryKey: "CFBundleVersion") as? String == "2"
                    && (try fileHash(url.appendingPathComponent("Contents/MacOS/NotchMediaFixture"))) == pin,
                    "producer_identity_mismatch")
        guard let pid = running(url, identifier: producerID) else { throw Refusal.reason("exact_running_producer_required") }
        journey.producerPID = pid
        journey.producer = XCUIApplication(url: url)
        try require(try producerValue(journey, "identity") == "\(producerID) pid=\(pid)"
                    && producerValue(journey, "engine") == "stopped"
                    && producerValue(journey, "publication") == "cleared"
                    && producerValue(journey, "elapsed") == "0.000"
                    && producerValue(journey, "error") == "none", "fresh_idle_producer_required")
        journey.discovery["producerPID"] = Int(pid)
        journey.discovery["producerSHA256"] = pin
    }

    @MainActor
    private func producerValue(_ journey: Journey, _ key: String) throws -> String {
        guard let app = journey.producer, let path = journey.fixture["producerPath"] as? String,
              running(URL(fileURLWithPath: path), identifier: producerID) == journey.producerPID else {
            throw Refusal.reason("producer_identity_changed")
        }
        let fields = app.staticTexts.matching(identifier: "mediafixture.v2." + key)
        guard fields.count == 1, let value = fields.firstMatch.value as? String else {
            throw Refusal.reason("actual_producer_ui_value_required")
        }
        return value
    }

    @MainActor
    private func engine(_ journey: Journey, setup: Bool = false) throws {
        let title = try producerValue(journey, "title")
        guard let before = Double(try producerValue(journey, "elapsed")) else {
            throw Refusal.reason("engine_sample_unavailable")
        }
        Thread.sleep(forTimeInterval: 0.5)
        guard let after = Double(try producerValue(journey, "elapsed")),
              let next = Int(try producerValue(journey, "remote-next")),
              let previous = Int(try producerValue(journey, "remote-previous")) else {
            throw Refusal.reason("engine_sample_unavailable")
        }
        let engineState = try producerValue(journey, "engine")
        let engineError = try producerValue(journey, "error")
        let currentTitle = try producerValue(journey, "title")
        let advancing = after.isFinite && before >= 0 && after < 30 && after - before >= 0.15
            && engineState == "playing" && engineError == "none" && currentTitle == title
        try require(advancing, setup ? "real_audio_engine_unavailable" : "real_audio_engine_lost")
        journey.engineSamples.append(["title": title, "before": before, "after": after, "next": next, "previous": previous])
    }

    @MainActor
    private func mediaJourney(_ journey: Journey) throws {
        try clickOpen(journey)
        try openSettings(journey)
        try setHover(journey, false)
        try closeSettings(journey)
        guard let producer = journey.producer else { throw Refusal.reason("producer_required") }
        producer.activate()
        let play = producer.buttons["mediafixture.v2.play"]
        try require(play.exists && play.isHittable, "producer_play_control_required")
        journey.producerTouched = true
        play.click()
        try engine(journey, setup: true)
        let initialNext = journey.engineSamples[0]["next"] as? Int ?? -1
        let initialPrevious = journey.engineSamples[0]["previous"] as? Int ?? -1
        try require(initialNext >= 0 && initialPrevious >= 0, "producer_command_baseline_required")
        journey.app?.activate()
        if journey.panel?.value as? String != "open" { try clickOpen(journey) }
        try selectTab(journey, "home")
        try require(wait(5) { journey.panel?.staticTexts["Regression Alpha"].exists == true }, "os_consumer_delivery_unavailable")
        try capture(journey, role: "baseline", expected: "Regression Alpha", media: true)
        try capture(journey, role: "baseline-repeat", expected: "Regression Alpha", media: true)
        try require(journey.observed.values.allSatisfy { $0 }
                    && transportHashes(journey, 0) == transportHashes(journey, 1), "stable_consumer_transport_baseline_required")
        guard let title = journey.panel?.staticTexts["Regression Alpha"], title.exists,
              journey.frame.contains(title.frame), !title.frame.isEmpty else {
            throw Refusal.reason("native_music_hover_region_required")
        }
        let musicPoint = CGPoint(x: title.frame.midX, y: title.frame.midY)
        try at(journey, musicPoint).hover()
        try scroll(journey, next: true, point: musicPoint)
        Thread.sleep(forTimeInterval: 0.6)
        try engine(journey)
        try at(journey, top(journey)).hover()
        try capture(journey, role: "next", expected: "Regression Bravo", media: true)
        try at(journey, musicPoint).hover()
        try scroll(journey, next: false, point: musicPoint)
        Thread.sleep(forTimeInterval: 0.6)
        try engine(journey)
        try at(journey, top(journey)).hover()
        try capture(journey, role: "previous", expected: "Regression Alpha", media: true)
        if environment["NOTCH_VM_SCENARIO"] != "pr106-media" {
            try require(journey.observed.values.allSatisfy { $0 }
                        && transportHashes(journey, 2) == transportHashes(journey, 0)
                        && transportHashes(journey, 3) == transportHashes(journey, 0),
                        "negative_control_prerequisite_missing")
        }
        try exitPanel(journey)
        try at(journey, top(journey)).hover()
        try qualify(journey)
        let axPanel = try nativePanel(journey)
        try require(try axString(axPanel, kAXValueAttribute) == "closed", "race_closed_start_required")
        journey.discovery["raceStartedClosed"] = true
        let start = ProcessInfo.processInfo.systemUptime
        try scroll(journey, next: environment["NOTCH_VM_SCENARIO"] != "pr106-media-wrong-direction",
                   point: top(journey), alreadyQualified: true)
        try mouseClick(top(journey))
        var opened: TimeInterval?
        while ProcessInfo.processInfo.systemUptime - start < 0.14 {
            if try axString(axPanel, kAXValueAttribute) == "open" {
                opened = ProcessInfo.processInfo.systemUptime - start
                break
            }
            Thread.sleep(forTimeInterval: 0.001)
        }
        guard let opened, opened > 0, opened < 0.14 else {
            throw Refusal.reason("closed_gesture_open_race_not_established")
        }
        journey.discovery["raceOpenSeconds"] = opened
        Thread.sleep(forTimeInterval: 0.8)
        try engine(journey)
        if environment["NOTCH_VM_SCENARIO"] == "pr106-media-wrong-pulse" {
            guard let next = journey.transport["next"] else { throw Refusal.reason("transport_region_required") }
            // A real hover paints a different transport region. Do not alter the image or the oracle.
            try at(journey, CGPoint(x: next.midX, y: next.midY)).hover()
        }
        try capture(journey, role: "race", expected: "Regression Bravo", media: true)
        observe(journey, "pulseCleanup", journey.captures.indices.dropFirst(2).allSatisfy {
            transportHashes(journey, $0) == transportHashes(journey, 0)
        })
        let counts = journey.engineSamples.map { [$0["next"] as? Int ?? -1, $0["previous"] as? Int ?? -1] }
        observe(journey, "commands", counts == [
            [initialNext, initialPrevious], [initialNext + 1, initialPrevious],
            [initialNext + 1, initialPrevious + 1], [initialNext + 2, initialPrevious + 1]
        ])
        observe(journey, "engineTracks", journey.engineSamples.compactMap { $0["title"] as? String } == [
            "Regression Alpha", "Regression Bravo", "Regression Alpha", "Regression Bravo"
        ])
        journey.discovery["engineSamples"] = journey.engineSamples
    }

    @MainActor
    private func scroll(_ journey: Journey, next: Bool, point: CGPoint, alreadyQualified: Bool = false) throws {
        if !alreadyQualified { try qualify(journey) }
        guard let event = CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 2,
                                  wheel1: 0, wheel2: next ? -400 : 400, wheel3: 0),
              let native = NSEvent(cgEvent: event) else { throw Refusal.reason("native_scroll_unavailable") }
        // Derive the outgoing sign from the real event, not a preference/default assumption.
        // The scenario requires normalization off, observed in Advanced before media input.
        try require(abs(native.scrollingDeltaX) >= 400 && native.scrollingDeltaY == 0
                    && (native.scrollingDeltaX < 0) == next, "native_scroll_direction_unavailable")
        event.location = point
        event.post(tap: .cghidEventTap)
    }

    private func mouseClick(_ point: CGPoint) throws {
        guard let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left),
              let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left) else {
            throw Refusal.reason("native_click_unavailable")
        }
        down.setIntegerValueField(.mouseEventClickState, value: 1)
        up.setIntegerValueField(.mouseEventClickState, value: 1)
        down.post(tap: .cghidEventTap)
        up.post(tap: .cghidEventTap)
    }

    private func axString(_ element: AXUIElement, _ attribute: String) throws -> String {
        var value: CFTypeRef?
        try require(AXUIElementCopyAttributeValue(element, attribute as CFString, &value) == .success,
                    "native_ax_value_unavailable")
        guard let string = value as? String else { throw Refusal.reason("native_ax_string_required") }
        return string
    }

    @MainActor
    private func nativePanel(_ journey: Journey) throws -> AXUIElement {
        var value: CFTypeRef?
        try require(AXUIElementCopyAttributeValue(AXUIElementCreateApplication(journey.pid),
                                                kAXWindowsAttribute as CFString, &value) == .success,
                    "native_ax_windows_unavailable")
        guard let windows = value as? [AXUIElement], windows.count <= 10 else {
            throw Refusal.reason("bounded_native_windows_required")
        }
        let matches = try windows.filter { try axString($0, kAXIdentifierAttribute) == marker + "window.\(journey.windowID)" }
        try require(matches.count == 1, "exact_native_panel_required")
        return matches[0]
    }

    @MainActor
    private func transportHashes(_ journey: Journey, _ index: Int) -> [String: String] {
        journey.captures[index]["transportSHA256"] as? [String: String] ?? [:]
    }

    private func rect(_ frame: CGRect) -> [String: CGFloat] {
        ["x": frame.minX, "y": frame.minY, "width": frame.width, "height": frame.height]
    }

    @MainActor
    private func capture(_ journey: Journey, role: String, expected: String, media: Bool = false) throws {
        try qualify(journey)
        guard let panel = journey.panel else { throw Refusal.reason("panel_unavailable") }
        Thread.sleep(forTimeInterval: 0.5)
        let frame = journey.frame
        try require(frame.width >= 400 && frame.width <= 1000 && frame.height >= 180 && frame.height <= 500,
                    "standard_panel_geometry_required")
        let labels = media ? ["Regression Alpha", "Regression Bravo", "Regression Charlie", "Notch Test Fixture"]
            : ["Edit Dashboard", "Drop files here"]
        var textFrames: [String: CGRect] = [:]
        for label in labels {
            let matches = panel.staticTexts.matching(identifier: label).allElementsBoundByIndex.filter {
                !$0.frame.isEmpty && frame.contains($0.frame) && $0.frame.minY > frame.minY + 40
            }
            if matches.count == 1 { textFrames[label] = matches[0].frame }
        }
        if media && journey.transport.isEmpty {
            for (name, icon) in [("previous", "backward.fill"), ("next", "forward.fill")] {
                let buttons = panel.buttons.matching(NSPredicate(format: "label == %@ OR identifier == %@", icon, icon))
                try require(buttons.count == 1 && buttons.firstMatch.isHittable, "visible_transport_controls_required")
                let bounds = buttons.firstMatch.frame.insetBy(dx: -4, dy: -4)
                try require(frame.contains(bounds) && bounds.width >= 12 && bounds.width <= 100
                            && bounds.height >= 12 && bounds.height <= 100, "transport_geometry_required")
                journey.transport[name] = bounds
            }
        }
        let state = panel.value as? String ?? ""
        let selection = try tabs(journey)
        let screenshot = panel.screenshot()
        try qualify(journey)
        try require(panel.value as? String == state && (try tabs(journey)) == selection, "capture_state_changed")
        guard let image = screenshot.image.cgImage(forProposedRect: nil, context: nil, hints: nil),
              image.width <= 4096 && image.height <= 4096 else { throw Refusal.reason("capture_pixels_unavailable") }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["en-US"]
        request.usesLanguageCorrection = false
        try VNImageRequestHandler(cgImage: image).perform([request])
        let texts = (request.results ?? []).compactMap { observation -> AboutOutputOracle.Observation? in
            guard let value = observation.topCandidates(1).first?.string else { return nil }
            let text = AboutOutputOracle.normalize(value)
            return labels.contains(text) ? .init(text: text, frame: observation.boundingBox) : nil
        }
        var observed: [String: Bool] = [:]
        for label in labels {
            observed[label] = textFrames[label].map { native in
                texts.contains {
                    $0.text == label && abs($0.frame.midX - (native.midX - frame.minX) / frame.width) <= 0.02
                        && abs($0.frame.midY - (frame.maxY - native.midY) / frame.height) <= 0.02
                }
            } ?? false
        }
        var transport: [String: String] = [:]
        var ink: [String: Int] = [:]
        for (key, region) in journey.transport where media {
            let scale = CGFloat(image.width) / frame.width
            let crop = CGRect(x: (region.minX - frame.minX) * scale, y: (region.minY - frame.minY) * scale,
                              width: region.width * scale, height: region.height * scale).integral
            guard let pixels = image.cropping(to: crop) else { throw Refusal.reason("transport_pixels_unavailable") }
            var bytes = [UInt8](repeating: 0, count: pixels.width * pixels.height * 4)
            let rendered = bytes.withUnsafeMutableBytes { buffer -> Bool in
                guard let context = CGContext(data: buffer.baseAddress, width: pixels.width, height: pixels.height,
                                              bitsPerComponent: 8, bytesPerRow: pixels.width * 4,
                                              space: CGColorSpaceCreateDeviceRGB(),
                                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
                context.draw(pixels, in: CGRect(x: 0, y: 0, width: pixels.width, height: pixels.height))
                return true
            }
            try require(rendered, "transport_pixels_unavailable")
            let count = stride(from: 0, to: bytes.count, by: 4).filter {
                bytes[$0 + 3] > 200 && max(bytes[$0], max(bytes[$0 + 1], bytes[$0 + 2])) > 60
            }.count
            try require(count >= 10 && count < pixels.width * pixels.height / 2, "visible_transport_ink_required")
            ink[key] = count
            transport[key] = hash(Data(bytes))
        }
        let run = environment["NOTCH_VM_RUN_ID"] ?? ""
        let name = "guest-public-pr106-\(run)-\(role)"
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        journey.captures.append([
            "role": role, "name": name, "sha256": hash(screenshot.pngRepresentation), "runID": run,
            "scenario": environment["NOTCH_VM_SCENARIO"] ?? "",
            "testIdentifier": "GuestRegressionProbe/PR106Probe/" + (media ? "testMedia" : "testPanel"),
            "candidateSHA256": expectedHash, "candidatePID": Int(journey.pid), "windowID": journey.windowID,
            "windowMarker": marker + "window.\(journey.windowID)", "windowFrame": rect(frame),
            "pixelWidth": image.width, "pixelHeight": image.height, "state": state, "tabs": selection,
            "expected": expected, "labels": observed, "textFrames": textFrames.mapValues(rect),
            "ocr": texts.map { ["text": $0.text, "frame": rect($0.frame)] }, "transportSHA256": transport,
            "transportFrames": media ? journey.transport.mapValues(rect) : [:], "transportInkPixels": ink
        ])
        let tab = media ? "home" : expected
        let label = media ? expected : expected == "dashboard" ? "Edit Dashboard" : "Drop files here"
        observe(journey, role, state == "open" && selection[tab] == "selected"
                && observed[label] == true && (!media || observed["Notch Test Fixture"] == true))
    }

    @MainActor
    private func restore(_ journey: Journey) {
        guard journey.touched else { return }
        func attempt(_ key: String, _ work: () throws -> Bool) {
            do { journey.restoration[key] = try work() }
            catch Refusal.reason(let reason) { journey.restoration[key] = false; journey.errors[key] = reason }
            catch {
                journey.restoration[key] = false
                let native = error as NSError
                journey.errors[key] = "\(native.domain):\(native.code)"
            }
        }
        attempt("producer") {
            guard journey.producerTouched else { return true }
            guard let producer = journey.producer else { return false }
            producer.activate()
            let stop = producer.buttons["mediafixture.v2.stop"]
            try self.require(stop.exists && stop.isHittable, "producer_stop_control_required")
            stop.click()
            guard let path = journey.fixture["producerPath"] as? String,
                  let pin = journey.fixture["producerSHA256"] as? String else { return false }
            return try self.producerValue(journey, "engine") == "stopped"
                && self.producerValue(journey, "publication") == "cleared"
                && self.producerValue(journey, "elapsed") == "0.000"
                && self.producerValue(journey, "error") == "none"
                && self.fileHash(URL(fileURLWithPath: path).appendingPathComponent("Contents/MacOS/NotchMediaFixture")) == pin
        }
        attempt("preferences") {
            journey.app?.activate()
            if journey.panel?.value as? String != "open" { try self.clickOpen(journey) }
            if journey.changedHover {
                try self.openSettings(journey)
                guard let original = journey.originalHover else { return false }
                try self.setHover(journey, original)
            }
            if journey.settings?.exists == true {
                for (key, original) in journey.preferences {
                    let parts = key.split(separator: ":", maxSplits: 1).map(String.init)
                    let control = try self.toggle(journey, pane: parts[0], label: parts[1])
                    try self.require(self.toggleValue(control.value) == original, "preference_restoration_unverified")
                }
            }
            return !journey.changedHover || journey.settings?.exists == true
        }
        attempt("settings") {
            if journey.settings?.exists == true { try self.closeSettings(journey) }
            return journey.settings?.exists == false
        }
        attempt("tab") {
            if journey.panel?.value as? String != "open" { try self.clickOpen(journey) }
            guard let original = journey.originalTab, ["home", "dashboard", "shelf"].contains(original) else { return false }
            try self.selectTab(journey, original)
            return try self.tabs(journey)[original] == "selected"
        }
        attempt("panel") {
            try self.exitPanel(journey)
            // Recheck close's remembered/default-tab policy, not only the selection before close.
            try self.clickOpen(journey)
            guard let original = journey.originalTab else { return false }
            let restoredTab = try self.tabs(journey)[original] == "selected"
            journey.restoration["tab"] = journey.restoration["tab"] == true && restoredTab
            try self.exitPanel(journey)
            return journey.panel?.value as? String == "closed"
        }
        attempt("pointer") {
            try self.at(journey, journey.pointer).hover()
            return CGEvent(source: nil)?.location == journey.pointer
        }
        attempt("foreground") {
            guard let original = journey.foreground, !original.isTerminated else { return false }
            original.activate(options: [])
            return self.wait { NSWorkspace.shared.frontmostApplication?.processIdentifier == original.processIdentifier }
        }
        attempt("candidate") {
            try self.qualify(journey)
            return try self.fileHash(self.candidate.appendingPathComponent("Contents/MacOS/notch-pocket")) == self.expectedHash
        }
    }

    @MainActor
    private func finish(_ journey: Journey, media: Bool) {
        let primaryVerdict = journey.verdict
        let primaryReason = journey.reason
        let nativeFailures = testRun?.failureCount ?? 0
        var verdict = journey.verdict
        var reason = journey.reason
        let restored = journey.restoration.count == 8 && journey.restoration.values.allSatisfy { $0 }
        if nativeFailures > 0 && verdict != "FAIL" { verdict = "BLOCKED"; reason = "native_interaction_aborted" }
        if journey.touched && !restored { verdict = "BLOCKED"; reason = "restoration_unverified" }
        if !journey.errors.isEmpty && verdict != "BLOCKED" { verdict = "BLOCKED"; reason = "incomplete_native_journey" }
        let receipt: [String: Any] = [
            "runID": environment["NOTCH_VM_RUN_ID"] ?? "", "scenario": environment["NOTCH_VM_SCENARIO"] ?? "",
            "testIdentifier": "GuestRegressionProbe/PR106Probe/" + (media ? "testMedia" : "testPanel"),
            "verdict": verdict, "reason": reason, "primaryVerdict": primaryVerdict, "primaryReason": primaryReason,
            "cleanup": restored ? "restored_original_state" : journey.touched ? "blocked" : "not_needed",
            "candidateVerified": journey.pid > 0, "expectedCandidateSHA256": expectedHash,
            "interactionCaptureVersion": 1, "interactionFixture": journey.fixture,
            "interactionWorker": environment["NOTCH_VM_INTERACTION_WORKER"] ?? "",
            "interactionRestoration": journey.restoration, "captures": journey.captures,
            "observedPublicText": journey.observed, "discovery": journey.discovery, "errors": journey.errors,
            "profileRestoration": "parent-required-not-performed-by-test",
            "nativeFailureCountBeforeReport": nativeFailures
        ]
        do {
            let data = try JSONSerialization.data(withJSONObject: receipt, options: [.sortedKeys])
            print("NOTCH_VM_RESULT " + String(decoding: data, as: UTF8.self))
        } catch {
            XCTFail("BLOCKED: result_serialization_failed")
            return
        }
        if verdict != "PASS" && nativeFailures == 0 { XCTFail("\(verdict): \(reason)") }
    }
}
