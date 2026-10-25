import Foundation
import Network
@testable import AbhyasaCore

/// A small HTTP server on 127.0.0.1 for the tests: each path gives a fixed status and body.
final class FakeServer: @unchecked Sendable {
    let routes: [String: (Int, String)]
    private var listener: NWListener?
    private let q = DispatchQueue(label: "fake-server")

    init(_ routes: [String: (Int, String)]) { self.routes = routes }

    /// listens on `port`; waits until the listener is ready
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
            let (code, body) = routes[path] ?? (404, "not found")
            let resp = "HTTP/1.1 \(code) X\r\nContent-Type: application/json\r\nContent-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n\(body)"
            c.send(content: Data(resp.utf8), completion: .contentProcessed { _ in c.cancel() })
        }
    }
}

/// a new empty folder for one test
func tempDir() -> URL {
    let u = FileManager.default.temporaryDirectory.appending(path: "abhyasa-tests-\(UUID().uuidString)")
    try! FileManager.default.createDirectory(at: u, withIntermediateDirectories: true)
    return u
}

func tempPaths() -> Paths {
    let d = tempDir()
    return Paths(support: d.appending(path: "support"), caches: d.appending(path: "caches"))
}

