// Bounded derivative of PR86's public-API test producer, not its launcher journey.
// Retains repository GPL-3.0 licensing; see README.md for source provenance.
import AppKit
import AVFoundation
import MediaPlayer

@MainActor
final class MediaFixture: NSObject, NSApplicationDelegate {
    static let identity = "com.jdylanmc.notchpocket.regression.mediafixture"
    static let titles = ["Regression Alpha", "Regression Bravo", "Regression Charlie"]
    private var player: AVAudioPlayer?
    private var window: NSWindow?
    private var fields: [String: NSTextField] = [:]
    private var timer: Timer?
    private var targets: [(MPRemoteCommand, Any)] = []
    private var track = 0
    private var remoteNext = 0
    private var remotePrevious = 0
    private var error = "none"
    private var published = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        makeWindow()
        do {
            guard Bundle.main.bundleIdentifier == Self.identity else { throw CocoaError(.executableLoad) }
            let audio = try AVAudioPlayer(data: GeneratedAudio.wave(), fileTypeHint: AVFileType.wav.rawValue)
            guard abs(audio.duration - 30) < 0.01 else { throw CocoaError(.fileReadCorruptFile) }
            audio.volume = 0
            audio.numberOfLoops = 0
            player = audio
            let commands = MPRemoteCommandCenter.shared()
            for (remote, action) in [(commands.nextTrackCommand, 1), (commands.previousTrackCommand, -1)] {
                remote.isEnabled = true
                let token = remote.addTarget { [weak self] _ in
                    if Thread.isMainThread {
                        return MainActor.assumeIsolated { self?.change(action) ?? .commandFailed }
                    }
                    return DispatchQueue.main.sync { self?.change(action) ?? .commandFailed }
                }
                targets.append((remote, token))
            }
            timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.sample() }
            }
        } catch {
            fail("initialization_failed")
        }
        publish()
        refresh()
    }

    private func change(_ direction: Int) -> MPRemoteCommandHandlerStatus {
        if direction == 1 { remoteNext += 1 } else { remotePrevious += 1 }
        guard error == "none", let player, player.isPlaying else { return .commandFailed }
        player.stop()
        player.currentTime = 0
        track = (track + direction + Self.titles.count) % Self.titles.count
        guard player.play(), player.isPlaying else {
            fail("audio_start_failed")
            return .commandFailed
        }
        published = true
        publish()
        refresh()
        return .success
    }

    @objc private func play() {
        guard error == "none", let player else { fail("producer_unavailable"); return }
        // Explicit UI preparation/restoration always returns to the same synthetic track.
        player.stop()
        player.currentTime = 0
        track = 0
        guard player.play(), player.isPlaying else { fail("audio_start_failed"); return }
        published = true
        publish()
        refresh()
    }

    @objc private func stop() {
        player?.stop()
        player?.currentTime = 0
        track = 0
        published = false
        publish()
        refresh()
    }

    private func fail(_ code: String) {
        error = code
        stop()
        fputs("NOTCH_MEDIA_FIXTURE_ERROR \(code)\n", stderr)
    }

    private func sample() {
        guard let player else { return }
        guard player.currentTime.isFinite, (0...30).contains(player.currentTime) else {
            fail("invalid_engine_observation")
            return
        }
        if published && !player.isPlaying { published = false }
        publish()
        refresh()
    }

    private func publish() {
        let center = MPNowPlayingInfoCenter.default()
        if published, let player, player.isPlaying {
            center.nowPlayingInfo = [
                MPMediaItemPropertyTitle: Self.titles[track],
                MPMediaItemPropertyArtist: "Notch Test Fixture",
                MPMediaItemPropertyAlbumTitle: "Local Synthetic Audio",
                MPMediaItemPropertyPlaybackDuration: 30.0,
                MPNowPlayingInfoPropertyElapsedPlaybackTime: player.currentTime,
                MPNowPlayingInfoPropertyPlaybackRate: 1.0,
                MPNowPlayingInfoPropertyMediaType: MPNowPlayingInfoMediaType.audio.rawValue
            ]
            center.playbackState = .playing
        } else {
            center.nowPlayingInfo = nil
            center.playbackState = .stopped
        }
    }

    private func refresh() {
        let values = [
            "identity": "\(Self.identity) pid=\(getpid())",
            "title": Self.titles[track],
            "engine": player?.isPlaying == true ? "playing" : "stopped",
            "elapsed": String(format: "%.3f", player?.currentTime ?? 0),
            "publication": published ? "playing" : "cleared",
            "remote-next": String(remoteNext), "remote-previous": String(remotePrevious),
            "error": error
        ]
        for (key, value) in values { fields[key]?.stringValue = value }
    }

    private func makeWindow() {
        let window = NSWindow(contentRect: NSRect(x: 30, y: 100, width: 640, height: 380),
                              styleMask: [.titled, .closable], backing: .buffered, defer: false)
        self.window = window
        window.title = "Notch Regression Media Fixture"
        window.setAccessibilityIdentifier("mediafixture.v2.window")
        window.isRestorable = false
        window.isReleasedWhenClosed = false
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.translatesAutoresizingMaskIntoConstraints = false
        for (title, name, action) in [("Play Alpha", "play", #selector(play)), ("Stop", "stop", #selector(stop))] {
            let button = NSButton(title: title, target: self, action: action)
            button.setAccessibilityIdentifier("mediafixture.v2." + name)
            stack.addArrangedSubview(button)
        }
        for key in ["identity", "title", "engine", "elapsed", "publication", "remote-next", "remote-previous", "error"] {
            let field = NSTextField(labelWithString: "")
            field.setAccessibilityIdentifier("mediafixture.v2." + key)
            field.setAccessibilityLabel(key)
            fields[key] = field
            stack.addArrangedSubview(field)
        }
        guard let content = window.contentView else { preconditionFailure("Missing content view") }
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 20),
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 20),
            stack.trailingAnchor.constraint(lessThanOrEqualTo: content.trailingAnchor, constant: -20),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: content.bottomAnchor, constant: -20)
        ])
        window.makeKeyAndOrderFront(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) {
        timer?.invalidate()
        stop()
        for (command, target) in targets { command.removeTarget(target); command.isEnabled = false }
    }
}

@main
enum FixtureMain {
    @MainActor static func main() {
        let app = NSApplication.shared
        let delegate = MediaFixture()
        app.setActivationPolicy(.regular)
        app.delegate = delegate
        withExtendedLifetime(delegate) { app.run() }
    }
}
