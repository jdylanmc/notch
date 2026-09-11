import AppKit
import ApplicationServices
import ControlCore

final class SettingsControl {
    private let target: AppTarget
    private let application: AXUIElement
    private let settingsID = "NotchPocketSettingsWindow"

    init(target: AppTarget) throws {
        try target.requireAccessibility()
        self.target = target
        application = AXUIElementCreateApplication(target.identity.pid)
    }

    private func prepare(_ element: AXUIElement) throws {
        try target.requireAccessibility()
        var pid: pid_t = 0
        guard AXUIElementGetPid(element, &pid) == .success, pid == target.identity.pid else {
            throw ControlFailure(.staleTarget, "Accessibility element no longer belongs to the target app.")
        }
        let seconds = Float(min(0.3, try target.budget.remaining()))
        guard AXUIElementSetMessagingTimeout(element, seconds) == .success else {
            throw ControlFailure(.accessibilityFailed, "Cannot bound Accessibility messaging.")
        }
    }

    private func read(_ element: AXUIElement, _ attribute: String, optional: Bool = false) throws -> CFTypeRef? {
        try target.budget.read(pause: Thread.sleep(forTimeInterval:), prepare: { try self.prepare(element) }, attempt: {
            var value: CFTypeRef?
            let result = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
            if result == .cannotComplete { return .cannotComplete(result.rawValue) }
            if optional && (result == .noValue || result == .attributeUnsupported) { return .value(nil) }
            guard result == .success else {
                throw ControlFailure(.accessibilityFailed, "Accessibility attribute read failed (AX \(result.rawValue)).")
            }
            return .value(value)
        })
    }

    private func elements(_ element: AXUIElement, _ attribute: String, optional: Bool = false) throws -> [AXUIElement] {
        guard let value = try read(element, attribute, optional: optional) else { return [] }
        guard let array = value as? [AXUIElement] else {
            throw ControlFailure(.unsupportedControl, "Accessibility collection has an unsupported shape.")
        }
        return array
    }

    private func string(_ element: AXUIElement, _ attribute: String) throws -> String? {
        guard let value = try read(element, attribute, optional: true) else { return nil }
        guard let text = value as? String else {
            throw ControlFailure(.unsupportedControl, "Accessibility text has an unsupported shape.")
        }
        return text
    }

    private func matching(
        _ root: AXUIElement,
        predicate: (AXUIElement) throws -> Bool
    ) throws -> [AXUIElement] {
        var stack: [(AXUIElement, Int)] = [(root, 0)]
        var matches: [AXUIElement] = []
        var visited = 0
        while let (element, depth) = stack.popLast() {
            visited += 1
            guard visited <= 600, depth <= 24 else {
                throw ControlFailure(.unsupportedControl, "Accessibility search exceeded its bounded scope.")
            }
            if try predicate(element) { matches.append(element) }
            let children = try elements(element, kAXChildrenAttribute, optional: true)
            guard children.count <= 600 else {
                throw ControlFailure(.unsupportedControl, "Accessibility collection exceeds the search limit.")
            }
            stack.append(contentsOf: children.map { ($0, depth + 1) })
        }
        return matches
    }

    private func unique(_ values: [AXUIElement], description: String) throws -> AXUIElement {
        guard values.count == 1, let value = values.first else {
            throw ControlFailure(.unsupportedControl, "Expected one \(description); found \(values.count). No guessed action.")
        }
        return value
    }

    private func settingsWindow() throws -> AXUIElement? {
        let windows = try elements(application, kAXWindowsAttribute)
        let matching = try windows.filter { try string($0, kAXIdentifierAttribute) == settingsID }
        guard matching.count <= 1 else {
            throw ControlFailure(.unsupportedControl, "Multiple Settings windows; no guessed target.")
        }
        return matching.first
    }

    private func outline(_ window: AXUIElement) throws -> AXUIElement {
        try unique(matching(window) { try self.string($0, kAXRoleAttribute) == kAXOutlineRole },
                   description: "Settings outline")
    }

    private func rowHasLabel(_ row: AXUIElement, _ label: String) throws -> Bool {
        let matches = try matching(row) {
            try self.string($0, kAXRoleAttribute) == kAXStaticTextRole &&
                self.string($0, kAXValueAttribute) == label
        }
        return matches.count == 1
    }

    private func captureID(_ window: AXUIElement) throws -> UInt32? {
        guard let rawPosition = try read(window, kAXPositionAttribute, optional: true),
              let rawSize = try read(window, kAXSizeAttribute, optional: true) else { return nil }
        guard CFGetTypeID(rawPosition) == AXValueGetTypeID(), CFGetTypeID(rawSize) == AXValueGetTypeID() else {
            throw ControlFailure(.unsupportedWindow, "Settings geometry has an unsupported shape.")
        }
        let positionValue = unsafeBitCast(rawPosition, to: AXValue.self)
        let sizeValue = unsafeBitCast(rawSize, to: AXValue.self)
        var position = CGPoint.zero
        var size = CGSize.zero
        guard AXValueGetValue(positionValue, .cgPoint, &position), AXValueGetValue(sizeValue, .cgSize, &size) else {
            throw ControlFailure(.unsupportedWindow, "Settings geometry could not be read.")
        }
        return try target.windowID(matching: CGRect(origin: position, size: size))
    }

    func state() throws -> SettingsState {
        guard let window = try settingsWindow() else {
            return SettingsState(status: "closed", selectedPane: nil)
        }
        let rows = try elements(outline(window), kAXSelectedRowsAttribute)
        var labels: [String] = []
        for label in ["General", "About"] where try rows.contains(where: { try rowHasLabel($0, label) }) {
            labels.append(label.lowercased())
        }
        return SettingsState(status: "open", selectedPane: labels.count == 1 ? labels.first : nil,
                             windowID: try captureID(window))
    }

    func navigate(_ pane: String) throws -> SettingsState {
        if try settingsWindow() == nil {
            let item = try selectSettingsMenuItem(
                immediateChildren: elements(application, kAXChildrenAttribute),
                role: { try self.string($0, kAXRoleAttribute) },
                children: { try self.elements($0, kAXChildrenAttribute, optional: true) },
                title: { try self.string($0, kAXTitleAttribute) }
            )
            try prepare(item)
            let result = AXUIElementPerformAction(item, kAXPressAction as CFString)
            guard result == .success else {
                throw ControlFailure(.accessibilityFailed, "Settings menu press failed (AX \(result.rawValue)).")
            }
        }
        try target.budget.until(pause: Thread.sleep(forTimeInterval:)) { try self.settingsWindow() != nil }
        guard pane != "open" else { return try state() }
        guard let window = try settingsWindow() else {
            throw ControlFailure(.staleTarget, "Settings window disappeared.")
        }
        let list = try outline(window)
        let label = pane == "general" ? "General" : "About"
        let row = try unique(elements(list, kAXRowsAttribute).filter { try rowHasLabel($0, label) },
                             description: "\(label) row")
        try prepare(list)
        var settable = DarwinBoolean(false)
        guard AXUIElementIsAttributeSettable(list, kAXSelectedRowsAttribute as CFString, &settable) == .success,
              settable.boolValue else {
            throw ControlFailure(.unsupportedControl, "Settings row selection is not settable.")
        }
        try prepare(list)
        try prepare(row)
        let result = AXUIElementSetAttributeValue(list, kAXSelectedRowsAttribute as CFString, [row] as CFArray)
        guard result == .success else {
            throw ControlFailure(.accessibilityFailed, "Settings selection failed (AX \(result.rawValue)).")
        }
        try target.budget.until(pause: Thread.sleep(forTimeInterval:)) {
            guard let current = try self.settingsWindow() else { return false }
            let state = try self.state()
            let title = try self.string(current, kAXTitleAttribute)
            return state.selectedPane == pane && title == label
        }
        return try state()
    }
}
