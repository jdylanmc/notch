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

    func testSectionStaysVisibleInBothPresentations() {
        XCTAssertTrue(MusicPresentationPolicy.presentation(isPlaying: true).isSectionVisible)
        XCTAssertTrue(MusicPresentationPolicy.presentation(isPlaying: false).isSectionVisible)
    }

    func testResumingPlaybackRestoresPlayerPresentation() {
        var presentation = MusicPresentationPolicy.presentation(isPlaying: true)
        presentation = MusicPresentationPolicy.presentation(isPlaying: false)
        presentation = MusicPresentationPolicy.presentation(isPlaying: true)

        XCTAssertEqual(presentation, .player)
        XCTAssertTrue(presentation.showsPlaybackControls)
    }

    func testPresentationDependsOnlyOnPlaybackState() {
        XCTAssertEqual(
            MusicPresentationPolicy.presentation(isPlaying: true),
            MusicPresentationPolicy.presentation(isPlaying: true)
        )
        XCTAssertEqual(
            MusicPresentationPolicy.presentation(isPlaying: false),
            MusicPresentationPolicy.presentation(isPlaying: false)
        )
        XCTAssertNotEqual(
            MusicPresentationPolicy.presentation(isPlaying: true),
            MusicPresentationPolicy.presentation(isPlaying: false)
        )
    }
}
