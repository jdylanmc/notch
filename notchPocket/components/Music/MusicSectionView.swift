//
//  MusicSectionView.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//

import Defaults
import SwiftUI

@MainActor
struct MusicSectionView<PlayingContent: View>: View {
    @ObservedObject private var musicManager = MusicManager.shared
    @Default(.lastSupportedNowPlayingBundleIdentifier) private var rememberedBundleIdentifier
    @State private var launchFailure: LocalizedStringResource?

    private let playingContent: (@escaping () -> Void) -> PlayingContent

    init(@ViewBuilder playingContent: @escaping (@escaping () -> Void) -> PlayingContent) {
        self.playingContent = playingContent
    }

    var body: some View {
        Group {
            if MusicPresentationPolicy.presentation(isPlaying: musicManager.isPlaying).showsPlaybackControls {
                playingContent(openMusicApp)
            } else {
                Button(action: openMusicApp) {
                    launcherIcon
                        .resizable()
                        .scaledToFit()
                        .frame(width: 32, height: 32)
                        .padding(4)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text(launcherLabel))
                .accessibilityHint("Opens your preferred music app without starting playback.")
                .help(Text(launcherLabel))
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .alert("Could not open music app", isPresented: isShowingLaunchFailure, presenting: launchFailure) { _ in
            Button("OK", role: .cancel) {}
        } message: { message in
            Text(message)
        }
    }

    private var launchTarget: String? {
        MusicLaunchTargetResolver.bundleIdentifier(
            preferred: musicManager.preferredMediaController,
            currentBundleIdentifier: musicManager.bundleIdentifier,
            rememberedNowPlayingBundleIdentifier: rememberedBundleIdentifier
        )
    }

    private var launcherIcon: Image {
        if let launchTarget {
            return appIcon(for: launchTarget)
        }
        return Image(systemName: "music.note")
    }

    private var launcherLabel: LocalizedStringResource {
        guard let launchTarget,
              let controller = MediaControllerType(nowPlayingBundleIdentifier: launchTarget) else {
            return "Open music app"
        }
        return LocalizedStringResource(
            "Open \(controller.localizedString)",
            comment: "Music launcher button label. The placeholder is the user's selected music app."
        )
    }

    private var isShowingLaunchFailure: Binding<Bool> {
        Binding(
            get: { launchFailure != nil },
            set: { if !$0 { launchFailure = nil } }
        )
    }

    private func openMusicApp() {
        Task { @MainActor in
            let outcome = await musicManager.openMusicApp()
            switch outcome {
            case .opened:
                launchFailure = nil
            case .noTarget:
                launchFailure = "No music app is selected. Choose a Music Source in Settings or play music once with Now Playing."
            case .notInstalled(let bundleIdentifier):
                launchFailure = LocalizedStringResource(
                    "Music app \(bundleIdentifier) is not installed. Install it or choose a different Music Source in Settings.",
                    comment: "Music launcher failure. The placeholder identifies the app that could not be found."
                )
            case .openFailed(let bundleIdentifier):
                launchFailure = LocalizedStringResource(
                    "Music app \(bundleIdentifier) could not be opened. Try opening it from Applications.",
                    comment: "Music launcher failure. The placeholder identifies the app that macOS could not open."
                )
            }
        }
    }
}
