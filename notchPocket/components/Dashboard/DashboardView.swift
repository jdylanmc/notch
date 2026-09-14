//
//  DashboardView.swift
//  notchPocket
//

import SwiftUI

@MainActor
enum DashboardRuntime {
    private static var storedController: DashboardController?

    static var controller: DashboardController {
        if let storedController {
            return storedController
        }
        let controller = DashboardController(store: .live())
        storedController = controller
        return controller
    }

    static func ownerDidTearDown(ownerID: UUID) {
        storedController?.handleOwnerLifecycleEvent(.ownerDidTearDown, ownerID: ownerID)
    }
}

@MainActor
struct DashboardView: View {
    let ownerID: UUID
    let dropInteraction: DropInteractionState

    @ObservedObject private var controller: DashboardController
    @State private var editError: DashboardEditError?

    private let metrics = DashboardLayoutMetrics(
        minimumCellWidth: 220,
        rowHeight: 96,
        spacing: 10
    )
    private let constraints: [DashboardWidgetKind: DashboardWidgetConstraints] = [
        .shelfSummary: .init(
            minimum: .init(columns: 1, rows: 1),
            maximum: .init(columns: 2, rows: 2)
        )
    ]

    init(
        ownerID: UUID,
        dropInteraction: DropInteractionState
    ) {
        self.init(
            ownerID: ownerID,
            dropInteraction: dropInteraction,
            controller: DashboardRuntime.controller
        )
    }

    init(
        ownerID: UUID,
        dropInteraction: DropInteractionState,
        controller: DashboardController
    ) {
        self.ownerID = ownerID
        self.dropInteraction = dropInteraction
        _controller = ObservedObject(wrappedValue: controller)
    }

    private var isEditOwner: Bool {
        controller.editSession?.ownerID == ownerID
    }

    private var isEditingElsewhere: Bool {
        guard let editSession = controller.editSession else { return false }
        return editSession.ownerID != ownerID
    }

    private var isRecoveryRequired: Bool {
        if case .recoveryRequired = controller.loadResult {
            return true
        }
        return false
    }

    private var editControlsPolicy: DashboardEditControlsPolicy {
        DashboardEditControlsPolicy(
            isEditOwner: isEditOwner,
            isRecoveryRequired: isRecoveryRequired
        )
    }

    var body: some View {
        VStack(spacing: 8) {
            header

            if let editError {
                editErrorView(editError)
            }

            content
        }
        .onDisappear {
            controller.handleOwnerLifecycleEvent(.contentDidDisappear, ownerID: ownerID)
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Text("Dashboard")
                .font(.headline)

            if isEditingElsewhere {
                Text("Editing on another display")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer(minLength: 8)

            if isEditOwner {
                Button("Add Shelf Summary", systemImage: "plus") {
                    addShelfSummary()
                }
                .labelStyle(.iconOnly)
                .help("Add Shelf Summary")
                .disabled(!editControlsPolicy.canAdd)

                Button("Cancel", role: .cancel) {
                    handle(controller.cancel(ownerID: ownerID))
                }
                .disabled(!editControlsPolicy.canCancel)

                Button("Done") {
                    handle(controller.done(ownerID: ownerID))
                }
                .buttonStyle(.borderedProminent)
                .disabled(!editControlsPolicy.canFinish)
            } else {
                Button("Edit Dashboard") {
                    handle(controller.beginEditing(ownerID: ownerID))
                }
                .disabled(isEditingElsewhere || controller.committedConfiguration == nil)
            }
        }
        .controlSize(.small)
        .frame(maxWidth: .infinity)
    }

    @ViewBuilder
    private var content: some View {
        switch controller.loadResult {
        case .recoveryRequired:
            DashboardUnavailableView(
                title: "Dashboard configuration needs attention",
                message: "Editing is disabled to preserve the original configuration data."
            )
        case .storageFailure:
            DashboardUnavailableView(
                title: "Dashboard configuration is unavailable",
                message: "The saved Dashboard configuration could not be read."
            )
        case .missing, .loaded:
            if let configuration = controller.configuration(for: ownerID) {
                dashboard(configuration)
            } else {
                DashboardUnavailableView(
                    title: "Dashboard configuration is unavailable",
                    message: "Close and reopen the panel after the configuration issue is resolved."
                )
            }
        }
    }

    private func dashboard(_ configuration: DashboardConfiguration) -> some View {
        GeometryReader { proxy in
            let width = max(1, proxy.size.width)

            switch resolvedLayout(for: configuration, width: width) {
            case .success(let layout):
                ScrollView(.vertical) {
                    ZStack(alignment: .topLeading) {
                        ForEach(layout.items) { resolved in
                            if let instance = configuration.instances.first(where: {
                                $0.id == resolved.id
                            }) {
                                DashboardWidgetCard(
                                    instance: instance,
                                    resolved: resolved,
                                    columnCount: layout.columnCount,
                                    metrics: metrics,
                                    constraints: constraints[instance.kind],
                                    ownerID: ownerID,
                                    isEditing: isEditOwner,
                                    controller: controller,
                                    dropInteraction: dropInteraction,
                                    editError: $editError
                                )
                                .frame(
                                    width: resolved.frame.width,
                                    height: resolved.frame.height,
                                    alignment: .topLeading
                                )
                                .coordinateSpace(.named(instance.id))
                                .position(
                                    x: resolved.frame.midX,
                                    y: resolved.frame.midY
                                )
                            }
                        }
                    }
                    .frame(
                        width: width,
                        height: max(layout.contentHeight, proxy.size.height)
                            + (isEditOwner ? metrics.rowHeight + metrics.spacing : 0),
                        alignment: .topLeading
                    )
                }
                .scrollIndicators(.visible)
            case .failure(let error):
                DashboardUnavailableView(
                    title: "Dashboard layout is unavailable",
                    message: "The current widget layout cannot be rendered safely.",
                    diagnostic: error.diagnosticDescription
                )
            }
        }
    }

    private func resolvedLayout(
        for configuration: DashboardConfiguration,
        width: CGFloat
    ) -> Result<DashboardResolvedLayout, DashboardLayoutPresentationError> {
        DashboardWidgetInteraction.resolveLayout {
            try DashboardLayoutEngine.resolve(
                instances: configuration.instances,
                availableWidth: width,
                metrics: metrics,
                constraints: constraints
            )
        }
    }

    private func addShelfSummary() {
        guard let configuration = controller.configuration(for: ownerID) else {
            editError = .configurationUnavailable
            return
        }
        let nextRow: Int
        do {
            nextRow = try DashboardWidgetInteraction.nextInsertionRow(
                for: configuration.instances
            )
        } catch {
            editError = .invalidConfiguration
            return
        }
        let instance = DashboardWidgetInstance.shelfSummary(
            position: .init(column: 0, row: nextRow),
            footprint: .init(columns: 1, rows: 1)
        )
        handle(controller.add(instance, ownerID: ownerID))
    }

    private func handle(_ result: DashboardEditResult) {
        switch result {
        case .success:
            editError = nil
        case .failure(let error):
            editError = error
            if case .persistenceFailure(let message) = error {
                Log.general.error("Dashboard persistence failed: \(message)")
            }
        }
    }

    private func editErrorView(_ error: DashboardEditError) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
                .accessibilityHidden(true)

            switch error {
            case .editInProgress:
                Text("Dashboard editing is already active on another display.")
            case .notEditOwner:
                Text("Only the display that started editing can change this draft.")
            case .recoveryRequired:
                Text("Editing is disabled to preserve the original configuration data.")
            case .configurationUnavailable:
                Text("Dashboard configuration is unavailable.")
            case .instanceNotFound:
                Text("That widget is no longer available.")
            case .invalidConfiguration:
                Text("The requested widget change is not valid.")
            case .revisionConflict:
                Text("The Dashboard changed elsewhere. Your draft was preserved.")
            case .revisionExhausted:
                Text("The Dashboard revision cannot be advanced.")
            case .persistenceFailure:
                Text("The Dashboard could not be saved. Your draft was preserved.")
            }
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

private struct DashboardUnavailableView: View {
    let title: LocalizedStringKey
    let message: LocalizedStringKey
    let diagnostic: String?

    init(
        title: LocalizedStringKey,
        message: LocalizedStringKey,
        diagnostic: String? = nil
    ) {
        self.title = title
        self.message = message
        self.diagnostic = diagnostic
    }

    var body: some View {
        VStack(spacing: 5) {
            Image(systemName: "exclamationmark.triangle")
                .foregroundStyle(.orange)
                .accessibilityHidden(true)
            Text(title)
                .font(.headline)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            if let diagnostic {
                Text(verbatim: diagnostic)
                    .font(.caption2.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityElement(children: .combine)
    }
}
