//
//  MusicAppFeedbackTests.swift
//  notchPocketTests
//

import Foundation
import XCTest

@testable import notchPocket

final class MusicAppFeedbackTests: XCTestCase {
    private let unknownBundleIdentifier = "com.example.unknown-player"

    private func render(_ resource: LocalizedStringResource?) -> String? {
        resource.map { String(localized: $0) }
    }

    // MARK: - displayName

    func testKnownBundleIdentifiersUseExistingLocalizedNames() {
        XCTAssertEqual(
            render(MusicAppFeedback.displayName(for: MediaAppBundleID.spotify)),
            MediaControllerType.spotify.localizedString
        )
        XCTAssertEqual(
            render(MusicAppFeedback.displayName(for: MediaAppBundleID.appleMusic)),
            MediaControllerType.appleMusic.localizedString
        )
        XCTAssertEqual(
            render(MusicAppFeedback.displayName(for: MediaAppBundleID.youTubeMusic)),
            MediaControllerType.youtubeMusic.localizedString
        )
    }

    func testKnownAppsHaveDistinctDisplayNames() {
        let names = [
            MediaAppBundleID.spotify,
            MediaAppBundleID.appleMusic,
            MediaAppBundleID.youTubeMusic,
        ].compactMap { render(MusicAppFeedback.displayName(for: $0)) }

        XCTAssertEqual(names.count, 3)
        XCTAssertEqual(Set(names).count, 3)
    }

    func testDisplayNameTrimsBundleIdentifier() {
        XCTAssertEqual(
            render(MusicAppFeedback.displayName(for: "  \(MediaAppBundleID.spotify) \n")),
            MediaControllerType.spotify.localizedString
        )
    }

    func testDisplayNameIsNilForMissingOrBlankIdentifier() {
        XCTAssertNil(MusicAppFeedback.displayName(for: nil))
        XCTAssertNil(MusicAppFeedback.displayName(for: ""))
        XCTAssertNil(MusicAppFeedback.displayName(for: "  \t\n"))
    }

    func testDisplayNameIsNilForUnknownIdentifier() {
        XCTAssertNil(MusicAppFeedback.displayName(for: unknownBundleIdentifier))
    }

    // MARK: - message

    func testSuccessfulLaunchProducesNoMessage() {
        let outcome = MusicAppLaunchOutcome.opened(bundleIdentifier: MediaAppBundleID.spotify)

        XCTAssertNil(MusicAppFeedback.message(for: outcome))
    }

    func testEveryFailureOutcomeProducesAMessage() {
        let failures: [MusicAppLaunchOutcome] = [
            .noTarget,
            .notInstalled(bundleIdentifier: MediaAppBundleID.spotify),
            .openFailed(bundleIdentifier: MediaAppBundleID.spotify),
            .notInstalled(bundleIdentifier: unknownBundleIdentifier),
            .openFailed(bundleIdentifier: unknownBundleIdentifier),
        ]

        for failure in failures {
            let message = render(MusicAppFeedback.message(for: failure))

            XCTAssertNotNil(message, "\(failure) must explain itself to the user")
            XCTAssertFalse(message?.isEmpty ?? true, "\(failure) must not render an empty message")
        }
    }

    func testNoTargetMessageGuidesWithoutNamingAnApp() {
        let message = render(MusicAppFeedback.message(for: .noTarget))

        XCTAssertNotNil(message)
        XCTAssertFalse(message?.contains("com.") ?? true)
    }

    func testNotInstalledMessageNamesAKnownApp() {
        let outcome = MusicAppLaunchOutcome.notInstalled(bundleIdentifier: MediaAppBundleID.spotify)
        let message = render(MusicAppFeedback.message(for: outcome))

        XCTAssertNotNil(message)
        XCTAssertTrue(message?.contains(MediaControllerType.spotify.localizedString) ?? false)
        XCTAssertFalse(message?.contains(MediaAppBundleID.spotify) ?? true)
    }

    func testOpenFailureMessageNamesAKnownApp() {
        let outcome = MusicAppLaunchOutcome.openFailed(bundleIdentifier: MediaAppBundleID.appleMusic)
        let message = render(MusicAppFeedback.message(for: outcome))

        XCTAssertNotNil(message)
        XCTAssertTrue(message?.contains(MediaControllerType.appleMusic.localizedString) ?? false)
        XCTAssertFalse(message?.contains(MediaAppBundleID.appleMusic) ?? true)
    }

    func testUnknownBundleIdentifiersNeverReachUserFacingMessages() {
        let outcomes: [MusicAppLaunchOutcome] = [
            .notInstalled(bundleIdentifier: unknownBundleIdentifier),
            .openFailed(bundleIdentifier: unknownBundleIdentifier),
        ]

        for outcome in outcomes {
            guard let message = render(MusicAppFeedback.message(for: outcome)) else {
                XCTFail("\(outcome) must still explain the failure")
                continue
            }

            XCTAssertFalse(message.contains(unknownBundleIdentifier))
            XCTAssertFalse(message.contains("com."), "raw identifiers must not leak: \(message)")
            XCTAssertTrue(message.contains(" "), "generic wording must be a sentence: \(message)")
        }
    }
}
