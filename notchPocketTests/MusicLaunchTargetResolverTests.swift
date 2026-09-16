//
//  MusicLaunchTargetResolverTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class MusicLaunchTargetResolverTests: XCTestCase {
    private func resolve(
        _ preferred: MediaControllerType,
        current: String? = nil,
        remembered: String? = nil
    ) -> String? {
        MusicLaunchTargetResolver.bundleIdentifier(
            preferred: preferred,
            currentBundleIdentifier: current,
            rememberedNowPlayingBundleIdentifier: remembered
        )
    }

    func testSpotifyResolvesToSpotifyBundleIdentifier() {
        XCTAssertEqual(resolve(.spotify), MediaAppBundleID.spotify)
    }

    func testAppleMusicResolvesToAppleMusicBundleIdentifier() {
        XCTAssertEqual(resolve(.appleMusic), MediaAppBundleID.appleMusic)
    }

    func testYouTubeMusicResolvesToYouTubeMusicBundleIdentifier() {
        XCTAssertEqual(resolve(.youtubeMusic), MediaAppBundleID.youTubeMusic)
    }

    func testDirectControllerIgnoresObservedBundleIdentifiers() {
        let resolved = resolve(
            .spotify,
            current: MediaAppBundleID.appleMusic,
            remembered: MediaAppBundleID.youTubeMusic
        )

        XCTAssertEqual(resolved, MediaAppBundleID.spotify)
    }

    func testNowPlayingPrefersCurrentBundleIdentifier() {
        let resolved = resolve(
            .nowPlaying,
            current: MediaAppBundleID.spotify,
            remembered: MediaAppBundleID.appleMusic
        )

        XCTAssertEqual(resolved, MediaAppBundleID.spotify)
    }

    func testNowPlayingFallsBackToRememberedBundleIdentifierWhenCurrentIsMissing() {
        XCTAssertEqual(
            resolve(.nowPlaying, current: nil, remembered: MediaAppBundleID.spotify),
            MediaAppBundleID.spotify
        )
    }

    func testNowPlayingTreatsBlankCurrentBundleIdentifierAsAbsent() {
        XCTAssertEqual(
            resolve(.nowPlaying, current: "   \n", remembered: MediaAppBundleID.spotify),
            MediaAppBundleID.spotify
        )
    }

    func testNowPlayingWithoutAnyObservedTargetResolvesToNil() {
        XCTAssertNil(resolve(.nowPlaying, current: nil, remembered: nil))
    }

    func testNowPlayingWithBlankObservedTargetsResolvesToNil() {
        XCTAssertNil(resolve(.nowPlaying, current: " ", remembered: "\t"))
    }

    func testNowPlayingDoesNotFallBackToAppleMusic() {
        let resolved = resolve(.nowPlaying, current: nil, remembered: nil)

        XCTAssertNotEqual(resolved, MediaAppBundleID.appleMusic)
        XCTAssertNil(resolved)
    }

    func testNowPlayingTrimsResolvedBundleIdentifier() {
        XCTAssertEqual(
            resolve(.nowPlaying, current: "  \(MediaAppBundleID.spotify) \n", remembered: nil),
            MediaAppBundleID.spotify
        )
        XCTAssertEqual(
            resolve(.nowPlaying, current: nil, remembered: " \(MediaAppBundleID.appleMusic)  "),
            MediaAppBundleID.appleMusic
        )
    }
}
