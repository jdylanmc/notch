//
//  MediaOutputSlotButton.swift
//  notchPocket
//
//  Shared media-output controls retained from CompactHomeView.
//

import SwiftUI

/// Output device list for the player's media-output button.
struct AudioOutputPicker: View {
    @ObservedObject var routeManager: AudioRouteManager
    let onSelect: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Output")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 12)
                .padding(.top, 10)
                .padding(.bottom, 6)

            if routeManager.devices.isEmpty {
                // Enumeration is async, so an empty list on first open is
                // normal rather than an error worth alarming anyone about.
                Text("Looking for devices…")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 10)
            } else {
                ForEach(routeManager.devices) { device in
                    Button {
                        routeManager.select(device)
                        onSelect()
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: device.iconName)
                                .frame(width: 18)
                            Text(device.name)
                                .font(.system(size: 12))
                                .lineLimit(1)
                            Spacer(minLength: 12)
                            if device.id == routeManager.activeDeviceID {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 10, weight: .bold))
                            }
                        }
                        .contentShape(Rectangle())
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                    }
                    .buttonStyle(.plain)
                }
                .padding(.bottom, 6)
            }
        }
        .frame(minWidth: 220)
    }
}

/// Audio-output slot for the standard layout's control row.
struct MediaOutputSlotButton: View {
    @ObservedObject private var routeManager = AudioRouteManager.shared
    @State private var showingPicker = false

    var body: some View {
        HoverButton(icon: routeSymbol, scale: .medium) {
            routeManager.refreshDevices()
            showingPicker.toggle()
        }
        .popover(isPresented: $showingPicker, arrowEdge: .bottom) {
            AudioOutputPicker(routeManager: routeManager) {
                showingPicker = false
            }
        }
    }

    private var routeSymbol: String {
        routeManager.activeDevice?.iconName ?? AudioOutputRouteResolver.shared.outputRouteSymbol()
    }
}
