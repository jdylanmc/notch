import Foundation

public enum FailureCode: String, Codable, CaseIterable {
    case invalidInput = "invalid_input"
    case appMissing = "app_missing"
    case ambiguousApp = "ambiguous_app"
    case appPathMismatch = "app_path_mismatch"
    case staleTarget = "stale_target"
    case permissionDenied = "permission_denied"
    case unsupportedControl = "unsupported_control"
    case accessibilityFailed = "accessibility_failed"
    case windowMissing = "window_missing"
    case windowExcluded = "window_excluded"
    case unsupportedWindow = "unsupported_window"
    case timeout
    case captureFailed = "capture_failed"
    case outputExists = "output_exists"
    case unsafeOutput = "unsafe_output"
    case outputFailed = "output_failed"
    case internalError = "internal_error"

    public var exitStatus: Int32 {
        switch self {
        case .invalidInput: return 2
        case .appMissing, .ambiguousApp, .appPathMismatch, .staleTarget: return 3
        case .permissionDenied: return 4
        case .unsupportedControl, .accessibilityFailed: return 5
        case .windowMissing, .windowExcluded, .unsupportedWindow: return 6
        case .timeout: return 7
        case .captureFailed: return 8
        case .outputExists, .unsafeOutput, .outputFailed: return 9
        case .internalError: return 10
        }
    }
}

public struct ControlFailure: Error, Codable {
    public let code: FailureCode
    public let message: String

    public init(_ code: FailureCode, _ message: String) {
        self.code = code
        self.message = message
    }
}

public struct Options: Equatable {
    public enum Command: String {
        case inspect, settings, capture, help
    }
    public let command: Command
    public let pane: String?
    public let appPath: String?
    public let windowID: UInt32?
    public let output: String?
    public let timeout: TimeInterval

    public static func parse(_ arguments: [String]) throws -> Options {
        guard let first = arguments.first, let command = Command(rawValue: first) else {
            throw ControlFailure(.invalidInput, "Use inspect, settings, capture, or help.")
        }
        var tail = Array(arguments.dropFirst())
        var pane: String?
        if command == .settings {
            guard let value = tail.first, ["open", "general", "about"].contains(value) else {
                throw ControlFailure(.invalidInput, "settings requires open, general, or about.")
            }
            pane = tail.removeFirst()
        }
        var flags: [String: String] = [:]
        while !tail.isEmpty {
            let flag = tail.removeFirst()
            guard ["--app-path", "--window", "--output", "--timeout"].contains(flag),
                  flags[flag] == nil, !tail.isEmpty else {
                throw ControlFailure(.invalidInput, "Unknown, duplicate, or incomplete option.")
            }
            flags[flag] = tail.removeFirst()
        }
        guard command != .help || flags.isEmpty else {
            throw ControlFailure(.invalidInput, "help takes no options.")
        }
        let timeout: TimeInterval
        if let raw = flags["--timeout"] {
            guard let value = Double(raw), value.isFinite, (0.5...15).contains(value) else {
                throw ControlFailure(.invalidInput, "--timeout must be 0.5 through 15 seconds.")
            }
            timeout = value
        } else {
            timeout = 5
        }
        if let path = flags["--app-path"] {
            try validateAbsolutePath(path)
            guard path.hasSuffix(".app") else {
                throw ControlFailure(.invalidInput, "--app-path must name an absolute .app path.")
            }
        }
        var windowID: UInt32?
        if command == .capture {
            guard let raw = flags["--window"], !raw.isEmpty,
                  raw.utf8.allSatisfy({ (48...57).contains($0) }),
                  let value = UInt32(raw), value > 0, let output = flags["--output"] else {
                throw ControlFailure(.invalidInput, "capture requires a positive --window and absolute --output PNG path.")
            }
            windowID = value
            try validateAbsolutePath(output)
            guard output.hasSuffix(".png") else {
                throw ControlFailure(.invalidInput, "--output must end in .png.")
            }
        } else if flags["--window"] != nil || flags["--output"] != nil {
            throw ControlFailure(.invalidInput, "--window and --output are only valid for capture.")
        }
        return Options(command: command, pane: pane, appPath: flags["--app-path"],
                       windowID: windowID, output: flags["--output"], timeout: timeout)
    }
}

public func validateAbsolutePath(_ path: String) throws {
    let parts = path.split(separator: "/", omittingEmptySubsequences: false)
    guard path.hasPrefix("/"), path != "/", !path.contains("\0"),
          !path.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }),
          parts.dropFirst().allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else {
        throw ControlFailure(.invalidInput, "Paths must be absolute, normalized, and contain no control characters.")
    }
}

public struct AppIdentity: Codable, Equatable {
    public let pid: Int32
    public let path: String
    public let launchedAt: Date

    public init(pid: Int32, path: String, launchedAt: Date) {
        self.pid = pid
        self.path = path
        self.launchedAt = launchedAt
    }
}

public func selectApp(_ candidates: [AppIdentity], expectedPath: String?) throws -> AppIdentity {
    guard !candidates.isEmpty else {
        throw ControlFailure(.appMissing, "No running com.jdylanmc.notchpocket app.")
    }
    guard candidates.count == 1, let app = candidates.first else {
        throw ControlFailure(.ambiguousApp, "Multiple app instances; quit duplicates manually.")
    }
    guard expectedPath == nil || expectedPath == app.path else {
        throw ControlFailure(.appPathMismatch, "Running app does not match --app-path.")
    }
    return app
}

public func requireSameApp(_ expected: AppIdentity, _ current: AppIdentity) throws {
    guard expected == current else {
        throw ControlFailure(.staleTarget, "App identity changed; inspect again.")
    }
}

public func selectSettingsMenuItem<Element: Equatable>(
    immediateChildren: [Element],
    role: (Element) throws -> String?,
    children: (Element) throws -> [Element],
    title: (Element) throws -> String?
) throws -> Element {
    guard immediateChildren.count <= 600 else {
        throw ControlFailure(.unsupportedControl, "App children exceed the menu search limit.")
    }
    var roots: [Element] = []
    for child in immediateChildren where try role(child) == "AXMenuBar" && !roots.contains(child) {
        roots.append(child)
    }
    var stack = roots.map { ($0, 0) }
    var matches: [Element] = []
    var visited = 0
    while let (element, depth) = stack.popLast() {
        visited += 1
        guard visited <= 600, depth <= 24 else {
            throw ControlFailure(.unsupportedControl, "Settings menu search exceeded its bounded scope.")
        }
        if try role(element) == "AXMenuItem",
           ["Settings", "Settings…", "Settings..."].contains(try title(element) ?? ""),
           !matches.contains(element) {
            matches.append(element)
        }
        let descendants = try children(element)
        guard descendants.count <= 600 else {
            throw ControlFailure(.unsupportedControl, "Menu children exceed the search limit.")
        }
        stack.append(contentsOf: descendants.map { ($0, depth + 1) })
    }
    guard matches.count == 1, let item = matches.first else {
        throw ControlFailure(.unsupportedControl, "Expected one English Settings menu item; found \(matches.count). No guessed action.")
    }
    return item
}

public struct WindowInfo: Codable, Equatable {
    public let id: UInt32
    public let ownerPID: Int32
    public let onScreen: Bool
    public let sharingAllowed: Bool
    public let layer: Int

    public init(id: UInt32, ownerPID: Int32, onScreen: Bool, sharingAllowed: Bool, layer: Int) {
        self.id = id
        self.ownerPID = ownerPID
        self.onScreen = onScreen
        self.sharingAllowed = sharingAllowed
        self.layer = layer
    }
}

public func captureWindow(_ windows: [WindowInfo], id: UInt32, pid: Int32) throws -> WindowInfo {
    let matches = windows.filter { $0.id == id && $0.ownerPID == pid }
    guard matches.count == 1, let window = matches.first else {
        throw ControlFailure(.windowMissing, "Selected window is not uniquely owned by the current app.")
    }
    guard window.sharingAllowed else {
        throw ControlFailure(.windowExcluded, "Window excludes sharing; no preference changes or fallback.")
    }
    guard window.onScreen else {
        throw ControlFailure(.unsupportedWindow, "Selected window is not on screen.")
    }
    return window
}

public struct PollBudget {
    private let end: TimeInterval
    private let now: () -> TimeInterval

    public init(timeout: TimeInterval, now: @escaping () -> TimeInterval = {
        ProcessInfo.processInfo.systemUptime
    }) {
        self.now = now
        self.end = now() + timeout
    }

    public func remaining() throws -> TimeInterval {
        let left = end - now()
        guard left > 0 else {
            throw ControlFailure(.timeout, "Timed out waiting for an observed app postcondition.")
        }
        return left
    }

    public func until(pause: (TimeInterval) -> Void, condition: () throws -> Bool) throws {
        while true {
            _ = try remaining()
            if try condition() { return }
            pause(min(0.1, try remaining()))
        }
    }
}
