//
//  CompactMusicHoverTrackingView.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//

import AppKit
import SwiftUI

enum CompactMusicHoverPolicy {
    static func hoverState(
        bounds: CGRect,
        pointInView: CGPoint,
        isHidden: Bool,
        previous: Bool?
    ) -> Bool? {
        guard bounds.size.width > 0, bounds.size.height > 0 else { return nil }
        let hovering = !isHidden && bounds.contains(pointInView)
        if previous == nil && !hovering { return nil }
        return hovering == previous ? nil : hovering
    }
}

@MainActor
struct CompactMusicHoverTrackingView: NSViewRepresentable {
    let initialHovering: Bool
    let onHover: (Bool) -> Void

    func makeNSView(context: Context) -> HoverView {
        let view = HoverView()
        view.hovering = initialHovering
        view.onHover = onHover
        return view
    }

    func updateNSView(_ nsView: HoverView, context: Context) {
        nsView.onHover = onHover
        nsView.reconcileHoverAfterLayout()
    }

    static func dismantleNSView(_ nsView: HoverView, coordinator: ()) {
        nsView.stopTracking()
    }

    final class HoverView: NSView {
        var onHover: ((Bool) -> Void)?
        fileprivate var hovering: Bool?
        private var trackingArea: NSTrackingArea?
        private var reconcileTask: Task<Void, Never>?

        override func hitTest(_ point: NSPoint) -> NSView? { nil }

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            updateTrackingAreas()
        }

        override func updateTrackingAreas() {
            super.updateTrackingAreas()
            removeHoverTrackingArea()
            guard window != nil else { return }

            let area = NSTrackingArea(
                rect: bounds,
                options: [.mouseEnteredAndExited, .activeAlways, .enabledDuringMouseDrag],
                owner: self,
                userInfo: nil
            )
            addTrackingArea(area)
            trackingArea = area
            reconcileHoverAfterLayout()
        }

        func reconcileHoverAfterLayout() {
            reconcileTask?.cancel()
            // Reconcile a stationary pointer after layout, outside SwiftUI's update pass.
            reconcileTask = Task { @MainActor [weak self] in
                guard !Task.isCancelled, let self else { return }
                self.reconcileTask = nil
                self.updateHover()
            }
        }

        override func mouseEntered(with event: NSEvent) { updateHover() }
        override func mouseExited(with event: NSEvent) { updateHover() }

        func stopTracking() {
            reconcileTask?.cancel()
            reconcileTask = nil
            onHover = nil
            removeHoverTrackingArea()
        }

        private func removeHoverTrackingArea() {
            if let trackingArea {
                removeTrackingArea(trackingArea)
                self.trackingArea = nil
            }
        }

        private func updateHover() {
            guard let window, let onHover else { return }
            let point = convert(window.convertPoint(fromScreen: NSEvent.mouseLocation), from: nil)
            guard let inside = CompactMusicHoverPolicy.hoverState(
                bounds: bounds,
                pointInView: point,
                isHidden: isHiddenOrHasHiddenAncestor,
                previous: hovering
            ) else { return }
            hovering = inside
            onHover(inside)
        }
    }
}
