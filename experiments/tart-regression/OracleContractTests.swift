import CoreGraphics
import Foundation

@main
enum OracleContractTests {
    static func main() throws {
        typealias Observation = AboutOutputOracle.Observation
        func box(_ text: String, _ x: Double, _ y: Double, _ width: Double = 0.15) -> Observation {
            Observation(text: text, frame: CGRect(x: x, y: y, width: width, height: 0.03))
        }
        let fixed = [box("Release name", 0.3, 0.8), box("Notch Pocket", 0.75, 0.8),
                     box("Version", 0.3, 0.6), box("Version info", 0.3, 0.9)]
        let expectedVersion = "1.2.3"
        let expectedBuild = "(456)"
        var count = 0
        func check(_ name: String, _ observations: [Observation], version: Bool, build: Bool) throws {
            let output = AboutOutputOracle.evaluate(observations, version: expectedVersion, build: "456")
            guard output[expectedVersion] == version && output[expectedBuild] == build else {
                throw NSError(domain: "OracleContractTests", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "\(name): \(output)"])
            }
            count += 1
        }
        try check("exact values", fixed + [box("(456)", 0.7, 0.6), box("1.2.3", 0.85, 0.6)], version: true, build: true)
        try check("prefixed version", fixed + [box("(456)", 0.7, 0.6), box("11.2.3", 0.85, 0.6)], version: false, build: true)
        try check("suffixed version", fixed + [box("(456)", 0.7, 0.6), box("1.2.30", 0.85, 0.6)], version: false, build: true)
        try check("expected version elsewhere", fixed + [box("(456)", 0.7, 0.6), box("9.9", 0.85, 0.6),
                                                        box("1.2.3", 0.85, 0.2)], version: false, build: true)
        try check("wrong build", fixed + [box("(457)", 0.7, 0.6), box("1.2.3", 0.85, 0.6)], version: true, build: false)
        try check("missing build", fixed + [box("1.2.3", 0.85, 0.6)], version: true, build: false)
        try check("expected build elsewhere", fixed + [box("(457)", 0.7, 0.6), box("1.2.3", 0.85, 0.6),
                                                       box("(456)", 0.7, 0.2)], version: true, build: false)
        let combined = [box("Release name Notch Pocket", 0.3, 0.8, 0.65),
                        box("Version (456) 1.2.3", 0.3, 0.6, 0.65)]
        try check("merged OCR lines", combined, version: true, build: true)
        try check("normalized whitespace", [box("Release name   Notch Pocket", 0.3, 0.8, 0.65),
                                           box("Version   (456)  1.2.3 ", 0.3, 0.6, 0.65)], version: true, build: true)
        try check("extra version in row", fixed + [box("(456) 11.2.3 1.2.3", 0.7, 0.6, 0.3)], version: false, build: true)
        try check("no version row", [box("Release name", 0.3, 0.8), box("Notch Pocket", 0.75, 0.8),
                                    box("1.2.3", 0.85, 0.2)], version: false, build: false)
        print("About output oracle: \(count) cases passed.")
        try checkAppearance()
    }

    private static func checkAppearance() throws {
        typealias Observation = AboutOutputOracle.Observation
        let labels = AppearanceOutputOracle.retainedLabels
        let content = CGRect(x: 0.3, y: 0, width: 0.7, height: 1)
        let rendered = labels.enumerated().map { index, label in
            Observation(text: label, frame: CGRect(x: 0.4, y: 0.9 - Double(index) * 0.1, width: 0.5, height: 0.03))
        }
        var controls = Dictionary(uniqueKeysWithValues: labels.map { ($0, true) })
        controls["faceControlAbsent"] = true
        controls["additionalFeaturesAbsent"] = true
        var count = 0
        func check(_ name: String, _ observations: [Observation], _ accessible: [String: Bool], passes: Bool) throws {
            let result = AppearanceOutputOracle.evaluate(observations, contentFrame: content, controls: accessible)
            guard result.count == labels.count + 2 && result.values.allSatisfy({ $0 }) == passes else {
                throw NSError(domain: "AppearanceOracleContractTests", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "\(name): \(result)"])
            }
            count += 1
        }
        try check("retained controls and pixels", rendered, controls, passes: true)
        try check("empty pixels cannot prove absence", [], controls, passes: false)
        try check("missing accessibility cannot prove absence", rendered, [:], passes: false)
        for label in labels {
            try check("missing pixel: \(label)", rendered.filter { $0.text != label }, controls, passes: false)
            var missing = controls
            missing[label] = false
            try check("missing control: \(label)", rendered, missing, passes: false)
        }
        for removed in ["faceControlAbsent", "additionalFeaturesAbsent"] {
            var old = controls
            old[removed] = false
            try check("old app exposes \(removed) even if OCR misses it", rendered, old, passes: false)
        }
        for removed in [AppearanceOutputOracle.faceLabel, "Additional features"] {
            let extra = Observation(text: removed, frame: CGRect(x: 0.4, y: 0.1, width: 0.5, height: 0.03))
            try check("old app pixels: \(removed)", rendered + [extra], controls, passes: false)
        }
        let sidebarOnly = rendered.map {
            Observation(text: $0.text, frame: CGRect(x: 0, y: $0.frame.minY, width: 0.2, height: 0.03))
        }
        try check("sidebar text is not detail output", sidebarOnly, controls, passes: false)
        print("Appearance output oracle: \(count) cases passed.")
    }
}
