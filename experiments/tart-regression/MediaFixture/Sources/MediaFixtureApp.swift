import AppKit
import AVFoundation
import MediaPlayer

@MainActor
final class MediaFixtureApp: NSObject, NSApplicationDelegate, AVAudioPlayerDelegate {
    private var window: NSWindow?
    private var labels: [String: NSTextField] = [:]
    private var buttons: [NSButton] = []
    private var store: FixtureStore?
    private var state = FixtureState(launchCount: 0)
    private var player: AVAudioPlayer?
    private var timer: Timer?
    private var commandTargets: [(MPRemoteCommand, Any)] = []
    private var receiptFailed = false
    private let center = MPNowPlayingInfoCenter.default()

    func applicationDidFinishLaunching(_ notification: Notification) {
        makeWindow()
        do {
            guard Bundle.main.bundleIdentifier == FixtureIdentity.bundleID else {
                throw FixtureStoreError.unsafeDirectory
            }
            let root = Bundle.main.bundleURL.deletingLastPathComponent()
                .appendingPathComponent("MediaFixtureData", isDirectory: true)
            let store = try FixtureStore(root: root)
            self.store = store
            state = FixtureState(launchCount: store.launchCount)
            let player = try AVAudioPlayer(contentsOf: store.audioURL)
            guard abs(player.duration - FixtureIdentity.duration) < 0.01 else {
                throw FixtureStoreError.ioFailure
            }
            player.volume = 0
            player.numberOfLoops = 0
            player.delegate = self
            self.player = player
            configureRemoteCommands()
            publish()
            record("launch_idle")
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.sample() }
            }
        } catch {
            fail("initialization_failed")
        }
        refreshLabels()
        window?.makeKeyAndOrderFront(nil)
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        state.activation(true)
        record("became_active")
    }

    func applicationDidResignActive(_ notification: Notification) {
        state.activation(false)
        record("resigned_active")
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        state.reopen()
        window?.makeKeyAndOrderFront(nil)
        record("reopen")
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        timer?.invalidate()
        for (command, target) in commandTargets {
            command.removeTarget(target)
            command.isEnabled = false
        }
        player?.stop()
        player?.currentTime = 0
        state.stopped(observation: observation)
        publish()
        record("shutdown_cleared")
    }

    private var observation: PlayerObservation {
        PlayerObservation(isPlaying: player?.isPlaying ?? false, elapsed: player?.currentTime ?? 0)
    }

    private func perform(_ command: FixtureCommand, origin: FixtureOrigin) -> MPRemoteCommandHandlerStatus {
        let action = state.request(command, origin: origin)
        guard let player, !receiptFailed else {
            fail("producer_unavailable")
            return .commandFailed
        }
        switch action {
        case .play:
            if player.currentTime >= player.duration { player.currentTime = 0 }
            let success = player.play()
            state.started(success: success, observation: observation)
        case .pause:
            player.pause()
            state.paused(observation: observation)
        case .stop:
            player.stop()
            player.currentTime = 0
            state.stopped(observation: observation)
        case .toggle:
            preconditionFailure("Toggle is resolved by FixtureState.request")
        }
        if state.errorCode != nil { player.stop() }
        state.sample(observation)
        publish()
        record("\(origin.rawValue)_\(command.rawValue)")
        return state.errorCode == nil ? .success : .commandFailed
    }

    private func configureRemoteCommands() {
        let commands = MPRemoteCommandCenter.shared()
        let enabled: [(MPRemoteCommand, FixtureCommand)] = [
            (commands.playCommand, .play),
            (commands.pauseCommand, .pause),
            (commands.stopCommand, .stop),
            (commands.togglePlayPauseCommand, .toggle)
        ]
        for (remote, command) in enabled {
            remote.isEnabled = true
            let token = remote.addTarget { [weak self] _ in
                // MediaPlayer may deliver off-main; all player/UI state is main-actor owned.
                if Thread.isMainThread {
                    return MainActor.assumeIsolated {
                        self?.perform(command, origin: .remote) ?? .commandFailed
                    }
                }
                return DispatchQueue.main.sync {
                    self?.perform(command, origin: .remote) ?? .commandFailed
                }
            }
            commandTargets.append((remote, token))
        }
    }

    private func publish() {
        if state.metadataPublished {
            center.nowPlayingInfo = [
                MPMediaItemPropertyTitle: FixtureIdentity.title,
                MPMediaItemPropertyArtist: FixtureIdentity.artist,
                MPMediaItemPropertyAlbumTitle: FixtureIdentity.album,
                MPMediaItemPropertyPlaybackDuration: FixtureIdentity.duration,
                MPNowPlayingInfoPropertyElapsedPlaybackTime: state.engineElapsed,
                MPNowPlayingInfoPropertyPlaybackRate: state.engineIsPlaying ? 1.0 : 0.0,
                MPNowPlayingInfoPropertyDefaultPlaybackRate: 1.0,
                MPNowPlayingInfoPropertyMediaType: MPNowPlayingInfoMediaType.audio.rawValue
            ]
            center.playbackState = state.engineIsPlaying ? .playing : .paused
        } else {
            center.nowPlayingInfo = nil
            center.playbackState = .stopped
        }
    }

    private func sample() {
        guard let player, !receiptFailed else { return }
        let wasPlaying = state.engineIsPlaying
        guard wasPlaying || player.isPlaying else { return }
        state.sample(observation)
        if let code = state.errorCode {
            fail(code)
            return
        }
        publish()
        if wasPlaying || state.engineIsPlaying {
            record("engine_sample")
        } else {
            refreshLabels()
        }
    }

    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        if Thread.isMainThread {
            MainActor.assumeIsolated { finished(success: flag) }
        } else {
            DispatchQueue.main.sync { self.finished(success: flag) }
        }
    }

    nonisolated func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        if Thread.isMainThread {
            MainActor.assumeIsolated { fail("audio_decode_failed") }
        } else {
            DispatchQueue.main.sync { self.fail("audio_decode_failed") }
        }
    }

    private func finished(success: Bool) {
        state.finished(success: success, observation: observation)
        if let code = state.errorCode {
            fail(code)
            return
        }
        publish()
        record("audio_finished")
    }

    private func fail(_ code: String) {
        player?.stop()
        state.sample(observation)
        state.fail(code)
        publish()
        fputs("NOTCH_MEDIA_FIXTURE_ERROR \(code)\n", stderr)
        record("failure")
    }

    private func record(_ event: String) {
        if let store, !receiptFailed {
            do {
                try store.append(event: event, state: state)
            } catch {
                receiptFailed = true
                player?.stop()
                state.sample(observation)
                state.fail("receipt_write_failed")
                publish()
                fputs("NOTCH_MEDIA_FIXTURE_ERROR receipt_write_failed\n", stderr)
            }
        }
        refreshLabels()
    }

    @objc private func playPressed() { _ = perform(.play, origin: .ui) }
    @objc private func pausePressed() { _ = perform(.pause, origin: .ui) }
    @objc private func stopPressed() { _ = perform(.stop, origin: .ui) }
    @objc private func quitPressed() { NSApp.terminate(nil) }

    private func makeWindow() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 680, height: 590),
            styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false
        )
        self.window = window
        window.title = "Notch Regression Media Fixture"
        window.setAccessibilityIdentifier("mediafixture.v1.window")
        window.isReleasedWhenClosed = false
        window.isRestorable = false
        window.center()
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.translatesAutoresizingMaskIntoConstraints = false
        let heading = NSTextField(labelWithString: "Local test producer - muted 30-second generated tone")
        heading.font = .boldSystemFont(ofSize: 15)
        stack.addArrangedSubview(heading)
        let controls = NSStackView()
        for (title, identifier, selector) in [
            ("Play", "play", #selector(playPressed)),
            ("Pause", "pause", #selector(pausePressed)),
            ("Stop", "stop", #selector(stopPressed)),
            ("Quit", "quit", #selector(quitPressed))
        ] {
            let button = NSButton(title: title, target: self, action: selector)
            button.bezelStyle = .rounded
            button.setAccessibilityIdentifier("mediafixture.v1.\(identifier)")
            controls.addArrangedSubview(button)
            if identifier != "quit" { buttons.append(button) }
        }
        stack.addArrangedSubview(controls)
        for name in ["identity", "status", "engine", "elapsed", "publication", "launch-count",
                     "activation-count", "reopen-count", "active", "play-attempts", "play-starts",
                     "ui-commands", "remote-commands", "natural-ends", "error"] {
            let field = NSTextField(labelWithString: "")
            field.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
            field.setAccessibilityIdentifier("mediafixture.v1.\(name)")
            field.setAccessibilityLabel(name)
            labels[name] = field
            stack.addArrangedSubview(field)
        }
        stack.addArrangedSubview(NSTextField(
            wrappingLabelWithString:
                "Counters and publication are producer-local, not proof of OS delivery or audible output."
        ))
        guard let content = window.contentView else { preconditionFailure("Missing window content") }
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 20),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -20),
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 20),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: content.bottomAnchor, constant: -20)
        ])
        installMenu()
    }

    private func installMenu() {
        let menu = NSMenu()
        let applicationItem = NSMenuItem()
        let applicationMenu = NSMenu()
        applicationMenu.addItem(withTitle: "Quit Media Fixture", action: #selector(quitPressed), keyEquivalent: "q")
            .target = self
        applicationItem.submenu = applicationMenu
        menu.addItem(applicationItem)
        NSApp.mainMenu = menu
    }

    private func refreshLabels() {
        func commands(_ counts: [String: Int]) -> String {
            FixtureCommand.allCases.map { "\($0.rawValue)=\(counts[$0.rawValue, default: 0])" }.joined(separator: " ")
        }
        let values = [
            "identity": "\(FixtureIdentity.bundleID) pid=\(getpid())",
            "status": state.phase.rawValue,
            "engine": state.engineIsPlaying ? "playing" : "not-playing",
            "elapsed": String(format: "%.3f / 30.000", state.engineElapsed),
            "publication": state.metadataPublished ? state.phase.rawValue : "cleared",
            "launch-count": String(state.launchCount),
            "activation-count": String(state.activationCount),
            "reopen-count": String(state.reopenCount),
            "active": String(state.active),
            "play-attempts": String(state.playAttempts),
            "play-starts": String(state.playStarts),
            "ui-commands": commands(state.uiCommands),
            "remote-commands": commands(state.remoteCommands),
            "natural-ends": String(state.naturalEnds),
            "error": state.errorCode ?? "none"
        ]
        for (name, value) in values { labels[name]?.stringValue = value }
        for button in buttons { button.isEnabled = player != nil && !receiptFailed }
    }
}

@main
enum MediaFixtureMain {
    @MainActor static func main() {
        let app = NSApplication.shared
        let delegate = MediaFixtureApp()
        app.setActivationPolicy(.regular)
        app.delegate = delegate
        withExtendedLifetime(delegate) { app.run() }
    }
}
