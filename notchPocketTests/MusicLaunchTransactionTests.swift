//
//  MusicLaunchTransactionTests.swift
//  notchPocketTests
//

import Combine
import XCTest

@testable import notchPocket

@MainActor
private final class SuspendedMusicAppOpening: MusicAppOpening {
    private(set) var openCount = 0
    private(set) var lookupCount = 0
    var onOpen: (() -> Void)?
    var onLookup: (() -> Void)?
    private var continuation: CheckedContinuation<Bool, Never>?

    func applicationURL(forBundleIdentifier bundleIdentifier: String) -> URL? {
        lookupCount += 1
        onLookup?()
        return URL(fileURLWithPath: "/Applications/Test Player.app")
    }

    func openApplication(at url: URL) async -> Bool {
        openCount += 1
        return await withCheckedContinuation { continuation in
            self.continuation = continuation
            onOpen?()
        }
    }

    func complete(_ opened: Bool) {
        let pending = continuation
        continuation = nil
        pending?.resume(returning: opened)
    }
}

@MainActor
final class MusicLaunchTransactionTests: XCTestCase {
    private func context(
        playing: Bool = false,
        preferred: MediaControllerType = .nowPlaying,
        effective: MediaControllerType = .nowPlaying,
        observed: String = MediaAppBundleID.spotify,
        remembered: String? = nil
    ) -> MusicLaunchContext {
        MusicLaunchContext(
            isPlaying: playing, preferred: preferred, effective: effective,
            observedBundleIdentifier: observed, rememberedBundleIdentifier: remembered
        )
    }

    private func start(
        _ transaction: MusicLaunchTransaction,
        workspace: SuspendedMusicAppOpening,
        current: MusicLaunchContext
    ) async {
        let dispatched = expectation(description: "one workspace request dispatched")
        workspace.onOpen = { dispatched.fulfill() }
        transaction.start(context: current, currentContext: { current })
        await fulfillment(of: [dispatched], timeout: 1)
        workspace.onOpen = nil
    }

    private func drain(_ launcher: MusicAppLauncher) async {
        // Bounded even on a broken implementation; never await the suspended OS task.
        for _ in 0..<100 where launcher.isOpening {
            await Task.yield()
        }
        XCTAssertFalse(launcher.isOpening, "completed OS request must release the shared gate")
    }

    func testTimeoutReleasesUIWhileNoncooperativeOSRequestStaysSingle() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher, timeout: .milliseconds(50))
        let current = context()
        let expired = expectation(description: "UI deadline returns without OS completion")
        let subscription = transaction.$failure.sink { if $0 == .timedOut { expired.fulfill() } }
        await start(transaction, workspace: workspace, current: current)
        XCTAssertTrue(transaction.isLaunching)
        await fulfillment(of: [expired], timeout: 1)
        subscription.cancel()

        XCTAssertFalse(transaction.isLaunching)
        XCTAssertEqual(transaction.failure, .timedOut)
        XCTAssertTrue(launcher.isOpening)
        for _ in 0..<20 {
            let outcome = await launcher.launch(bundleIdentifier: MediaAppBundleID.appleMusic)
            XCTAssertEqual(outcome, .alreadyOpening)
        }
        XCTAssertEqual(workspace.openCount, 1)
        XCTAssertEqual(workspace.lookupCount, 1)
        workspace.complete(false)
        await drain(launcher)
        XCTAssertEqual(transaction.failure, .timedOut, "late failure must not replace timeout")
    }

    func testPlaybackResumeCancelsHoldAndSuppressesLateFailure() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher)
        var current = context()
        let dispatched = expectation(description: "dispatched before resume")
        workspace.onOpen = { dispatched.fulfill() }
        transaction.start(context: current, currentContext: { current })
        await fulfillment(of: [dispatched], timeout: 1)

        current = context(playing: true)
        transaction.cancel() // The view's context-change handler.
        XCTAssertFalse(transaction.isLaunching)
        XCTAssertNil(transaction.failure)
        workspace.complete(false)
        await drain(launcher)
        XCTAssertNil(transaction.failure)
    }

    func testSourceChangeIsCheckedAfterAwaitEvenBeforeViewNotification() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher)
        var current = context(playing: true)
        let dispatched = expectation(description: "dispatched before source change")
        workspace.onOpen = { dispatched.fulfill() }
        transaction.start(context: current, currentContext: { current })
        await fulfillment(of: [dispatched], timeout: 1)

        current = context(playing: true, observed: "org.videolan.vlc")
        workspace.complete(false)
        await drain(launcher)
        XCTAssertFalse(transaction.isLaunching)
        XCTAssertNil(transaction.failure)
    }

    func testCancelBeforeDispatchDoesNotEvenLookUpApplication() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher)
        let current = context()
        transaction.start(context: current, currentContext: { current })
        transaction.cancel()
        await Task.yield()
        XCTAssertEqual(workspace.lookupCount, 0)
        XCTAssertEqual(workspace.openCount, 0)
        XCTAssertFalse(transaction.isLaunching)
    }

    func testDisappearanceSuppressesTheDeadlineAndReleasesUIWithoutOSCompletion() async throws {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher, timeout: .milliseconds(20))
        await start(transaction, workspace: workspace, current: context())
        transaction.cancel()
        try await Task.sleep(for: .milliseconds(50))
        XCTAssertFalse(transaction.isLaunching)
        XCTAssertNil(transaction.failure)
        XCTAssertTrue(launcher.isOpening, "UI cancellation must not pretend the OS request ended")
        workspace.complete(false)
        await drain(launcher)
        XCTAssertNil(transaction.failure)
    }

    func testChangedContextBeforeDispatchCancelsWithoutOSWork() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher)
        let cancelled = expectation(description: "stale context releases hold")
        var current = context()
        transaction.start(context: current, currentContext: { current })
        let subscription = transaction.$isLaunching.dropFirst().sink { if !$0 { cancelled.fulfill() } }
        current = context(preferred: .appleMusic, effective: .appleMusic)
        await fulfillment(of: [cancelled], timeout: 1)
        subscription.cancel()
        XCTAssertEqual(workspace.lookupCount, 0)
        XCTAssertEqual(workspace.openCount, 0)
        XCTAssertNil(transaction.failure)
    }

    func testDisappearReappearCannotAccumulateRequestsOrOverwriteNewFeedback() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let original = MusicLaunchTransaction(launcher: launcher)
        let current = context()
        await start(original, workspace: workspace, current: current)
        original.cancel() // Disappearance releases UI, not the outstanding OS request.
        XCTAssertFalse(original.isLaunching)

        let replacement = MusicLaunchTransaction(launcher: launcher)
        let refused = expectation(description: "new view reports still-pending OS operation")
        let subscription = replacement.$failure.sink { if $0 == .alreadyOpening { refused.fulfill() } }
        replacement.start(context: current, currentContext: { current })
        await fulfillment(of: [refused], timeout: 1)
        subscription.cancel()
        XCTAssertFalse(replacement.isLaunching)
        XCTAssertEqual(workspace.openCount, 1)
        workspace.complete(true)
        await drain(launcher)
        XCTAssertNil(original.failure)
        XCTAssertEqual(replacement.failure, .alreadyOpening, "old success cannot clear newer feedback")

        await start(replacement, workspace: workspace, current: current)
        XCTAssertEqual(workspace.openCount, 2, "retry is allowed only after the old operation returns")
        workspace.complete(true)
        await drain(launcher)
        XCTAssertFalse(replacement.isLaunching)
        XCTAssertNil(replacement.failure)
    }

    func testRepeatedClicksAreCoalescedAndPlayingFailureIsPublished() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher)
        let current = context(playing: true)
        await start(transaction, workspace: workspace, current: current)
        for _ in 0..<20 { transaction.start(context: current, currentContext: { current }) }
        XCTAssertEqual(workspace.openCount, 1)
        workspace.complete(false)
        await drain(launcher)
        XCTAssertFalse(transaction.isLaunching)
        XCTAssertEqual(transaction.failure, .openFailed(bundleIdentifier: MediaAppBundleID.spotify))
        transaction.dismissFailure()
        XCTAssertNil(transaction.failure)
    }

    func testStateChangeClearsAlreadyVisibleFeedback() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher)
        await start(transaction, workspace: workspace, current: context())
        workspace.complete(false)
        await drain(launcher)
        XCTAssertNotNil(transaction.failure)
        transaction.cancel()
        XCTAssertNil(transaction.failure)
        XCTAssertFalse(transaction.isLaunching)
    }

    func testCancellationDuringLookupPreventsDispatch() async {
        let workspace = SuspendedMusicAppOpening()
        let launcher = MusicAppLauncher(workspace: workspace)
        let transaction = MusicLaunchTransaction(launcher: launcher)
        let lookedUp = expectation(description: "lookup cancels transaction before OS dispatch")
        workspace.onLookup = {
            transaction.cancel()
            lookedUp.fulfill()
        }
        let current = context()
        transaction.start(context: current, currentContext: { current })
        await fulfillment(of: [lookedUp], timeout: 1)
        XCTAssertEqual(workspace.openCount, 0)
        XCTAssertFalse(transaction.isLaunching)
        XCTAssertNil(transaction.failure)
    }
}
