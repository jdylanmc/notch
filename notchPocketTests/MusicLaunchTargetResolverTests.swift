//
//  MusicLaunchTargetResolverTests.swift
//  notchPocketTests
//

import XCTest

@testable import notchPocket

final class MusicLaunchTargetResolverTests: XCTestCase {
    func testPlayingAppleMusicFallbackOpensObservedSourceWithoutNowPlayingHistory() {
        let context = MusicLaunchContext(
            isPlaying: true, preferred: .nowPlaying, effective: .appleMusic,
            observedBundleIdentifier: MediaAppBundleID.appleMusic, rememberedBundleIdentifier: nil
        )
        XCTAssertEqual(context.bundleIdentifier, MediaAppBundleID.appleMusic)
    }

    func testPlayingSpotifyFallbackIgnoresOtherRememberedPublisher() {
        let context = MusicLaunchContext(
            isPlaying: true, preferred: .nowPlaying, effective: .spotify,
            observedBundleIdentifier: MediaAppBundleID.spotify, rememberedBundleIdentifier: "org.videolan.vlc"
        )
        XCTAssertEqual(context.bundleIdentifier, MediaAppBundleID.spotify)
    }

    func testIdleFallbackDoesNotMasqueradeAsTrueNowPlayingPublisher() {
        for remembered in [nil, "org.videolan.vlc"] {
            let context = MusicLaunchContext(
                isPlaying: false, preferred: .nowPlaying, effective: .appleMusic,
                observedBundleIdentifier: MediaAppBundleID.appleMusic, rememberedBundleIdentifier: remembered
            )
            XCTAssertEqual(context.bundleIdentifier, remembered)
        }
    }

    func testIdleDirectPreferenceWinsButPlayingObservedSourceWins() {
        for playing in [false, true] {
            let context = MusicLaunchContext(
                isPlaying: playing, preferred: .spotify, effective: .spotify,
                observedBundleIdentifier: MediaAppBundleID.appleMusic, rememberedBundleIdentifier: "org.videolan.vlc"
            )
            XCTAssertEqual(context.bundleIdentifier, playing ? MediaAppBundleID.appleMusic : MediaAppBundleID.spotify)
        }
    }

    func testTrueNowPlayingUsesCurrentArbitraryPublisherBeforeHistory() {
        for source in ["org.videolan.vlc", "com.google.Chrome", "org.example.ExternalPlayer"] {
            for playing in [false, true] {
                let context = MusicLaunchContext(
                    isPlaying: playing, preferred: .nowPlaying, effective: .nowPlaying,
                    observedBundleIdentifier: source, rememberedBundleIdentifier: MediaAppBundleID.spotify
                )
                XCTAssertEqual(context.bundleIdentifier, source)
                XCTAssertEqual(String(localized: MusicAppFeedback.launchLabel(for: context.bundleIdentifier)), "Open music app")
            }
        }
    }

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

    func testNowPlayingPreservesAnExternalPlayersBundleIdentifier() {
        XCTAssertEqual(resolve(.nowPlaying, current: "org.example.external-player"), "org.example.external-player")
        XCTAssertEqual(resolve(.nowPlaying, remembered: "org.example.remembered-player"), "org.example.remembered-player")
    }

    func testRememberedLauncherTargetSurvivesClearedAndBlankNowPlayingUpdates() {
        var remembered: String?
        for observed in [" org.example.external-player ", "", " \n"] {
            remembered = MusicLaunchTargetResolver.rememberedBundleIdentifier(observed: observed, previous: remembered)
            XCTAssertEqual(remembered, "org.example.external-player")
        }
        XCTAssertEqual(
            MusicLaunchTargetResolver.rememberedBundleIdentifier(observed: nil, previous: remembered),
            "org.example.external-player"
        )
    }

    func testNewNowPlayingSourceReplacesRememberedLauncherTarget() {
        XCTAssertEqual(
            MusicLaunchTargetResolver.rememberedBundleIdentifier(
                observed: "org.example.new-player", previous: MediaAppBundleID.spotify
            ),
            "org.example.new-player"
        )
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
