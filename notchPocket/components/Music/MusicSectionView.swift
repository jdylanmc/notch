//
//  MusicSectionView.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//

import Defaults
import SwiftUI

@MainActor
func musicAppLaunchIcon(for bundleIdentifier: String?) -> Image {
    if let bundleIdentifier,
       let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleIdentifier) {
        return Image(nsImage: NSWorkspace.shared.icon(forFile: url.path))
    }
    return Image(systemName: "music.note")
}

struct MusicLaunchInteractionPreferenceKey: PreferenceKey {
    static let defaultValue = false

    static func reduce(value: inout Bool, nextValue: () -> Bool) {
        value = value || nextValue()
    }
}

struct MusicLaunchFeedbackHoverPreferenceKey: PreferenceKey {
    static let defaultValue = false

    static func reduce(value: inout Bool, nextValue: () -> Bool) {
        value = value || nextValue()
    }
}

@MainActor
struct MusicSectionView<PlayingContent: View>: View {
    @ObservedObject private var musicManager = MusicManager.shared
    @Default(.lastNowPlayingLauncherBundleIdentifier) private var rememberedBundleIdentifier
    @Default(.lastSupportedNowPlayingBundleIdentifier) private var legacyRememberedBundleIdentifier
    @StateObject private var launch = MusicLaunchTransaction(launcher: MusicManager.shared.musicAppLauncher)
    @State private var isHoveringFeedback = false

    private let playingContent: (@escaping () -> Void) -> PlayingContent

    init(@ViewBuilder playingContent: @escaping (@escaping () -> Void) -> PlayingContent) {
        self.playingContent = playingContent
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if MusicPresentationPolicy.presentation(isPlaying: musicManager.isPlaying).showsPlaybackControls {
                playingContent(openMusicApp)
            } else {
                launcherButton
            }
            if let failure = launch.failure {
                failureFeedback(failure)
                    .onHover { isHoveringFeedback = $0 }
                    .onDisappear { isHoveringFeedback = false }
            }
        }
        .preference(key: MusicLaunchInteractionPreferenceKey.self, value: launch.isLaunching)
        .preference(
            key: MusicLaunchFeedbackHoverPreferenceKey.self,
            value: launch.failure != nil && isHoveringFeedback
        )
        .onChange(of: launchContext) { _, _ in
            clearLaunch()
        }
        .onDisappear(perform: clearLaunch)
    }

    private var launchContext: MusicLaunchContext {
        // Defaults wrappers invalidate the view when history changes without a playback update.
        MusicLaunchContext(
            isPlaying: musicManager.isPlaying,
            preferred: musicManager.preferredMediaController,
            effective: musicManager.effectiveMediaController,
            observedBundleIdentifier: musicManager.bundleIdentifier,
            rememberedBundleIdentifier: rememberedBundleIdentifier ?? legacyRememberedBundleIdentifier
        )
    }

    private var launcherButton: some View {
        Button(action: openMusicApp) {
            launcherIcon
                .resizable()
                .scaledToFit()
                .frame(width: 32, height: 32)
                .padding(4)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(launch.isLaunching)
        .accessibilityLabel(Text(MusicAppFeedback.launchLabel(for: launchContext.bundleIdentifier)))
        .accessibilityHint("Opens your preferred music app without starting playback.")
        .accessibilityIdentifier("com.jdylanmc.notchpocket.music.v1.idle-launcher")
        .help(Text(MusicAppFeedback.launchLabel(for: launchContext.bundleIdentifier)))
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var launcherIcon: Image {
        musicAppLaunchIcon(for: launchContext.bundleIdentifier)
    }

    @ViewBuilder
    private func failureFeedback(_ outcome: MusicAppLaunchOutcome) -> some View {
        if let message = MusicAppFeedback.conciseMessage(for: outcome),
           let guidance = MusicAppFeedback.message(for: outcome) {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                    .accessibilityHidden(true)
                Text(message)
                    .font(.caption.weight(.semibold))
                    .lineLimit(2)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityHint(Text(guidance))
                    .accessibilityIdentifier("com.jdylanmc.notchpocket.music.v1.launch-status")
                Button("OK") {
                    launch.dismissFailure()
                    isHoveringFeedback = false
                }
                .buttonStyle(.plain)
                .font(.caption.weight(.semibold))
                .frame(minWidth: 24, minHeight: 24)
                .contentShape(Rectangle())
                .accessibilityIdentifier("com.jdylanmc.notchpocket.music.v1.launch-dismiss")
            }
            .frame(height: 32)
            .help(Text(guidance))
            .accessibilityElement(children: .contain)
        }
    }

    private func clearLaunch() {
        launch.cancel()
        isHoveringFeedback = false
    }

    private func openMusicApp() {
        let manager = musicManager
        launch.start(context: launchContext, currentContext: { manager.musicLaunchContext })
    }
}
