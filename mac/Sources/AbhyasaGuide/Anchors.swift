import CoreGraphics
import Foundation

/// One thing that the Accessibility read found: its role, its text and its frame in CG global points.
public struct AXItem: Equatable, Sendable {
    public enum Near: String, Sendable { case target, selection, visible }
    public var role: String
    public var subrole: String = ""
    public var text: String
    public var frame: CGRect
    public var near: Near = .visible
    /// a password field, or a field with a name like a key or a token: its text never leaves the Mac
    public var secure = false

    public init(role: String, subrole: String = "", text: String, frame: CGRect, near: Near = .visible, secure: Bool = false) {
        self.role = role
        self.subrole = subrole
        self.text = text
        self.frame = frame
        self.near = near
        self.secure = secure
    }
}

/// The front window, as the read found it. `title` is empty when the app does not give it.
public struct FrontWindow: Equatable, Sendable {
    public var app: String
    public var bundle: String
    public var title: String
    public var frame: CGRect
    public var windowID: UInt32 = 0

    public init(app: String, bundle: String = "", title: String = "", frame: CGRect, windowID: UInt32 = 0) {
        self.app = app
        self.bundle = bundle
        self.title = title
        self.frame = frame
        self.windowID = windowID
    }
}

/// One anchor for the tutor (design 4.2): an id, a kind from the server's list, the visible text, the AX role and how near it
/// is. `frame` (CG global points) stays on the Mac: the overlay uses it, and the JSON leaves it out.
public struct Anchor: Equatable, Sendable, Encodable {
    public var id: String
    public var kind: String
    public var text: String
    public var role: String
    public var near: String
    public var frame: CGRect

    enum CodingKeys: String, CodingKey { case id, kind, text, role, near }
}

/// The context that goes to the guide's ask route. The server keeps `page`, `title`, `anchors` (with `id`, `kind` and
/// `text`) and `focus` (what the learner showed with the pointer), and drops the other keys. `app` and `role` are there for a
/// later server. With no focus, the JSON has no `focus` key.
public struct GuideContext: Equatable, Sendable, Encodable {
    public var page: String
    public var title: String
    public var app: String
    public var anchors: [Anchor]
    public var focus: [Gestures.Focus]? = nil
}

/// Why the guide reads less than it can. The strip shows the words.
public enum Limit: Equatable, Sendable {
    case none
    /// no Accessibility permission: the window frame only
    case noAccess
    /// the app is on the never-look list
    case neverLook(String)
    /// a password field has the focus
    case password
}

/// Makes the anchor list from what the Accessibility read found: the target first, then the selection, then the window, then
/// up to 40 anchors in all, nearest first. Text is cut to 300 characters an anchor and 6,000 in all. Secure fields are left
/// out. The ids match the server's rule (letters, digits, `:`, `_` and `-`).
public enum AnchorList {
    public static let most = 40, textMost = 300, totalMost = 6000
    /// apps that the guide never reads (design 8.2). The learner can change the list later.
    public static let neverLook: Set<String> = ["Keychain Access", "1Password", "1Password 7", "Bitwarden", "Passwords", "Messages",
                                                 "Mail", "Signal", "WhatsApp", "System Settings"]
    static let secretWords = ["password", "passcode", "token", "secret", "api key", "apikey", "private key"]

    /// the words of a role in front of the text, so the tutor knows a button from a label
    static let roleWords = ["AXButton": "button", "AXLink": "link", "AXCheckBox": "checkbox", "AXRadioButton": "option",
                            "AXPopUpButton": "menu", "AXMenuItem": "menu item", "AXTextField": "text field", "AXTab": "tab",
                            "AXCell": "cell", "AXSlider": "slider", "AXComboBox": "menu"]

    public static func isSecret(role: String, subrole: String, name: String) -> Bool {
        if role == "AXSecureTextField" || subrole == "AXSecureTextField" { return true }
        let n = name.lowercased()
        return (role == "AXTextField" || role == "AXTextArea") && secretWords.contains { n.contains($0) }
    }

    public static func kind(role: String, subrole: String, text: String) -> String {
        switch role {
        case "AXImage": return "figure"
        case "AXHeading": return "title"
        default: return text.count > 200 ? "passage" : "text"
        }
    }

    /// `s` with each run of white space made one space, and cut to `n` characters
    public static func cut(_ s: String, _ n: Int) -> String {
        String(s.split(whereSeparator: { $0.isWhitespace || $0.isNewline }).joined(separator: " ").prefix(n))
    }

    public static func build(window: FrontWindow?, items: [AXItem], limit: Limit = .none) -> GuideContext {
        let app = window?.app ?? ""
        let title = cut([app, window?.title ?? ""].filter { !$0.isEmpty }.joined(separator: " · "), 200)
        var out: [Anchor] = []
        var total = 0
        func add(_ id: String, _ kind: String, _ text: String, _ role: String, _ near: String, _ frame: CGRect) {
            guard out.count < most else { return }
            let t = String(cut(text, textMost).prefix(max(0, totalMost - total)))
            total += t.count
            out.append(Anchor(id: id, kind: kind, text: t, role: role, near: near, frame: frame))
        }
        let readable: Bool = { if case .none = limit { return true }; return false }()
        let usable = readable ? items.filter { !$0.secure && !$0.frame.isEmpty && !$0.frame.isNull } : []
        let target = usable.first { $0.near == .target }
        let selection = usable.first { $0.near == .selection }
        if let t = target { add("t", kind(role: t.role, subrole: t.subrole, text: t.text), label(t), t.role, "target", t.frame) }
        if let s = selection { add("s", "text", s.text, s.role, "selection", s.frame) }
        if let w = window { add("w", "title", title.isEmpty ? app : title, "AXWindow", "visible", w.frame) }
        let centre = (target?.frame ?? selection?.frame ?? window?.frame).map { CGPoint(x: $0.midX, y: $0.midY) } ?? .zero
        var seen = Set<String>()
        let rest = usable.filter { $0.near == .visible }
            .filter { i in window.map { $0.frame.intersects(i.frame) } ?? true }
            .filter { !cut($0.text, textMost).isEmpty || $0.role == "AXImage" }
            .sorted { dist($0.frame, centre) < dist($1.frame, centre) }
        var n = 0
        for i in rest {
            let key = "\(Int(i.frame.minX)),\(Int(i.frame.minY)),\(Int(i.frame.width)),\(Int(i.frame.height))|\(cut(i.text, 80))"
            guard seen.insert(key).inserted else { continue }
            n += 1
            add("e\(n)", kind(role: i.role, subrole: i.subrole, text: i.text), label(i), i.role, "visible", i.frame)
        }
        return GuideContext(page: "app:" + (window?.bundle.isEmpty == false ? window!.bundle : app), title: title, app: app, anchors: out)
    }

    static func label(_ i: AXItem) -> String {
        let t = cut(i.text, textMost)
        guard let w = roleWords[i.role] else { return t }
        return t.isEmpty ? w : "\(w): \(t)"
    }

    static func dist(_ r: CGRect, _ p: CGPoint) -> CGFloat { hypot(r.midX - p.x, r.midY - p.y) }

    /// the JSON body of one question: `{"said": …, "ctx": …}`
    public static func body(said: String, ctx: GuideContext) throws -> Data {
        struct Body: Encodable { let said: String; let ctx: GuideContext }
        let e = JSONEncoder()
        e.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return try e.encode(Body(said: cut(said, 300), ctx: ctx))
    }
}
