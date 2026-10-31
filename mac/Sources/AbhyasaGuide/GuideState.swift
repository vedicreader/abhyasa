import Foundation

/// Where the speech to text runs. The server's `/voice/stt` uses the engine of the Mac Settings, or else the engine of the
/// Settings page; the Mac knows only the first.
public enum Speech: Equatable, Sendable {
    case local(String), hosted(String), unknown

    public var isHosted: Bool { if case .hosted = self { true } else { false } }

    /// the place of the engine `id` (`ABHYASA_STT`, as `engine` or `engine:model`); empty means the Settings page chooses
    public static func of(_ id: String) -> Speech {
        let e = id.lowercased().split(separator: ":").first.map(String.init) ?? ""
        switch e {
        case "": return .unknown
        case "openai": return .hosted("OpenAI")
        case "gemma", "mlx": return .local(id.lowercased().contains("whisper") ? "Whisper" : "Qwen3-ASR")   // gemma: the name before 0.0.16
        case "whisper": return .local("Whisper")
        case "parakeet": return .local("Parakeet")
        default: return .unknown
        }
    }
}

/// The model that gets the question, and where it runs. The Mac guesses it from its Settings; the server's state events
/// (`model`, `where`, `who`) name the real one, and they win.
public struct Who: Equatable, Sendable {
    public var model: String
    public var local: Bool
    public var company: String

    public init(model: String, local: Bool, company: String = "") {
        self.model = model; self.local = local; self.company = company
    }

    /// the where chip: "on this Mac", or "hosted · Anthropic"
    public var chip: String { local ? GuideText.onThisMac : GuideText.hosted(company) }

    /// the model of the Mac Settings: an id such as `claude/sonnet`; empty is the server default, Claude Sonnet
    public static func guess(_ id: String, names: [String: String] = [:]) -> Who {
        let id = id.isEmpty ? "claude/sonnet" : id
        let l = id.lowercased()
        let name = names[id] ?? Self.name(id)
        let localWords = ["gemma", "ollama", "mlx", "litert", "lmstudio", "llama.cpp", "local"]
        if localWords.contains(where: l.contains) { return Who(model: name, local: true) }
        if l.hasPrefix("claude") || l.hasPrefix("anthropic") { return Who(model: name, local: false, company: "Anthropic") }
        if l.hasPrefix("openai") || l.hasPrefix("gpt") || l.hasPrefix("codex") { return Who(model: name, local: false, company: "OpenAI") }
        if l.hasPrefix("gemini") || l.hasPrefix("google") { return Who(model: name, local: false, company: "Google") }
        return Who(model: name, local: false)   // when the Mac does not know, it says that the text can leave
    }

    /// "claude/sonnet" -> "Claude Sonnet"
    static func name(_ id: String) -> String {
        id.split(whereSeparator: { "/-_:".contains($0) }).map { $0.prefix(1).uppercased() + $0.dropFirst() }.joined(separator: " ")
    }

    /// the server's fields win over the guess; a missing field keeps the guess
    public func with(_ s: GuideEvent.Status) -> Who {
        var w = self
        if let m = s.model, !m.isEmpty { w.model = m }
        if let p = s.place { w.local = p == "on this Mac" }
        if let c = s.who { w.company = c } else if s.place != nil, w.local { w.company = "" }
        return w
    }
}

/// What the guide does now. The menu bar mark and its state line follow it.
public enum GuideState: Equatable, Sendable {
    case off, ready, listening, writing, reading, asking(Who), searching, saving, drawing

    /// the state of a server event's `state` field; nil for a state that the Mac does not know
    public static func server(_ s: String?, who: Who) -> GuideState? {
        switch s {
        case "reading": .reading
        case "asking": .asking(who)
        case "searching": .searching
        case "saving": .saving
        case "drawing": .drawing
        default: nil
        }
    }

    /// the SF Symbol of the menu bar mark: small, a template image, no animation
    public var symbol: String {
        switch self {
        case .off: "circle.dashed"
        case .ready: "circle"
        case .listening: "mic"
        case .writing: "text.bubble"
        case .reading: "doc.text.magnifyingglass"
        case .asking: "ellipsis.circle"
        case .searching: "globe"
        case .saving: "tray.and.arrow.down"
        case .drawing: "scribble"
        }
    }

    /// the first line of the menu
    public var line: String {
        switch self {
        case .off: GuideText.menuOff
        case .ready: GuideText.menuReady
        case .listening: GuideText.menuListening
        case .writing: GuideText.menuWriting
        case .reading: GuideText.menuReading
        case .asking(let w): GuideText.menuAsking(w.model, w.chip)
        case .searching: GuideText.menuSearching
        case .saving: GuideText.menuSaving
        case .drawing: GuideText.menuDrawing
        }
    }

    /// true while the guide works on a question: Stop has something to stop
    public var busy: Bool { self != .off && self != .ready }
}

/// The strip's line for a server event: the text, the where chip, and a second line. A pure part, for the tests.
public enum Lines {
    public struct Line: Equatable, Sendable {
        public var text: String
        public var chip = ""
        public var hosted = false
        public var detail = ""
    }

    /// a wait event: its STE line, with the chip of its state; an old server sends no state, so no chip shows
    public static func wait(_ t: String, _ s: GuideEvent.Status?, who: Who) -> Line {
        guard let s else { return Line(text: t) }
        var l = Line(text: t)
        var more: [String] = []
        switch s.state {
        case "searching":
            l.chip = GuideText.web; l.hosted = true
            if let q = s.query, !q.isEmpty, !t.contains(q) { more.append("\u{201C}\(q)\u{201D}") }
        case "reading", "saving" where s.place == nil:
            l.chip = GuideText.onThisMac
        default:
            if s.place != nil || s.model != nil || s.state == "asking" { l.chip = who.chip; l.hosted = !who.local }
        }
        if let n = s.sources, n > 0 { more.append(GuideText.sources(n)) }
        l.detail = more.joined(separator: " ")
        return l
    }

    /// the chip of the board strip: "Claude Sonnet · hosted" or "Gemma 4 E4B · on this Mac"
    public static func boardChip(_ w: Who) -> String { "\(w.model) · \(w.local ? GuideText.onThisMac : "hosted")" }

    /// the count of text parts that go with the question: the anchors, but not the window title
    public static func parts(_ anchors: [Anchor]) -> Int { anchors.filter { $0.kind != "title" }.count }
}
