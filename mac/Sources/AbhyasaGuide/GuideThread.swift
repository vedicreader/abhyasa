import Foundation

/// The short thread of one window, so that a follow-up ("say that more simply", "why?") has the last board: the last 3 turns,
/// each the question, the lines that its board said and its tier. It is in memory only. It clears when the window changes (the
/// app's bundle id and the window title), after 10 minutes with no question, or with Start fresh. The bounds are the server's
/// too (`clean_context` in nbs/21_guide.ipynb), and the page keeps the same thread (guide.js).
public struct GuideThread: Equatable, Sendable {
    public struct Turn: Equatable, Sendable, Encodable {
        public var said: String
        public var says: [String]
        public var t: String
    }
    public static let most = 3, saidMost = 300, saysMost = 6, sayMost = 160, total = 1500
    /// the seconds with no question after which the thread clears
    public static let idle = 600.0
    public static let tiers: Set<String> = ["tutor", "vault", "web"]

    public private(set) var key = ""
    /// the clock (seconds) of the last question
    public private(set) var at = 0.0
    public private(set) var turns: [Turn] = []

    public init() {}

    /// the key of a window: the app's bundle id and the window title
    public static func key(bundle: String, title: String) -> String { "\(bundle)\n\(title)" }

    /// the turns for a question over the window `key` at `now`; another window, or 10 minutes with no question, clears them first
    public mutating func current(key: String, now: Double) -> [Turn] {
        if key != self.key || now - at > Self.idle { self.key = key; turns = [] }
        return turns
    }

    /// a question goes now, with the thread: the 10 minutes start again
    public mutating func asked(now: Double) { if !turns.isEmpty { at = now } }

    /// keeps the turn of a board that the learner saw over the window `key`; a board with no line adds nothing
    public mutating func keep(said: String, says: [String], tier: String, key: String, now: Double) {
        let lines = says.prefix(Self.saysMost).map { AnchorList.cut($0, Self.sayMost) }.filter { !$0.isEmpty }
        let q = AnchorList.cut(said, Self.saidMost)
        guard !lines.isEmpty, !q.isEmpty else { return }
        _ = current(key: key, now: now)
        turns.append(Turn(said: q, says: lines, t: Self.tiers.contains(tier) ? tier : "tutor"))
        turns = Array(turns.suffix(Self.most))
        while !turns.isEmpty, turns.reduce(0, { $0 + Self.size($1) }) > Self.total { turns.removeFirst() }
        at = now
    }

    /// Start fresh
    public mutating func clear() { turns = [] }

    /// the last question, for the strip's "Follows up on" line
    public var last: String? { turns.last?.said }

    static func size(_ t: Turn) -> Int { t.said.count + t.says.reduce(0) { $0 + $1.count } }

    /// the lines and the tier of a board event (`{"board": {"tier", "steps": [{"say"}]}}`), or nil when it is not one
    public static func board(_ raw: String) -> (says: [String], tier: String)? {
        guard let o = (try? JSONSerialization.jsonObject(with: Data(raw.utf8))) as? [String: Any], let b = o["board"] as? [String: Any] else { return nil }
        let says = (b["steps"] as? [[String: Any]] ?? []).compactMap { $0["say"] as? String }
        return (says, b["tier"] as? String ?? "tutor")
    }
}
