import Foundation

/// A parser for server-sent events that takes the bytes as they come. It gives the `data` of each event; a comment line
/// (`: still listening`) and the other fields are ignored. Lines can end with LF, CR LF or CR.
public struct SSEParser {
    var buf = Data()
    var data: [String] = []
    var lastCR = false

    public init() {}

    public mutating func feed(_ chunk: Data) -> [String] {
        var out: [String] = []
        for b in chunk {
            if lastCR { lastCR = false; if b == 0x0A { continue } }
            if b == 0x0A || b == 0x0D {
                lastCR = b == 0x0D
                line(String(decoding: buf, as: UTF8.self), &out)
                buf.removeAll(keepingCapacity: true)
            } else { buf.append(b) }
        }
        return out
    }

    public mutating func feed(_ s: String) -> [String] { feed(Data(s.utf8)) }

    mutating func line(_ l: String, _ out: inout [String]) {
        if l.isEmpty {
            if !data.isEmpty { out.append(data.joined(separator: "\n")) }
            data = []
            return
        }
        if l.hasPrefix(":") { return }
        let (field, value): (Substring, Substring) = {
            guard let k = l.firstIndex(of: ":") else { return (Substring(l), "") }
            var v = l[l.index(after: k)...]
            if v.hasPrefix(" ") { v = v.dropFirst() }
            return (l[..<k], v)
        }()
        if field == "data" { data.append(String(value)) }
    }
}

/// One event of the guide's ask route (abhyasa/blocks/guide/app.py): `{"wait": text}`, `{"step": {…}, "k": n, "tier": t, "point": look}`,
/// `{"board": {…}, "point": look}`, `{"error": text}`, `{"saved": {"title", "url", "undo"}}`, or `{"show": {"href", "title", "find"}}` for "show me …"
/// (Show: a moving demo in abhyasa, with no board; the overlay gives the link "Open in abhyasa"). A wait event can also tell the state:
/// `{"wait", "state", "model", "where", "who", "query", "sources"}`. Each of these fields is optional, so an older server works
/// too. `raw` is the JSON as it came, for board.js in the overlay.
public struct GuideEvent: Equatable, Sendable {
    public enum Kind: Equatable, Sendable { case wait(String), step(Int), board, error(String), saved(Saved), show(Show), other }

    /// Show for "show me …": the local path that opens the Show slot of the idea in abhyasa, and the name of the idea. `find` is true when
    /// no idea of the learner matches the window: then the path opens the Library with the words.
    public struct Show: Equatable, Sendable {
        public var href: String
        public var title: String
        public var find: Bool
        public init(href: String, title: String = "", find: Bool = false) { self.href = href; self.title = title; self.find = find }
    }

    /// a thing that the guide put in the vault, with the route that takes it out again
    public struct Saved: Equatable, Sendable {
        public var title: String
        public var url: String
        public var undo: String
    }

    /// what the server does now, and who gets the text; nil fields are not in the event
    public struct Status: Equatable, Sendable {
        public var state: String?
        public var model: String?
        public var place: String?   // "where": "on this Mac" or "hosted"
        public var who: String?
        public var query: String?
        public var sources: Int?
        public init(state: String? = nil, model: String? = nil, place: String? = nil, who: String? = nil, query: String? = nil, sources: Int? = nil) {
            self.state = state; self.model = model; self.place = place; self.who = who; self.query = query; self.sources = sources
        }
    }

    public var kind: Kind
    public var raw: String
    public var status: Status?

    /// the event in `data`, or nil when it is not a JSON object
    public static func parse(_ data: String) -> GuideEvent? {
        guard let o = (try? JSONSerialization.jsonObject(with: Data(data.utf8))) as? [String: Any] else { return nil }
        let st = status(o)
        func e(_ k: Kind) -> GuideEvent { GuideEvent(kind: k, raw: data, status: st) }
        if let t = o["error"] as? String { return e(.error(t)) }
        if o["board"] is [String: Any] { return e(.board) }
        if o["step"] is [String: Any] { return e(.step((o["k"] as? Int) ?? 0)) }
        if let s = o["saved"] as? [String: Any] {
            return e(.saved(Saved(title: s["title"] as? String ?? "", url: s["url"] as? String ?? "", undo: s["undo"] as? String ?? "")))
        }
        if let s = o["show"] as? [String: Any], let h = s["href"] as? String {
            return e(.show(Show(href: h, title: s["title"] as? String ?? "", find: s["find"] as? Bool ?? false)))
        }
        if let t = o["wait"] as? String { return e(.wait(t)) }
        return e(.other)
    }

    static func status(_ o: [String: Any]) -> Status? {
        let s = Status(state: o["state"] as? String, model: o["model"] as? String, place: o["where"] as? String,
                       who: o["who"] as? String, query: o["query"] as? String, sources: o["sources"] as? Int)
        return s == Status() ? nil : s
    }

    /// true for the last event of a question: the route ends the stream after a board, an error or a show
    public var isLast: Bool {
        switch kind { case .board, .error, .show: true; default: false }
    }
}
