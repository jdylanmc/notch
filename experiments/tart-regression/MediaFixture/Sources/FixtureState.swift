import Foundation

enum FixtureIdentity {
    static let bundleID = "com.jdylanmc.notchpocket.regression.mediafixture"
    static let title = "Regression Tone"
    static let artist = "Notch Test Fixture"
    static let album = "Local Synthetic Audio"
    static let duration: Double = 30
}

enum FixtureCommand: String, Codable, CaseIterable {
    case play, pause, stop, toggle
}

enum FixtureOrigin: String, Codable {
    case ui, remote
}

struct PlayerObservation: Equatable {
    let isPlaying: Bool
    let elapsed: Double
}

struct FixtureState: Codable, Equatable {
    enum Phase: String, Codable {
        case idle, playing, paused, stopped, failed
    }

    let launchCount: Int
    private(set) var activationCount = 0
    private(set) var reopenCount = 0
    private(set) var active = false
    private(set) var phase = Phase.idle
    private(set) var engineIsPlaying = false
    private(set) var engineElapsed: Double = 0
    private(set) var metadataPublished = false
    private(set) var playAttempts = 0
    private(set) var playStarts = 0
    private(set) var naturalEnds = 0
    private(set) var uiCommands: [String: Int] = [:]
    private(set) var remoteCommands: [String: Int] = [:]
    private(set) var errorCode: String?

    mutating func activation(_ active: Bool) {
        self.active = active
        if active { activationCount += 1 }
    }

    mutating func reopen() {
        reopenCount += 1
    }

    mutating func request(_ command: FixtureCommand, origin: FixtureOrigin) -> FixtureCommand {
        switch origin {
        case .ui: uiCommands[command.rawValue, default: 0] += 1
        case .remote: remoteCommands[command.rawValue, default: 0] += 1
        }
        let resolved = command == .toggle ? (engineIsPlaying ? .pause : .play) : command
        if resolved == .play { playAttempts += 1 }
        return resolved
    }

    mutating func started(success: Bool, observation: PlayerObservation) {
        guard accept(observation) else { return }
        guard success, observation.isPlaying else {
            fail("audio_start_failed")
            return
        }
        phase = .playing
        metadataPublished = true
        playStarts += 1
        errorCode = nil
    }

    mutating func paused(observation: PlayerObservation) {
        guard accept(observation) else { return }
        guard !observation.isPlaying else {
            fail("audio_pause_failed")
            return
        }
        if metadataPublished { phase = .paused }
    }

    mutating func stopped(observation: PlayerObservation) {
        guard accept(observation) else { return }
        guard !observation.isPlaying else {
            fail("audio_stop_failed")
            return
        }
        phase = .stopped
        metadataPublished = false
        errorCode = nil
    }

    mutating func sample(_ observation: PlayerObservation) {
        guard accept(observation) else { return }
        if phase == .playing, !observation.isPlaying {
            phase = .stopped
            metadataPublished = false
        } else if phase != .playing, observation.isPlaying {
            fail("unexpected_audio_playback")
        }
    }

    mutating func finished(success: Bool, observation: PlayerObservation) {
        if success {
            stopped(observation: observation)
            naturalEnds += 1
        } else {
            _ = accept(observation)
            fail("audio_finish_failed")
        }
    }

    mutating func fail(_ code: String) {
        phase = .failed
        metadataPublished = false
        errorCode = code
    }

    private mutating func accept(_ observation: PlayerObservation) -> Bool {
        engineIsPlaying = observation.isPlaying
        guard observation.elapsed.isFinite,
              (0...FixtureIdentity.duration).contains(observation.elapsed) else {
            fail("invalid_audio_observation")
            return false
        }
        engineElapsed = observation.elapsed
        return true
    }
}

struct FixtureReceipt: Encodable {
    let schemaVersion = 1
    let bundleIdentifier = FixtureIdentity.bundleID
    let pid: Int32
    let event: String
    let sequence: Int
    let state: FixtureState
    let muted = true
    // This describes the local public API assignment, not OS delivery to Notch.
    let publicationIsConsumerProof = false
}
