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
    var isSectionVisible: Bool { true }
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
            nonemptyBundleIdentifier(currentBundleIdentifier)
                ?? nonemptyBundleIdentifier(rememberedNowPlayingBundleIdentifier)
        }
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
}

@MainActor
struct MusicAppLauncher {
    private let workspace: any MusicAppOpening

    init(workspace: any MusicAppOpening) {
        self.workspace = workspace
    }

    func launch(bundleIdentifier: String?) async -> MusicAppLaunchOutcome {
        guard let bundleIdentifier = nonemptyBundleIdentifier(bundleIdentifier) else {
            Log.music.error("Cannot open music app: no preferred or observed target")
            return .noTarget
        }
        guard let url = workspace.applicationURL(forBundleIdentifier: bundleIdentifier) else {
            Log.music.error("Music app is not installed: \(bundleIdentifier)")
            return .notInstalled(bundleIdentifier: bundleIdentifier)
        }
        guard await workspace.openApplication(at: url) else {
            Log.music.error("Failed to open music app: \(bundleIdentifier)")
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
        do {
            _ = try await NSWorkspace.shared.openApplication(at: url, configuration: configuration)
            return true
        } catch {
            Log.music.error("NSWorkspace could not open music app: \(error)")
            return false
        }
    }
}
