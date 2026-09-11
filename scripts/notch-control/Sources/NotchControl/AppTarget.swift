import AppKit
import ApplicationServices
import ControlCore

struct Permissions: Encodable {
    let accessibility: Bool
    let screenRecording: Bool

    static func current() -> Permissions {
        Permissions(accessibility: AXIsProcessTrusted(), screenRecording: CGPreflightScreenCaptureAccess())
    }
}

struct SettingsState: Encodable {
    let status: String
    let selectedPane: String?
    var windowID: UInt32?
}

final class AppTarget {
    static let bundleID = "com.jdylanmc.notchpocket"
    let identity: AppIdentity
    let options: Options
    let budget: PollBudget

    init(options: Options) throws {
        self.options = options
        budget = PollBudget(timeout: options.timeout)
        identity = try Self.resolve(expectedPath: options.appPath)
    }

    static func resolve(expectedPath: String?) throws -> AppIdentity {
        let running = NSWorkspace.shared.runningApplications.filter {
            $0.bundleIdentifier == bundleID && !$0.isTerminated
        }
        // Do not discard unverifiable candidates and accidentally choose a remaining instance.
        guard running.count <= 1 else {
            throw ControlFailure(.ambiguousApp, "Multiple app instances; quit duplicates manually.")
        }
        let identities = try running.map { app -> AppIdentity in
            guard let path = app.bundleURL?.standardizedFileURL.path, let date = app.launchDate else {
                throw ControlFailure(.staleTarget, "Cannot establish app path and launch identity.")
            }
            return AppIdentity(pid: app.processIdentifier, path: path, launchedAt: date)
        }
        return try selectApp(identities, expectedPath: expectedPath)
    }

    func recheck() throws {
        _ = try budget.remaining()
        try requireSameApp(identity, Self.resolve(expectedPath: options.appPath))
    }

    func requireAccessibility() throws {
        try recheck()
        guard AXIsProcessTrusted() else {
            throw ControlFailure(.permissionDenied, "Accessibility is not granted; human grant and terminal restart may be required.")
        }
    }

    func requireCapture() throws {
        try recheck()
        guard CGPreflightScreenCaptureAccess() else {
            throw ControlFailure(.permissionDenied, "Screen Recording is not granted; human grant and terminal restart may be required.")
        }
    }

    func windows() throws -> [WindowInfo] {
        try recheck()
        guard let list = CGWindowListCopyWindowInfo(.optionAll, kCGNullWindowID) as? [[String: Any]] else {
            throw ControlFailure(.unsupportedWindow, "Window metadata is unavailable.")
        }
        return try list.filter {
            ($0[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == identity.pid
        }.map { row in
            guard let number = row[kCGWindowNumber as String] as? NSNumber,
                  let sharing = row[kCGWindowSharingState as String] as? NSNumber,
                  let layer = row[kCGWindowLayer as String] as? NSNumber else {
                throw ControlFailure(.unsupportedWindow, "App window metadata is incomplete.")
            }
            return WindowInfo(id: number.uint32Value, ownerPID: identity.pid,
                              onScreen: (row[kCGWindowIsOnscreen as String] as? NSNumber)?.boolValue ?? false,
                              sharingAllowed: sharing.intValue != 0, layer: layer.intValue)
        }.sorted { $0.id < $1.id }
    }

    func ownedWindow(_ id: UInt32) throws -> WindowInfo {
        try captureWindow(windows(), id: id, pid: identity.pid)
    }

    func windowID(matching bounds: CGRect) throws -> UInt32? {
        try recheck()
        guard let list = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as? [[String: Any]] else {
            throw ControlFailure(.unsupportedWindow, "Window metadata is unavailable.")
        }
        let matches: [UInt32] = list.compactMap { row in
            guard (row[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == identity.pid,
                  let rawBounds = row[kCGWindowBounds as String] as? [String: Any],
                  let rectangle = CGRect(dictionaryRepresentation: rawBounds as CFDictionary),
                  rectangle == bounds,
                  let number = row[kCGWindowNumber as String] as? NSNumber else { return nil }
            return number.uint32Value
        }
        guard matches.count <= 1 else {
            throw ControlFailure(.unsupportedWindow, "Settings geometry matches multiple app windows; no guessed capture target.")
        }
        return matches.first
    }
}
