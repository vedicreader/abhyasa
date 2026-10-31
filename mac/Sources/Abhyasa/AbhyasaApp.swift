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
                .background(WindowOpener())   // a click on a notification of research opens this window
        }
        .defaultSize(width: 1100, height: 800)
        .handlesExternalEvents(matching: [Links.scheme])
        .commands {
            // no menu item uses ⌥ + a letter: ⌥D, ⌥S and ⌥W go to the page
            CommandGroup(replacing: .newItem) {
                Button("New Session") { model.newSession() }.keyboardShortcut("n")
            }
            CommandMenu("Go") {
                // a wrong click is never a dead end: back, forward, and home from anywhere (also a two-finger swipe)
                Button("Back") { model.back() }.keyboardShortcut("[")
                Button("Forward") { model.forward() }.keyboardShortcut("]")
                Divider()
                Button("Today") { model.today() }.keyboardShortcut("h", modifiers: [.command, .shift])
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
        MainActor.assumeIsolated { AppModel.shared.start(); ResearchWatch.shared.start() }
    }

    /// while research of a walk runs, closing the window keeps the app in the menu bar, so research goes on
    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool {
        MainActor.assumeIsolated { ResearchWatch.shared.quitOnLastWindow() }
    }

    func applicationWillTerminate(_ n: Notification) {
        MainActor.assumeIsolated { ResearchWatch.shared.stop(); AppModel.shared.quit() }
    }
}
