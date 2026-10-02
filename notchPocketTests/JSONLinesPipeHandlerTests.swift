//
//  JSONLinesPipeHandlerTests.swift
//  notchPocketTests
//

import Darwin
import Foundation
import XCTest
import os

@testable import notchPocket

@MainActor
final class JSONLinesPipeHandlerTests: XCTestCase {
    private struct DescriptorIdentity: Equatable {
        let device: dev_t
        let inode: ino_t

        init(_ handle: FileHandle) throws {
            var metadata = stat()
            guard fstat(handle.fileDescriptor, &metadata) == 0 else {
                throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
            }
            device = metadata.st_dev
            inode = metadata.st_ino
        }
    }

    private final class CloseProbe: Sendable {
        let pipe = Pipe()
        let failingReadClose: Bool
        private let counts = OSAllocatedUnfairLock(initialState: (reading: 0, writing: 0))
        var readCloses: Int { counts.withLock { $0.reading } }
        var writeCloses: Int { counts.withLock { $0.writing } }

        init(failingReadClose: Bool = false) { self.failingReadClose = failingReadClose }

        func close(_ handle: FileHandle) throws {
            let isReader = handle === pipe.fileHandleForReading
            XCTAssertTrue(isReader || handle === pipe.fileHandleForWriting)
            counts.withLock {
                if isReader { $0.reading += 1 } else { $0.writing += 1 }
            }
            try handle.close()
            if isReader && failingReadClose {
                throw NSError(domain: NSPOSIXErrorDomain, code: Int(EIO))
            }
        }
    }

    private struct Message: Decodable, Equatable, Sendable {
        let value: String
    }

    private final class CallbackOwner: Sendable {
        let released: XCTestExpectation

        init(released: XCTestExpectation) { self.released = released }

        deinit { released.fulfill() }
    }

    private actor Values {
        private var values: [Message] = []

        func append(_ value: Message) {
            values.append(value)
        }

        func snapshot() -> [String] {
            values.map(\.value)
        }
    }

    private actor Gate {
        private var isOpen = false
        private var continuation: CheckedContinuation<Void, Never>?

        func wait() async {
            guard !isOpen else { return }
            await withCheckedContinuation { continuation = $0 }
        }

        func open() {
            isOpen = true
            continuation?.resume()
            continuation = nil
        }
    }

    @MainActor
    private final class Run {
        let handler: JSONLinesPipeHandler
        let values = Values()
        let completed = XCTestExpectation(description: "reader returned")
        let drained = XCTestExpectation(description: "reader cleanup")
        let closeCompleted = XCTestExpectation(description: "close returned")
        let closeDrained = XCTestExpectation(description: "close cleanup")
        let readDescriptor: Int32
        let writeDescriptor: Int32
        let readIdentity: DescriptorIdentity?
        let writeIdentity: DescriptorIdentity?
        var reader: Task<Void, Never>?
        var closer: Task<Void, Never>?
        private var disposal: Task<Void, Never>?
        private let disposed = XCTestExpectation(description: "physical disposal completed")
        private var disposalFinished = false
        private var disposalWaited = false
        private var producer: Task<Void, Error>?
        private let producerDrained = XCTestExpectation(description: "owned producer drained")
        private var producerJoined = false
        private var producerWaited = false
        private var cleanupAttempted = false
        private(set) var cleanupFinished = false
        var gates: [Gate] = []
        private var producerWriters: [FileHandle] = []
        private var replacementPipes: [Pipe] = []
        private var replacementReaders: [FileHandle] = []
        private var writerClosed = false
        var failFirstWriterClose = false

        init(handler: JSONLinesPipeHandler) {
            self.handler = handler
            readDescriptor = handler.fileHandle.fileDescriptor
            writeDescriptor = handler.outputPipe.fileHandleForWriting.fileDescriptor
            readIdentity = try? DescriptorIdentity(handler.fileHandle)
            writeIdentity = try? DescriptorIdentity(handler.outputPipe.fileHandleForWriting)
            XCTAssertNotNil(readIdentity)
            XCTAssertNotNil(writeIdentity)
        }

        func gate() -> Gate {
            let gate = Gate()
            gates.append(gate)
            return gate
        }

        func start(
            beforeReading: Gate? = nil,
            onValue: @escaping @Sendable (String) async -> Void = { _ in }
        ) {
            precondition(reader == nil)
            reader = Task.detached { [handler, values, completed, drained] in
                await beforeReading?.wait()
                await handler.readJSONLines(as: Message.self) { value in
                    await values.append(value)
                    await onValue(value.value)
                }
                completed.fulfill()
                drained.fulfill()
            }
        }

        func write(_ text: String) throws {
            try write(Data(text.utf8))
        }

        func write(_ bytes: Data) throws {
            // Small synchronous fixture writes; the separate bulk producer is owned and joined.
            precondition(bytes.count < 512)
            try handler.outputPipe.fileHandleForWriting.write(contentsOf: bytes)
        }

        func finishWriting() throws {
            guard !writerClosed else { return }
            try handler.outputPipe.fileHandleForWriting.close()
            writerClosed = true
            if failFirstWriterClose {
                throw NSError(domain: NSPOSIXErrorDomain, code: Int(EIO))
            }
        }

        func duplicateProducerWriter() throws -> FileHandle {
            let descriptor = dup(writeDescriptor)
            guard descriptor >= 0 else {
                throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
            }
            let writer = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
            producerWriters.append(writer)
            return writer
        }

        func startProducer(_ data: Data) throws {
            precondition(producer == nil)
            let writer = try duplicateProducerWriter()
            guard fcntl(writer.fileDescriptor, F_SETNOSIGPIPE, 1) == 0 else {
                throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
            }
            // Exactly one test-owned writer; cleanup closes the reader to release
            // a failed test's blocked write, then joins it with a failing deadline.
            producer = Task.detached { [producerDrained] in
                defer { producerDrained.fulfill() }
                try Task.checkCancellation()
                try writer.write(contentsOf: data)
                try writer.close()
            }
        }

        func waitForProducer() async throws {
            guard let producer, !producerWaited else { return }
            producerWaited = true
            let result = await XCTWaiter.fulfillment(of: [producerDrained], timeout: 3)
            XCTAssertEqual(result, .completed, "Owned producer did not drain")
            if result == .completed {
                producerJoined = true
                try await producer.value
            }
        }

        func closeFromConsumer() {
            precondition(closer == nil)
            closer = Task.detached { [handler, closeCompleted, closeDrained] in
                handler.close()
                closeCompleted.fulfill()
                closeDrained.fulfill()
            }
        }

        func cancelAndCloseConcurrently() {
            precondition(closer == nil)
            closer = Task.detached { [handler, reader, closeCompleted, closeDrained] in
                await withTaskGroup(of: Void.self) { group in
                    group.addTask { reader?.cancel() }
                    group.addTask { for _ in 0..<32 { handler.close() } }
                }
                closeCompleted.fulfill()
                closeDrained.fulfill()
            }
        }

        func replacementPipe() -> Pipe {
            let pipe = Pipe()
            replacementPipes.append(pipe)
            return pipe
        }

        func reuseReadDescriptor(from pipe: Pipe) throws -> FileHandle {
            // Allocate, never overwrite: even if another host thread wins the slot,
            // F_DUPFD cannot close a descriptor belonging to that thread.
            let descriptor = fcntl(pipe.fileHandleForReading.fileDescriptor, F_DUPFD, readDescriptor)
            guard descriptor >= 0 else {
                throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
            }
            let reader = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
            replacementReaders.append(reader)
            XCTAssertEqual(descriptor, readDescriptor, "The negative control must actually reuse the old descriptor")
            XCTAssertNoThrow(try reader.read(upToCount: 0), "Check the owned handle, not just its number")
            XCTAssertEqual(try DescriptorIdentity(reader), try DescriptorIdentity(pipe.fileHandleForReading))
            XCTAssertNotEqual(try DescriptorIdentity(reader), readIdentity, "Replacement must be a different pipe")
            return reader
        }

        @discardableResult
        func waitForDisposal() async -> Bool {
            if disposalFinished { return true }
            guard !disposalWaited else { return false }
            disposalWaited = true
            if disposal == nil {
                disposal = Task.detached { [handler, disposed] in
                    await handler.waitUntilClosed()
                    disposed.fulfill()
                }
            }
            let result = await XCTWaiter.fulfillment(of: [disposed], timeout: 3)
            XCTAssertEqual(result, .completed, "Owned physical cleanup did not drain")
            if result == .completed {
                await disposal?.value
                disposal = nil
                disposalFinished = true
            }
            return disposalFinished
        }

        func cleanup() async throws {
            guard !cleanupAttempted else { return }
            cleanupAttempted = true
            var firstError: Error?
            var tasksDrained = true
            func attempt(_ operation: () throws -> Void) {
                do { try operation() } catch { if firstError == nil { firstError = error } }
            }
            // Always release gates and drain tasks, even if the first close throws.
            attempt { try finishWriting() }
            producer?.cancel()
            reader?.cancel()
            handler.close()
            // Close the read endpoint before a possibly blocked producer writer.
            let physicallyDisposed = await waitForDisposal()
            if !producerJoined {
                do { try await waitForProducer() } catch {
                    if producer?.isCancelled != true && firstError == nil { firstError = error }
                }
            }
            tasksDrained = producer == nil || producerJoined
            for writer in producerWriters { attempt { try writer.close() } }
            for pipe in replacementPipes { attempt { try pipe.fileHandleForWriting.close() } }
            for gate in gates { await gate.open() }
            if let reader {
                let result = await XCTWaiter.fulfillment(of: [drained], timeout: 3)
                XCTAssertEqual(result, .completed, "Owned reader did not drain after cancellation and EOF")
                if result == .completed { await reader.value }
                tasksDrained = tasksDrained && result == .completed
            }
            if let closer {
                let result = await XCTWaiter.fulfillment(of: [closeDrained], timeout: 3)
                XCTAssertEqual(result, .completed, "Owned close task did not drain after EOF")
                if result == .completed { await closer.value }
                tasksDrained = tasksDrained && result == .completed
            }
            handler.close()
            handler.close()
            // Zero-length probes cannot hang; numeric descriptors may already be reused.
            XCTAssertThrowsError(try handler.fileHandle.read(upToCount: 0))
            XCTAssertThrowsError(try handler.outputPipe.fileHandleForWriting.write(contentsOf: Data()))
            for writer in producerWriters {
                XCTAssertThrowsError(try writer.write(contentsOf: Data()))
            }
            for reader in replacementReaders { attempt { try reader.close() } }
            for pipe in replacementPipes { attempt { try pipe.fileHandleForReading.close() } }
            cleanupFinished = tasksDrained && physicallyDisposed
            if let firstError { throw firstError }
        }
    }

    private func makeRun(handler: JSONLinesPipeHandler = JSONLinesPipeHandler()) -> Run {
        let run = Run(handler: handler)
        addTeardownBlock { try await run.cleanup() }
        return run
    }

    private func makeDescriptorReuseRun() throws -> Run {
        // Leave low slots free for the XCTest app host before triggering reuse.
        // dup/F_DUPFD only allocate; no dup2 can overwrite a host-owned descriptor.
        let seed = Pipe()
        var reservations: [FileHandle] = []
        defer {
            for handle in reservations { XCTAssertNoThrow(try handle.close()) }
            XCTAssertNoThrow(try seed.fileHandleForReading.close())
            XCTAssertNoThrow(try seed.fileHandleForWriting.close())
        }
        var descriptor: Int32 = 0
        while descriptor < 128 && reservations.count < 128 {
            descriptor = dup(seed.fileHandleForReading.fileDescriptor)
            guard descriptor >= 0 else {
                throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
            }
            reservations.append(FileHandle(fileDescriptor: descriptor, closeOnDealloc: true))
        }
        let run = makeRun()
        XCTAssertGreaterThanOrEqual(run.readDescriptor, 128, "Reuse fixture must leave low slots for host activity")
        return run
    }

    @discardableResult
    private func wait(
        for expectation: XCTestExpectation,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async -> Bool {
        let result = await XCTWaiter.fulfillment(of: [expectation], timeout: 3)
        XCTAssertEqual(result, .completed, expectation.expectationDescription, file: file, line: line)
        return result == .completed
    }
}

extension JSONLinesPipeHandlerTests {
    func testSuppliedPipeDeliversMultipleValuesInOrderAndKeepsOwnershipUntilClose() async throws {
        let pipe = Pipe()
        let run = makeRun(handler: JSONLinesPipeHandler(pipe: pipe))
        XCTAssertTrue(run.handler.outputPipe === pipe)
        XCTAssertTrue(run.handler.fileHandle === pipe.fileHandleForReading)
        XCTAssertNoThrow(try pipe.fileHandleForWriting.write(contentsOf: Data()))
        run.start()
        try run.write("{\"value\":\"one\"}\n{\"value\":\"two\"}\n{\"value\":\"three\"}\n")
        try run.finishWriting()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one", "two", "three"])
        XCTAssertNoThrow(try run.handler.fileHandle.read(upToCount: 0))
        XCTAssertEqual(try DescriptorIdentity(run.handler.fileHandle), run.readIdentity, "EOF retains the same reader")
    }

    func testSeparateWritesReassembleJSONUTF8AndSplitCRLF() async throws {
        let run = makeRun()
        let first = expectation(description: "first complete line")
        let release = run.gate()
        run.start { value in
            if value == "first" {
                first.fulfill()
                await release.wait()
            }
        }
        try run.write("{\"value\":\"first\"}\n{\"val")
        guard await wait(for: first) else { return }
        try run.write("ue\":\"caf")
        try run.write(Data([0xC3]))
        try run.write(Data([0xA9]))
        try run.write("\"}\r")
        let beforeDelimiter = await run.values.snapshot()
        XCTAssertEqual(beforeDelimiter, ["first"])
        await release.open()
        try run.write("\n{\"value\":")
        try run.write("\"last\"}\r\n")
        try run.finishWriting()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["first", "caf\u{00E9}", "last"])
    }

    func testOneAndTwoMalformedLinesAreSkippedAndSuccessResetsTheCounter() async throws {
        let run = makeRun()
        run.start()
        try run.write("not-json\n{\"value\":\"one\"}\n")
        try run.write("{\"value\":42}\n{}\n{\"value\":\"two\"}\n")
        try run.write("null\n[]\n{\"value\":\"three\"}\n")
        try run.finishWriting()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one", "two", "three"])
    }

    func testThirdConsecutiveMalformedLineStopsBeforeBufferedValidValueWithoutEOF() async throws {
        let run = makeRun()
        run.start()
        try run.write("{\"value\":\"before\"}\ninvalid\n{}\n{\"value\":false}\n{\"value\":\"after\"}\n")

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["before"])
        XCTAssertNoThrow(try run.handler.outputPipe.fileHandleForWriting.write(contentsOf: Data()))
        XCTAssertEqual(try DescriptorIdentity(run.handler.outputPipe.fileHandleForWriting), run.writeIdentity)
        XCTAssertNoThrow(try run.handler.fileHandle.read(upToCount: 0))
        XCTAssertEqual(try DescriptorIdentity(run.handler.fileHandle), run.readIdentity, "Caller still owns cleanup")
    }

    func testEmptyCRLFAndWhitespaceLinesCountTowardTheSameMalformedThreshold() async throws {
        let run = makeRun()
        run.start()
        try run.write("\n\r\n \t\n{\"value\":\"unreachable\"}\n")

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, [])
    }

    func testEmptyEOFReturnsWithoutCallback() async throws {
        let run = makeRun()
        run.start()
        try run.finishWriting()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, [])
    }

    func testInvalidUTF8CountsAsMalformedAndAValidLineStillResetsTheCounter() async throws {
        let run = makeRun()
        run.start()
        try run.write(Data([0xFF, 0x0A, 0xC3, 0x0A]))
        try run.write("{\"value\":\"recovered\"}\ninvalid\ninvalid\n{\"value\":\"reset\"}\n")
        try run.finishWriting()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["recovered", "reset"])
    }

    func testEOFDropsUnterminatedValidJSONPartialJSONAndCarriageReturn() async throws {
        for suffix in ["{\"value\":\"trailing\"}", "{\"value\":", "{\"value\":\"trailing\"}\r"] {
            let run = makeRun()
            run.start()
            try run.write("{\"value\":\"terminated\"}\n" + suffix)
            try run.finishWriting()

            await wait(for: run.completed)
            let values = await run.values.snapshot()
            XCTAssertEqual(values, ["terminated"], suffix)
        }
    }

    func testAsyncCallbackIsAwaitedBeforeTheNextBufferedValue() async throws {
        let run = makeRun()
        let first = expectation(description: "callback entered")
        let release = run.gate()
        run.start { value in
            if value == "one" {
                first.fulfill()
                await release.wait()
            }
        }
        try run.write("{\"value\":\"one\"}\n{\"value\":\"two\"}\n")
        try run.finishWriting()
        guard await wait(for: first) else { return }
        let whileSuspended = await run.values.snapshot()
        XCTAssertEqual(whileSuspended, ["one"])
        await release.open()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one", "two"])
    }

    func testCompletedReadReleasesItsCallbackCapture() async throws {
        let run = makeRun()
        let released = expectation(description: "callback capture released")
        var owner: CallbackOwner? = CallbackOwner(released: released)
        run.start { [owner] _ in
            XCTAssertNotNil(owner)
        }
        owner = nil
        try run.write("{\"value\":\"one\"}\n")
        try run.finishWriting()

        guard await wait(for: run.completed) else { return }
        await run.reader?.value
        await wait(for: released)
    }

    func testPrecancelledReadReturnsWithoutRequiringBytesOrEOF() async throws {
        let run = makeRun()
        let enter = run.gate()
        run.start(beforeReading: enter)
        run.reader?.cancel()
        await enter.open()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, [])
    }

    func testCancellationDuringCallbackReturnsWithoutRequiringAnotherByteOrEOF() async throws {
        let run = makeRun()
        let first = expectation(description: "callback entered")
        let release = run.gate()
        run.start { _ in
            first.fulfill()
            await release.wait()
        }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        run.reader?.cancel()
        await release.open()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
    }

    func testConsumerCancelThenCloseDrainsAnActiveRead() async throws {
        let run = makeRun()
        let first = expectation(description: "reader delivered a value")
        run.start { _ in first.fulfill() }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        run.reader?.cancel()
        run.closeFromConsumer()

        await wait(for: run.closeCompleted)
        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
    }

    func testCancellationAfterDeliveredValueReturnsWithoutProducerEOF() async throws {
        let run = makeRun()
        let first = expectation(description: "reader delivered a value")
        run.start { _ in first.fulfill() }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        run.reader?.cancel()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
    }

    func testCancellationClosesBothEndpointsWhileCallbackIsSuspended() async throws {
        let run = makeRun()
        let first = expectation(description: "callback entered")
        let release = run.gate()
        run.start { _ in
            first.fulfill()
            await release.wait()
        }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        run.reader?.cancel()
        await run.waitForDisposal()
        XCTAssertThrowsError(try run.handler.fileHandle.read(upToCount: 0))
        XCTAssertThrowsError(try run.handler.outputPipe.fileHandleForWriting.write(contentsOf: Data()))
        await release.open()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
    }

    func testCancellationReturnsWhileAnOwnedProducerRetainsItsWriter() async throws {
        let run = makeRun()
        // A Process using standardOutput retains its own writer; no child process is needed here.
        let producer = try run.duplicateProducerWriter()
        let producerIdentity = try DescriptorIdentity(producer)
        let first = expectation(description: "producer value delivered")
        run.start { _ in first.fulfill() }
        try producer.write(contentsOf: Data("{\"value\":\"one\"}\n".utf8))
        guard await wait(for: first) else { return }
        run.reader?.cancel()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
        await run.waitForDisposal()
        XCTAssertNoThrow(try producer.write(contentsOf: Data()))
        XCTAssertEqual(try DescriptorIdentity(producer), producerIdentity, "Producer retains its own descriptor")
    }

    func testCloseWithoutCancellationEndsAnActiveRead() async throws {
        let run = makeRun()
        let first = expectation(description: "reader delivered a value")
        run.start { _ in first.fulfill() }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        run.closeFromConsumer()

        await wait(for: run.closeCompleted)
        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
        XCTAssertEqual(run.reader?.isCancelled, false)
    }

    func testMalformedThresholdAndCloseDoNotAffectAnotherHandler() async throws {
        let stopped = makeRun()
        let live = makeRun()
        stopped.start()
        try stopped.write("invalid\ninvalid\ninvalid\n")
        await wait(for: stopped.completed)
        stopped.handler.close()
        live.start()
        try live.write("invalid\ninvalid\n{\"value\":\"independent\"}\n")
        try live.finishWriting()

        await wait(for: live.completed)
        let stoppedValues = await stopped.values.snapshot()
        let liveValues = await live.values.snapshot()
        XCTAssertEqual(stoppedValues, [])
        XCTAssertEqual(liveValues, ["independent"])
    }

    func testCancelAndCloseDuringCallbackDoesNotPublishBufferedValues() async throws {
        let run = makeRun()
        let first = expectation(description: "callback entered")
        let release = run.gate()
        run.start { value in
            if value == "one" {
                first.fulfill()
                await release.wait()
            }
        }
        try run.write("{\"value\":\"one\"}\n{\"value\":\"two\"}\n")
        guard await wait(for: first) else { return }
        run.reader?.cancel()
        run.closeFromConsumer()
        await wait(for: run.closeCompleted)
        await release.open()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
    }

    func testRepeatedCloseBeforeReadingReturnsAndDoesNotCloseAnotherPipe() async throws {
        let run = makeRun()
        run.handler.close()
        await run.waitForDisposal()
        let other = Pipe()
        let readIdentity = try DescriptorIdentity(other.fileHandleForReading)
        let writeIdentity = try DescriptorIdentity(other.fileHandleForWriting)
        defer {
            other.fileHandleForReading.closeFile()
            other.fileHandleForWriting.closeFile()
        }
        run.handler.close()
        run.start()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, [])
        XCTAssertNoThrow(try other.fileHandleForReading.read(upToCount: 0))
        XCTAssertNoThrow(try other.fileHandleForWriting.write(contentsOf: Data()))
        XCTAssertEqual(try DescriptorIdentity(other.fileHandleForReading), readIdentity)
        XCTAssertEqual(try DescriptorIdentity(other.fileHandleForWriting), writeIdentity)
    }

    func testCloseOnlyDuringSuspendedCallbackDropsBufferedAndFutureValues() async throws {
        let run = makeRun()
        let first = expectation(description: "callback suspended before close")
        let release = run.gate()
        run.start { value in
            if value == "one" {
                first.fulfill()
                await release.wait()
            }
        }
        try run.write("{\"value\":\"one\"}\n{\"value\":\"buffered\"}\n")
        guard await wait(for: first) else { return }
        try run.write("{\"value\":\"future\"}\n")
        run.handler.close()
        XCTAssertEqual(run.reader?.isCancelled, false)
        await release.open()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"], "Close alone must stop already-admitted parsing")
    }

    func testAdmittedReaderCannotConsumeAReusedDescriptorAfterCloseDuringCallback() async throws {
        let run = try makeDescriptorReuseRun()
        let other = run.replacementPipe()
        let first = expectation(description: "callback suspended with admitted iterator")
        let release = run.gate()
        run.start { value in
            if value == "one" {
                first.fulfill()
                await release.wait()
            }
        }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        run.handler.close()
        await run.waitForDisposal()
        let reused = try run.reuseReadDescriptor(from: other)
        let foreign = Data("{\"value\":\"foreign\"}\n".utf8)
        try other.fileHandleForWriting.write(contentsOf: foreign)
        try other.fileHandleForWriting.close()
        await release.open()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
        XCTAssertEqual(try reused.readToEnd(), foreign, "The old reader must not consume the other pipe")
        XCTAssertEqual(run.reader?.isCancelled, false)
    }

    func testConcurrentCancellationAndRepeatedCloseDisposeEachEndpointExactlyOnce() async throws {
        let probe = CloseProbe()
        let run = makeRun(handler: JSONLinesPipeHandler(pipe: probe.pipe, closeEndpoint: { try probe.close($0) }))
        let producer = try run.duplicateProducerWriter()
        let producerIdentity = try DescriptorIdentity(producer)
        let first = expectation(description: "callback suspended for concurrent close")
        let release = run.gate()
        run.start { _ in
            first.fulfill()
            await release.wait()
        }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        run.cancelAndCloseConcurrently()
        await wait(for: run.closeCompleted)
        await run.waitForDisposal()
        XCTAssertEqual(probe.readCloses, 1)
        XCTAssertEqual(probe.writeCloses, 1)
        XCTAssertNoThrow(try producer.write(contentsOf: Data()))
        XCTAssertEqual(try DescriptorIdentity(producer), producerIdentity)
        await release.open()
        await wait(for: run.completed)
        run.handler.close()
        XCTAssertEqual(probe.readCloses, 1)
        XCTAssertEqual(probe.writeCloses, 1)
    }

    func testPhysicalDisposalAttemptsWriterEvenWhenReadHandleCloseThrows() async throws {
        let probe = CloseProbe(failingReadClose: true)
        let run = makeRun(handler: JSONLinesPipeHandler(pipe: probe.pipe, closeEndpoint: { try probe.close($0) }))
        run.handler.close()
        await run.waitForDisposal()
        XCTAssertEqual(probe.readCloses, 1)
        XCTAssertEqual(probe.writeCloses, 1)
        XCTAssertThrowsError(try probe.pipe.fileHandleForReading.read(upToCount: 0))
        XCTAssertThrowsError(try probe.pipe.fileHandleForWriting.write(contentsOf: Data()))
    }

    func testFixtureCleanupStillReleasesCallbackAndDrainsTasksAfterFirstCloseError() async throws {
        let probe = CloseProbe()
        let run = makeRun(handler: JSONLinesPipeHandler(pipe: probe.pipe, closeEndpoint: { try probe.close($0) }))
        run.failFirstWriterClose = true
        let first = expectation(description: "callback suspended until failing cleanup")
        let release = run.gate()
        run.start { _ in
            first.fulfill()
            await release.wait()
        }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        do {
            try await run.cleanup()
            XCTFail("Injected first close error must be reported, not swallowed")
        } catch {
            XCTAssertEqual((error as NSError).domain, NSPOSIXErrorDomain)
            XCTAssertEqual((error as NSError).code, Int(EIO))
        }
        XCTAssertTrue(run.cleanupFinished, "Cleanup must join every owned task before rethrowing")
        // Also rescues the deliberate missing-gate-release negative control.
        await release.open()
        await wait(for: run.completed)
        XCTAssertEqual(probe.readCloses, 1)
        XCTAssertEqual(probe.writeCloses, 1, "Lifecycle owner still attempts close after the fixture error")
    }

    func testSecondReaderIsRejectedWithoutStealingOrCancellingFirstReader() async throws {
        let first = makeRun()
        let entered = expectation(description: "first reader suspended")
        let release = first.gate()
        first.start { value in
            if value == "one" {
                entered.fulfill()
                await release.wait()
            }
        }
        try first.write("{\"value\":\"one\"}\n{\"value\":\"two\"}\n")
        guard await wait(for: entered) else { return }
        let second = makeRun(handler: first.handler)
        second.start()
        await wait(for: second.completed)
        let rejected = await second.values.snapshot()
        XCTAssertEqual(rejected, [])
        await release.open()
        try first.finishWriting()
        await wait(for: first.completed)
        let values = await first.values.snapshot()
        XCTAssertEqual(values, ["one", "two"])
    }

    func testSuspendedCallbackLeavesFutureDataInPipeInsteadOfPrefetching() async throws {
        let run = makeRun()
        let first = expectation(description: "callback suspended for backpressure")
        let release = run.gate()
        run.start { value in
            if value == "one" {
                first.fulfill()
                await release.wait()
            }
        }
        try run.write("{\"value\":\"one\"}\n")
        guard await wait(for: first) else { return }
        let future = "{\"value\":\"two\"}\n{\"value\":\"three\"}\n"
        try run.write(future)
        var unread: Int32 = 0
        // Darwin sys/filio.h: FIONREAD = _IOR('f', 127, int), not imported by Swift.
        let unreadByteCountRequest: UInt = 0x4004667f
        XCTAssertEqual(ioctl(run.readDescriptor, unreadByteCountRequest, &unread), 0)
        XCTAssertEqual(Int(unread), future.utf8.count, "Awaited callbacks must apply kernel backpressure")
        XCTAssertEqual(try DescriptorIdentity(run.handler.fileHandle), run.readIdentity)
        await release.open()
        try run.finishWriting()
        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one", "two", "three"])
    }

    func testChunkBoundariesAndSustainedLineThroughputPreserveEveryValue() async throws {
        let run = makeRun()
        let longValue = String(repeating: "x", count: 48 * 1024)
        let expected = [longValue] + (0..<4096).map(String.init)
        let data = Data(expected.map { "{\"value\":\"\($0)\"}\r\n" }.joined().utf8)
        let clock = ContinuousClock()
        let started = clock.now
        run.start()
        try run.startProducer(data)
        try run.finishWriting()
        guard await wait(for: run.completed) else { return }
        try await run.waitForProducer()
        let elapsed = started.duration(to: clock.now)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, expected)
        XCTAssertLessThan(elapsed, .seconds(3), "4097 records, including a multi-chunk line, must sustain bounded throughput")
        let measurement = XCTAttachment(string: "4097 records; \(data.count) bytes; elapsed \(elapsed)")
        measurement.lifetime = .keepAlways
        add(measurement)
    }

    func testOneIdleHandlerDoesNotBlockAnotherHandlersProgress() async throws {
        let idle = makeRun()
        let active = makeRun()
        let entered = expectation(description: "idle handler has delivered its first value")
        idle.start { _ in entered.fulfill() }
        try idle.write("{\"value\":\"idle\"}\n")
        guard await wait(for: entered) else { return }
        active.start()
        try active.write("{\"value\":\"independent\"}\n")
        try active.finishWriting()
        await wait(for: active.completed)
        let values = await active.values.snapshot()
        XCTAssertEqual(values, ["independent"])
        idle.handler.close()
        await wait(for: idle.completed)
    }

    func testUnstartedHandlerDeinitDisposesOwnedHandles() async throws {
        let probe = CloseProbe()
        let disposed = expectation(description: "unstarted owner disposed")
        var handler: JSONLinesPipeHandler? = JSONLinesPipeHandler(pipe: probe.pipe) { handle in
            try probe.close(handle)
            if handle === probe.pipe.fileHandleForWriting { disposed.fulfill() }
        }
        weak var weakHandler = handler
        XCTAssertNotNil(weakHandler)
        handler = nil
        await wait(for: disposed)
        XCTAssertNil(weakHandler)
        XCTAssertEqual(probe.readCloses, 1)
        XCTAssertEqual(probe.writeCloses, 1)
        XCTAssertThrowsError(try probe.pipe.fileHandleForReading.read(upToCount: 0))
        XCTAssertThrowsError(try probe.pipe.fileHandleForWriting.write(contentsOf: Data()))
    }
}
