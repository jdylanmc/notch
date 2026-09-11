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
        case inspect, settings, notch, capture, help
    }
    public let command: Command
    public let pane: String?
    public let notchAction: NotchAction?
    public let appPath: String?
    public let windowID: UInt32?
    public let output: String?
    public let timeout: TimeInterval

    public static func parse(_ arguments: [String]) throws -> Options {
        guard let first = arguments.first, let command = Command(rawValue: first) else {
            throw ControlFailure(.invalidInput, "Use inspect, settings, notch, capture, or help.")
        }
        var tail = Array(arguments.dropFirst())
        var pane: String?
        if command == .settings {
            guard let value = tail.first, ["open", "general", "about"].contains(value) else {
                throw ControlFailure(.invalidInput, "settings requires open, general, or about.")
            }
            pane = tail.removeFirst()
        }
        var notchAction: NotchAction?
        if command == .notch {
            guard let value = tail.first, let action = NotchAction(rawValue: value) else {
                throw ControlFailure(.invalidInput, "notch requires open or close.")
            }
            notchAction = action
            tail.removeFirst()
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
        let windowID = try parseWindowID(command: command, flags: flags)
        return Options(command: command, pane: pane, notchAction: notchAction, appPath: flags["--app-path"],
                       windowID: windowID, output: flags["--output"], timeout: timeout)
    }

    private static func parseWindowID(command: Command, flags: [String: String]) throws -> UInt32? {
        if command == .capture {
            guard let raw = flags["--window"], !raw.isEmpty,
                  raw.utf8.allSatisfy({ (48...57).contains($0) }),
                  let value = UInt32(raw), value > 0, let output = flags["--output"] else {
                throw ControlFailure(.invalidInput, "capture requires a positive --window and absolute --output PNG path.")
            }
            try validateAbsolutePath(output)
            guard output.hasSuffix(".png") else {
                throw ControlFailure(.invalidInput, "--output must end in .png.")
            }
            return value
        } else if command == .notch {
            guard let raw = flags["--window"], let value = UInt32(raw), value > 0,
                  String(value) == raw, flags["--output"] == nil else {
                throw ControlFailure(.invalidInput, "notch requires a canonical positive --window ID and no --output.")
            }
            return value
        } else if flags["--window"] != nil || flags["--output"] != nil {
            throw ControlFailure(.invalidInput, "--window is only valid for capture or notch; --output is only valid for capture.")
        }
        return nil
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

public struct NotchPanelMetadata: Equatable {
    public static let identifierPrefix = "com.jdylanmc.notchpocket.notch."
    public static let versionPrefix = identifierPrefix + "v1.window."
    public let identifier: String
    public let value: String?

    public init(identifier: String, value: String?) {
        self.identifier = identifier
        self.value = value
    }
}

public struct NotchPanelState: Codable, Equatable {
    public enum State: String, Codable {
        case open, closed
    }
    public let windowID: UInt32
    public let state: State
}

public struct NotchInspection: Codable, Equatable {
    public enum Status: String, Codable {
        case observed, unsupported
        case accessibilityUnavailable = "accessibility_unavailable"
    }
    public let status: Status
    public let panels: [NotchPanelState]?

    public static let unsupported = NotchInspection(status: .unsupported, panels: nil)
    public static let accessibilityUnavailable = NotchInspection(status: .accessibilityUnavailable, panels: nil)
}

public func observeNotchPanels(
    _ metadata: [NotchPanelMetadata], windows: [WindowInfo], pid: Int32
) throws -> NotchInspection {
    guard !metadata.isEmpty else { return .unsupported }
    guard metadata.count <= 600 else {
        throw ControlFailure(.unsupportedControl, "Notch panel collection exceeds the observation limit.")
    }
    var seen: Set<UInt32> = []
    let panels = try metadata.map { item -> NotchPanelState in
        guard item.identifier.hasPrefix(NotchPanelMetadata.versionPrefix) else {
            throw ControlFailure(.unsupportedControl, "Unsupported notch observation contract.")
        }
        let rawID = String(item.identifier.dropFirst(NotchPanelMetadata.versionPrefix.count))
        guard let id = UInt32(rawID), id > 0, String(id) == rawID,
              let rawState = item.value, let state = NotchPanelState.State(rawValue: rawState) else {
            throw ControlFailure(.unsupportedControl, "Malformed notch observation metadata.")
        }
        guard seen.insert(id).inserted else {
            throw ControlFailure(.unsupportedControl, "Duplicate notch panel identity; no guessed state.")
        }
        let matching = windows.filter { $0.id == id }
        guard matching.count == 1, matching.first?.ownerPID == pid else {
            throw ControlFailure(.staleTarget, "Notch panel is not uniquely owned by the current app.")
        }
        return NotchPanelState(windowID: id, state: state)
    }
    return NotchInspection(status: .observed, panels: panels.sorted { $0.windowID < $1.windowID })
}

public enum AttributeRead<Value> {
    case value(Value)
    case cannotComplete(Int32)
}

public enum NotchAction: String, Codable, CaseIterable {
    case open, close

    public var nativeName: String { "com.jdylanmc.notchpocket.notch.v1." + rawValue }
    public var targetState: NotchPanelState.State { self == .open ? .open : .closed }
}

public struct NotchActionResult: Codable, Equatable {
    public enum Outcome: String, Codable {
        case changed
        case alreadyAtTarget = "already_at_target"
    }
    public let windowID: UInt32
    public let action: NotchAction
    public let state: NotchPanelState.State
    public let outcome: Outcome
}

public func selectedNotchPanel(_ inspection: NotchInspection, windowID: UInt32) throws -> NotchPanelState {
    guard inspection.status == .observed, let panels = inspection.panels else {
        throw ControlFailure(.unsupportedControl, "No supported notch observation for the selected panel.")
    }
    let matching = panels.filter { $0.windowID == windowID }
    guard matching.count == 1, let panel = matching.first else {
        throw ControlFailure(.staleTarget, "Selected notch panel is missing or ambiguous; inspect again.")
    }
    return panel
}

public struct NotchActionTransport {
    public let observe: () throws -> NotchInspection
    public let actionNames: () throws -> [String]
    public let perform: (String) throws -> Void

    public init(
        observe: @escaping () throws -> NotchInspection,
        actionNames: @escaping () throws -> [String],
        perform: @escaping (String) throws -> Void
    ) {
        self.observe = observe
        self.actionNames = actionNames
        self.perform = perform
    }
}

public func changeNotchState(
    windowID: UInt32, action: NotchAction, budget: PollBudget,
    pause: (TimeInterval) -> Void, transport: NotchActionTransport
) throws -> NotchActionResult {
    _ = try budget.remaining()
    _ = try selectedNotchPanel(transport.observe(), windowID: windowID)
    _ = try budget.remaining()
    let names = try transport.actionNames()
    _ = try budget.remaining()
    guard names.count <= 600, names.filter({ $0 == action.nativeName }).count == 1 else {
        throw ControlFailure(.unsupportedControl, "Selected panel does not advertise the exact notch action.")
    }
    let before = try selectedNotchPanel(transport.observe(), windowID: windowID)
    _ = try budget.remaining()
    if before.state == action.targetState {
        return NotchActionResult(windowID: windowID, action: action, state: before.state, outcome: .alreadyAtTarget)
    }
    try transport.perform(action.nativeName)
    _ = try budget.remaining()
    try budget.until(pause: pause) {
        let current = try selectedNotchPanel(transport.observe(), windowID: windowID)
        _ = try budget.remaining()
        return current.state == action.targetState
    }
    return NotchActionResult(windowID: windowID, action: action, state: action.targetState, outcome: .changed)
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
        try remaining(timeoutMessage: "Timed out waiting for an observed app postcondition.")
    }

    private func remaining(timeoutMessage: String) throws -> TimeInterval {
        let left = end - now()
        guard left > 0 else {
            throw ControlFailure(.timeout, timeoutMessage)
        }
        return left
    }

    public func read<Value>(
        pause: (TimeInterval) -> Void,
        prepare: () throws -> Void,
        attempt: () throws -> AttributeRead<Value>
    ) throws -> Value {
        var timeoutMessage = "Timed out waiting for an Accessibility attribute read."
        while true {
            _ = try remaining(timeoutMessage: timeoutMessage)
            try prepare()
            _ = try remaining(timeoutMessage: timeoutMessage)
            switch try attempt() {
            case .value(let value):
                _ = try remaining(timeoutMessage: timeoutMessage)
                return value
            case .cannotComplete(let code):
                timeoutMessage = "Timed out waiting for a busy Accessibility attribute read (last AX \(code))."
                pause(min(0.1, try remaining(timeoutMessage: timeoutMessage)))
            }
        }
    }

    public func until(pause: (TimeInterval) -> Void, condition: () throws -> Bool) throws {
        while true {
            _ = try remaining()
            if try condition() { return }
            pause(min(0.1, try remaining()))
        }
    }
}
