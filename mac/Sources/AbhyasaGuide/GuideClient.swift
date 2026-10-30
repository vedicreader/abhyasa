import Foundation

/// The guide's calls to the abhyasa server, on one long-lived URLSession (Clicky's note: a new session for each stream breaks
/// the connection pool).
public final class GuideClient: Sendable {
    public enum Failure: Error, Equatable { case status(Int, String) }
    public let base: URL
    let session: URLSession

    public init(base: URL) {
        self.base = base
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 120
        c.timeoutIntervalForResource = 300
        session = URLSession(configuration: c)
    }

    /// posts one question to `/guide/ask` and gives its events as they come, to the board or the error at the end
    public func ask(_ body: Data) -> AsyncThrowingStream<GuideEvent, Error> {
        var r = URLRequest(url: base.appending(path: "guide/ask"))
        r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        r.httpBody = body
        let session = session
        return AsyncThrowingStream { c in
            let t = Task {
                do {
                    let (bytes, resp) = try await session.bytes(for: r)
                    let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                    if code != 200 {
                        var text = Data()
                        for try await b in bytes { if text.count < 400 { text.append(b) } }
                        throw Failure.status(code, String(decoding: text, as: UTF8.self))
                    }
                    var p = SSEParser(), line = Data(), ended = false
                    for try await b in bytes {
                        line.append(b)
                        guard b == 0x0A else { continue }
                        for d in p.feed(line) {
                            guard let e = GuideEvent.parse(d) else { continue }
                            if case .error = e.kind { c.yield(e); c.finish(); return }
                            // after the board, only a saved event can come: what the guide put in the vault, with its Undo
                            if ended { if case .saved = e.kind { c.yield(e) }; continue }
                            c.yield(e)
                            ended = e.isLast
                        }
                        line.removeAll(keepingCapacity: true)
                    }
                    c.finish()
                } catch { c.finish(throwing: error) }
            }
            c.onTermination = { _ in t.cancel() }
        }
    }

    /// posts to `route`, a path on the server (the Undo of a saved event); true when the server says ok
    public func post(_ route: String) async -> Bool {
        guard let u = Self.route(route, base: base) else { return false }
        var r = URLRequest(url: u)
        r.httpMethod = "POST"
        guard let (_, resp) = try? await session.data(for: r) else { return false }
        return (200..<300).contains((resp as? HTTPURLResponse)?.statusCode ?? 0)
    }

    /// the URL of `route` on the server, or nil when it is not a plain path there (no host, no scheme, no `..`)
    public static func route(_ route: String, base: URL) -> URL? {
        guard route.hasPrefix("/"), !route.hasPrefix("//"), !route.contains(".."), !route.contains("\\"),
              let u = URL(string: route, relativeTo: base)?.absoluteURL,
              u.scheme == base.scheme, u.host == base.host, u.port == base.port else { return nil }
        return u
    }

    /// one line in the natural voice of the Settings page, from `/guide/say`
    public func say(_ text: String) async -> SayReply {
        var r = URLRequest(url: base.appending(path: "guide/say"))
        r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.httpBody = try? JSONSerialization.data(withJSONObject: ["text": text])
        r.timeoutInterval = 60
        guard let (d, resp) = try? await session.data(for: r) else { return .failed("abhyasa did not answer") }
        return SayReply.parse(status: (resp as? HTTPURLResponse)?.statusCode ?? 0, d)
    }

    /// the text of one WAV clip from `/voice/stt`
    public func stt(_ wav: Data) async throws -> String {
        var r = URLRequest(url: base.appending(path: "voice/stt"))
        r.httpMethod = "POST"
        r.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
        r.httpBody = wav
        let (d, resp) = try await session.data(for: r)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        let o = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any]
        guard code == 200 else { throw Failure.status(code, o?["error"] as? String ?? "") }
        return o?["text"] as? String ?? ""
    }
}
