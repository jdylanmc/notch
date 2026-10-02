import CoreGraphics
import Foundation

struct AppearanceOutputOracle {
    static let retainedLabels = [
        "Always show tabs", "Show settings icon in notch", "Colored spectrogram",
        "Real-time audio waveform", "Player tinting", "Enable blur effect behind album art", "Slider color"
    ]
    static let faceLabel = "Show cool face animation while inactive"

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
        // The native full-form fit checks Accessibility; pixels independently reject a rendered remnant.
        let rendered = rows.joined(separator: " ").lowercased()
        result["faceControlAbsent"] = controls["faceControlAbsent"] == true && !rendered.contains("face animation")
        result["additionalFeaturesAbsent"] =
            controls["additionalFeaturesAbsent"] == true && !rendered.contains("additional features")
        return result
    }
}
