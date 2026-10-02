//
//  JSONLinesPipeHandler.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//
//  Shared source compiled into BOTH targets (via the Shared synchronized
//  group). There is intentionally one copy — edit once, both sides build it.
//

import Darwin
import Foundation
import os

/// Streams newline-delimited JSON from a pipe, decoding each line.
/// Used by the app (mediaremote-adapter now-playing stream) and the XPC
/// helper (Lunar daemon event stream).
actor JSONLinesPipeHandler {
    nonisolated let outputPipe: Pipe
    nonisolated let fileHandle: FileHandle
    nonisolated private let reader: JSONLinesPipeReader
    private var hasStartedReading = false
    private var consecutiveMalformedLines = 0

    init(
        pipe: Pipe = Pipe(),
        closeEndpoint: @escaping @Sendable (FileHandle) throws -> Void = { try $0.close() }
    ) {
        outputPipe = pipe
        fileHandle = pipe.fileHandleForReading
        reader = JSONLinesPipeReader(pipe: pipe, closeEndpoint: closeEndpoint)
    }

    func readJSONLines<Value: Decodable & Sendable>(
        as type: Value.Type,
        onValue: @escaping @Sendable (Value) async -> Void
    ) async {
        guard !hasStartedReading else {
            JSONLinesPipeReader.logger.error("JSON-lines pipe only supports one reader per lifetime")
            return
        }
        hasStartedReading = true

        await withTaskCancellationHandler {
            var line = Data()
            let decoder = JSONDecoder()
            while let chunk = await reader.nextChunk() {
                guard !Task.isCancelled, reader.admitValue() else { return }
                for byte in chunk {
                    guard byte == UInt8(ascii: "\n") else {
                        line.append(byte)
                        continue
                    }

                    if line.last == UInt8(ascii: "\r") {
                        line.removeLast()
                    }

                    guard !line.isEmpty,
                          let decoded = try? decoder.decode(Value.self, from: line)
                    else {
                        consecutiveMalformedLines += 1
                        line.removeAll(keepingCapacity: true)
                        if consecutiveMalformedLines >= 3 {
                            return
                        }
                        continue
                    }

                    consecutiveMalformedLines = 0
                    line.removeAll(keepingCapacity: true)
                    guard !Task.isCancelled, reader.admitValue() else { return }
                    await onValue(decoded)
                    guard !Task.isCancelled, reader.admitValue() else { return }
                }
            }
        } onCancel: {
            close()
        }
    }

    /// Immediately rejects new read/value admissions. An already-admitted async
    /// callback may finish cooperatively; close never waits for that callback.
    /// Physical disposal is asynchronous, after the source has quiesced.
    nonisolated func close() {
        reader.close()
    }

    /// For owners that need a disposal barrier (not a join of the async callback).
    /// Call close first. Existing app/helper stop methods need not wait.
    nonisolated func waitUntilClosed() async {
        await reader.waitUntilClosed()
    }
}

/// One demand, one <=16 KiB read, no prefetch while the consumer awaits a callback.
/// The source is suspended without demand, so idle pipes consume no worker thread.
private final class JSONLinesPipeReader: Sendable {
    static let logger = Logger(subsystem: "com.jdylanmc.notchpocket", category: "json-lines")

    private struct State {
        var closed = false
        var suspended = true
        var pending: CheckedContinuation<Data?, Never>?
    }

    private let source: DispatchSourceRead
    private let descriptor: Int32
    private let state = OSAllocatedUnfairLock(initialState: State())
    private let disposed = DispatchGroup()

    init(pipe: Pipe, closeEndpoint: @escaping @Sendable (FileHandle) throws -> Void) {
        let handle = pipe.fileHandleForReading
        let writer = pipe.fileHandleForWriting
        descriptor = handle.fileDescriptor
        source = DispatchSource.makeReadSource(
            fileDescriptor: descriptor,
            queue: DispatchQueue(label: "com.jdylanmc.notchpocket.json-lines")
        )
        disposed.enter()
        source.setEventHandler { [weak self] in self?.readReadyChunk() }
        source.setCancelHandler { [disposed] in
            // dispatch/source.h: only this handler runs after BOTH the event
            // handler and the system's references to the descriptor have ended.
            // Attempt both closes even if the first fails; never retry raw close
            // on a numeric descriptor that may already have been recycled.
            defer { disposed.leave() }
            for endpoint in [handle, writer] {
                do {
                    try closeEndpoint(endpoint)
                } catch {
                    let code = (error as NSError).code
                    Self.logger.error("JSON-lines pipe close failed (code \(code, privacy: .public))")
                }
            }
        }

        let flags = fcntl(descriptor, F_GETFL)
        if flags == -1 || fcntl(descriptor, F_SETFL, flags | O_NONBLOCK) == -1 {
            let code = errno
            Self.logger.error("JSON-lines pipe setup failed (errno \(code, privacy: .public))")
            close()
        }
    }

    deinit { close() }

    func admitValue() -> Bool {
        state.withLock { !$0.closed }
    }

    func nextChunk() async -> Data? {
        await withCheckedContinuation { continuation in
            state.withLock { state in
                guard !state.closed else {
                    continuation.resume(returning: nil)
                    return
                }
                precondition(state.pending == nil && state.suspended)
                state.pending = continuation
                state.suspended = false
                source.resume()
            }
        }
    }

    private func readReadyChunk() {
        state.withLock { state in
            guard !state.closed, let pending = state.pending else { return }
            var data = Data(count: 16 * 1024)
            // Nonblocking, bounded syscall only; this lock is NEVER held across
            // await or a user callback. Close cannot interleave read admission.
            let count = data.withUnsafeMutableBytes {
                Darwin.read(descriptor, $0.baseAddress, $0.count)
            }
            let code = errno
            if count < 0 && (code == EAGAIN || code == EWOULDBLOCK || code == EINTR) {
                return
            }
            source.suspend()
            state.suspended = true
            state.pending = nil
            if count > 0 {
                data.count = count
                pending.resume(returning: data)
            } else {
                if count < 0 {
                    Self.logger.error("JSON-lines pipe read failed (errno \(code, privacy: .public))")
                }
                pending.resume(returning: nil)
            }
        }
    }

    func close() {
        state.withLock { state in
            guard !state.closed else { return }
            state.closed = true
            source.cancel()
            // A cancelled suspended source must resume to run its cancel handler.
            if state.suspended {
                state.suspended = false
                source.resume()
            }
            state.pending?.resume(returning: nil)
            state.pending = nil
        }
    }

    func waitUntilClosed() async {
        await withCheckedContinuation { continuation in
            disposed.notify(queue: .global()) { continuation.resume() }
        }
    }
}
