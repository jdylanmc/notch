//
//  IdentityCompatibilityTests.swift
//  notchPocketTests
//

import Foundation
import Defaults
import MachO
import XCTest

@testable import notchPocket

final class IdentityCompatibilityTests: XCTestCase {
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
