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
        let text = observations.filter { contentFrame.contains(CGPoint(x: $0.frame.midX, y: $0.frame.midY)) }
            .map { AboutOutputOracle.normalize($0.text) }
        var result = Dictionary(uniqueKeysWithValues: retainedLabels.map {
            ($0, text.contains($0) && controls[$0] == true)
        })
        // The native tail visit checks Accessibility; pixels independently reject a rendered remnant.
        let rendered = text.joined(separator: " ").lowercased()
        result["faceControlAbsent"] = controls["faceControlAbsent"] == true && !rendered.contains("face animation")
        result["additionalFeaturesAbsent"] =
            controls["additionalFeaturesAbsent"] == true && !rendered.contains("additional features")
        return result
    }
}
