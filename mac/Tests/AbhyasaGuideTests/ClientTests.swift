import Foundation
import Network
import Testing
import AbhyasaCore
@testable import AbhyasaGuide

/// A small HTTP server on 127.0.0.1, as in the core tests: each path gives a fixed status, type and body, then closes.
final class StreamServer: @unchecked Sendable {
    let routes: [String: (Int, String, String)]
    private var listener: NWListener?
    private let q = DispatchQueue(label: "stream-server")

    init(_ routes: [String: (Int, String, String)]) { self.routes = routes }

    func start(port: Int) throws {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: NWEndpoint.Port(rawValue: UInt16(port))!)
        params.allowLocalEndpointReuse = true
        let l = try NWListener(using: params)
        let ready = DispatchSemaphore(value: 0)
        l.stateUpdateHandler = { s in if case .ready = s { ready.signal() } }
        l.newConnectionHandler = { [weak self] c in self?.serve(c) }
        l.start(queue: q)
        listener = l
        _ = ready.wait(timeout: .now() + 5)
    }

    func stop() { listener?.cancel() }

    private func serve(_ c: NWConnection) {
        c.start(queue: q)
        c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] d, _, _, _ in
            guard let self else { return c.cancel() }
            let head = d.map { String(decoding: $0, as: UTF8.self) } ?? ""
            let path = head.split(separator: " ").dropFirst().first.map(String.init) ?? "/"
            let (code, type, body) = routes[path] ?? (404, "text/plain", "not found")
            let resp = "HTTP/1.1 \(code) X\r\nContent-Type: \(type)\r\nContent-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n\(body)"
            c.send(content: Data(resp.utf8), completion: .contentProcessed { _ in c.cancel() })
        }
    }
}

@Suite struct GuideClientTests {
    func serve(_ routes: [String: (Int, String, String)]) throws -> (StreamServer, GuideClient) {
        let p = try Port.free()
        let s = StreamServer(routes)
        try s.start(port: p)
        return (s, GuideClient(base: Port.base(p)))
    }

    @Test func askGivesTheEventsToTheBoard() async throws {
        let sse = ": hi\n\ndata: {\"wait\": \"The tutor looks in your vault.\"}\n\n"
            + "data: {\"step\": {\"say\": \"Look here.\", \"strokes\": []}, \"k\": 0, \"tier\": \"tutor\"}\n\n"
            + "data: {\"board\": {\"steps\": [], \"tier\": \"tutor\"}}\n\ndata: {\"wait\": \"never read\"}\n\n"
        let (s, c) = try serve(["/guide/ask": (200, "text/event-stream", sse)])
        defer { s.stop() }
        var kinds: [GuideEvent.Kind] = []
        for try await e in c.ask(Data("{}".utf8)) { kinds.append(e.kind) }
        #expect(kinds == [.wait("The tutor looks in your vault."), .step(0), .board])
    }

    @Test func aSavedEventAfterTheBoardStillComes() async throws {
        let sse = "data: {\"wait\": \"Asks Claude Sonnet.\", \"state\": \"asking\", \"model\": \"Claude Sonnet\", \"where\": \"hosted\"}\n\n"
            + "data: {\"board\": {\"steps\": []}}\n\n"
            + "data: {\"wait\": \"not read\"}\n\n"
            + "data: {\"saved\": {\"title\": \"Attention\", \"url\": \"u\", \"undo\": \"/guide/undo/1\"}}\n\n"
        let (s, c) = try serve(["/guide/ask": (200, "text/event-stream", sse)])
        defer { s.stop() }
        var kinds: [GuideEvent.Kind] = []
        for try await e in c.ask(Data("{}".utf8)) { kinds.append(e.kind) }
        #expect(kinds == [.wait("Asks Claude Sonnet."), .board, .saved(GuideEvent.Saved(title: "Attention", url: "u", undo: "/guide/undo/1"))])
    }

    @Test func undoPostsToTheRoute() async throws {
        let (s, c) = try serve(["/guide/undo/1": (200, "application/json", "{}")])
        defer { s.stop() }
        #expect(await c.post("/guide/undo/1"))
        #expect(!(await c.post("/guide/undo/2")))   // 404
    }

    @Test func undoGoesOnlyToTheServer() {
        let base = URL(string: "http://127.0.0.1:5001/")!
        #expect(GuideClient.route("/guide/undo/1", base: base)?.absoluteString == "http://127.0.0.1:5001/guide/undo/1")
        #expect(GuideClient.route("https://evil.example/x", base: base) == nil)
        #expect(GuideClient.route("//evil.example/x", base: base) == nil)
        #expect(GuideClient.route("/a/../../x", base: base) == nil)
        #expect(GuideClient.route("guide/undo", base: base) == nil)
    }

    @Test func aRefusalGivesItsStatusAndText() async throws {
        let (s, c) = try serve(["/guide/ask": (400, "text/plain", "Say or type what you do not understand.")])
        defer { s.stop() }
        await #expect(throws: GuideClient.Failure.status(400, "Say or type what you do not understand.")) {
            for try await _ in c.ask(Data("{}".utf8)) {}
        }
    }

    @Test func sttGivesTheText() async throws {
        let (s, c) = try serve(["/voice/stt": (200, "application/json", #"{"text": "I don't get the loss curve"}"#)])
        defer { s.stop() }
        #expect(try await c.stt(Audio.wav([0, 0])) == "I don't get the loss curve")
    }
}
