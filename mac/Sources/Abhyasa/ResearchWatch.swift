import SwiftUI
import AppKit
import UserNotifications
import AbhyasaCore

/// Keeps research of walks going when the window closes, and tells the learner when it ends.
/// It asks the server for `/walk/research.json` every 5 seconds. While research runs, closing the last window keeps the app in the
/// menu bar; when research ends there, the app quits as before. Each end of research gives a macOS notification; a click opens the walk.
/// It asks for permission to notify only the first time research runs, never at launch.
@MainActor
final class ResearchWatch: NSObject, UNUserNotificationCenterDelegate {
    static let shared = ResearchWatch()

    private(set) var status = ResearchStatus.idle
    private var timer: Timer?
    private var item: NSStatusItem?
    private var told = Set<String>()
    private let since = Date().timeIntervalSince1970
    /// the action of SwiftUI that opens the main window, kept by `WindowOpener`
    var openMain: (() -> Void)?

    private var keptAlive: Bool { item != nil }
    private var windows: Int { NSApp.windows.filter { $0.isVisible && $0.canBecomeMain }.count }

    func start() {
        UNUserNotificationCenter.current().delegate = self
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { _ in Task { @MainActor in await ResearchWatch.shared.poll() } }
    }

    func stop() { timer?.invalidate(); timer = nil }

    private func poll() async {
        guard case .ready(let base) = AppModel.shared.supervisor.phase, let s = await Research.status(base) else { return }
        status = s
        if !s.running.isEmpty { askOnce() }
        for w in Research.toTell(s, since: since, told: told) { told.insert(Research.key(w)); notify(w) }
        if Research.quitNow(running: s.running.count, windows: windows, keptAlive: keptAlive) { NSApp.terminate(nil) }
    }

    /// the answer to `applicationShouldTerminateAfterLastWindowClosed`: while research runs, stay in the menu bar
    func quitOnLastWindow() -> Bool {
        if Research.quitOnLastWindow(running: status.running.count) { return true }
        keepAlive()
        return false
    }

    private func keepAlive() {
        guard item == nil else { return }
        let it = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        it.button?.image = NSImage(systemSymbolName: "book", accessibilityDescription: "Abhyasa")
        it.button?.toolTip = Research.menuBarNote
        let menu = NSMenu()
        menu.addItem(withTitle: Research.menuBarNote, action: nil, keyEquivalent: "").isEnabled = false
        menu.addItem(.separator())
        menu.addItem(withTitle: "Open Abhyasa", action: #selector(openWindow), keyEquivalent: "").target = self
        menu.addItem(withTitle: "Quit Abhyasa", action: #selector(quitApp), keyEquivalent: "").target = self
        it.menu = menu
        item = it
        NSApp.setActivationPolicy(.accessory)   // no Dock icon while it waits in the menu bar
        if !UserDefaults.standard.bool(forKey: "research.toldMenuBar") {
            UserDefaults.standard.set(true, forKey: "research.toldMenuBar")
            post(title: "Abhyasa", body: Research.menuBarNote, path: nil)
        }
    }

    /// the window is open again: back to a normal app with a Dock icon
    func windowBack() {
        guard let it = item else { return }
        NSStatusBar.system.removeStatusItem(it)
        item = nil
        NSApp.setActivationPolicy(.regular)
    }

    @objc private func openWindow() { show(path: nil) }
    @objc private func quitApp() { NSApp.terminate(nil) }

    private func show(path: String?) {
        windowBack()
        NSApp.activate()
        openMain?()
        if let path { AppModel.shared.web.go(path) }
    }

    private func askOnce() {
        guard !UserDefaults.standard.bool(forKey: "research.askedNotify") else { return }
        UserDefaults.standard.set(true, forKey: "research.askedNotify")
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    private func notify(_ w: ResearchWalk) { post(title: Research.notifyTitle, body: Research.notifyBody(w), path: Research.walkPath(w)) }

    private func post(title: String, body: String, path: String?) {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        if let path { c.userInfo = ["path": path] }
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: UUID().uuidString, content: c, trigger: nil))
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler done: @escaping () -> Void) {
        let path = response.notification.request.content.userInfo["path"] as? String
        Task { @MainActor in ResearchWatch.shared.show(path: path); done() }
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent n: UNNotification, withCompletionHandler done: @escaping (UNNotificationPresentationOptions) -> Void) {
        done([.banner])   // also when the window is in front: the line on the page says it too
    }
}

/// An empty view in the main window that keeps SwiftUI's `openWindow` for `ResearchWatch`, so a click on a notification opens the window.
struct WindowOpener: View {
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .onAppear {
                ResearchWatch.shared.openMain = { openWindow(id: "main") }
                ResearchWatch.shared.windowBack()
            }
    }
}
