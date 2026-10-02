//
//  MusicLaunchTransaction.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//

import Combine
import Foundation

@MainActor
final class MusicLaunchTransaction: ObservableObject {
    @Published private(set) var isLaunching = false
    @Published private(set) var failure: MusicAppLaunchOutcome?

    private let launcher: MusicAppLauncher
    private let timeout: Duration
    private var generation = UUID()
    private var requestTask: Task<Void, Never>?
    private var deadlineTask: Task<Void, Never>?

    init(launcher: MusicAppLauncher, timeout: Duration = .seconds(5)) {
        self.launcher = launcher
        self.timeout = timeout
    }

    deinit {
        requestTask?.cancel()
        deadlineTask?.cancel()
    }

    func start(context: MusicLaunchContext, currentContext: @escaping @MainActor () -> MusicLaunchContext) {
        guard !isLaunching else { return }
        cancel()
        let request = generation
        isLaunching = true
        requestTask = Task { @MainActor [weak self, launcher] in
            guard !Task.isCancelled,
                  self?.isCurrent(request, context: context, currentContext: currentContext) == true else { return }
            let outcome = await launcher.launch(bundleIdentifier: context.bundleIdentifier)
            guard !Task.isCancelled,
                  self?.isCurrent(request, context: context, currentContext: currentContext) == true else { return }
            self?.finish(outcome)
        }
        // No task group: an uncooperative workspace completion must not delay the UI deadline.
        deadlineTask = Task { @MainActor [weak self, timeout] in
            do {
                try await Task.sleep(for: timeout)
            } catch is CancellationError {
                return
            } catch {
                Log.music.error("Music launch deadline failed: \(error)")
            }
            guard !Task.isCancelled,
                  self?.isCurrent(request, context: context, currentContext: currentContext) == true else { return }
            Log.music.error("Music app open timed out; OS request may still complete")
            self?.finish(.timedOut)
        }
    }

    func cancel() {
        generation = UUID()
        requestTask?.cancel()
        deadlineTask?.cancel()
        requestTask = nil
        deadlineTask = nil
        isLaunching = false
        failure = nil
    }

    func dismissFailure() {
        failure = nil
    }

    private func isCurrent(
        _ request: UUID,
        context: MusicLaunchContext,
        currentContext: () -> MusicLaunchContext
    ) -> Bool {
        guard generation == request else { return false }
        guard context == currentContext() else {
            cancel()
            return false
        }
        return true
    }

    private func finish(_ outcome: MusicAppLaunchOutcome) {
        // Cancellation releases UI ownership, not the OS open. The shared launcher
        // retains its single-operation gate until that await actually returns.
        cancel()
        failure = MusicAppFeedback.message(for: outcome) == nil ? nil : outcome
    }
}
