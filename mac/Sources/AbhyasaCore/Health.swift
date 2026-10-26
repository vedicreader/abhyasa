import Foundation

public enum HealthError: Error, Equatable { case timedOut, exited }

/// Calls to the server: `/health` before the page loads, and `/due.json` for the Dock badge.
public enum Health {
    /// a session that never uses a proxy, so a system proxy cannot catch loopback calls
    public static let session: URLSession = {
        let c = URLSessionConfiguration.ephemeral
        c.connectionProxyDictionary = [:]
        c.timeoutIntervalForRequest = 2
        return URLSession(configuration: c)
    }()

    static func json(_ url: URL) async -> [String: Any]? {
        guard let (d, r) = try? await session.data(from: url), (r as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return try? JSONSerialization.jsonObject(with: d) as? [String: Any]
    }

    /// true when `/health` gives status ok
    public static func check(_ base: URL) async -> Bool {
        await json(base.appending(path: "health"))?["status"] as? String == "ok"
    }

    /// waits until `/health` is ok; stops early when `alive` gives false, because the server stopped
    public static func wait(_ base: URL, timeout: Duration, every: Duration = .milliseconds(200),
                            alive: @escaping @Sendable () -> Bool = { true }) async throws {
        let clock = ContinuousClock()
        let end = clock.now + timeout
        while clock.now < end {
            if await check(base) { return }
            guard alive() else { throw HealthError.exited }
            try await Task.sleep(for: every)
        }
        throw HealthError.timedOut
    }

    /// the number of due reviews, or nil when the server has no `/due.json` (abhyasa 0.0.2 does not)
    public static func due(_ base: URL) async -> Int? {
        await json(base.appending(path: "due.json"))?["due"] as? Int
    }
}
