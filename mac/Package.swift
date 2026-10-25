// swift-tools-version: 6.2
import PackageDescription

let v5: [SwiftSetting] = [.swiftLanguageMode(.v5)]

let package = Package(
    name: "Abhyasa",
    platforms: [.macOS(.v26)],
    targets: [
        // the supervisor logic, without AppKit: paths, port, health wait, lock stamp, child environment, links
        .target(name: "AbhyasaCore", swiftSettings: v5),
        .executableTarget(name: "Abhyasa", dependencies: ["AbhyasaCore"], swiftSettings: v5),
        .testTarget(name: "AbhyasaCoreTests", dependencies: ["AbhyasaCore"], swiftSettings: v5),
    ]
)
