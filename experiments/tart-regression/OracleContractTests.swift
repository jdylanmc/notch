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
        try checkSettingsRemoval(.notifications)
        try checkSettingsRemoval(.general)
    }

    private static func checkSettingsRemoval(_ scenario: SettingsRemovalScenario) throws {
        typealias Observation = AboutOutputOracle.Observation
        let labels = scenario.retainedLabels
        let absence = scenario.absenceKey
        let content = CGRect(x: 0.3, y: 0, width: 0.7, height: 1)
        let rendered = labels.enumerated().map { index, label in
            Observation(text: label, frame: CGRect(x: 0.4, y: 0.9 - Double(index) * 0.05, width: 0.5, height: 0.03))
        }
        var controls = Dictionary(uniqueKeysWithValues: labels.map { ($0, true) })
        controls[absence] = true
        let labelFrames = Dictionary(uniqueKeysWithValues: rendered.map { ($0.text, $0.frame) })
        var count = 0
        func check(_ name: String, _ observations: [Observation], _ accessible: [String: Bool], passes: Bool) throws {
            let result = SettingsRemovalOutputOracle.evaluate(
                observations, scenario: scenario, contentFrame: content, controls: accessible, labelFrames: labelFrames
            )
            guard result.count == labels.count + 1 && result.values.allSatisfy({ $0 }) == passes else {
                throw NSError(domain: "\(scenario.pane)OracleContractTests", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "\(name): \(result)"])
            }
            count += 1
        }
        try check("retained controls and pixels", rendered, controls, passes: true)
        try check("empty pixels cannot prove removal", [], controls, passes: false)
        try check("missing accessibility cannot prove removal", rendered, [:], passes: false)
        for (index, label) in labels.enumerated() {
            let others = rendered.filter { $0.text != label }
            try check("missing retained pixels: \(label)", others, controls, passes: false)
            var missing = controls
            missing[label] = false
            try check("missing retained control: \(label)", rendered, missing, passes: false)
            let original = rendered[index]
            let words = label.split(separator: " ", maxSplits: 1).map(String.init)
            if words.count == 2 {
                let left = Observation(text: words[0],
                                       frame: CGRect(x: 0.4, y: original.frame.minY, width: 0.1, height: 0.03))
                let right = Observation(text: words[1],
                                        frame: CGRect(x: 0.51, y: original.frame.minY, width: 0.3, height: 0.03))
                try check("split same-row label: \(label)", others + [left, right], controls, passes: true)
                let differentRow = Observation(text: words[1],
                                               frame: CGRect(x: 0.51, y: 0.02, width: 0.3, height: 0.03))
                try check("different rows are not a label: \(label)", others + [left, differentRow], controls, passes: false)
            }
            let suffix = Observation(text: label + "x", frame: original.frame)
            try check("near label: \(label)", others + [suffix], controls, passes: false)
            let offscreen = Observation(text: label, frame: CGRect(x: 0.4, y: 1.1, width: 0.5, height: 0.03))
            try check("offscreen label: \(label)", others + [offscreen], controls, passes: false)
        }
        var old = controls
        old[absence] = false
        try check("old app control rejected even if OCR misses it", rendered, old, passes: false)
        for text in [scenario.removedLabel] + scenario.forbiddenText {
            let remnant = Observation(text: text, frame: CGRect(x: 0.4, y: 0.1, width: 0.5, height: 0.03))
            try check("old app pixels: \(text)", rendered + [remnant], controls, passes: false)
        }
        let removedWords = scenario.removedLabel.split(separator: " ", maxSplits: 1).map(String.init)
        let splitRemoved = [
            Observation(text: removedWords[0], frame: CGRect(x: 0.4, y: 0.1, width: 0.1, height: 0.03)),
            Observation(text: removedWords[1], frame: CGRect(x: 0.51, y: 0.1, width: 0.35, height: 0.03))
        ]
        try check("split removed label", rendered + splitRemoved, controls, passes: false)
        let sidebarOnly = rendered.map {
            Observation(text: $0.text, frame: CGRect(x: 0, y: $0.frame.minY, width: 0.2, height: 0.03))
        }
        try check("sidebar is not detail output", sidebarOnly, controls, passes: false)
        let emptyOutput = SettingsRemovalOutputOracle.evaluate(
            sidebarOnly, scenario: scenario, contentFrame: content, controls: controls, labelFrames: labelFrames
        )
        guard emptyOutput[absence] == false else {
            throw NSError(domain: "\(scenario.pane)EmptyViewport", code: 1)
        }
        count += 1
        try check("clipped remnant still rejects absence", rendered + [
            Observation(text: scenario.removedLabel, frame: CGRect(x: 0.4, y: 0.99, width: 0.3, height: 0.03))
        ], controls, passes: false)
        for frames in [[:], [labels[0]: rendered[0].frame],
                       labelFrames.mapValues { $0.offsetBy(dx: 0, dy: -0.1) },
                       labelFrames.mapValues { $0.offsetBy(dx: 0, dy: 1) }] {
            let output = SettingsRemovalOutputOracle.evaluate(
                rendered, scenario: scenario, contentFrame: content, controls: controls, labelFrames: frames
            )
            guard output.values.contains(false) else {
                throw NSError(domain: "\(scenario.pane)LabelGeometry", code: 1)
            }
            count += 1
        }
        let top = controls
        var bottom = Dictionary(uniqueKeysWithValues: labels.map { ($0, false) })
        bottom[absence] = true
        var oldBottom = bottom
        oldBottom[absence] = false
        var missingTop = top
        missingTop[labels[0]] = false
        var splitBottom = bottom
        splitBottom[labels[0]] = true
        for (captures, expected) in [
            ([top, bottom], true), ([top], false), ([], false), ([top, bottom, bottom], false),
            ([top, [:]], false), ([top, oldBottom], false), ([missingTop, bottom], false),
            ([missingTop, splitBottom], true),
        ] {
            guard SettingsRemovalOutputOracle.combine(captures, scenario: scenario).values.allSatisfy({ $0 }) == expected else {
                throw NSError(domain: "\(scenario.pane)CaptureCombination", code: 1)
            }
            count += 1
        }
        print("\(scenario.pane) output oracle: \(count) cases passed.")
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
        for (index, label) in labels.enumerated() {
            let original = rendered[index]
            let words = label.split(separator: " ", maxSplits: 1).map(String.init)
            let left = Observation(text: words[0],
                                   frame: CGRect(x: 0.4, y: original.frame.minY, width: 0.1, height: 0.03))
            let right = Observation(text: words[1],
                                    frame: CGRect(x: 0.51, y: original.frame.minY, width: 0.3, height: 0.03))
            let others = rendered.filter { $0.text != label }
            try check("exact split OCR row: \(label)", others + [left, right], controls, passes: true)
            let differentRow = Observation(text: words[1],
                                           frame: CGRect(x: 0.51, y: 0.02, width: 0.3, height: 0.03))
            try check("fragments on different rows: \(label)", others + [left, differentRow], controls, passes: false)
            let suffix = Observation(text: label + "x", frame: original.frame)
            try check("near-match is not exact label: \(label)", others + [suffix], controls, passes: false)
            let offscreen = Observation(text: label, frame: CGRect(x: 0.4, y: 1.1, width: 0.5, height: 0.03))
            try check("offscreen text is not visible output: \(label)", others + [offscreen], controls, passes: false)
        }
        let splitSection = [
            Observation(text: "Additional", frame: CGRect(x: 0.4, y: 0.1, width: 0.15, height: 0.03)),
            Observation(text: "features", frame: CGRect(x: 0.56, y: 0.1, width: 0.15, height: 0.03))
        ]
        try check("split removed header is still detected", rendered + splitSection, controls, passes: false)
        var missingControls = controls
        missingControls["Colored spectrogram"] = false
        missingControls["Slider color"] = false
        try check("former prerequisite controls are output failures", rendered, missingControls, passes: false)
        print("Appearance output oracle: \(count) cases passed.")
    }
}
