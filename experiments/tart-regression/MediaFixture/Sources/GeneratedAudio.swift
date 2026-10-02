import Foundation

enum GeneratedAudio {
    static let sampleRate = 22_050
    static let frameCount = Int(FixtureIdentity.duration) * sampleRate

    static func wave() -> Data {
        let byteCount = frameCount * 2
        var result = Data()
        func ascii(_ text: String) { result.append(contentsOf: text.utf8) }
        func integer<T: FixedWidthInteger>(_ value: T) {
            var littleEndian = value.littleEndian
            withUnsafeBytes(of: &littleEndian) { result.append(contentsOf: $0) }
        }
        ascii("RIFF")
        integer(UInt32(36 + byteCount))
        ascii("WAVEfmt ")
        integer(UInt32(16))
        integer(UInt16(1))
        integer(UInt16(1))
        integer(UInt32(sampleRate))
        integer(UInt32(sampleRate * 2))
        integer(UInt16(2))
        integer(UInt16(16))
        ascii("data")
        integer(UInt32(byteCount))
        for frame in 0..<frameCount {
            let fade = min(1, Double(min(frame, frameCount - 1 - frame)) / 220)
            let sample = sin(2 * Double.pi * 440 * Double(frame) / Double(sampleRate))
            integer(Int16((sample * fade * 4_000).rounded()))
        }
        return result
    }
}
