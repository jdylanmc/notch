//
//  MusicAppLauncher.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//

import AppKit

enum MusicSectionPresentation: Equatable {
    case player
    case launcher

    var showsPlaybackControls: Bool { self == .player }
    var showsLauncherIcon: Bool { self == .launcher }
}

enum MusicPresentationPolicy {
    static func presentation(isPlaying: Bool) -> MusicSectionPresentation {
        isPlaying ? .player : .launcher
    }
}

enum MusicLaunchTargetResolver {
    static func bundleIdentifier(
        preferred: MediaControllerType,
        currentBundleIdentifier: String?,
        rememberedNowPlayingBundleIdentifier: String?
    ) -> String? {
        switch preferred {
        case .appleMusic:
            MediaAppBundleID.appleMusic
        case .spotify:
            MediaAppBundleID.spotify
        case .youtubeMusic:
            MediaAppBundleID.youTubeMusic
        case .nowPlaying:
            rememberedBundleIdentifier(
                observed: currentBundleIdentifier,
                previous: rememberedNowPlayingBundleIdentifier
            )
        }
    }

    static func rememberedBundleIdentifier(observed: String?, previous: String?) -> String? {
        nonemptyBundleIdentifier(observed) ?? nonemptyBundleIdentifier(previous)
    }
}

struct MusicLaunchContext: Equatable {
    let isPlaying: Bool
    let preferred: MediaControllerType
    let effective: MediaControllerType?
    let observedBundleIdentifier: String?
    let rememberedBundleIdentifier: String?

    var bundleIdentifier: String? {
        if isPlaying, let observed = nonemptyBundleIdentifier(observedBundleIdentifier) {
            return observed
        }
        return MusicLaunchTargetResolver.bundleIdentifier(
            preferred: preferred,
            currentBundleIdentifier: effective == .nowPlaying ? observedBundleIdentifier : nil,
            rememberedNowPlayingBundleIdentifier: rememberedBundleIdentifier
        )
    }
}

private func nonemptyBundleIdentifier(_ value: String?) -> String? {
    guard let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines),
          !trimmed.isEmpty else { return nil }
    return trimmed
}

@MainActor
protocol MusicAppOpening {
    func applicationURL(forBundleIdentifier bundleIdentifier: String) -> URL?
    func openApplication(at url: URL) async -> Bool
}

enum MusicAppLaunchOutcome: Equatable {
    case opened(bundleIdentifier: String)
    case noTarget
    case notInstalled(bundleIdentifier: String)
    case openFailed(bundleIdentifier: String)
    case timedOut
    case alreadyOpening
    case cancelled
}

enum MusicAppFeedback {
    static func displayName(for bundleIdentifier: String?) -> LocalizedStringResource? {
        guard let bundleIdentifier = nonemptyBundleIdentifier(bundleIdentifier),
              let controller = MediaControllerType(nowPlayingBundleIdentifier: bundleIdentifier) else {
            return nil
        }
        return controller.localizedResource
    }

    static func launchLabel(for bundleIdentifier: String?) -> LocalizedStringResource {
        guard let name = displayName(for: bundleIdentifier) else { return "Open music app" }
        return LocalizedStringResource(
            "Open \(String(localized: name))",
            comment: "Music launcher button label. The placeholder is the user's selected music app."
        )
    }

    static func conciseMessage(for outcome: MusicAppLaunchOutcome) -> LocalizedStringResource? {
        switch outcome {
        case .opened, .cancelled:
            return nil
        case .noTarget:
            return "No music app selected."
        case .notInstalled(let bundleIdentifier):
            guard let name = displayName(for: bundleIdentifier) else { return "Music app is not installed." }
            return LocalizedStringResource(
                "\(String(localized: name)) is not installed.",
                comment: "Concise music launcher failure. The placeholder is a human-readable music app name."
            )
        case .openFailed:
            return "Music app open was not confirmed."
        case .timedOut:
            return "Music app open timed out."
        case .alreadyOpening:
            return "A music app open is still pending."
        }
    }

    static func message(for outcome: MusicAppLaunchOutcome) -> LocalizedStringResource? {
        switch outcome {
        case .opened, .cancelled:
            return nil
        case .noTarget:
            return "No music app is selected. Choose a Music Source in Settings or play music once with Now Playing."
        case .notInstalled(let bundleIdentifier):
            guard let name = displayName(for: bundleIdentifier) else {
                return "The selected music app is not installed. Choose a different Music Source in Settings."
            }
            return LocalizedStringResource(
                "Music app \(String(localized: name)) is not installed. Install it or choose a different Music Source in Settings.",
                comment: "Music launcher failure. The placeholder is a human-readable music app name."
            )
        case .openFailed(let bundleIdentifier):
            guard let name = displayName(for: bundleIdentifier) else {
                return "The music app open was not confirmed. It may still open. Check Applications before trying again."
            }
            return LocalizedStringResource(
                "Opening \(String(localized: name)) was not confirmed. It may still open. Check Applications before trying again.",
                comment: "Music launcher failure. The placeholder is a human-readable music app name."
            )
        case .timedOut:
            return "The music app open request timed out. It may still open. Check Applications before trying again."
        case .alreadyOpening:
            return "A previous music app open request is still pending. Check Applications before trying again."
        }
    }
}

@MainActor
final class MusicAppLauncher {
    private let workspace: any MusicAppOpening
    private(set) var isOpening = false

    init(workspace: any MusicAppOpening) {
        self.workspace = workspace
    }

    func launch(bundleIdentifier: String?) async -> MusicAppLaunchOutcome {
        guard !Task.isCancelled else { return .cancelled }
        guard let bundleIdentifier = nonemptyBundleIdentifier(bundleIdentifier) else {
            Log.music.error("Cannot open music app: no preferred or observed target")
            return .noTarget
        }
        guard !isOpening else {
            Log.music.error("Music app open still pending; refusing another OS request")
            return .alreadyOpening
        }
        guard let url = workspace.applicationURL(forBundleIdentifier: bundleIdentifier) else {
            Log.music.error("Music app is not installed: \(bundleIdentifier)")
            return .notInstalled(bundleIdentifier: bundleIdentifier)
        }
        guard !Task.isCancelled else { return .cancelled }
        isOpening = true
        defer { isOpening = false }
        let opened = await workspace.openApplication(at: url)
        guard !Task.isCancelled else { return .cancelled }
        guard opened else {
            Log.music.error("Music app open was not confirmed: \(bundleIdentifier)")
            return .openFailed(bundleIdentifier: bundleIdentifier)
        }
        Log.music.debug("Opened music app: \(bundleIdentifier)")
        return .opened(bundleIdentifier: bundleIdentifier)
    }
}

@MainActor
struct WorkspaceMusicAppOpening: MusicAppOpening {
    func applicationURL(forBundleIdentifier bundleIdentifier: String) -> URL? {
        NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleIdentifier)
    }

    func openApplication(at url: URL) async -> Bool {
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = true
        configuration.createsNewApplicationInstance = false
        // Only the native completion releases the gate; Task cancellation cannot
        // tell us whether an already-dispatched OS open is still pending.
        return await withCheckedContinuation { continuation in
            NSWorkspace.shared.openApplication(at: url, configuration: configuration) { application, error in
                if let error {
                    Log.music.error("NSWorkspace did not confirm music app open: \(error)")
                    continuation.resume(returning: false)
                } else if application != nil {
                    continuation.resume(returning: true)
                } else {
                    Log.music.error("NSWorkspace completed music app open without an application or error")
                    continuation.resume(returning: false)
                }
            }
        }
    }
}
