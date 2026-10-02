import CoreGraphics
import Foundation

enum IdleMusicScenario: String {
    case noTarget = "music-idle-no-target"
    case unavailable = "music-idle-unavailable"

    var source: String { self == .noTarget ? "Now Playing" : "Spotify" }
    var message: String { self == .noTarget ? "No music app selected." : "Spotify is not installed." }
}

enum IdleMusicOutputOracle {
    static func statusVisible(
        _ observations: [AboutOutputOracle.Observation], scenario: IdleMusicScenario, statusFrame: CGRect?
    ) -> Bool {
        guard let statusFrame, !statusFrame.isEmpty,
              CGRect(x: 0, y: 0, width: 1, height: 1).contains(statusFrame) else { return false }
        let rows = observations.filter {
            let overlap = min($0.frame.maxY, statusFrame.maxY) - max($0.frame.minY, statusFrame.minY)
            return $0.frame.minX >= statusFrame.minX
                && $0.frame.maxX <= statusFrame.maxX
                && overlap >= min($0.frame.height, statusFrame.height) / 2
                && $0.frame.height > 0 && $0.frame.height <= statusFrame.height
        }.sorted { $0.frame.minX < $1.frame.minX }
        return AboutOutputOracle.normalize(rows.map(\.text).joined(separator: " ")) == scenario.message
    }
}
