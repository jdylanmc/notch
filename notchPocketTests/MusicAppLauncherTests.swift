//
//  MusicAppLauncherTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

@MainActor
private final class MusicAppOpeningSpy: MusicAppOpening {
    enum Operation: Equatable {
        case lookup(bundleIdentifier: String)
        case open(url: URL)
    }

    private(set) var operations: [Operation] = []
    var installedApplications: [String: URL] = [:]
    var openSucceeds = true

    func applicationURL(forBundleIdentifier bundleIdentifier: String) -> URL? {
        operations.append(.lookup(bundleIdentifier: bundleIdentifier))
        return installedApplications[bundleIdentifier]
    }

    func openApplication(at url: URL) async -> Bool {
        operations.append(.open(url: url))
        return openSucceeds
    }
}

@MainActor
final class MusicAppLauncherTests: XCTestCase {
    private let spotifyURL = URL(fileURLWithPath: "/Applications/Spotify.app")

    private func makeSpy(installed: Bool = true, openSucceeds: Bool = true) -> MusicAppOpeningSpy {
        let spy = MusicAppOpeningSpy()
        if installed {
            spy.installedApplications[MediaAppBundleID.spotify] = spotifyURL
        }
        spy.openSucceeds = openSucceeds
        return spy
    }

    func testMissingTargetReportsNoTargetWithoutTouchingWorkspace() async {
        let spy = makeSpy()
        let launcher = MusicAppLauncher(workspace: spy)

        let outcome = await launcher.launch(bundleIdentifier: nil)

        XCTAssertEqual(outcome, .noTarget)
        XCTAssertTrue(spy.operations.isEmpty)
    }

    func testBlankTargetReportsNoTargetWithoutTouchingWorkspace() async {
        let spy = makeSpy()
        let launcher = MusicAppLauncher(workspace: spy)

        let outcome = await launcher.launch(bundleIdentifier: "   \n")

        XCTAssertEqual(outcome, .noTarget)
        XCTAssertTrue(spy.operations.isEmpty)
    }

    func testUninstalledTargetReportsNotInstalledWithoutOpening() async {
        let spy = makeSpy(installed: false)
        let launcher = MusicAppLauncher(workspace: spy)

        let outcome = await launcher.launch(bundleIdentifier: MediaAppBundleID.spotify)

        XCTAssertEqual(outcome, .notInstalled(bundleIdentifier: MediaAppBundleID.spotify))
        XCTAssertEqual(spy.operations, [.lookup(bundleIdentifier: MediaAppBundleID.spotify)])
    }

    func testInstalledTargetOpensApplicationAndReportsSuccess() async {
        let spy = makeSpy()
        let launcher = MusicAppLauncher(workspace: spy)

        let outcome = await launcher.launch(bundleIdentifier: MediaAppBundleID.spotify)

        XCTAssertEqual(outcome, .opened(bundleIdentifier: MediaAppBundleID.spotify))
        XCTAssertEqual(
            spy.operations,
            [.lookup(bundleIdentifier: MediaAppBundleID.spotify), .open(url: spotifyURL)]
        )
    }

    func testFailedOpenReportsOpenFailedForThatTarget() async {
        let spy = makeSpy(openSucceeds: false)
        let launcher = MusicAppLauncher(workspace: spy)

        let outcome = await launcher.launch(bundleIdentifier: MediaAppBundleID.spotify)

        XCTAssertEqual(outcome, .openFailed(bundleIdentifier: MediaAppBundleID.spotify))
        XCTAssertEqual(
            spy.operations,
            [.lookup(bundleIdentifier: MediaAppBundleID.spotify), .open(url: spotifyURL)]
        )
    }

    func testTargetIsTrimmedBeforeLookupAndReporting() async {
        let spy = makeSpy()
        let launcher = MusicAppLauncher(workspace: spy)

        let outcome = await launcher.launch(bundleIdentifier: "  \(MediaAppBundleID.spotify) \n")

        XCTAssertEqual(outcome, .opened(bundleIdentifier: MediaAppBundleID.spotify))
        XCTAssertEqual(
            spy.operations,
            [.lookup(bundleIdentifier: MediaAppBundleID.spotify), .open(url: spotifyURL)]
        )
    }

    func testLaunchOnlyOpensTheAppOnceAndInvokesNoOtherOperation() async {
        let spy = makeSpy()
        let launcher = MusicAppLauncher(workspace: spy)

        _ = await launcher.launch(bundleIdentifier: MediaAppBundleID.spotify)

        let openCount = spy.operations.filter { operation in
            if case .open = operation { return true }
            return false
        }.count
        let lookupCount = spy.operations.filter { operation in
            if case .lookup = operation { return true }
            return false
        }.count

        XCTAssertEqual(openCount, 1)
        XCTAssertEqual(lookupCount, 1)
        XCTAssertEqual(spy.operations.count, 2)
    }
}
