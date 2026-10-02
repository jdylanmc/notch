import CoreGraphics
import Foundation

struct NotificationsOutputOracle {
    static let retainedLabels = ["Show notifications in the notch", "From all apps"]
    static let suggestionLabel = "Suggest replies with Apple Intelligence"

    static func evaluate(
        _ observations: [AboutOutputOracle.Observation],
        contentFrame: CGRect,
        controls: [String: Bool]
    ) -> [String: Bool] {
        let content = observations.filter {
            $0.frame.height > 0 && contentFrame.contains(CGPoint(x: $0.frame.midX, y: $0.frame.midY))
        }
        let rows = content.map { AboutOutputOracle.rowText(anchor: $0, observations: content) }
        var result = Dictionary(uniqueKeysWithValues: retainedLabels.map {
            let label = $0
            return (label, rows.contains { $0 == label || $0.hasPrefix(label + " ") } && controls[label] == true)
        })
        let rendered = rows.joined(separator: " ").lowercased()
        result["suggestionControlAbsent"] = controls["suggestionControlAbsent"] == true
            && !rendered.contains("suggest replies") && !rendered.contains("apple intelligence")
        return result
    }
}
