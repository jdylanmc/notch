//
//  IdentityCompatibilityTests.swift
//  notchPocketTests
//

import Foundation
import AppKit
import Defaults
import MachO
import XCTest

@testable import notchPocket

final class IdentityCompatibilityTests: XCTestCase {
    @MainActor
    private final class ObservationSource: NotchObservationSource {
        var notchState: NotchState = .closed
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
        XCTAssertEqual(panel.accessibilityValue() as? String, "open")
        XCTAssertEqual(panel.accessibilityIdentifier(), identifier)
        XCTAssertFalse(panel.isAccessibilitySelectorAllowed(#selector(NotchPocketSkyLightWindow.setAccessibilityValue(_:))))
        XCTAssertFalse(panel.isAccessibilitySelectorAllowed(#selector(NotchPocketSkyLightWindow.setAccessibilityIdentifier(_:))))
        XCTAssertFalse(panel.accessibilityIsAttributeSettable(.value))
        XCTAssertFalse(panel.accessibilityIsAttributeSettable(.identifier))
        source.notchState = .closed
        XCTAssertEqual(panel.accessibilityValue() as? String, "closed")
        panel.close()
        XCTAssertEqual(panel.accessibilityIdentifier(), "")
        XCTAssertNil(panel.accessibilityValue())
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
