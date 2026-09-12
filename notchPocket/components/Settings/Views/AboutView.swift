//
//  AboutView.swift
//  notchPocket
//
//  Created by Richard Kunkli on 07/08/2024.
//

import SwiftUI

struct AboutView: View {
    @State private var showBuildNumber: Bool = false
    @Environment(\.openWindow) var openWindow
    var body: some View {
        VStack {
            Form {
                Section {
                    HStack {
                        Text("Release name")
                        Spacer()
                        Text(verbatim: "Notch Pocket")
                            .foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("Version")
                        Spacer()
                        if showBuildNumber {
                            Text("(\(Bundle.main.buildVersionNumber ?? ""))")
                                .foregroundStyle(.secondary)
                        }
                        Text(Bundle.main.releaseVersionNumber ?? "unkown")
                            .foregroundStyle(.secondary)
                    }
                    .onTapGesture {
                        withAnimation {
                            showBuildNumber.toggle()
                        }
                    }
                } header: {
                    Text("Version info")
                }

                HStack(spacing: 30) {
                    Spacer(minLength: 0)
                    Button {
                        if let url = URL(string: "https://github.com/jdylanmc/notch") {
                            NSWorkspace.shared.open(url)
                        }
                    } label: {
                        VStack(spacing: 5) {
                            Image("Github")
                                .resizable()
                                .aspectRatio(contentMode: .fit)
                                .frame(width: 18)
                            Text("GitHub")
                        }
                        .contentShape(Rectangle())
                    }
                    Spacer(minLength: 0)
                }
                .buttonStyle(PlainButtonStyle())
            }
            VStack(spacing: 0) {
                Divider()
                if let noticesURL = URL(string: "https://github.com/jdylanmc/notch/blob/pocket/THIRD_PARTY_LICENSES") {
                    Link("Third-party notices", destination: noticesURL)
                        .foregroundStyle(.secondary)
                        .padding(.top, 5)
                        .padding(.bottom, 7)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 10)
                }
            }
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .navigationTitle("About")
    }
}
