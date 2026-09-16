//
//  CompactMusicHoverTrackingView.swift
//  notchPocket
//
//  SPDX-License-Identifier: GPL-3.0-only
//

import AppKit
import SwiftUI

@MainActor
struct CompactMusicHoverTrackingView: NSViewRepresentable {
    let onHover: (Bool) -> Void

    func makeNSView(context: Context) -> HoverView {
        let view = HoverView()
        view.onHover = onHover
        return view
    }

    func updateNSView(_ nsView: HoverView, context: Context) {
        nsView.onHover = onHover
    }

    static func dismantleNSView(_ nsView: HoverView, coordinator: ()) {
        nsView.stopTracking()
    }

    final class HoverView: NSView {
        var onHover: ((Bool) -> Void)?
        private var trackingArea: NSTrackingArea?
        private var hovering: Bool?

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

            // Reconcile a stationary pointer after layout, outside SwiftUI's update pass.
            DispatchQueue.main.async { [weak self] in
                self?.updateHover()
            }
        }

        override func mouseEntered(with event: NSEvent) { updateHover() }
        override func mouseExited(with event: NSEvent) { updateHover() }

        func stopTracking() {
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
            let inside = bounds.contains(point) && !isHiddenOrHasHiddenAncestor
            guard hovering != inside else { return }
            hovering = inside
            onHover(inside)
        }
    }
}
