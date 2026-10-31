import SwiftUI
import AppKit
import UserNotifications
import AbhyasaCore
import AbhyasaGuide

/// Tells the learner when the research of a walk ends. The app runs until you quit it (`Life`), so research goes on with the window closed.
/// It asks the server for `/jobs.json` every 5 seconds and reads its research rows. Each end of research gives a macOS notification; a click opens the walk.
/// It asks for permission to notify only the first time research runs, never at launch.
@MainActor
final class ResearchWatch: NSObject, UNUserNotificationCenterDelegate {
    static let shared = ResearchWatch()

    private(set) var status = ResearchStatus.idle
    private var timer: Timer?
    private var told = Set<String>()
    private let since = Date().timeIntervalSince1970
    /// the action of SwiftUI that opens the main window, kept by `WindowOpener`
    var openMain: (() -> Void)?

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
    }

    /// opens the main window (and the page `path`): after a click on a notification, on the Dock icon or on Open Abhyasa in the menu bar mark
    func show(path: String?) {
        NSApp.activate()
        openMain?()
        if let path { AppModel.shared.web.go(path) }
    }

    private func askOnce() {
        guard !UserDefaults.standard.bool(forKey: "research.askedNotify") else { return }
        UserDefaults.standard.set(true, forKey: "research.askedNotify")
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    private func notify(_ w: ResearchWalk) {
        let c = UNMutableNotificationContent()
        c.title = Research.notifyTitle
        c.body = Research.notifyBody(w)
        if let path = Research.walkPath(w) { c.userInfo = ["path": path] }
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

/// An empty view in the main window that keeps SwiftUI's `openWindow` for `ResearchWatch`, so a notification, the Dock icon and
/// Open Abhyasa in the menu bar mark open the window again.
struct WindowOpener: View {
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .onAppear {
                ResearchWatch.shared.openMain = { openWindow(id: "main") }
                Guide.shared.openApp = { ResearchWatch.shared.show(path: nil) }
            }
    }
}
