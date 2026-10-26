import AppKit
import WebKit
import AbhyasaCore

/// The web view on the server. It gives the microphone only to the server's own origin, and it opens other links in
/// the default browser.
@MainActor
final class WebController: NSObject, WKUIDelegate, WKNavigationDelegate {
    let view: WKWebView
    var port = 0
    var onLoad: (() -> Void)?

    override init() {
        let c = WKWebViewConfiguration()
        c.websiteDataStore = .default()
        view = WKWebView(frame: .zero, configuration: c)
        super.init()
        view.uiDelegate = self
        view.navigationDelegate = self
        view.allowsBackForwardNavigationGestures = true
    }

    func url(_ path: String) -> URL? { port > 0 ? URL(string: path, relativeTo: Port.base(port)) : nil }

    func go(_ path: String) {
        guard let u = url(path) else { return }
        view.load(URLRequest(url: u))
    }

    /// a form post with no fields, as the "Start" button sends
    func post(_ path: String) {
        guard let u = url(path) else { return }
        var r = URLRequest(url: u)
        r.httpMethod = "POST"
        r.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        r.httpBody = Data()
        view.load(r)
    }

    func run(_ js: String, done: @escaping (Bool) -> Void) {
        view.evaluateJavaScript(js) { v, _ in done(v as? Bool ?? false) }
    }

    // the microphone, for getUserMedia: only the server's origin gets it
    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo,
                 type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        let ok = type == .microphone && Links.isServer(scheme: origin.protocol, host: origin.host, port: origin.port, server: port)
        decisionHandler(ok ? .grant : .deny)
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void) {
        guard let u = action.request.url else { return decisionHandler(.cancel) }
        if Links.isServer(u, port: port) || u.scheme == "about" || u.scheme == "blob" || u.scheme == "data" {
            return decisionHandler(.allow)
        }
        if let local = Links.path(u) { go(local) } else { NSWorkspace.shared.open(u) }
        decisionHandler(.cancel)
    }

    // target=_blank: a server page opens here, other pages open in the browser
    func webView(_ webView: WKWebView, createWebViewWith c: WKWebViewConfiguration, for action: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let u = action.request.url {
            if Links.isServer(u, port: port) { view.load(URLRequest(url: u)) } else { NSWorkspace.shared.open(u) }
        }
        return nil
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { onLoad?() }
}
