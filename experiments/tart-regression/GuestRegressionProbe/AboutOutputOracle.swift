import CoreGraphics
import Foundation

struct AboutOutputOracle {
    struct Observation {
        let text: String
        let frame: CGRect
    }

    static func normalize(_ text: String) -> String {
        text.split(whereSeparator: \.isWhitespace).joined(separator: " ")
    }

    static func rowText(anchor: Observation, observations: [Observation]) -> String {
        let row = observations.filter {
            let overlap = min($0.frame.maxY, anchor.frame.maxY) - max($0.frame.minY, anchor.frame.minY)
            return $0.frame.midX >= anchor.frame.minX
                && $0.frame.height <= anchor.frame.height * 2
                && overlap >= min($0.frame.height, anchor.frame.height) / 2
        }.sorted { $0.frame.minX < $1.frame.minX }
        return normalize(row.map(\.text).joined(separator: " "))
    }

    static func rowValue(_ label: String, observations: [Observation]) -> String? {
        let anchors = observations.filter {
            let text = normalize($0.text)
            return (text == label || text.hasPrefix(label + " "))
                && !(label == "Version" && text.hasPrefix("Version info"))
        }
        guard anchors.count == 1, let anchor = anchors.first, anchor.frame.height > 0 else { return nil }
        let text = rowText(anchor: anchor, observations: observations)
        guard text == label || text.hasPrefix(label + " ") else { return nil }
        return normalize(String(text.dropFirst(label.count)))
    }

    static func evaluate(_ observations: [Observation], version: String, build: String) -> [String: Bool] {
        let release = rowValue("Release name", observations: observations)
        let value = rowValue("Version", observations: observations)
        var visibleVersion = value
        var visibleBuild: String?
        if let value, value.hasPrefix("("), let end = value.firstIndex(of: ")") {
            visibleBuild = String(value[...end])
            visibleVersion = normalize(String(value[value.index(after: end)...]))
        }
        return [
            "Release name": release != nil,
            "Notch Pocket": release == "Notch Pocket",
            "Version": value != nil,
            version: visibleVersion == normalize(version),
            "(\(build))": visibleBuild == "(\(normalize(build)))"
        ]
    }
}
