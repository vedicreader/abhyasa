import Foundation

/// `abhyasa://` links, and the check that a URL is the app's own server.
public enum Links {
    public static let scheme = "abhyasa"

    /// a slug from abhyasa's `slugify`: lower-case letters, digits and hyphens
    public static func isSlug(_ s: String) -> Bool {
        !s.isEmpty && s.count <= 200 && s.allSatisfy { ("a"..."z").contains($0) || ("0"..."9").contains($0) || $0 == "-" }
    }

    /// the server path for a link: `abhyasa://concept/<slug>` gives `/c/<slug>`, `abhyasa://` and
    /// `abhyasa://today` give `/`. Other links give nil.
    public static func path(_ url: URL) -> String? {
        guard url.scheme?.lowercased() == scheme else { return nil }
        let parts = url.pathComponents.filter { $0 != "/" }
        switch url.host()?.lowercased() ?? "" {
        case "concept":
            guard parts.count == 1, isSlug(parts[0].lowercased()) else { return nil }
            return "/c/\(parts[0].lowercased())"
        case "", "today":
            return parts.isEmpty ? "/" : nil
        default:
            return nil
        }
    }

    /// true only for http://127.0.0.1:<port>, the server that the app started
    public static func isServer(_ url: URL?, port: Int) -> Bool {
        guard let url, port > 0 else { return false }
        return url.scheme == "http" && url.host() == Port.host && url.port == port
    }

    /// the same check for a web origin (scheme, host and port), as WebKit gives for a mic request
    public static func isServer(scheme: String, host: String, port: Int, server: Int) -> Bool {
        server > 0 && scheme == "http" && host == Port.host && port == server
    }
}
