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
        try checkSettingsRemoval(.panelSwipes)
        try checkGeneralNativeLabelGeometry(.general)
        try checkGeneralNativeLabelGeometry(.panelSwipes)
        try checkFixtureAudio()
    }

    private static func checkFixtureAudio() throws {
        let wave = [UInt8](GeneratedAudio.wave())
        func unsigned(_ offset: Int, _ size: Int) -> UInt32 {
            (0..<size).reduce(UInt32(0)) { $0 | UInt32(wave[offset + $1]) << (8 * $1) }
        }
        let expectedBytes = 30 * 22_050 * 2
        guard wave.count == expectedBytes + 44,
              String(decoding: wave[0..<4], as: UTF8.self) == "RIFF",
              String(decoding: wave[8..<16], as: UTF8.self) == "WAVEfmt ",
              String(decoding: wave[36..<40], as: UTF8.self) == "data",
              unsigned(4, 4) == UInt32(expectedBytes + 36), unsigned(16, 4) == 16,
              unsigned(20, 2) == 1, unsigned(22, 2) == 1,
              unsigned(24, 4) == 22_050, unsigned(28, 4) == 44_100,
              unsigned(32, 2) == 2, unsigned(34, 2) == 16,
              unsigned(40, 4) == UInt32(expectedBytes) else {
            throw NSError(domain: "FixtureAudioContract", code: 1)
        }
        let samples = stride(from: 44, to: wave.count, by: 2).map {
            Int(Int16(bitPattern: UInt16(unsigned($0, 2))))
        }
        guard samples.first == 0, samples.last == 0, samples.contains(where: { $0 > 1000 }),
              samples.contains(where: { $0 < -1000 }), samples.allSatisfy({ abs($0) <= 4000 }) else {
            throw NSError(domain: "FixtureAudioContract", code: 2)
        }
        print("Fixture audio: real generated PCM structure and bounded samples verified; no playback performed.")
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
                observations, scenario: scenario, contentFrame: content, controls: accessible,
                labelFrames: labelFrames, pixelWidth: 700
            )
            guard result.count == labels.count + 1 && result.values.allSatisfy({ $0 }) == passes else {
                throw NSError(domain: "\(scenario.pane)OracleContractTests", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "\(name): \(result)"])
            }
            count += 1
        }
        try check("retained controls and pixels", rendered, controls, passes: true)
        if scenario == .panelSwipes {
            for label in ["Change media with horizontal gestures", "Gesture sensitivity", "Normalize gesture direction"] {
                try check("media configuration is not panel copy: \(label)", rendered + [
                    Observation(text: label, frame: CGRect(x: 0.4, y: 0.1, width: 0.5, height: 0.03))
                ], controls, passes: true)
            }
            let footerSource = "Two-finger swipe up on notch to close, two-finger swipe down on notch to open when **Open notch on hover** option is disabled"
            let footer = footerSource.replacingOccurrences(of: "**", with: "")
            for sourceTrue in [false, true] {
                for visible in [false, true] {
                    var accessible = controls
                    accessible[absence] = scenario.removedLabelsAbsent { $0 == footer && sourceTrue }
                    let pixels = rendered + (visible ? [
                        Observation(text: footer, frame: CGRect(x: 0.4, y: 0.1, width: 0.5, height: 0.03))
                    ] : [])
                    let result = SettingsRemovalOutputOracle.evaluate(
                        pixels, scenario: scenario, contentFrame: content, controls: accessible,
                        labelFrames: labelFrames, pixelWidth: 700
                    )
                    guard accessible[absence] == !sourceTrue,
                          result[absence] == (!sourceTrue && !visible),
                          labels.allSatisfy({ result[$0] == true }) else {
                        throw NSError(domain: "PanelFooterOnly", code: 1, userInfo: [
                            NSLocalizedDescriptionKey: "sourceTrue=\(sourceTrue), visible=\(visible): \(result)"
                        ])
                    }
                    count += 1
                }
            }
        }
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
        for text in scenario.removedLabels + scenario.forbiddenText {
            let remnant = Observation(text: text, frame: CGRect(x: 0.4, y: 0.1, width: 0.5, height: 0.03))
            try check("old app pixels: \(text)", rendered + [remnant], controls, passes: false)
        }
        let removedWords = scenario.removedLabels[0].split(separator: " ", maxSplits: 1).map(String.init)
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
            sidebarOnly, scenario: scenario, contentFrame: content, controls: controls,
            labelFrames: labelFrames, pixelWidth: 700
        )
        guard emptyOutput[absence] == false else {
            throw NSError(domain: "\(scenario.pane)EmptyViewport", code: 1)
        }
        count += 1
        try check("clipped remnant still rejects absence", rendered + [
            Observation(text: scenario.removedLabels[0], frame: CGRect(x: 0.4, y: 0.99, width: 0.3, height: 0.03))
        ], controls, passes: false)
        for frames in [[:], [labels[0]: rendered[0].frame],
                       labelFrames.mapValues { $0.offsetBy(dx: 0, dy: -0.1) },
                       labelFrames.mapValues { $0.offsetBy(dx: 0, dy: 1) }] {
            let output = SettingsRemovalOutputOracle.evaluate(
                rendered, scenario: scenario, contentFrame: content, controls: controls,
                labelFrames: frames, pixelWidth: 700
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
        print("\(scenario.rawValue) output oracle: \(count) cases passed.")
    }

    private static func checkGeneralNativeLabelGeometry(_ scenario: SettingsRemovalScenario) throws {
        typealias Observation = AboutOutputOracle.Observation
        let content = CGRect(x: 208.0 / 700, y: 0, width: 492.0 / 700, height: 548.0 / 600)
        let cases: [(String, CGRect, CGRect)] = [
            ("Launch at login",
             CGRect(x: 0.34, y: 0.7316666666666667, width: 93.0 / 700, height: 16.0 / 600),
             CGRect(x: 0.33428571560714287, y: 0.72666666633333343,
                    width: 0.13999999999999996, height: 0.026666666666666616)),
            ("Remember last tab",
             CGRect(x: 0.34, y: 0.5716666666666667, width: 114.0 / 700, height: 16.0 / 600),
             CGRect(x: 0.33428571214285724, y: 0.56999999983333338,
                    width: 0.17142857142857143, height: 0.026666666666666616))
        ]
        var count = 0
        for (label, frame, pixels) in cases {
            func check(_ name: String, _ text: String, _ box: CGRect, expected: Bool,
                       present: Bool = true, frames: [String: CGRect]? = nil, width: Int = 700) throws {
                let output = SettingsRemovalOutputOracle.evaluate(
                    [Observation(text: text, frame: box)], scenario: scenario, contentFrame: content,
                    controls: [label: present, scenario.absenceKey: false],
                    labelFrames: frames ?? [label: frame], pixelWidth: width
                )
                guard output[label] == expected, output[scenario.absenceKey] == false, output.count == 14 else {
                    throw NSError(domain: "GeneralNativeLabelGeometry", code: 1,
                                  userInfo: [NSLocalizedDescriptionKey: "\(label) \(name): \(output)"])
                }
                count += 1
            }
            try check("actual guest OCR and AXValue", label, pixels, expected: true)
            try check("missing native label", label, pixels, expected: false, present: false)
            try check("missing native frame", label, pixels, expected: false, frames: [:])
            try check("missing pixels", "", pixels, expected: false)
            try check("near text", label + "x", pixels, expected: false)
            try check("wrong row", label, pixels.offsetBy(dx: 0, dy: -0.05), expected: false)
            try check("wrong right-hand label", label, pixels.offsetBy(dx: 0.3, dy: 0), expected: false)
            try check("five pixels left is outside measured allowance", label,
                      CGRect(x: frame.minX - 5.0 / 700, y: pixels.minY,
                             width: pixels.width, height: pixels.height), expected: false)
            try check("no pixel dimensions", label, pixels, expected: false, width: 0)
            try check("same fraction is eight pixels at double resolution", label, pixels, expected: false, width: 1400)
            try check("clipped label frame", label, pixels, expected: false,
                      frames: [label: frame.offsetBy(dx: 0, dy: 1)])
        }
        for (scenario, label) in [
            (SettingsRemovalScenario.general, "Show menu bar icon"),
            (.notifications, "From all apps")
        ] {
            let frame = cases[0].1
            let output = SettingsRemovalOutputOracle.evaluate(
                [Observation(text: label, frame: cases[0].2)], scenario: scenario,
                contentFrame: content, controls: [label: true, scenario.absenceKey: true],
                labelFrames: [label: frame], pixelWidth: 700
            )
            guard output[label] == false else { throw NSError(domain: "UnchangedLabelAlignment", code: 1) }
            count += 1
        }
        print("\(scenario.rawValue) measured native label geometry: \(count) cases passed.")
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
