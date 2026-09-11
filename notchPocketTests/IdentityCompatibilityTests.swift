//
//  IdentityCompatibilityTests.swift
//  notchPocketTests
//

import Foundation
import AppKit
import Defaults
import MachO
import ObjectiveC
import XCTest

@testable import notchPocket

final class IdentityCompatibilityTests: XCTestCase {
    @MainActor
    private final class ObservationSource: NotchObservationSource {
        var notchState: NotchState = .closed
        var openCalls = 0
        var closeCalls = 0
        var refusesOpen = false
        var refusesClose = false

        func open() -> Bool {
            openCalls += 1
            guard !refusesOpen, notchState != .open else { return false }
            notchState = .open
            return true
        }

        func close() {
            closeCalls += 1
            if !refusesClose { notchState = .closed }
        }
    }

    @MainActor
    private func observationPanel() -> NotchPocketSkyLightWindow {
        NotchPocketSkyLightWindow(
            contentRect: NSRect(x: 0, y: 0, width: 200, height: 40),
            styleMask: [.borderless, .nonactivatingPanel, .utilityWindow, .hudWindow],
            backing: .buffered, defer: false
        )
    }

    @MainActor
    func testNotchPanelObservationPreservesNativeDefaults() {
        let panel = observationPanel()
        defer { panel.close() }
        // AppKit normalizes requested sharing/style flags; observation must preserve its result.
        let baselineSharing = panel.sharingType
        let baselineStyle = panel.styleMask
        XCTAssertEqual(panel.accessibilityIdentifier(), "")
        XCTAssertNil(panel.accessibilityValue())
        XCTAssertFalse(panel.isAccessibilityAlternateUIVisible())
        XCTAssertEqual(panel.level, .mainMenu + 3)
        XCTAssertEqual(panel.sharingType, baselineSharing)
        XCTAssertTrue(panel.isFloatingPanel)
        XCTAssertFalse(panel.canBecomeKey)
        XCTAssertFalse(panel.canBecomeMain)
        XCTAssertFalse(panel.hasShadow)
        XCTAssertFalse(panel.isOpaque)
        XCTAssertTrue(panel.styleMask.contains(.nonactivatingPanel))
        XCTAssertTrue(panel.styleMask.contains(.hudWindow))
        XCTAssertFalse(panel.styleMask.contains(.titled))
        XCTAssertEqual(panel.styleMask, baselineStyle)
        let source = ObservationSource()
        panel.observationSource = source
        for state in [NotchState.open, .closed] {
            source.notchState = state
            XCTAssertEqual(panel.accessibilityIdentifier(),
                           "com.jdylanmc.notchpocket.notch.v1.window.\(panel.windowNumber)")
            XCTAssertEqual(panel.accessibilityValue() as? String, state == .open ? "open" : "closed")
            XCTAssertEqual(panel.isAccessibilityAlternateUIVisible(), state == .open)
            XCTAssertEqual(panel.sharingType, baselineSharing)
            XCTAssertEqual(panel.styleMask, baselineStyle)
        }
    }

    @MainActor
    func testNotchPanelReadOnlyMetadataTracksSourceWithoutMediaHooks() {
        let source = ObservationSource()
        let panel = observationPanel()
        defer { panel.close() }
        panel.observationSource = source
        XCTAssertGreaterThan(panel.windowNumber, 0)
        let identifier = "com.jdylanmc.notchpocket.notch.v1.window.\(panel.windowNumber)"
        XCTAssertEqual(panel.accessibilityIdentifier(), identifier)
        XCTAssertEqual(panel.accessibilityValue() as? String, "closed")
        source.notchState = .open
        XCTAssertEqual(panel.accessibilityValue() as? String, "open")
        panel.setAccessibilityValue("closed")
        panel.setAccessibilityIdentifier("foreign")
        panel.setAccessibilityAlternateUIVisible(false)
        XCTAssertEqual(panel.accessibilityValue() as? String, "open")
        XCTAssertTrue(panel.isAccessibilityAlternateUIVisible())
        XCTAssertEqual(panel.accessibilityIdentifier(), identifier)
        XCTAssertFalse(panel.isAccessibilitySelectorAllowed(#selector(NotchPocketSkyLightWindow.setAccessibilityValue(_:))))
        XCTAssertFalse(panel.isAccessibilitySelectorAllowed(#selector(NotchPocketSkyLightWindow.setAccessibilityIdentifier(_:))))
        XCTAssertFalse(panel.isAccessibilitySelectorAllowed(
            #selector(NotchPocketSkyLightWindow.setAccessibilityAlternateUIVisible(_:))
        ))
        XCTAssertFalse(panel.accessibilityIsAttributeSettable(.value))
        XCTAssertFalse(panel.accessibilityIsAttributeSettable(.identifier))
        XCTAssertFalse(panel.accessibilityIsAttributeSettable(.alternateUIVisible))
        source.notchState = .closed
        XCTAssertEqual(panel.accessibilityValue() as? String, "closed")
        panel.close()
        XCTAssertEqual(panel.accessibilityIdentifier(), "")
        XCTAssertNil(panel.accessibilityValue())
        XCTAssertFalse(panel.isAccessibilityAlternateUIVisible())
    }

    @MainActor
    func testNotchPanelDoesNotRetainObservationSource() {
        let panel = observationPanel()
        defer { panel.close() }
        var source: ObservationSource? = ObservationSource()
        panel.observationSource = source
        XCTAssertEqual(panel.accessibilityValue() as? String, "closed")
        source = nil
        XCTAssertNil(panel.observationSource)
        XCTAssertEqual(panel.accessibilityIdentifier(), "")
        XCTAssertNil(panel.accessibilityValue())
        XCTAssertFalse(panel.isAccessibilityAlternateUIVisible())
    }

    @MainActor
    func testNotchActionsBindExactNativeSelectorsOnlyWithLiveSource() throws {
        let panel = observationPanel()
        defer { panel.close() }
        let nativeRole = panel.accessibilityRole()
        let bindings: [(NSAccessibility.Action, String, Selector)] = [
            (.showAlternateUI, "AXShowAlternateUI",
             #selector(NotchPocketSkyLightWindow.accessibilityPerformShowAlternateUI)),
            (.showDefaultUI, "AXShowDefaultUI",
             #selector(NotchPocketSkyLightWindow.accessibilityPerformShowDefaultUI))
        ]
        // This verifies the Objective-C bridge contract, not cross-process AX dispatch.
        for (action, name, selector) in bindings {
            XCTAssertEqual(action.rawValue, name)
            XCTAssertTrue(panel.responds(to: selector))
            XCTAssertFalse(panel.isAccessibilitySelectorAllowed(selector))
            let method = try XCTUnwrap(class_getInstanceMethod(NotchPocketSkyLightWindow.self, selector))
            let inherited = try XCTUnwrap(class_getInstanceMethod(NSPanel.self, selector))
            XCTAssertNotEqual(method, inherited, "The panel must override AppKit's native action selector")
            XCTAssertEqual(method_getNumberOfArguments(method), 2)
            let encoding = String(cString: try XCTUnwrap(method_getTypeEncoding(method)))
            XCTAssertTrue(encoding.hasPrefix("B") || encoding.hasPrefix("c"), "Objective-C BOOL return required")
        }
        let source = ObservationSource()
        panel.observationSource = source
        for (_, _, selector) in bindings {
            XCTAssertTrue(panel.isAccessibilitySelectorAllowed(selector))
        }
        XCTAssertEqual(panel.accessibilityRole(), nativeRole)
        XCTAssertEqual(panel.accessibilityActionDescription(.showAlternateUI),
                       String(localized: "Open Notch"))
        XCTAssertEqual(panel.accessibilityActionDescription(.showDefaultUI),
                       String(localized: "Close Notch"))
        panel.close()
        for (_, _, selector) in bindings {
            XCTAssertFalse(panel.isAccessibilitySelectorAllowed(selector))
        }
        XCTAssertFalse(panel.accessibilityPerformShowAlternateUI())
        XCTAssertFalse(panel.accessibilityPerformShowDefaultUI())
    }

    @MainActor
    func testNotchActionsRouteToOnlyTheBoundModelWithoutWindowTeardown() {
        let panel = observationPanel()
        let otherPanel = observationPanel()
        defer { panel.close(); otherPanel.close() }
        let source = ObservationSource()
        let otherSource = ObservationSource()
        panel.observationSource = source
        otherPanel.observationSource = otherSource
        let identifier = panel.accessibilityIdentifier()
        let sharing = panel.sharingType
        let style = panel.styleMask
        XCTAssertTrue(panel.accessibilityPerformShowAlternateUI())
        XCTAssertEqual(source.openCalls, 1)
        XCTAssertEqual(panel.accessibilityValue() as? String, "open")
        XCTAssertTrue(panel.accessibilityPerformShowDefaultUI())
        XCTAssertEqual(source.closeCalls, 1)
        XCTAssertEqual(panel.accessibilityValue() as? String, "closed")
        XCTAssertEqual(otherSource.openCalls, 0)
        XCTAssertEqual(otherSource.closeCalls, 0)
        XCTAssertTrue(panel.observationSource === source)
        XCTAssertEqual(panel.accessibilityIdentifier(), identifier)
        XCTAssertEqual(panel.sharingType, sharing)
        XCTAssertEqual(panel.styleMask, style)
        XCTAssertEqual(panel.level, .mainMenu + 3)
        XCTAssertFalse(panel.canBecomeKey)
        XCTAssertFalse(panel.canBecomeMain)
        XCTAssertFalse(panel.wantsKeyForTextInput)
        XCTAssertFalse(panel.accessibilityIsAttributeSettable(.value))
        XCTAssertFalse(panel.accessibilityIsAttributeSettable(.identifier))
    }

    @MainActor
    func testNotchActionsAlreadyAtTargetAvoidModelSideEffects() {
        let panel = observationPanel()
        defer { panel.close() }
        let source = ObservationSource()
        panel.observationSource = source
        XCTAssertTrue(panel.accessibilityPerformShowDefaultUI())
        XCTAssertEqual(source.closeCalls, 0)
        source.notchState = .open
        XCTAssertTrue(panel.accessibilityPerformShowAlternateUI())
        XCTAssertEqual(source.openCalls, 0)
    }

    @MainActor
    func testNotchActionsLeaveRefusedTransitionsUnchanged() {
        let panel = observationPanel()
        defer { panel.close() }
        let source = ObservationSource()
        panel.observationSource = source
        source.refusesOpen = true
        XCTAssertTrue(panel.accessibilityPerformShowAlternateUI())
        XCTAssertEqual(source.openCalls, 1)
        XCTAssertEqual(panel.accessibilityValue() as? String, "closed")
        source.notchState = .open
        source.refusesClose = true
        XCTAssertTrue(panel.accessibilityPerformShowDefaultUI())
        XCTAssertEqual(source.closeCalls, 1)
        XCTAssertEqual(panel.accessibilityValue() as? String, "open")
    }

    @MainActor
    func testNotchActionsDoNotRetainOrReviveReleasedSources() {
        let panel = observationPanel()
        defer { panel.close() }
        var source: ObservationSource? = ObservationSource()
        weak var weakSource = source
        panel.observationSource = source
        source = nil
        XCTAssertNil(weakSource)
        for selector in [
            #selector(NotchPocketSkyLightWindow.accessibilityPerformShowAlternateUI),
            #selector(NotchPocketSkyLightWindow.accessibilityPerformShowDefaultUI)
        ] {
            XCTAssertFalse(panel.isAccessibilitySelectorAllowed(selector))
        }
        XCTAssertFalse(panel.accessibilityPerformShowAlternateUI())
        XCTAssertFalse(panel.accessibilityPerformShowDefaultUI())
        XCTAssertNil(panel.observationSource)
        XCTAssertNil(panel.accessibilityValue())
        let replacement = ObservationSource()
        panel.observationSource = replacement
        panel.close()
        XCTAssertFalse(panel.accessibilityPerformShowAlternateUI())
        XCTAssertEqual(replacement.openCalls, 0)
        XCTAssertNil(panel.observationSource)
    }

    func testAppAndEmbeddedHelperIdentity() throws {
        let app = Bundle.main
        XCTAssertEqual(app.bundleIdentifier, "com.jdylanmc.notchpocket")
        XCTAssertEqual(app.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String, "Notch Pocket")
        XCTAssertEqual(app.executableURL?.lastPathComponent, "notch-pocket")
        XCTAssertEqual(app.bundleURL.lastPathComponent, "notch-pocket.app")

        let helperURL = app.bundleURL.appendingPathComponent("Contents/XPCServices/notchPocketXPCHelper.xpc")
        let helper = try XCTUnwrap(Bundle(url: helperURL))
        XCTAssertEqual(helper.bundleIdentifier, "com.jdylanmc.notchpocket.XPCHelper")
        XCTAssertEqual(helper.executableURL?.lastPathComponent, "notchPocketXPCHelper")
        XCTAssertEqual(Bundle(for: Self.self).bundleIdentifier, "com.jdylanmc.notchpocket.tests")
        XCTAssertEqual(String(reflecting: NotchPocketApp.self), "notchPocket.NotchPocketApp")
    }

    func testBuiltProductHasNoInAppUpdater() throws {
        let app = Bundle.main
        let updaterKeys = [
            "SUFeedURL", "SUPublicEDKey", "SUBundleName", "SUEnableAutomaticChecks",
            "SUEnableDownloaderService", "SUEnableInstallerLauncherService"
        ]
        for key in updaterKeys {
            XCTAssertNil(app.object(forInfoDictionaryKey: key), key)
        }

        let resources = try XCTUnwrap(FileManager.default.enumerator(
            at: app.bundleURL,
            includingPropertiesForKeys: nil
        ))
        for case let url as URL in resources {
            XCTAssertNotEqual(url.lastPathComponent, "Sparkle.framework")
            XCTAssertNotEqual(url.lastPathComponent, "Updater.app")
            XCTAssertNotEqual(url.lastPathComponent, "Installer.xpc")
            XCTAssertNotEqual(url.lastPathComponent, "Downloader.xpc")
        }
        for index in 0..<_dyld_image_count() {
            let name = try XCTUnwrap(_dyld_get_image_name(index))
            XCTAssertFalse(String(cString: name).localizedCaseInsensitiveContains("Sparkle"))
        }
    }

    func testShelfStorageIdentityAndDefault() {
        XCTAssertEqual(Defaults.Keys.notchPocketShelf.name, "notchPocketShelf")
        XCTAssertTrue(Defaults.Keys.notchPocketShelf.defaultValue)
        let support = URL(fileURLWithPath: "/ApplicationSupport", isDirectory: true)
        XCTAssertEqual(
            ShelfPersistenceService.shelfDirectory(in: support).path,
            "/ApplicationSupport/notchPocket/Shelf"
        )
        XCTAssertEqual(Notification.Name.sharingDidFinish.rawValue, "com.notchPocket.sharingDidFinish")
    }

    func testLunarEventKeepsObjectiveCWireNameAndSecureCoding() throws {
        XCTAssertEqual(NSStringFromClass(BNLunarBrightnessEvent.self), "BNLunarBrightnessEvent")
        let event = BNLunarBrightnessEvent(brightness: 0.75, display: 42)
        let data = try NSKeyedArchiver.archivedData(withRootObject: event, requiringSecureCoding: true)
        let decoded = try XCTUnwrap(
            NSKeyedUnarchiver.unarchivedObject(ofClass: BNLunarBrightnessEvent.self, from: data)
        )
        XCTAssertEqual(decoded.brightness, 0.75)
        XCTAssertEqual(decoded.display, 42)
    }

    func testRenamedXPCProtocolsKeepMessageSelectors() {
        XCTAssertEqual(
            NSStringFromSelector(#selector(NotchPocketXPCHelperLunarListener.lunarEventDidUpdate(_:))),
            "lunarEventDidUpdate:"
        )
        XCTAssertEqual(
            NSStringFromSelector(#selector(NotchPocketXPCHelperDelegate.notificationDidAppear(_:))),
            "notificationDidAppear:"
        )
        XCTAssertEqual(
            NSStringFromSelector(#selector(NotchPocketXPCHelperProtocol.setNotchOpen(_:))),
            "setNotchOpen:"
        )
    }
}
