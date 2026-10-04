import AppKit
import CoreGraphics
import CryptoKit
import Darwin
import Foundation
import XCTest

final class SettingsFixture: XCTestCase {
    @MainActor
    func testPrepareSettings() throws {
        continueAfterFailure = false
        var size = 0
        guard sysctlbyname("hw.model", nil, &size, nil, 0) == 0 else {
            XCTFail("Guest model unavailable")
            return
        }
        var model = [CChar](repeating: 0, count: size)
        guard sysctlbyname("hw.model", &model, &size, nil, 0) == 0,
              String(cString: model).hasPrefix("VirtualMac") else {
            XCTFail("Fixture preparation requires the test guest")
            return
        }
        let environment = ProcessInfo.processInfo.environment
        let fixture = environment["NOTCH_VM_FIXTURE"] ?? ""
        guard ["closed", "general", "about"].contains(fixture) else {
            XCTFail("Explicit fixture selection required")
            return
        }
        let path = URL(fileURLWithPath: "/Applications/notch-pocket.app")
        let bytes = try Data(contentsOf: path.appendingPathComponent("Contents/MacOS/notch-pocket"))
        let hash = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
        guard hash == environment["NOTCH_VM_EXPECTED_SHA256"] else {
            XCTFail("Candidate identity mismatch")
            return
        }
        let running = NSRunningApplication.runningApplications(withBundleIdentifier: "com.jdylanmc.notchpocket")
        guard running.count == 1, running[0].bundleURL == path else {
            XCTFail("Exact running candidate required")
            return
        }
        let originalPID = running[0].processIdentifier
        let app = XCUIApplication(url: path)
        app.activate()
        let settings = app.descendants(matching: .any).matching(identifier: "NotchPocketSettingsWindow").firstMatch
        if !settings.exists && fixture != "closed" {
            let panels = app.dialogs.matching(NSPredicate(format: "identifier BEGINSWITH %@", "com.jdylanmc.notchpocket.notch.v1.window."))
            XCTAssertEqual(panels.count, 1)
            let panel = panels.firstMatch
            let origin = panel.coordinate(withNormalizedOffset: .zero)
            let pointer = CGEvent(source: nil)?.location
            let frame = panel.frame
            origin.withOffset(CGVector(dx: frame.width / 2, dy: 5)).hover()
            let gear = panel.buttons.matching(NSPredicate(format: "label IN %@ OR identifier IN %@", ["Settings", "gear"], ["Settings", "gear"])).firstMatch
            let ready = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: gear)
            XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 5), .completed)
            gear.click()
            XCTAssertTrue(settings.waitForExistence(timeout: 5))
            if let pointer {
                origin.withOffset(CGVector(dx: pointer.x - frame.minX, dy: pointer.y - frame.minY)).hover()
            }
        }
        if fixture == "closed" {
            if settings.exists {
                settings.buttons[XCUIIdentifierCloseWindow].click()
                let closed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: settings)
                XCTAssertEqual(XCTWaiter.wait(for: [closed], timeout: 5), .completed)
            }
        } else {
            let pane = fixture == "general" ? "General" : "About"
            let row = settings.descendants(matching: .outlineRow).containing(.staticText, identifier: pane).firstMatch
            let control = row.staticTexts[pane]
            if !row.exists || !row.isSelected {
                let ready = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: control)
                XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 5), .completed)
                control.click()
            }
            let selected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "selected == true"), object: row)
            XCTAssertEqual(XCTWaiter.wait(for: [selected], timeout: 5), .completed)
            if fixture == "about" {
                let build = settings.staticTexts["(\(environment["NOTCH_VM_EXPECTED_BUILD"] ?? ""))"]
                if !build.exists { settings.staticTexts["Version"].click() }
                XCTAssertTrue(build.waitForExistence(timeout: 5))
            }
        }
        let after = NSRunningApplication.runningApplications(withBundleIdentifier: "com.jdylanmc.notchpocket")
        XCTAssertEqual(after.count, 1)
        XCTAssertEqual(after.first?.processIdentifier, originalPID)
        XCTAssertEqual(after.first?.bundleURL, path)
        print("NOTCH_VM_FIXTURE_READY \(fixture)")
    }
}
