// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NotchControl",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "notch-control", targets: ["NotchControl"])],
    targets: [
        .target(name: "ControlCore"),
        .executableTarget(name: "NotchControl", dependencies: ["ControlCore"]),
        .testTarget(name: "ControlCoreTests", dependencies: ["ControlCore"])
    ]
)
