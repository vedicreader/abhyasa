import AppKit
import WebKit

/// The overlay: one panel for each display, made when a board first needs it, each with a transparent web view that runs
/// board.js (OverlayPage). A board plays in the panel of the display that holds the window in front.
@MainActor
public final class Overlay: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
    final class Sheet {
        let panel: OverlayPanel
        let web: WKWebView
        var ready = false
        var queue: [String] = []
        init(panel: OverlayPanel, web: WKWebView) { self.panel = panel; self.web = web }
    }

    /// the server, for board.js and its files
    public var base: URL? { didSet { if base != oldValue { closeAll() } } }
    /// calls from the page: `speak`, `hush`, `stop`, `first`
    public var onSpeak: ((Int, String) -> Void)?
    public var onHush: ((Int) -> Void)?
    public var onStop: (() -> Void)?
    public var onFirst: (() -> Void)?

    var sheets: [UInt32: Sheet] = [:]
    /// the display where the board shows now
    public private(set) var current: UInt32?
    /// the display where the trail of the pointer shows now
    var trailOn: UInt32?

    public override init() {
        super.init()
        NotificationCenter.default.addObserver(forName: NSApplication.didChangeScreenParametersNotification, object: nil, queue: .main) {
            [weak self] _ in MainActor.assumeIsolated { self?.closeAll() }
        }
    }

    func sheet(for d: Display) -> Sheet? {
        if let s = sheets[d.id] { s.panel.setFrame(d.frame, display: false); return s }
        guard let base else { return nil }
        let panel = OverlayPanel(display: d)
        let c = WKWebViewConfiguration()
        c.websiteDataStore = .nonPersistent()
        c.userContentController.add(WeakHandler(self), name: "guide")
        let web = WKWebView(frame: NSRect(origin: .zero, size: d.frame.size), configuration: c)
        web.setValue(false, forKey: "drawsBackground")
        web.underPageBackgroundColor = .clear
        web.navigationDelegate = self
        web.autoresizingMask = [.width, .height]
        panel.contentView = web
        web.loadHTMLString(OverlayPage.html, baseURL: base)
        let s = Sheet(panel: panel, web: web)
        sheets[d.id] = s
        return s
    }

    /// puts the anchor boxes on the panel of `display` and shows that panel; it never takes the focus
    public func show(on d: Display, boxes: [OverlayPage.Box]) {
        if let c = current, c != d.id { run("overlay.stop()", on: c); sheets[c]?.panel.orderOut(nil) }
        guard let s = sheet(for: d), let list = OverlayPage.js(boxes) else { return }
        current = d.id
        run("overlay.begin(); overlay.anchors(\(list))", on: d.id)
        s.panel.orderFrontRegardless()
        _ = s
    }

    /// one event of the ask route, as its JSON text
    public func event(_ raw: String) { if let c = current { run("overlay.event(\(raw))", on: c) } }
    public func note(_ text: String) { if let c = current, let t = OverlayPage.js([text]) { run("overlay.note(\(t)[0])", on: c) } }
    public func move(dx: CGFloat, dy: CGFloat) { if let c = current { run("overlay.move(\(Double(dx)), \(Double(dy)))", on: c) } }
    public func word(_ id: Int, _ k: Int) { if let c = current { run("overlay.word(\(id), \(k))", on: c) } }
    public func done(_ id: Int) { if let c = current { run("overlay.done(\(id))", on: c) } }
    public func again() { if let c = current { run("overlay.again()", on: c) } }
    public func stop() { if let c = current { run("overlay.stop()", on: c) } }

    // --- show while you talk: the trail of the pointer while the guide asks, in the same click-through panels ---------------
    /// the trail (CG global points of the last 1.5 s), on the display that holds its last point
    public func trail(_ pts: [CGPoint]) {
        guard let last = pts.last else { return }
        let ds = Display.all, h = Geometry.mainHeight(ds)
        guard let d = Geometry.display(for: Geometry.appKit(fromCG: CGRect(origin: last, size: .zero), mainHeight: h), in: ds),
              let s = sheet(for: d) else { return }
        if let t = trailOn, t != d.id { endTrail() }
        trailOn = d.id
        let list = pts.map { p -> [Double] in
            let r = Geometry.panel(fromCG: CGRect(origin: p, size: .zero), display: d, mainHeight: h)
            return [Double(r.minX), Double(r.minY)]
        }
        guard let js = OverlayPage.js(list) else { return }
        run("overlay.trail(\(js))", on: d.id)
        if !s.panel.isVisible { s.panel.orderFrontRegardless() }
    }

    /// a soft ring on a gesture (its box in CG global points), on the display of the trail
    public func ring(_ g: Gestures.Gesture) {
        let ds = Display.all
        guard let id = trailOn, let d = ds.first(where: { $0.id == id }) else { return }
        let r = Geometry.panel(fromCG: CGRect(x: g.box[0], y: g.box[1], width: g.box[2] - g.box[0], height: g.box[3] - g.box[1]),
                               display: d, mainHeight: Geometry.mainHeight(ds))
        guard let js = OverlayPage.js([Double(r.minX), Double(r.minY), Double(r.maxX), Double(r.maxY)]) else { return }
        run("overlay.ring(\(js), \(g.kind == .point))", on: id)
    }

    /// takes the trail away; its panel goes too when no board shows on it
    public func endTrail() {
        guard let id = trailOn else { return }
        trailOn = nil
        run("overlay.endTrail()", on: id)
        if id != current { sheets[id]?.panel.orderOut(nil) }
    }

    /// takes the panels away, with no board
    public func hide() {
        for s in sheets.values { s.panel.orderOut(nil) }
        current = nil
    }

    /// whether a board shows now, from board.js
    public func showing() async -> Bool {
        guard let c = current, let s = sheets[c], s.ready else { return false }
        return (try? await s.web.evaluateJavaScript("!!(window.abhyasaBoard && abhyasaBoard.state)")) as? Bool ?? false
    }

    public func closeAll() {
        for s in sheets.values {
            s.web.configuration.userContentController.removeScriptMessageHandler(forName: "guide")
            s.panel.orderOut(nil)
            s.panel.close()
        }
        sheets = [:]
        current = nil
        trailOn = nil
    }

    func run(_ js: String, on id: UInt32) {
        guard let s = sheets[id] else { return }
        if s.ready { s.web.evaluateJavaScript(js) } else { s.queue.append(js) }
    }

    // the page says that it is ready: run the calls that waited
    public func userContentController(_ u: WKUserContentController, didReceive m: WKScriptMessage) {
        guard let d = m.body as? [String: Any], let op = d["op"] as? String else { return }
        switch op {
        case "ready":
            guard let s = sheets.values.first(where: { $0.web === m.webView }) else { return }
            s.ready = true
            let q = s.queue
            s.queue = []
            for js in q { s.web.evaluateJavaScript(js) }
        case "speak": if let id = d["id"] as? Int, let t = d["text"] as? String { onSpeak?(id, t) }
        case "hush": if let id = d["id"] as? Int { onHush?(id) }
        case "stop": onStop?()
        case "first": onFirst?()
        default: break
        }
    }

    // the page loads once; it never goes to another page
    public func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction,
                        decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void) {
        let u = a.request.url
        let first = sheets.values.first { $0.web === w }.map { !$0.ready } ?? false
        let same = u?.scheme == base?.scheme && u?.host == base?.host && u?.port == base?.port
        decisionHandler(first && (same || u?.scheme == "about") ? .allow : .cancel)
    }
}

/// A script message handler that does not keep the overlay alive (WKUserContentController keeps its handlers).
final class WeakHandler: NSObject, WKScriptMessageHandler {
    weak var target: (any WKScriptMessageHandler)?
    init(_ t: any WKScriptMessageHandler) { target = t }
    func userContentController(_ u: WKUserContentController, didReceive m: WKScriptMessage) {
        target?.userContentController(u, didReceive: m)
    }
}
