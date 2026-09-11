import AppKit
import ControlCore

private struct Response: Encodable {
    let ok: Bool
    var command: String?
    var app: AppIdentity?
    var permissions: Permissions?
    var windows: [WindowInfo]?
    var settings: SettingsState?
    var output: String?
    var error: ControlFailure?
    var settingsDiagnostic: ControlFailure?
    var notch: NotchInspection?
    var notchDiagnostic: ControlFailure?
    var usage: [String]?
}

@main
struct NotchControl {
    @MainActor
    static func main() async {
        do {
            let options = try Options.parse(Array(CommandLine.arguments.dropFirst()))
            if options.command == .help {
                emit(Response(ok: true, command: "help", usage: [
                    "inspect [--app-path /absolute/notch-pocket.app] [--timeout 5]",
                    "settings open|general|about [--app-path /absolute/notch-pocket.app] [--timeout 5]",
                    "capture --window ID --output /absolute/new.png [--app-path /absolute/notch-pocket.app] [--timeout 5]"
                ]))
                return
            }
            let target = try AppTarget(options: options)
            var response = Response(ok: true, command: options.command.rawValue, app: target.identity)
            switch options.command {
            case .inspect:
                response = try inspect(target: target)
            case .settings:
                guard let pane = options.pane else {
                    throw ControlFailure(.invalidInput, "Missing Settings destination.")
                }
                response.settings = try SettingsControl(target: target).navigate(pane)
                response.windows = try target.windows()
                response.permissions = Permissions.current()
            case .capture:
                guard let id = options.windowID, let path = options.output else {
                    throw ControlFailure(.invalidInput, "Missing capture selector or output.")
                }
                try await capture(target: target, id: id, output: path)
                response.output = path
                response.permissions = Permissions.current()
            case .help:
                break
            }
            emit(response)
        } catch let error as ControlFailure {
            emit(Response(ok: false, error: error))
            exit(error.code.exitStatus)
        } catch {
            emit(Response(ok: false, error: ControlFailure(.internalError, "Unexpected control tool failure.")))
            exit(FailureCode.internalError.exitStatus)
        }
    }

    @MainActor
    private static func inspect(target: AppTarget) throws -> Response {
        let permissions = Permissions.current()
        var response = Response(ok: true, command: "inspect", app: target.identity, permissions: permissions)
        response.windows = try target.windows()
        guard permissions.accessibility else {
            response.settings = SettingsState(status: "accessibility_unavailable", selectedPane: nil)
            response.notch = .accessibilityUnavailable
            return response
        }
        do {
            response.settings = try SettingsControl(target: target).state()
        } catch let error as ControlFailure where [
            FailureCode.unsupportedControl, .accessibilityFailed, .unsupportedWindow
        ].contains(error.code) {
            response.settings = SettingsState(status: "unsupported", selectedPane: nil)
            response.settingsDiagnostic = error
        }
        do {
            let observation = try NotchObservationControl(target: target).state()
            response.notch = observation.notch
            response.windows = observation.windows
        } catch let error as ControlFailure where [
            FailureCode.unsupportedControl, .accessibilityFailed, .unsupportedWindow
        ].contains(error.code) {
            response.notch = .unsupported
            response.notchDiagnostic = error
        }
        return response
    }

    private static func emit(_ response: Response) {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        do {
            let data = try encoder.encode(response)
            FileHandle.standardOutput.write(data)
            FileHandle.standardOutput.write(Data([10]))
        } catch {
            FileHandle.standardOutput.write(Data(
                "{\"ok\":false,\"error\":{\"code\":\"internal_error\",\"message\":\"JSON encoding failed.\"}}\n".utf8
            ))
            exit(FailureCode.internalError.exitStatus)
        }
    }
}
