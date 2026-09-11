import Darwin
import Foundation

/// Directory descriptors keep parent replacement from redirecting a write.
public enum SecureOutput {
    public static func write(_ data: Data, to path: String) throws {
        try validateAbsolutePath(path)
        let parts = path.split(separator: "/").map(String.init)
        guard let name = parts.last else {
            throw ControlFailure(.unsafeOutput, "Missing output filename.")
        }
        var directory = Darwin.open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC)
        guard directory >= 0 else {
            throw ControlFailure(.outputFailed, "Cannot open output directory.")
        }
        defer { Darwin.close(directory) }
        for component in parts.dropLast() {
            let next = openat(directory, component, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            guard next >= 0 else {
                throw ControlFailure(.unsafeOutput, "Output parents must exist and must not be symlinks.")
            }
            Darwin.close(directory)
            directory = next
        }
        let descriptor = openat(directory, name, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard descriptor >= 0 else {
            let code: FailureCode = errno == EEXIST ? .outputExists : .outputFailed
            throw ControlFailure(code, "Cannot create output; existing files are never overwritten.")
        }
        var complete = false
        defer {
            Darwin.close(descriptor)
            if !complete { unlinkat(directory, name, 0) }
        }
        try data.withUnsafeBytes { bytes in
            guard let base = bytes.baseAddress, !bytes.isEmpty else {
                throw ControlFailure(.outputFailed, "Empty image data.")
            }
            var offset = 0
            while offset < bytes.count {
                let count = Darwin.write(descriptor, base.advanced(by: offset), bytes.count - offset)
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else {
                    throw ControlFailure(.outputFailed, "Image write failed.")
                }
                offset += count
            }
        }
        guard fsync(descriptor) == 0 else {
            throw ControlFailure(.outputFailed, "Image flush failed.")
        }
        complete = true
    }
}
