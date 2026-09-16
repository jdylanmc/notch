//
//  MusicSectionView.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//

import Defaults
import SwiftUI

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
    @Default(.lastSupportedNowPlayingBundleIdentifier) private var rememberedBundleIdentifier
    @State private var launchFailure: LocalizedStringResource?
    @State private var launchTask: Task<Void, Never>?
    @State private var isHoveringFeedback = false

    private let playingContent: (@escaping () -> Void) -> PlayingContent

    init(@ViewBuilder playingContent: @escaping (@escaping () -> Void) -> PlayingContent) {
        self.playingContent = playingContent
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
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
                .disabled(launchTask != nil)
                .accessibilityLabel(Text(launcherLabel))
                .accessibilityHint("Opens your preferred music app without starting playback.")
                .help(Text(launcherLabel))
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .overlay(alignment: .topLeading) {
            if let launchFailure {
                failureFeedback(launchFailure)
                    .onHover { isHoveringFeedback = $0 }
                    .onDisappear { isHoveringFeedback = false }
            }
        }
        .preference(
            key: MusicLaunchInteractionPreferenceKey.self,
            value: launchTask != nil
        )
        .preference(
            key: MusicLaunchFeedbackHoverPreferenceKey.self,
            value: launchFailure != nil && isHoveringFeedback
        )
        .onDisappear {
            launchTask?.cancel()
            launchTask = nil
            launchFailure = nil
            isHoveringFeedback = false
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
        guard let name = MusicAppFeedback.displayName(for: launchTarget) else {
            return "Open music app"
        }
        return LocalizedStringResource(
            "Open \(String(localized: name))",
            comment: "Music launcher button label. The placeholder is the user's selected music app."
        )
    }

    private func failureFeedback(_ message: LocalizedStringResource) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
                .accessibilityHidden(true)

            ScrollView(.vertical) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Could not open music app")
                        .font(.caption.weight(.semibold))
                    Text(message)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .help(Text(message))

            Button("OK") {
                launchFailure = nil
            }
            .buttonStyle(.plain)
            .font(.caption.weight(.semibold))
            .frame(minWidth: 24, minHeight: 24)
            .contentShape(Rectangle())
        }
        .padding(.vertical, 4)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(.black)
        .clipped()
        .accessibilityElement(children: .contain)
    }

    private func openMusicApp() {
        guard launchTask == nil else { return }
        launchFailure = nil
        launchTask = Task { @MainActor in
            let outcome = await musicManager.openMusicApp()
            guard !Task.isCancelled else { return }
            launchFailure = MusicAppFeedback.message(for: outcome)
            launchTask = nil
        }
    }
}
