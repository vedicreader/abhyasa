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
                .background(WindowOpener())   // a notification, the Dock icon and the menu bar mark open this window again
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

    /// as Leela: the app runs until you quit it. Closing the window leaves the menu bar mark and the server running
    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { Life.quitOnLastWindow }

    /// a click on the Dock icon with no window open: the main window opens again
    func applicationShouldHandleReopen(_ app: NSApplication, hasVisibleWindows: Bool) -> Bool {
        if Life.reopen(visibleWindows: hasVisibleWindows) { MainActor.assumeIsolated { ResearchWatch.shared.show(path: nil) } }
        return true
    }

    func applicationWillTerminate(_ n: Notification) {
        MainActor.assumeIsolated { ResearchWatch.shared.stop(); AppModel.shared.quit() }
    }
}
