import Darwin
import Foundation

enum FixtureStoreError: Error {
    case unsafeDirectory, unsafeFile, alreadyRunning, invalidCounter, ioFailure, receiptLimit
}

final class FixtureStore {
    let launchCount: Int
    let audioURL: URL
    let receiptURL: URL
    private let lockFD: Int32
    private let receipt: FileHandle
    private var bytesWritten = 0
    private var sequence = 0

    init(root: URL) throws {
        guard root.isFileURL, root.path == root.resolvingSymlinksInPath().path else {
            throw FixtureStoreError.unsafeDirectory
        }
        var directory = stat()
        guard lstat(root.path, &directory) == 0,
              directory.st_mode & S_IFMT == S_IFDIR,
              directory.st_uid == getuid(),
              directory.st_mode & 0o077 == 0 else {
            throw FixtureStoreError.unsafeDirectory
        }
        let descriptor = open(root.appendingPathComponent("producer.lock").path,
                              O_CREAT | O_RDWR | O_NOFOLLOW, 0o600)
        guard descriptor >= 0 else { throw FixtureStoreError.ioFailure }
        var transferred = false
        defer { if !transferred { close(descriptor) } }
        try Self.validateFile(descriptor)
        guard flock(descriptor, LOCK_EX | LOCK_NB) == 0 else {
            throw FixtureStoreError.alreadyRunning
        }

        let counterURL = root.appendingPathComponent("launch-count.json")
        let counterFD = open(counterURL.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        let previous: Int
        if counterFD >= 0 {
            let handle = FileHandle(fileDescriptor: counterFD, closeOnDealloc: true)
            try Self.validateFile(counterFD)
            guard let bytes = try handle.read(upToCount: 1_025), bytes.count <= 1_024 else {
                throw FixtureStoreError.invalidCounter
            }
            let counter = try JSONDecoder().decode(Counter.self, from: bytes)
            guard counter.schemaVersion == 1, (1..<1_000_000).contains(counter.launches) else {
                throw FixtureStoreError.invalidCounter
            }
            previous = counter.launches
            try handle.close()
        } else if errno == ENOENT {
            previous = 0
        } else {
            throw FixtureStoreError.unsafeFile
        }

        launchCount = previous + 1
        let run = root.appendingPathComponent(String(format: "launch-%06d", launchCount))
        guard mkdir(run.path, 0o700) == 0 else { throw FixtureStoreError.ioFailure }
        audioURL = run.appendingPathComponent("tone.wav")
        receiptURL = run.appendingPathComponent("receipts.jsonl")
        try GeneratedAudio.wave().write(to: audioURL, options: .withoutOverwriting)
        let receiptFD = open(receiptURL.path, O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW, 0o600)
        guard receiptFD >= 0 else { throw FixtureStoreError.ioFailure }
        receipt = FileHandle(fileDescriptor: receiptFD, closeOnDealloc: true)
        try JSONEncoder().encode(Counter(schemaVersion: 1, launches: launchCount))
            .write(to: counterURL, options: .atomic)
        lockFD = descriptor
        transferred = true
    }

    func append(event: String, state: FixtureState) throws {
        let entry = FixtureReceipt(
            pid: getpid(), event: event, sequence: sequence + 1, state: state
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        var data = try encoder.encode(entry)
        data.append(0x0a)
        guard bytesWritten + data.count <= 8 * 1_024 * 1_024 else {
            throw FixtureStoreError.receiptLimit
        }
        try receipt.write(contentsOf: data)
        try receipt.synchronize()
        bytesWritten += data.count
        sequence += 1
    }

    private struct Counter: Codable {
        let schemaVersion: Int
        let launches: Int
    }

    private static func validateFile(_ descriptor: Int32) throws {
        var info = stat()
        guard fstat(descriptor, &info) == 0,
              info.st_mode & S_IFMT == S_IFREG,
              info.st_uid == getuid(), info.st_nlink == 1,
              info.st_mode & 0o022 == 0 else {
            throw FixtureStoreError.unsafeFile
        }
    }

    deinit {
        close(lockFD)
    }
}
