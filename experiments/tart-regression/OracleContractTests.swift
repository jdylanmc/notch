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
    }
}
