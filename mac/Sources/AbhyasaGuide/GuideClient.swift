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
                    var p = SSEParser(), line = Data()
                    for try await b in bytes {
                        line.append(b)
                        guard b == 0x0A else { continue }
                        for d in p.feed(line) {
                            guard let e = GuideEvent.parse(d) else { continue }
                            c.yield(e)
                            if e.isLast { c.finish(); return }
                        }
                        line.removeAll(keepingCapacity: true)
                    }
                    c.finish()
                } catch { c.finish(throwing: error) }
            }
            c.onTermination = { _ in t.cancel() }
        }
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
