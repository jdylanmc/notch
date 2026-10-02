//
//  JSONLinesPipeHandlerTests.swift
//  notchPocketTests
//

import Darwin
import Foundation
import XCTest

@testable import notchPocket

@MainActor
final class JSONLinesPipeHandlerTests: XCTestCase {
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
        var reader: Task<Void, Never>?
        var closer: Task<Void, Never>?
        var gates: [Gate] = []
        private var producerWriters: [FileHandle] = []
        private var writerClosed = false

        init(handler: JSONLinesPipeHandler) {
            self.handler = handler
            readDescriptor = handler.fileHandle.fileDescriptor
            writeDescriptor = handler.outputPipe.fileHandleForWriting.fileDescriptor
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
            // All fixture writes are smaller than PIPE_BUF; no writer task can outlive a test.
            precondition(bytes.count < 512)
            try handler.outputPipe.fileHandleForWriting.write(contentsOf: bytes)
        }

        func finishWriting() throws {
            guard !writerClosed else { return }
            try handler.outputPipe.fileHandleForWriting.close()
            writerClosed = true
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

        func closeFromConsumer() {
            closer = Task.detached { [handler, closeCompleted, closeDrained] in
                handler.close()
                closeCompleted.fulfill()
                closeDrained.fulfill()
            }
        }

        func cleanup() async throws {
            reader?.cancel()
            // EOF is the rescue path even when cancellation fails to wake AsyncBytes.
            try finishWriting()
            for writer in producerWriters { try writer.close() }
            for gate in gates { await gate.open() }
            if let reader {
                let result = await XCTWaiter.fulfillment(of: [drained], timeout: 3)
                XCTAssertEqual(result, .completed, "Owned reader did not drain after cancellation and EOF")
                if result == .completed { await reader.value }
            }
            if let closer {
                let result = await XCTWaiter.fulfillment(of: [closeDrained], timeout: 3)
                XCTAssertEqual(result, .completed, "Owned close task did not drain after EOF")
                if result == .completed { await closer.value }
            }
            reader = nil
            closer = nil
            handler.close()
            handler.close()
            // EOF is already established. An accidentally open reader returns nil, not a hang.
            // Probe owned handles, not numeric descriptors another thread could reuse.
            XCTAssertThrowsError(try handler.fileHandle.read(upToCount: 1))
            XCTAssertThrowsError(try handler.outputPipe.fileHandleForWriting.write(contentsOf: Data()))
            for writer in producerWriters {
                XCTAssertThrowsError(try writer.write(contentsOf: Data()))
            }
        }
    }

    private func makeRun(handler: JSONLinesPipeHandler = JSONLinesPipeHandler()) -> Run {
        let run = Run(handler: handler)
        addTeardownBlock { try await run.cleanup() }
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
        XCTAssertNotEqual(fcntl(run.readDescriptor, F_GETFD), -1, "EOF does not implicitly close the reader")
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
        XCTAssertNotEqual(fcntl(run.writeDescriptor, F_GETFD), -1, "Threshold, not EOF, must end this read")
        XCTAssertNotEqual(fcntl(run.readDescriptor, F_GETFD), -1, "The caller still owns cleanup")
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
        let first = expectation(description: "producer value delivered")
        run.start { _ in first.fulfill() }
        try producer.write(contentsOf: Data("{\"value\":\"one\"}\n".utf8))
        guard await wait(for: first) else { return }
        run.reader?.cancel()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, ["one"])
        XCTAssertNotEqual(fcntl(producer.fileDescriptor, F_GETFD), -1, "Cancellation must not close the producer's descriptor")
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
        let other = Pipe()
        defer {
            other.fileHandleForReading.closeFile()
            other.fileHandleForWriting.closeFile()
        }
        run.handler.close()
        run.start()

        await wait(for: run.completed)
        let values = await run.values.snapshot()
        XCTAssertEqual(values, [])
        XCTAssertNotEqual(fcntl(other.fileHandleForReading.fileDescriptor, F_GETFD), -1)
        XCTAssertNotEqual(fcntl(other.fileHandleForWriting.fileDescriptor, F_GETFD), -1)
    }
}
