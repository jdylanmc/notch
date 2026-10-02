//
//  JSONLinesPipeHandler.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//
//  Shared source compiled into BOTH targets (via the Shared synchronized
//  group). There is intentionally one copy — edit once, both sides build it.
//

import Foundation
import os

/// Streams newline-delimited JSON from a pipe, decoding each line.
/// Used by the app (mediaremote-adapter now-playing stream) and the XPC
/// helper (Lunar daemon event stream).
actor JSONLinesPipeHandler {
    nonisolated let outputPipe: Pipe
    nonisolated let fileHandle: FileHandle
    nonisolated private let isClosed = OSAllocatedUnfairLock(initialState: false)
    private var byteIterator: FileHandle.AsyncBytes.Iterator
    private var consecutiveMalformedLines = 0

    init(pipe: Pipe = Pipe()) {
        outputPipe = pipe
        fileHandle = pipe.fileHandleForReading
        byteIterator = fileHandle.bytes.makeAsyncIterator()
    }

    func readJSONLines<Value: Decodable & Sendable>(
        as type: Value.Type,
        onValue: @escaping @Sendable (Value) async -> Void
    ) async {
        var line = Data()
        var iterator = byteIterator

        await withTaskCancellationHandler {
            // AsyncBytes captures a numeric descriptor that can be reused after close.
            guard !isClosed.withLock({ $0 }) else { return }
            do {
                while let byte = try await iterator.next() {
                    guard !Task.isCancelled else { return }

                    guard byte == UInt8(ascii: "\n") else {
                        line.append(byte)
                        continue
                    }

                    if line.last == UInt8(ascii: "\r") {
                        line.removeLast()
                    }

                    guard !line.isEmpty,
                          let decoded = try? JSONDecoder().decode(Value.self, from: line)
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
                    await onValue(decoded)
                }
            } catch {}
        } onCancel: {
            // AsyncBytes can stay suspended on an idle pipe after task cancellation.
            close()
        }
    }

    nonisolated func close() {
        isClosed.withLock { $0 = true }
        try? fileHandle.close()
        try? outputPipe.fileHandleForWriting.close()
    }
}
