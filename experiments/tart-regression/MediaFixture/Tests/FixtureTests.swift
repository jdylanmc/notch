import Darwin
import Foundation

enum TestFailure: Error {
    case assertion(String)
}

@main
enum FixtureTests {
    private static func expect(_ condition: @autoclosure () -> Bool, _ message: String) throws {
        guard condition() else { throw TestFailure.assertion(message) }
    }

    static func main() throws {
        guard CommandLine.arguments.count == 2 else { throw TestFailure.assertion("Missing owned test root") }
        try lifecycle()
        try transport()
        try failures()
        try activationControls()
        try audio()
        try storage(URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true))
        print("PASS: 6 fixture contract groups (pure/synthetic + local storage; no native media or UI execution)")
    }

    private static func lifecycle() throws {
        var state = FixtureState(launchCount: 7)
        try expect(state.phase == .idle && !state.metadataPublished && !state.engineIsPlaying, "Idle launch")
        state.activation(true)
        state.reopen()
        state.activation(false)
        state.activation(true)
        try expect(state.launchCount == 7 && state.activationCount == 2 && state.reopenCount == 1, "Lifecycle counts")
        try expect(state.phase == .idle && state.engineElapsed == 0, "Activation cannot change transport")
        try expect(state.playAttempts == 0 && state.playStarts == 0, "Activation cannot request play")
        try expect(state.uiCommands.isEmpty && state.remoteCommands.isEmpty, "Lifecycle is not a command")
    }

    private static func playing() -> FixtureState {
        var state = FixtureState(launchCount: 1)
        _ = state.request(.play, origin: .ui)
        state.started(success: true, observation: PlayerObservation(isPlaying: true, elapsed: 0))
        return state
    }

    private static func transport() throws {
        var state = playing()
        try expect(state.phase == .playing && state.metadataPublished && state.playStarts == 1, "Successful play")
        state.sample(PlayerObservation(isPlaying: true, elapsed: 1.25))
        state.sample(PlayerObservation(isPlaying: true, elapsed: 1.25))
        try expect(state.engineElapsed == 1.25, "A repeated engine sample cannot fabricate progress")
        _ = state.request(.pause, origin: .ui)
        state.paused(observation: PlayerObservation(isPlaying: false, elapsed: 1.25))
        try expect(state.phase == .paused && state.metadataPublished, "Pause retains metadata")
        state.activation(true)
        state.reopen()
        try expect(state.phase == .paused && state.playAttempts == 1, "Paused activation cannot resume")
        let resolved = state.request(.toggle, origin: .remote)
        try expect(resolved == .play && state.remoteCommands["toggle"] == 1, "Remote resume recorded")
        state.started(success: true, observation: PlayerObservation(isPlaying: true, elapsed: 1.25))
        try expect(state.playAttempts == 2 && state.playStarts == 2, "Explicit resume")
        try expect(state.request(.toggle, origin: .remote) == .pause, "Playing toggle resolves to pause")
        state.paused(observation: PlayerObservation(isPlaying: false, elapsed: 1.25))
        _ = state.request(.stop, origin: .ui)
        state.stopped(observation: PlayerObservation(isPlaying: false, elapsed: 0))
        try expect(state.phase == .stopped && !state.metadataPublished, "Stop clears metadata")
        state.reopen()
        try expect(state.playAttempts == 2 && state.phase == .stopped, "Stopped reopen cannot play")
        _ = state.request(.play, origin: .remote)
        state.started(success: true, observation: PlayerObservation(isPlaying: true, elapsed: 0))
        state.finished(success: true, observation: PlayerObservation(isPlaying: false, elapsed: 30))
        try expect(state.naturalEnds == 1 && !state.metadataPublished && state.phase == .stopped, "Natural end")
        try expect(state.remoteCommands["play"] == 1 && state.uiCommands["play"] == 1, "Origin separation")
    }

    private static func failures() throws {
        var state = FixtureState(launchCount: 1)
        _ = state.request(.play, origin: .ui)
        state.started(success: false, observation: PlayerObservation(isPlaying: false, elapsed: 0))
        try expect(state.phase == .failed && state.playStarts == 0 && !state.metadataPublished, "Failed start")
        state = playing()
        state.paused(observation: PlayerObservation(isPlaying: true, elapsed: 1))
        try expect(state.errorCode == "audio_pause_failed" && !state.metadataPublished, "Failed pause")
        state = playing()
        state.stopped(observation: PlayerObservation(isPlaying: true, elapsed: 1))
        try expect(state.errorCode == "audio_stop_failed", "Failed stop")
        for elapsed in [Double.nan, .infinity, -1, 31] {
            state = playing()
            state.sample(PlayerObservation(isPlaying: true, elapsed: elapsed))
            try expect(state.errorCode == "invalid_audio_observation", "Reject invalid elapsed")
        }
        state = FixtureState(launchCount: 1)
        state.sample(PlayerObservation(isPlaying: true, elapsed: 0))
        try expect(state.errorCode == "unexpected_audio_playback", "Unrequested playback is an error")
        state = playing()
        state.finished(success: false, observation: PlayerObservation(isPlaying: false, elapsed: 1))
        try expect(state.phase == .failed && state.naturalEnds == 0, "Failed decoder/finish is not normal completion")
    }

    // A synthetic version of the worker's running-process activation assertion.
    // It cannot establish the caller, the frontmost application or OS delivery.
    private static func activationOnly(before: FixtureState, after: FixtureState) -> Bool {
        before.launchCount == after.launchCount
            && after.activationCount > before.activationCount && after.active
            && before.playAttempts == after.playAttempts && before.playStarts == after.playStarts
            && before.uiCommands == after.uiCommands && before.remoteCommands == after.remoteCommands
            && before.phase == after.phase && before.engineElapsed == after.engineElapsed
            && !after.engineIsPlaying && after.errorCode == nil
    }

    private static func activationControls() throws {
        var before = playing()
        _ = before.request(.pause, origin: .ui)
        before.paused(observation: PlayerObservation(isPlaying: false, elapsed: 2))
        var after = before
        after.activation(true)
        after.reopen()
        try expect(activationOnly(before: before, after: after), "Positive activation control")
        try expect(!activationOnly(before: before, after: before), "No activation must fail")
        var wrong = after
        _ = wrong.request(.play, origin: .remote)
        wrong.started(success: true, observation: PlayerObservation(isPlaying: true, elapsed: 2))
        try expect(!activationOnly(before: before, after: wrong), "Accidental remote play must fail")
        wrong.paused(observation: PlayerObservation(isPlaying: false, elapsed: 2))
        try expect(!activationOnly(before: before, after: wrong), "Play then pause cannot hide command")
        wrong = after
        _ = wrong.request(.play, origin: .remote)
        wrong.started(success: false, observation: PlayerObservation(isPlaying: false, elapsed: 2))
        try expect(!activationOnly(before: before, after: wrong), "Even failed play request must fail")
        wrong = FixtureState(launchCount: 2)
        wrong.activation(true)
        try expect(!activationOnly(before: before, after: wrong), "Process replacement must fail")
    }

    private static func audio() throws {
        let data = GeneratedAudio.wave()
        try expect(data == GeneratedAudio.wave(), "Repeatable generated waveform")
        try expect(data.count == 44 + 30 * 22_050 * 2, "Bounded 30-second mono PCM")
        try expect(String(data: data[0..<4], encoding: .utf8) == "RIFF", "RIFF header")
        try expect(String(data: data[8..<16], encoding: .utf8) == "WAVEfmt ", "WAVE header")
        func uint32(_ offset: Int) -> UInt32 {
            (0..<4).reduce(0) { $0 | (UInt32(data[offset + $1]) << ($1 * 8)) }
        }
        try expect(uint32(4) == data.count - 8 && uint32(40) == data.count - 44, "Chunk lengths")
        try expect(uint32(24) == 22_050 && uint32(28) == 44_100, "PCM clock")
        try expect(data[20] == 1 && data[22] == 1 && data[32] == 2 && data[34] == 16, "PCM format")
        var nonzero = 0
        for index in stride(from: 44, to: data.count, by: 2) {
            let sample = Int16(bitPattern: UInt16(data[index]) | UInt16(data[index + 1]) << 8)
            try expect(abs(Int(sample)) <= 4_000, "Amplitude bounded")
            if sample != 0 { nonzero += 1 }
        }
        try expect(nonzero > GeneratedAudio.frameCount / 2, "Real generated signal, not a silence placeholder")
    }

    private static func storage(_ root: URL) throws {
        let manager = FileManager.default
        try manager.createDirectory(at: root, withIntermediateDirectories: false,
                                    attributes: [.posixPermissions: 0o700])
        var first: FixtureStore? = try FixtureStore(root: root)
        try expect(first?.launchCount == 1, "First persistent launch")
        do {
            _ = try FixtureStore(root: root)
            throw TestFailure.assertion("Concurrent producer accepted")
        } catch FixtureStoreError.alreadyRunning { }
        let state = FixtureState(launchCount: 1)
        try first?.append(event: "unit_idle", state: state)
        guard let receiptURL = first?.receiptURL, let audioURL = first?.audioURL else {
            throw TestFailure.assertion("Missing test store")
        }
        let receipt = try JSONSerialization.jsonObject(with: Data(contentsOf: receiptURL)) as? [String: Any]
        try expect(receipt?["bundleIdentifier"] as? String == FixtureIdentity.bundleID, "Receipt identity")
        try expect(receipt?["publicationIsConsumerProof"] as? Bool == false, "Receipt scope")
        let writtenAudio = try Data(contentsOf: audioURL)
        try expect(writtenAudio == GeneratedAudio.wave(), "Owned audio file")
        first = nil
        var second: FixtureStore? = try FixtureStore(root: root)
        try expect(second?.launchCount == 2, "Launch count survives process-store lifetime")
        try expect(FixtureState(launchCount: 2).playAttempts == 0, "Transport never restored from disk")
        second = nil
        let counter = root.appendingPathComponent("launch-count.json")
        try Data("invalid".utf8).write(to: counter)
        do {
            _ = try FixtureStore(root: root)
            throw TestFailure.assertion("Malformed counter accepted")
        } catch is DecodingError { }
        try manager.removeItem(at: counter)
        try manager.createSymbolicLink(at: counter, withDestinationURL: audioURL)
        do {
            _ = try FixtureStore(root: root)
            throw TestFailure.assertion("Redirected counter accepted")
        } catch FixtureStoreError.unsafeFile { }
        try manager.removeItem(at: counter)
        try Data("{\"schemaVersion\":1,\"launches\":1}".utf8).write(to: counter)
        do {
            _ = try FixtureStore(root: root)
            throw TestFailure.assertion("Existing launch directory reused")
        } catch FixtureStoreError.ioFailure { }
        try manager.setAttributes([.posixPermissions: 0o755], ofItemAtPath: root.path)
        do {
            _ = try FixtureStore(root: root)
            throw TestFailure.assertion("Nonprivate fixture root accepted")
        } catch FixtureStoreError.unsafeDirectory { }
        try manager.setAttributes([.posixPermissions: 0o700], ofItemAtPath: root.path)
    }
}
