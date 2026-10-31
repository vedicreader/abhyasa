import Foundation

/// One walk in the research state of the server: its id, title, link, the time its research ended, and its sources.
public struct ResearchWalk: Decodable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let url: String
    public let end: Double?
    public let have: Int
    public let total: Int

    public init(id: String, title: String, url: String, end: Double?, have: Int, total: Int) {
        self.id = id; self.title = title; self.url = url; self.end = end; self.have = have; self.total = total
    }
}

/// `/walk/research.json`: the walks whose research runs now, and the walks whose research ended in the last hours.
public struct ResearchStatus: Decodable, Equatable, Sendable {
    public let running: [ResearchWalk]
    public let ended: [ResearchWalk]
    public static let idle = ResearchStatus(running: [], ended: [])

    public init(running: [ResearchWalk], ended: [ResearchWalk]) { self.running = running; self.ended = ended }
}

/// What the Mac app does with the research of walks: stay alive while it runs, and tell the learner when it ends.
public enum Research {
    public static let path = "walk/research.json"
    /// the line, said one time, when the last window closes while research runs
    public static let menuBarNote = "Abhyasa still looks for sources. It runs in the menu bar."
    public static let notifyTitle = "Sources are ready"

    public static func parse(_ data: Data) -> ResearchStatus? { try? JSONDecoder().decode(ResearchStatus.self, from: data) }

    /// whether the app quits when its last window closes: only when no research runs, so closing the window never stops it
    public static func quitOnLastWindow(running: Int) -> Bool { running == 0 }

    /// whether the app, kept alive in the menu bar with no window, quits now: research ended
    public static func quitNow(running: Int, windows: Int, keptAlive: Bool) -> Bool { keptAlive && running == 0 && windows == 0 }

    /// the walks to tell the learner about: research ended after `since` (the start of the app), and not told yet (`told`: `id@end`)
    public static func toTell(_ s: ResearchStatus, since: Double, told: Set<String>) -> [ResearchWalk] {
        s.ended.filter { ($0.end ?? 0) > since && !told.contains(key($0)) }
    }

    public static func key(_ w: ResearchWalk) -> String { "\(w.id)@\(w.end ?? 0)" }

    /// the text of the notification for walk `w`, in plain words
    public static func notifyBody(_ w: ResearchWalk) -> String {
        "Sources for your walk \u{2018}\(w.title)\u{2019} are ready. \(w.have) of \(w.total) \(w.total == 1 ? "idea has" : "ideas have") a source."
    }

    /// the server path of the link of `w` (`/w/<id>?plan=1#gather`), only when it is a path of the walk pages
    public static func walkPath(_ w: ResearchWalk) -> String? {
        w.url.hasPrefix("/w/") && !w.url.contains("//") ? w.url : nil
    }

    /// the research state from the server at `base`; nil when it does not answer
    public static func status(_ base: URL) async -> ResearchStatus? {
        var req = URLRequest(url: base.appending(path: path))
        req.timeoutInterval = 5
        guard let (data, resp) = try? await URLSession.shared.data(for: req), (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return parse(data)
    }
}
