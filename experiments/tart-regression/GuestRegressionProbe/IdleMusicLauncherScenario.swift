import AppKit
import CoreGraphics
import CryptoKit
import Vision
import XCTest

extension GuestRegressionProbe {
    @MainActor
    func testInstalledIdleMusicWithoutTarget() {
        runInstalledSettingsOutput(testName: "testInstalledIdleMusicWithoutTarget", modes: [IdleMusicScenario.noTarget.rawValue])
    }

    @MainActor
    func testInstalledIdleMusicUnavailableTarget() {
        runInstalledSettingsOutput(testName: "testInstalledIdleMusicUnavailableTarget", modes: [IdleMusicScenario.unavailable.rawValue])
    }

    @MainActor
    private func musicPanel(_ app: XCUIApplication) throws -> XCUIElement {
        let panels = app.dialogs.matching(
            NSPredicate(format: "identifier BEGINSWITH %@", "com.jdylanmc.notchpocket.notch.v1.window.")
        )
        try require(panels.count == 1, "exact_notch_panel_required")
        return panels.firstMatch
    }

    @MainActor
    private func waitValue(_ element: XCUIElement, _ value: String) -> Bool {
        let expected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "value == %@", value), object: element)
        return XCTWaiter.wait(for: [expected], timeout: 5) == .completed
    }

    @MainActor
    private func activateForeground(_ app: NSRunningApplication) throws {
        try require(!app.isTerminated && app.activate(), "music_foreground_unavailable")
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier
        }, object: nil)
        try require(XCTWaiter.wait(for: [ready], timeout: 5) == .completed, "music_foreground_not_observed")
    }

    @MainActor
    func recordMusicPanelFixture(_ app: XCUIApplication, state: RunState) throws {
        let domain = "com.jdylanmc.notchpocket" as CFString
        try require(CFPreferencesAppSynchronize(domain), "music_preferences_unavailable")
        try require(CFPreferencesCopyAppValue("didChooseMediaController" as CFString, domain) as? Bool == true,
                    "music_fixture_requires_explicit_original_source")
        try require(CFPreferencesCopyAppValue("lastSupportedNowPlayingBundleIdentifier" as CFString, domain) == nil,
                    "music_fixture_requires_no_remembered_source")
        try require(CFPreferencesCopyAppValue("lastNowPlayingLauncherBundleIdentifier" as CFString, domain) == nil,
                    "music_fixture_requires_no_remembered_launcher_source")
        state.originalMediaController = CFPreferencesCopyAppValue("mediaController" as CFString, domain) as? String
        try require(state.originalMediaController != nil, "music_original_preference_unavailable")
        let panel = try musicPanel(app)
        // These journeys start closed; an existing open workspace is not a disposable fixture.
        try require(panel.value as? String == "closed", "closed_music_panel_fixture_required")
        guard let pointer = CGEvent(source: nil)?.location else { throw Blocked.reason("guest_pointer_unavailable") }
        state.originalPanelState = "closed"
        state.musicPointerReturn = panel.coordinate(withNormalizedOffset: .zero).withOffset(
            CGVector(dx: pointer.x - panel.frame.minX, dy: pointer.y - panel.frame.minY)
        )
        state.discovery["musicFixture"] = "idle_guest_no_current_or_remembered_now_playing_source"
    }

    @MainActor
    private func openMusicPanel(_ app: XCUIApplication) throws -> XCUIElement {
        let panel = try musicPanel(app)
        panel.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: panel.frame.width / 2, dy: 5)).hover()
        try require(waitValue(panel, "open"), "music_panel_open_not_observed")
        return panel
    }

    @MainActor
    private func musicSourcePicker(_ settings: XCUIElement) throws -> XCUIElement {
        let row = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: "Media").firstMatch
        let media = row.staticTexts["Media"]
        try require(waitHittable(media), "media_settings_unavailable")
        if !row.isSelected { media.click() }
        let selected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "selected == true"), object: row)
        try require(XCTWaiter.wait(for: [selected], timeout: 5) == .completed, "media_settings_not_selected")
        let matches = settings.popUpButtons.matching(identifier: "Music Source")
        try require(matches.count == 1 && waitHittable(matches.firstMatch), "music_source_picker_unavailable")
        return matches.firstMatch
    }

    @MainActor
    private func chooseMusicSource(_ name: String, picker: XCUIElement, app: XCUIApplication) throws {
        if picker.value as? String != name {
            picker.click()
            let option = app.menuItems[name]
            if !waitHittable(option) || !option.isEnabled {
                app.typeKey(.escape, modifierFlags: [])
                throw Blocked.reason("music_source_option_unavailable")
            }
            option.click()
        }
        try require(waitValue(picker, name), "music_source_selection_not_observed")
    }

    @MainActor
    func restoreMusicSource(_ state: RunState) throws {
        guard let app = state.app, let settings = state.window, let original = state.originalMusicSource else {
            throw Blocked.reason("music_restoration_identity_missing")
        }
        try require(currentCandidatePID() == state.originalPID, "candidate_process_changed")
        if !settings.exists {
            let panel = try openMusicPanel(app)
            let gear = panel.buttons.matching(
                NSPredicate(format: "label IN %@ OR identifier IN %@", ["Settings", "gear"], ["Settings", "gear"])
            )
            try require(gear.count == 1 && waitHittable(gear.firstMatch), "music_restoration_gear_unavailable")
            gear.firstMatch.click()
            try require(settings.waitForExistence(timeout: 5), "music_restoration_settings_unavailable")
        }
        let picker = try musicSourcePicker(settings)
        try chooseMusicSource(original, picker: picker, app: app)
        let domain = "com.jdylanmc.notchpocket" as CFString
        try require(CFPreferencesAppSynchronize(domain)
                    && CFPreferencesCopyAppValue("mediaController" as CFString, domain) as? String == state.originalMediaController
                    && CFPreferencesCopyAppValue("didChooseMediaController" as CFString, domain) as? Bool == true
                    && CFPreferencesCopyAppValue("lastSupportedNowPlayingBundleIdentifier" as CFString, domain) == nil
                    && CFPreferencesCopyAppValue("lastNowPlayingLauncherBundleIdentifier" as CFString, domain) == nil,
                    "music_preferences_not_restored")
        state.discovery["musicSourceRestored"] = picker.value as? String == original
        state.discovery["musicPreferencesRestored"] = true
        state.musicSourceNeedsRestoration = false
    }

    @MainActor
    func restoreMusicPanel(_ state: RunState) throws {
        guard let app = state.app else { throw Blocked.reason("music_restoration_identity_missing") }
        let panel = try openMusicPanel(app)
        if let tab = state.originalTab {
            let button = panel.buttons[tab]
            try require(waitHittable(button), "music_original_tab_unavailable")
            if button.value as? String != "selected" { button.click() }
            try require(waitValue(button, "selected"), "music_original_tab_not_restored")
        }
        state.musicPointerReturn?.hover()
        try require(waitValue(panel, "closed"), "music_panel_not_restored")
        state.discovery["musicPanelRestored"] = true
        if let original = state.originalForeground {
            try activateForeground(original)
        }
    }

    @MainActor
    func inspectIdleMusicLauncher(
        _ settings: XCUIElement, scenario: IdleMusicScenario, state: RunState, runID: String
    ) throws {
        guard let app = state.app else { throw Blocked.reason("candidate_process_missing") }
        if scenario == .unavailable {
            try require(NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.spotify.client") == nil,
                        "fixture_requires_spotify_not_installed")
        }
        let picker = try musicSourcePicker(settings)
        guard let original = picker.value as? String,
              ["Now Playing", "Apple Music", "Spotify", "YouTube Music"].contains(original) else {
            throw Blocked.reason("original_music_source_unavailable")
        }
        state.originalMusicSource = original
        state.musicSourceNeedsRestoration = true
        try chooseMusicSource(scenario.source, picker: picker, app: app)
        state.observed["selectedSourceVerified"] = picker.value as? String == scenario.source
        settings.buttons[XCUIIdentifierCloseWindow].click()
        let closed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: settings)
        try require(XCTWaiter.wait(for: [closed], timeout: 5) == .completed, "music_settings_close_not_observed")

        let panel = try openMusicPanel(app)
        let tabs = panel.buttons.matching(NSPredicate(
            format: "identifier BEGINSWITH %@ AND value == %@", "com.jdylanmc.notchpocket.notch.v1.tab.", "selected"
        ))
        try require(tabs.count == 1, "music_fixture_requires_visible_tabs")
        state.originalTab = tabs.firstMatch.identifier
        let home = panel.buttons["com.jdylanmc.notchpocket.notch.v1.tab.home"]
        try require(waitHittable(home), "music_home_tab_unavailable")
        if home.value as? String != "selected" { home.click() }
        try require(waitValue(home, "selected"), "music_home_not_selected")
        let foregroundApps = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.finder")
        try require(foregroundApps.count == 1, "music_fixture_requires_running_guest_finder")
        let foreground = foregroundApps[0]
        try activateForeground(foreground)

        let launcher = panel.buttons["com.jdylanmc.notchpocket.music.v1.idle-launcher"]
        state.observed["idleLauncherVisible"] = waitHittable(launcher)
        state.observed["transportAbsent"] = panel.sliders.count == 0
        state.observed["headerPreserved"] = home.exists && panel.buttons.matching(
            NSPredicate(format: "label IN %@ OR identifier IN %@", ["Settings", "gear"], ["Settings", "gear"])
        ).count == 1
        if state.observed["idleLauncherVisible"] == true { launcher.click() }
        let status = panel.staticTexts["com.jdylanmc.notchpocket.music.v1.launch-status"]
        let appeared = status.waitForExistence(timeout: 5)
        state.observed["launchStatusVisible"] = appeared
            && ((status.value as? String) ?? status.label) == scenario.message && panel.frame.contains(status.frame)
        state.observed["noFocusChange"] = NSWorkspace.shared.frontmostApplication?.processIdentifier == foreground.processIdentifier
        try captureMusicStatus(panel, status: appeared ? status : nil, scenario: scenario, state: state, runID: runID)
        let dismiss = panel.buttons["OK"]
        if appeared && waitHittable(dismiss) { dismiss.click() }
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: status)
        state.observed["statusDismissed"] = appeared && XCTWaiter.wait(for: [gone], timeout: 5) == .completed
        state.observed["launcherRestored"] = waitHittable(launcher)
    }

    @MainActor
    private func captureMusicStatus(
        _ panel: XCUIElement, status: XCUIElement?, scenario: IdleMusicScenario, state: RunState, runID: String
    ) throws {
        let frame = panel.frame
        try require(currentCandidatePID() == state.originalPID && CGDisplayBounds(CGMainDisplayID()).contains(frame),
                    "music_capture_identity_unavailable")
        let windowID = Int(panel.identifier.replacingOccurrences(of: "com.jdylanmc.notchpocket.notch.v1.window.", with: ""))
        let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
        let matches = windows.filter {
            $0[kCGWindowNumber as String] as? Int == windowID
                && $0[kCGWindowOwnerPID as String] as? Int == Int(state.originalPID ?? -1)
        }
        try require(matches.count == 1, "music_capture_window_ambiguous")
        guard let sharing = matches[0][kCGWindowSharingState as String] as? Int,
              sharing != 0, let bounds = matches[0][kCGWindowBounds as String] as? NSDictionary,
              CGRect(dictionaryRepresentation: bounds) == frame else {
            throw Blocked.reason("music_capture_window_unshareable")
        }
        let capture = panel.screenshot()
        try require(currentCandidatePID() == state.originalPID && panel.frame == frame, "music_capture_identity_changed")
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
            return .init(text: text, frame: observation.boundingBox)
        }
        let statusFrame = status.map {
            CGRect(x: ($0.frame.minX - frame.minX) / frame.width, y: (frame.maxY - $0.frame.maxY) / frame.height,
                   width: $0.frame.width / frame.width, height: $0.frame.height / frame.height)
        }
        state.observed["statusPixels"] = IdleMusicOutputOracle.statusVisible(observations, scenario: scenario, statusFrame: statusFrame)
        state.screenshotHash = SHA256.hash(data: capture.pngRepresentation).map { String(format: "%02x", $0) }.joined()
        state.discovery["musicCandidatePID"] = Int(state.originalPID ?? -1)
        state.discovery["musicWindowID"] = windowID
        state.discovery["musicWindowMarker"] = panel.identifier
        state.discovery["musicCaptureRunID"] = runID
        state.discovery["musicSource"] = scenario.source
        let attachment = XCTAttachment(screenshot: capture)
        attachment.name = "guest-public-music-\(runID)"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
