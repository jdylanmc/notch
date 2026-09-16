//
//  MusicPresentationPolicyTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class MusicPresentationPolicyTests: XCTestCase {
    func testPlayingUsesPlayerPresentationWithControls() {
        let presentation = MusicPresentationPolicy.presentation(isPlaying: true)

        XCTAssertEqual(presentation, .player)
        XCTAssertTrue(presentation.showsPlaybackControls)
        XCTAssertFalse(presentation.showsLauncherIcon)
    }

    func testNotPlayingCollapsesToLauncherWithoutControls() {
        let presentation = MusicPresentationPolicy.presentation(isPlaying: false)

        XCTAssertEqual(presentation, .launcher)
        XCTAssertFalse(presentation.showsPlaybackControls)
        XCTAssertTrue(presentation.showsLauncherIcon)
    }
}
