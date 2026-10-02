import CoreGraphics
import Foundation

enum SettingsRemovalScenario: String {
    case notifications = "notifications-ai-replies-removed"
    case general = "general-haptics-removed"

    var pane: String { self == .notifications ? "Notifications" : "General" }
    var prefix: String { pane.lowercased() }
    var captureVersionKey: String { prefix + "CaptureVersion" }
    var testName: String {
        self == .notifications ? "testInstalledNotificationsWithoutAIReplies" : "testInstalledGeneralWithoutHaptics"
    }
    var retainedLabels: [String] {
        switch self {
        case .notifications: return ["Show notifications in the notch", "From all apps"]
        case .general:
            return [
                "Show menu bar icon", "Launch at login", "Language", "Show on all displays",
                "Preferred display", "Automatically switch displays",
                "Notch height on notch displays", "Notch height on non-notch displays",
                "Open notch on hover", "Remember last tab", "Notch animation",
                "Compact mode", "Enable gestures"
            ]
        }
    }
    var removedLabel: String {
        self == .notifications ? "Suggest replies with Apple Intelligence" : "Enable haptic feedback"
    }
    var absenceKey: String { self == .notifications ? "suggestionControlAbsent" : "hapticControlAbsent" }
    var forbiddenText: [String] {
        self == .notifications ? ["suggest replies", "apple intelligence"] : ["haptic"]
    }
    var leadingOCRPaddingPixels: [String: Int] {
        // Guest Vision boxes begin four pixels before these verified static-text AXValue frames.
        self == .general ? ["Launch at login": 4, "Remember last tab": 4] : [:]
    }
}

struct SettingsRemovalOutputOracle {
    static func evaluate(
        _ observations: [AboutOutputOracle.Observation],
        scenario: SettingsRemovalScenario,
        contentFrame: CGRect,
        controls: [String: Bool],
        labelFrames: [String: CGRect],
        pixelWidth: Int
    ) -> [String: Bool] {
        let content = observations.filter {
            !$0.frame.isEmpty && contentFrame.contains($0.frame)
        }
        let intersecting = observations.filter { !$0.frame.isEmpty && contentFrame.intersects($0.frame) }
        let rows = intersecting.map { AboutOutputOracle.rowText(anchor: $0, observations: intersecting) }
        var result = Dictionary(uniqueKeysWithValues: scenario.retainedLabels.map {
            let label = $0
            guard let frame = labelFrames[label], !frame.isEmpty, contentFrame.contains(frame),
                  controls[label] == true else { return (label, false) }
            let aligned = content.filter {
                let anchor = CGPoint(x: $0.frame.minX, y: $0.frame.midY)
                let alignment = frame.insetBy(dx: -0.005, dy: -0.005)
                if alignment.contains(anchor) { return true }
                guard pixelWidth > 0, let padding = scenario.leadingOCRPaddingPixels[label],
                      anchor.x < frame.minX, anchor.y >= alignment.minY, anchor.y <= alignment.maxY else {
                    return false
                }
                // Vision's normalized coordinates have subpixel serialization noise; compare pixel edges.
                let leadingPixels = (frame.minX * CGFloat(pixelWidth)).rounded()
                    - (anchor.x * CGFloat(pixelWidth)).rounded()
                return leadingPixels >= 0 && leadingPixels <= CGFloat(padding)
            }
            return (label, aligned.contains {
                let row = AboutOutputOracle.rowText(anchor: $0, observations: content)
                return row == label || row.hasPrefix(label + " ")
            })
        })
        let rendered = rows.joined(separator: " ").lowercased()
        result[scenario.absenceKey] = !content.isEmpty && controls[scenario.absenceKey] == true
            && !scenario.forbiddenText.contains { rendered.contains($0) }
        return result
    }

    static func combine(_ captures: [[String: Bool]], scenario: SettingsRemovalScenario) -> [String: Bool] {
        let keys = Set(scenario.retainedLabels + [scenario.absenceKey])
        guard captures.count == 2 && captures.allSatisfy({ Set($0.keys) == keys }) else {
            return Dictionary(uniqueKeysWithValues: keys.map { ($0, false) })
        }
        var result = Dictionary(uniqueKeysWithValues: scenario.retainedLabels.map { label in
            (label, captures.contains { $0[label] == true })
        })
        result[scenario.absenceKey] = captures.allSatisfy { $0[scenario.absenceKey] == true }
        return result
    }
}
