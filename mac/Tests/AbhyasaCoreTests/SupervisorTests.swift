import Foundation
import Testing
@testable import AbhyasaCore

/// The system Python runs a small HTTP server in place of abhyasa. Arguments: the port, then the seconds before it
/// stops with exit code 3 (0: never; less than 0: stop at once with exit code 2).
let fakeAbhyasa = """
import sys, os, threading, http.server
port, die = int(sys.argv[1]), float(sys.argv[2])
if die < 0: sys.exit(2)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        b = b'{"status":"ok"}' if self.path == '/health' else b'{}'
        self.send_response(200); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
if die > 0: threading.Timer(die, lambda: os._exit(3)).start()
print('fake abhyasa on', port, flush=True)
http.server.HTTPServer(('127.0.0.1', port), H).serve_forever()
"""
let python = URL(fileURLWithPath: "/usr/bin/python3")

func py(_ code: String, _ args: [String] = []) -> Launch {
    Launch(executable: python, args: ["-c", code] + args, env: ["PATH": "/usr/bin:/bin"])
}

@MainActor func until(_ seconds: Double = 15, _ cond: () -> Bool) async -> Bool {
    let end = Date().addingTimeInterval(seconds)
    while Date() < end {
        if cond() { return true }
        try? await Task.sleep(for: .milliseconds(50))
    }
    return cond()
}

@MainActor func fake(die: Double, paths: Paths = tempPaths()) -> Supervisor {
    let s = Supervisor(paths: paths, uv: nil, pin: nil, settings: ServerSettings())
    s.healthTimeout = .seconds(15)
    s.serverLaunch = { port, _ in py(fakeAbhyasa, [String(port), String(die)]) }
    return s
}

@MainActor @Suite(.serialized) struct SupervisorTests {
    @Test func startsWaitsForHealthAndStops() async throws {
        let s = fake(die: 0)
        await s.start()
        guard case .ready(let base) = s.phase else { Issue.record("phase \(s.phase)"); return }
        #expect(base == Port.base(s.port))
        #expect(await Health.check(base))
        s.stop()
        #expect(!s.isRunning)
        #expect(s.phase == .idle)
        #expect(await !Health.check(base))
    }

    @Test func aCrashGivesAMessageAndStartAgainWorks() async throws {
        let s = fake(die: 1.0)
        await s.start()
        guard case .ready = s.phase else { Issue.record("phase \(s.phase)"); return }
        #expect(await until { if case .failed = s.phase { true } else { false } })
        guard case .failed(let msg) = s.phase else { return }
        #expect(msg.contains("exit code 3"))
        #expect(msg.contains("fake abhyasa on"))
        s.serverLaunch = { port, _ in py(fakeAbhyasa, [String(port), "0"]) }
        await s.start()
        guard case .ready = s.phase else { Issue.record("phase \(s.phase)"); return }
        s.stop()
    }

    @Test func aServerThatNeverStartsFailsAfterTheTries() async throws {
        let s = fake(die: -1)
        var ports = [Int]()
        s.serverLaunch = { port, _ in ports.append(port); return py(fakeAbhyasa, [String(port), "-1"]) }
        s.tries = 2
        await s.start()
        guard case .failed(let msg) = s.phase else { Issue.record("phase \(s.phase)"); return }
        #expect(msg.hasPrefix("The abhyasa server did not start."))
        #expect(ports.count == 2)
    }

    @Test func theServerGetsTheSettings() async throws {
        let s = fake(die: 0)
        s.settings = ServerSettings(model: "m/x", stt: "whisper", vault: "/tmp/none.db")
        var got: ServerSettings?
        let inner = s.serverLaunch
        s.serverLaunch = { port, st in got = st; return inner(port, st) }
        await s.start()
        #expect(got == s.settings)
        s.stop()
    }

    func pin() throws -> URL {
        let d = tempDir()
        try Data("[project]\nname = 'x'\n".utf8).write(to: d.appending(path: "pyproject.toml"))
        try Data("lock".utf8).write(to: d.appending(path: "uv.lock"))
        return d
    }

    @Test func syncRunsWhenTheLockChangedThenWritesTheStamp() async throws {
        let paths = tempPaths(), dir = try pin()
        let s = Supervisor(paths: paths, uv: nil, pin: dir, settings: ServerSettings())
        s.syncLaunch = py("print('Installed 3 packages')")
        s.serverLaunch = { port, _ in py(fakeAbhyasa, [String(port), "0"]) }
        await s.start()
        guard case .ready = s.phase else { Issue.record("phase \(s.phase)"); return }
        let stamp = try String(contentsOf: paths.stamp, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
        #expect(stamp == (try Lock.hash(dir: dir)))
        #expect(try String(contentsOf: paths.syncLog, encoding: .utf8).contains("Installed 3 packages"))
        #expect(FileManager.default.fileExists(atPath: paths.project.appending(path: "uv.lock").path))
        s.stop()
    }

    @Test func aFailedSyncGivesTheSetupMessage() async throws {
        let paths = tempPaths()
        let s = Supervisor(paths: paths, uv: nil, pin: try pin(), settings: ServerSettings())
        s.syncLaunch = py("import sys; print('no network here'); sys.exit(1)")
        await s.start()
        guard case .failed(let msg) = s.phase else { Issue.record("phase \(s.phase)"); return }
        #expect(msg.hasPrefix("Setup did not complete."))
        #expect(msg.contains("no network here"))
        #expect(!FileManager.default.fileExists(atPath: paths.stamp.path))
    }
}
