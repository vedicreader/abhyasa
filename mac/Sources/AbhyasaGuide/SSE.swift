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

/// One event of the guide's ask route (abhyasa/blocks/guide/app.py): `{"wait": text}`, `{"step": {…}, "k": n, "tier": t}`,
/// `{"board": {…}}` or `{"error": text}`. `raw` is the JSON as it came, for board.js in the overlay.
public struct GuideEvent: Equatable, Sendable {
    public enum Kind: Equatable, Sendable { case wait(String), step(Int), board, error(String), other }
    public var kind: Kind
    public var raw: String

    /// the event in `data`, or nil when it is not a JSON object
    public static func parse(_ data: String) -> GuideEvent? {
        guard let o = (try? JSONSerialization.jsonObject(with: Data(data.utf8))) as? [String: Any] else { return nil }
        if let t = o["error"] as? String { return GuideEvent(kind: .error(t), raw: data) }
        if o["board"] is [String: Any] { return GuideEvent(kind: .board, raw: data) }
        if o["step"] is [String: Any] { return GuideEvent(kind: .step((o["k"] as? Int) ?? 0), raw: data) }
        if let t = o["wait"] as? String { return GuideEvent(kind: .wait(t), raw: data) }
        return GuideEvent(kind: .other, raw: data)
    }

    /// true for the last event of a question: the route ends the stream after a board or an error
    public var isLast: Bool {
        switch kind { case .board, .error: true; default: false }
    }
}
