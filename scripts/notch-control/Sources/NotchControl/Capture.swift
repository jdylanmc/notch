import AppKit
import ControlCore
import ImageIO
import ScreenCaptureKit
import UniformTypeIdentifiers

/// A framework callback may arrive after our deadline; it must not resume twice.
private final class CompletionGate<Value> {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<Value, Error>?

    init(_ continuation: CheckedContinuation<Value, Error>) {
        self.continuation = continuation
    }

    func finish(_ result: Result<Value, Error>) {
        lock.lock()
        let pending = continuation
        continuation = nil
        lock.unlock()
        pending?.resume(with: result)
    }
}

private func boundedCallback<Value>(
    seconds: TimeInterval,
    start: (@escaping (Result<Value, Error>) -> Void) -> Void
) async throws -> Value {
    try await withCheckedThrowingContinuation { continuation in
        let gate = CompletionGate<Value>(continuation)
        DispatchQueue.global().asyncAfter(deadline: .now() + seconds) {
            gate.finish(.failure(ControlFailure(.timeout, "Capture API deadline exceeded.")))
        }
        start { gate.finish($0) }
    }
}

func capture(target: AppTarget, id: UInt32, output: String) async throws {
    try target.requireCapture()
    _ = try target.ownedWindow(id)
    let content: SCShareableContent = try await boundedCallback(seconds: target.budget.remaining()) { done in
        SCShareableContent.getExcludingDesktopWindows(true, onScreenWindowsOnly: true) { content, error in
            if error != nil {
                done(.failure(ControlFailure(.captureFailed, "Shareable window enumeration failed; recheck Screen Recording.")))
            } else if let content {
                done(.success(content))
            } else {
                done(.failure(ControlFailure(.captureFailed, "Shareable window enumeration returned no content.")))
            }
        }
    }
    try target.requireCapture()
    _ = try target.ownedWindow(id)
    let matches = content.windows.filter {
        $0.windowID == id && $0.owningApplication?.processID == target.identity.pid &&
            $0.owningApplication?.bundleIdentifier == AppTarget.bundleID
    }
    guard matches.count == 1, let window = matches.first else {
        throw ControlFailure(.unsupportedWindow, "Selected window is absent from shareable app windows; no desktop fallback.")
    }
    let filter = SCContentFilter(desktopIndependentWindow: window)
    let config = SCStreamConfiguration()
    let width = Double(window.frame.width)
    let height = Double(window.frame.height)
    guard width.isFinite, height.isFinite, width > 0, height > 0,
          width <= 8192, height <= 8192 else {
        throw ControlFailure(.unsupportedWindow, "Window dimensions are unsupported.")
    }
    config.width = Int(width.rounded(.up))
    config.height = Int(height.rounded(.up))
    config.showsCursor = false
    config.ignoreShadowsSingleWindow = true
    try target.requireCapture()
    _ = try target.ownedWindow(id)
    let image: CGImage = try await boundedCallback(seconds: target.budget.remaining()) { done in
        SCScreenshotManager.captureImage(contentFilter: filter, configuration: config) { image, error in
            if error != nil {
                done(.failure(ControlFailure(.captureFailed, "Selected window capture failed; no fallback was attempted.")))
            } else if let image {
                done(.success(image))
            } else {
                done(.failure(ControlFailure(.captureFailed, "Capture returned no image.")))
            }
        }
    }
    try target.requireCapture()
    _ = try target.ownedWindow(id)
    let data = NSMutableData()
    guard let destination = CGImageDestinationCreateWithData(data as CFMutableData, UTType.png.identifier as CFString, 1, nil) else {
        throw ControlFailure(.captureFailed, "Cannot create local PNG encoder.")
    }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else {
        throw ControlFailure(.captureFailed, "PNG encoding failed.")
    }
    try target.requireCapture()
    _ = try target.ownedWindow(id)
    try SecureOutput.write(data as Data, to: output)
}
