import SwiftUI
import AppKit
import AbhyasaCore

@main
struct AbhyasaApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    let model = AppModel.shared

    var body: some Scene {
        Window("Abhyasa", id: "main") {
            MainView(model: model)
                .frame(minWidth: 640, minHeight: 480)
                .onOpenURL { model.open($0) }
        }
        .defaultSize(width: 1100, height: 800)
        .handlesExternalEvents(matching: [Links.scheme])
        .commands {
            // no menu item uses ⌥ + a letter: ⌥D, ⌥S and ⌥W go to the page
            CommandGroup(replacing: .newItem) {
                Button("New Session") { model.newSession() }.keyboardShortcut("n")
            }
            CommandMenu("Go") {
                Button("Today") { model.today() }
                Button("Graph") { model.graph() }
                Button("Search") { model.search() }.keyboardShortcut("f")
                Button("Add a Source") { model.addSource() }
            }
        }
        Settings {
            SettingsView(model: model)
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ n: Notification) {
        MainActor.assumeIsolated { AppModel.shared.start() }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ n: Notification) {
        MainActor.assumeIsolated { AppModel.shared.quit() }
    }
}
