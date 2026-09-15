//
//  NotchPocketHeader.swift
//  notchPocket
//
//  Created by Harsh Vardhan  Goswami  on 04/08/24.
//

import Defaults
import SwiftUI

enum NotchHeaderNavigationPresentation: Equatable {
    case tabs
    case dashboardShortcut
    case homeShortcut
}

enum NotchHeaderNavigationPolicy {
    static func presentation(
        alwaysShowTabs: Bool,
        shelfEnabled: Bool,
        shelfIsEmpty: Bool,
        currentView: NotchViews
    ) -> NotchHeaderNavigationPresentation {
        if alwaysShowTabs || shelfEnabled && !shelfIsEmpty {
            return .tabs
        }
        return currentView == .dashboard ? .homeShortcut : .dashboardShortcut
    }
}

struct NotchPocketHeader: View {
    @EnvironmentObject var vm: NotchPocketViewModel
    @ObservedObject var batteryModel = BatteryStatusViewModel.shared
    @ObservedObject var coordinator = NotchPocketViewCoordinator.shared
    @StateObject var shelfState = ShelfStateViewModel.shared
    @Default(.notchPocketShelf) private var shelfEnabled

    private var navigationPresentation: NotchHeaderNavigationPresentation {
        NotchHeaderNavigationPolicy.presentation(
            alwaysShowTabs: coordinator.alwaysShowTabs,
            shelfEnabled: shelfEnabled,
            shelfIsEmpty: shelfState.isEmpty,
            currentView: coordinator.currentView
        )
    }

    var body: some View {
        HStack(spacing: 0) {
            HStack {
                switch navigationPresentation {
                case .tabs:
                    TabSelectionView()
                case .dashboardShortcut:
                    navigationShortcut(
                        label: "Dashboard",
                        icon: "square.grid.2x2.fill",
                        destination: .dashboard
                    )
                case .homeShortcut:
                    navigationShortcut(
                        label: "Home",
                        icon: "house.fill",
                        destination: .home
                    )
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .opacity(vm.notchState == .closed ? 0 : 1)
            .blur(radius: vm.notchState == .closed ? 20 : 0)
            .zIndex(2)

            if vm.notchState == .open {
                Rectangle()
                    .fill(NSScreen.screen(withUUID: coordinator.selectedScreenUUID)?.safeAreaInsets.top ?? 0 > 0 ? .black : .clear)
                    .frame(width: vm.closedNotchSize.width)
                    .mask {
                        NotchShape()
                    }
            }

            HStack(spacing: 4) {
                if vm.notchState == .open {
                    if isOSDType(coordinator.sneakPeekState(for: vm.screenUUID).type) && coordinator.shouldShowSneakPeek(on: vm.screenUUID) && Defaults[.showOpenNotchOSD] {
                        OpenNotchOSD(
                             type: coordinator.binding(for: vm.screenUUID).type,
                             value: coordinator.binding(for: vm.screenUUID).value,
                             icon: coordinator.binding(for: vm.screenUUID).icon,
                             accent: coordinator.binding(for: vm.screenUUID).accent
                        )
                            .transition(.scale(scale: 0.8).combined(with: .opacity))
                    } else {
                        if Defaults[.showMirror] {
                            Button(action: {
                                vm.toggleCameraPreview()
                            }) {
                                Capsule()
                                    .fill(.black)
                                    .frame(width: 30, height: 30)
                                    .overlay {
                                        Image(systemName: "web.camera")
                                            .foregroundColor(.white)
                                            .padding()
                                            .imageScale(.medium)
                                    }
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                        if Defaults[.settingsIconInNotch] {
                            Button(action: {
                                DispatchQueue.main.async {
                                    SettingsWindowController.shared.showWindow()
                                }
                                
                            }) {
                                Capsule()
                                    .fill(.black)
                                    .frame(width: 30, height: 30)
                                    .overlay {
                                        Image(systemName: "gear")
                                            .foregroundColor(.white)
                                            .padding()
                                            .imageScale(.medium)
                                    }
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                        if Defaults[.showBatteryIndicator] {
                            NotchPocketBatteryView(
                                batteryWidth: 30,
                                isCharging: batteryModel.isCharging,
                                isInLowPowerMode: batteryModel.isInLowPowerMode,
                                isPluggedIn: batteryModel.isPluggedIn,
                                levelBattery: batteryModel.levelBattery,
                                maxCapacity: batteryModel.maxCapacity,
                                timeToFullCharge: batteryModel.timeToFullCharge,
                                timeToDischarge: batteryModel.timeToDischarge,
                                maxAdapterWatts: batteryModel.maxAdapterWatts,
                                isForNotification: false
                            )
                        }
                    }
                }
            }
            .font(.system(.headline, design: .rounded))
            .frame(maxWidth: .infinity, alignment: .trailing)
            .opacity(vm.notchState == .closed ? 0 : 1)
            .blur(radius: vm.notchState == .closed ? 20 : 0)
            .zIndex(2)
        }
        .foregroundColor(.gray)
        .environmentObject(vm)
    }

    private func navigationShortcut(
        label: LocalizedStringKey,
        icon: String,
        destination: NotchViews
    ) -> some View {
        TabButton(label: label, icon: icon, selected: false) {
            withAnimation(.smooth) {
                coordinator.currentView = destination
            }
        }
        .accessibilityIdentifier(destination.accessibilityIdentifier)
        .accessibilityValue(Text(verbatim: destination.accessibilityValue(
            isSelected: destination == coordinator.currentView
        )))
        .frame(height: 26)
        .foregroundStyle(.gray)
    }

    func isOSDType(_ type: SneakContentType) -> Bool {
        switch type {
        case .volume, .brightness, .backlight, .mic:
            return true
        default:
            return false
        }
    }
}

#Preview {
    NotchPocketHeader().environmentObject(NotchPocketViewModel())
}
