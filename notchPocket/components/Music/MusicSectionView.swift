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
    @State private var launchFailure: MusicAppLaunchOutcome?
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
        .frame(minHeight: launchFailure != nil ? 64 : nil, alignment: .topLeading)
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

    private func conciseFailureMessage(for outcome: MusicAppLaunchOutcome) -> LocalizedStringResource? {
        switch outcome {
        case .opened:
            return nil
        case .noTarget:
            return "No music app selected."
        case .notInstalled(let bundleIdentifier):
            guard let name = MusicAppFeedback.displayName(for: bundleIdentifier) else {
                return "Music app is not installed."
            }
            return LocalizedStringResource(
                "\(String(localized: name)) is not installed.",
                comment: "Concise music launcher failure. The placeholder is a human-readable music app name."
            )
        case .openFailed(let bundleIdentifier):
            guard let name = MusicAppFeedback.displayName(for: bundleIdentifier) else {
                return "Could not open music app"
            }
            return LocalizedStringResource(
                "\(String(localized: name)) could not be opened.",
                comment: "Concise music launcher failure. The placeholder is a human-readable music app name."
            )
        }
    }

    @ViewBuilder
    private func failureFeedback(_ outcome: MusicAppLaunchOutcome) -> some View {
        if let message = conciseFailureMessage(for: outcome),
           let guidance = MusicAppFeedback.message(for: outcome) {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                    .accessibilityHidden(true)

                Text(message)
                    .font(.caption.weight(.semibold))
                    .frame(maxWidth: .infinity, alignment: .leading)

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
            .help(Text(guidance))
            .accessibilityElement(children: .contain)
        }
    }

    private func openMusicApp() {
        guard launchTask == nil else { return }
        launchFailure = nil
        launchTask = Task { @MainActor in
            let outcome = await musicManager.openMusicApp()
            guard !Task.isCancelled else { return }
            launchFailure = MusicAppFeedback.message(for: outcome) == nil ? nil : outcome
            launchTask = nil
        }
    }
}
