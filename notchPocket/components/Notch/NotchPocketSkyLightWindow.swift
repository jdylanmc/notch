//
//  NotchPocketSkyLightWindow.swift
//  notchPocket
//
//  Created by Alexander on 2025-10-20.
//

import Cocoa
import SkyLightWindow
import Defaults
import Combine
import SwiftUI

extension SkyLightOperator {
    func undelegateWindow(_ window: NSWindow) {
        typealias F_SLSRemoveWindowsFromSpaces = @convention(c) (Int32, CFArray, CFArray) -> Int32
        
        let handler = dlopen("/System/Library/PrivateFrameworks/SkyLight.framework/Versions/A/SkyLight", RTLD_NOW)
        guard let SLSRemoveWindowsFromSpaces = unsafeBitCast(
            dlsym(handler, "SLSRemoveWindowsFromSpaces"),
            to: F_SLSRemoveWindowsFromSpaces?.self
        ) else {
            return
        }
        
        // Remove the window from the SkyLight space
        _ = SLSRemoveWindowsFromSpaces(
            connection,
            [window.windowNumber] as CFArray,
            [space] as CFArray
        )
    }
}

@MainActor
protocol NotchObservationSource: AnyObject {
    var notchState: NotchState { get }
    func open() -> Bool
    func close()
}

extension NotchPocketViewModel: NotchObservationSource {}

class NotchPocketSkyLightWindow: NSPanel {
    static let openNotchAction = NSAccessibility.Action(rawValue: "com.jdylanmc.notchpocket.notch.v1.open")
    static let closeNotchAction = NSAccessibility.Action(rawValue: "com.jdylanmc.notchpocket.notch.v1.close")
    private var isSkyLightEnabled: Bool = false
    weak var observationSource: (any NotchObservationSource)?

    // The identifier is machine-only; VoiceOver retains the native window role/title.
    // Read directly from the existing model, rather than caching a second state.
    override func accessibilityIdentifier() -> String {
        guard observationSource != nil, windowNumber > 0 else { return "" }
        return "com.jdylanmc.notchpocket.notch.v1.window.\(windowNumber)"
    }

    override func accessibilityValue() -> Any? {
        guard let source = observationSource else { return nil }
        switch source.notchState {
        case .open: return "open"
        case .closed: return "closed"
        }
    }

    override func setAccessibilityIdentifier(_ accessibilityIdentifier: String?) {}

    override func setAccessibilityValue(_ accessibilityValue: Any?) {}

    // Explicit AX action names keep discovery locale-independent. The legacy transport
    // has no result payload: clients must observe AXValue, not equate dispatch with success.
    override func accessibilityActionNames() -> [NSAccessibility.Action] {
        let native = super.accessibilityActionNames()
        guard observationSource != nil, windowNumber > 0 else { return native }
        return native + [Self.openNotchAction, Self.closeNotchAction]
    }

    override func accessibilityActionDescription(_ action: NSAccessibility.Action) -> String? {
        switch action {
        case Self.openNotchAction:
            return String(localized: "Open Notch")
        case Self.closeNotchAction:
            return String(localized: "Close Notch", comment: "Accessibility action to collapse the notch, not close its window.")
        default:
            return super.accessibilityActionDescription(action)
        }
    }

    override func accessibilityPerformAction(_ action: NSAccessibility.Action) {
        switch action {
        case Self.openNotchAction:
            guard let source = observationSource, windowNumber > 0, source.notchState != .open else { return }
            withAnimation(StandardAnimations.interactive) {
                _ = source.open()
            }
        case Self.closeNotchAction:
            guard let source = observationSource, windowNumber > 0, source.notchState != .closed else { return }
            // Match ordinary closing: ContentView owns the state-driven close animation.
            source.close()
        default:
            super.accessibilityPerformAction(action)
        }
    }

    override func isAccessibilitySelectorAllowed(_ selector: Selector) -> Bool {
        if selector == #selector(setAccessibilityValue(_:)) ||
            selector == #selector(setAccessibilityIdentifier(_:)) {
            return false
        }
        return super.isAccessibilitySelectorAllowed(selector)
    }

    // NSPanel's AX transport can advertise AXValue as writable despite selector denial.
    // Keep this compatibility hook narrow; other native attributes retain AppKit policy.
    override func accessibilityIsAttributeSettable(_ attribute: NSAccessibility.Attribute) -> Bool {
        if attribute == .value || attribute == .identifier {
            return false
        }
        return super.accessibilityIsAttributeSettable(attribute)
    }

    override func close() {
        observationSource = nil
        super.close()
    }
    
    override init(
        contentRect: NSRect,
        styleMask: NSWindow.StyleMask,
        backing: NSWindow.BackingStoreType,
        defer flag: Bool
    ) {
        super.init(
            contentRect: contentRect,
            styleMask: styleMask,
            backing: backing,
            defer: flag
        )
        
        configureWindow()
        setupObservers()
    }
    
    private func configureWindow() {
        isFloatingPanel = true
        isOpaque = false
        titleVisibility = .hidden
        titlebarAppearsTransparent = true
        backgroundColor = .clear
        isMovable = false
        level = .mainMenu + 3
        hasShadow = false
        isReleasedWhenClosed = false
        
        // Force dark appearance regardless of system setting
        appearance = NSAppearance(named: .darkAqua)
        
        updateCollectionBehavior()
        
        // Apply initial sharing type setting
        updateSharingType()
    }
    
    private func setupObservers() {
        // Listen for changes to the hideFromScreenRecording setting
        Defaults.publisher(.hideFromScreenRecording)
            .sink { [weak self] _ in
                self?.updateSharingType()
            }
            .store(in: &observers)
            
        Defaults.publisher(.hideNonNotchedFromMissionControl)
            .sink { [weak self] _ in
                self?.updateCollectionBehavior()
            }
            .store(in: &observers)
            
        NotificationCenter.default.publisher(for: NSWindow.didChangeScreenNotification, object: self)
            .sink { [weak self] _ in
                self?.updateCollectionBehavior()
            }
            .store(in: &observers)
        
        NotificationCenter.default.publisher(for: NSWindow.willCloseNotification, object: self)
            .sink { [weak self] _ in
                self?.cleanupObservers()
            }
            .store(in: &observers)
    }
    
    private func updateCollectionBehavior() {
        var newBehavior: NSWindow.CollectionBehavior = [
            .fullScreenAuxiliary,
            .stationary,
            .canJoinAllSpaces,
            .ignoresCycle,
        ]
        
        let hasNotch = (self.screen?.safeAreaInsets.top ?? 0) > 0
        
        if Defaults[.hideNonNotchedFromMissionControl] && !hasNotch {
            newBehavior.insert(.transient)
        }
        
        collectionBehavior = newBehavior
    }
    
    private func updateSharingType() {
        if Defaults[.hideFromScreenRecording] {
            sharingType = .none
        } else {
            sharingType = .readWrite
        }
    }
    
    func enableSkyLight() {
        if !isSkyLightEnabled {
            SkyLightOperator.shared.delegateWindow(self)
            isSkyLightEnabled = true
        }
    }
    
    func disableSkyLight() {
        if isSkyLightEnabled {
            SkyLightOperator.shared.undelegateWindow(self)
            isSkyLightEnabled = false
        }
    }
    
    private var observers: Set<AnyCancellable> = []
    
    private func cleanupObservers() {
        Task { @MainActor in
            self.observers.forEach { $0.cancel() }
            self.observers.removeAll()
        }
    }
    
    /// False by default so a click on the notch never activates the app or
    /// steals focus from whatever is frontmost — load-bearing for every
    /// normal interaction (hover-to-open, music controls, OSD). A text field
    /// needs this flipped on for the moment it's actually being typed into,
    /// and back off the instant it isn't — never left permanently true.
    ///
    /// This is the window class actually instantiated for the notch
    /// (createNotchPocketWindow uses NotchPocketSkyLightWindow, not the
    /// separate, unused NotchPocketWindow class) — an earlier fix targeted
    /// that unused class and silently did nothing.
    var wantsKeyForTextInput = false {
        didSet {
            guard wantsKeyForTextInput != oldValue else { return }
            if wantsKeyForTextInput {
                makeKey()
            }
        }
    }

    override var canBecomeKey: Bool { wantsKeyForTextInput }
    override var canBecomeMain: Bool { false }
}
