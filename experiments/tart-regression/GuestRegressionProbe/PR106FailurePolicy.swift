import Foundation

// Shared with permission-free contracts; process lookup and UI input stay in the native probe.
enum PR106FailurePolicy {
    struct ProcessIdentity: Equatable {
        let pid: Int32
        let bundleURL: URL
        let bundleID: String
    }

    enum ActionResult: Equatable { case performed, identityChanged, actionRejected }

    static func perform(
        expected: ProcessIdentity, current: ProcessIdentity?, action: () -> Bool
    ) -> ActionResult {
        guard expected.pid > 0, current == expected else { return .identityChanged }
        return action() ? .performed : .actionRejected
    }

    struct Outcome {
        private(set) var verdict = "BLOCKED"
        private(set) var reason = "preconditions_not_established"

        mutating func observe(_ matched: Bool) {
            if !matched { verdict = "FAIL"; reason = "rendered_output_mismatch" }
        }

        mutating func transition(qualified: Bool, matched: Bool) {
            if qualified { observe(matched) }
        }

        mutating func refuse(_ cause: String) {
            if verdict != "FAIL" { reason = cause }
        }

        mutating func complete(passed: Bool) {
            observe(passed)
            if verdict != "FAIL" { verdict = "PASS"; reason = "rendered_output_verified" }
        }

        func result(
            nativeFailures: Int, touched: Bool, restored: Bool, hasErrors: Bool,
            captureBefore: Bool?, captureAfter: Bool?
        ) -> (verdict: String, reason: String) {
            if touched && !restored { return ("BLOCKED", "restoration_unverified") }
            if nativeFailures > 0 { return ("BLOCKED", "native_interaction_aborted") }
            if hasErrors && verdict != "BLOCKED" { return ("BLOCKED", "incomplete_native_journey") }
            if verdict != "BLOCKED" && (captureBefore != true || captureAfter != true) {
                return ("BLOCKED", "screen_capture_permission_unverified")
            }
            return (verdict, reason)
        }
    }
}
