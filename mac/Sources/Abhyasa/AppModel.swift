import AppKit
import Observation
import AbhyasaCore
import AbhyasaGuide

/// The state of the app: the supervisor, the web view, the Dock badge and the settings.
@MainActor @Observable
final class AppModel {
    static let shared = AppModel()

    let supervisor: Supervisor
    let web = WebController()
    /// a page from an abhyasa:// link that came before the server was ready
    @ObservationIgnored private var pending: String?
    @ObservationIgnored private var badgeTimer: Timer?

    init() {
        let res = Bundle.main.resourceURL
        supervisor = Supervisor(paths: .user, pin: res?.appending(path: "Pin"), settings: Prefs.load())
        supervisor.onReady = { [weak self] base in self?.ready(base) }
        web.onLoad = { [weak self] in self?.refreshBadge() }
        // the Keys panel asks for the guide over other apps: the first-use sheet shows, and the learner starts the guide from it
        web.onGuideStart = { if !Guide.shared.status.on { Guide.shared.requestStart() } }
        // Caps+E over Abhyasa's own window opens the page's own guide box
        Guide.shared.ownApp = { [weak self] in self?.web.run("(() => { if (window.abhyasaGuide) { abhyasaGuide.open(); return true } return false })()") { _ in } }
    }

    func start() {
        Task { await supervisor.start() }
    }

    private func ready(_ base: URL) {
        web.port = supervisor.port
        web.go(pending ?? "/")
        Guide.shared.model = supervisor.settings.model
        Guide.shared.speechEngine = supervisor.settings.stt
        Guide.shared.start(port: supervisor.port)
        pending = nil
        refreshBadge()
        badgeTimer?.invalidate()
        badgeTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { _ in
            Task { @MainActor in AppModel.shared.refreshBadge() }
        }
    }

    func refreshBadge() {
        guard case .ready(let base) = supervisor.phase else { return NSApp.dockTile.badgeLabel = nil }
        Task {
            let n = await Health.due(base)
            NSApp.dockTile.badgeLabel = (n ?? 0) > 0 ? String(n!) : nil
        }
    }

    /// opens an abhyasa:// link, now or when the server is ready
    func open(_ url: URL) {
        guard let path = Links.path(url) else { return }
        if case .ready = supervisor.phase { web.go(path) } else { pending = path }
    }

    func apply(_ s: ServerSettings) {
        Prefs.save(s)
        supervisor.settings = s
        start()
    }

    func quit() {
        badgeTimer?.invalidate()
        Guide.shared.stop()
        supervisor.stop()
    }

    // the menu commands
    func newSession() { web.post("/start") }
    func today() { web.go("/") }
    func back() { web.back() }
    func forward() { web.forward() }
    func graph() { web.go("/graph") }
    func addSource() { web.go("/add") }
    /// puts the focus in the search box at the top of the page, or opens the search page
    func search() {
        web.run("(() => { const q = document.querySelector('input[name=q]'); if (q) { q.focus(); q.select(); return true } return false })()") {
            [weak self] found in if !found { self?.web.go("/search") }
        }
    }
}

/// The settings in UserDefaults.
enum Prefs {
    static let d = UserDefaults.standard

    static func load() -> ServerSettings {
        ServerSettings(model: d.string(forKey: "model") ?? "", stt: d.string(forKey: "stt") ?? "",
                 vault: d.string(forKey: "vault") ?? ServerSettings.defaultVault)
    }

    static func save(_ s: ServerSettings) {
        d.set(s.model, forKey: "model")
        d.set(s.stt, forKey: "stt")
        d.set(s.vault, forKey: "vault")
    }
}
