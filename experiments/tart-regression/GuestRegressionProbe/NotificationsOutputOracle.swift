import CoreGraphics
import Foundation

struct NotificationsOutputOracle {
    static let retainedLabels = ["Show notifications in the notch", "From all apps"]
    static let suggestionLabel = "Suggest replies with Apple Intelligence"

    static func evaluate(
        _ observations: [AboutOutputOracle.Observation],
        contentFrame: CGRect,
        controls: [String: Bool],
        labelFrames: [String: CGRect]
    ) -> [String: Bool] {
        let content = observations.filter {
            !$0.frame.isEmpty && contentFrame.contains($0.frame)
        }
        let intersecting = observations.filter { !$0.frame.isEmpty && contentFrame.intersects($0.frame) }
        let rows = intersecting.map { AboutOutputOracle.rowText(anchor: $0, observations: intersecting) }
        var result = Dictionary(uniqueKeysWithValues: retainedLabels.map {
            let label = $0
            guard let frame = labelFrames[label], !frame.isEmpty, contentFrame.contains(frame),
                  controls[label] == true else { return (label, false) }
            let aligned = content.filter {
                frame.insetBy(dx: -0.005, dy: -0.005).contains(CGPoint(x: $0.frame.minX, y: $0.frame.midY))
            }
            return (label, aligned.contains {
                let row = AboutOutputOracle.rowText(anchor: $0, observations: content)
                return row == label || row.hasPrefix(label + " ")
            })
        })
        let rendered = rows.joined(separator: " ").lowercased()
        result["suggestionControlAbsent"] = !content.isEmpty && controls["suggestionControlAbsent"] == true
            && !rendered.contains("suggest replies") && !rendered.contains("apple intelligence")
        return result
    }

    static func combine(_ captures: [[String: Bool]]) -> [String: Bool] {
        let keys = Set(retainedLabels + ["suggestionControlAbsent"])
        guard captures.count == 2 && captures.allSatisfy({ Set($0.keys) == keys }) else {
            return Dictionary(uniqueKeysWithValues: keys.map { ($0, false) })
        }
        var result = Dictionary(uniqueKeysWithValues: retainedLabels.map { label in
            (label, captures.contains { $0[label] == true })
        })
        result["suggestionControlAbsent"] = captures.allSatisfy { $0["suggestionControlAbsent"] == true }
        return result
    }
}
