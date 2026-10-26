import Foundation
import Observation

/// What the app shows: setup, start, the page, or a failure with "Start again".
public enum Phase: Equatable, Sendable {
    case idle
    /// `uv sync` runs; the text is the last line that uv wrote
    case syncing(String)
    /// no uv on this Mac; the app shows `brew install uv` and Retry
    case needsUV
    case starting
    case ready(URL)
    case failed(String)
}

enum SyncError: Error { case noUV }

/// One command to run.
public struct Launch: Sendable {
    public var executable: URL
    public var args: [String]
    public var env: [String: String]

    public init(executable: URL, args: [String], env: [String: String]) {
        self.executable = executable
        self.args = args
        self.env = env
    }
}

/// `Process` is not Sendable; the health wait reads only `isRunning`, which is safe from any thread.
final class Running: @unchecked Sendable {
    let p: Process
    init(_ p: Process) { self.p = p }
    var isRunning: Bool { p.isRunning }
}

/// Starts and stops the abhyasa server: sync the environment when the lock changed, pick a port, start the server,
/// wait for `/health`. A server that stops by itself gives `.failed`.
@MainActor @Observable
public final class Supervisor {
    public private(set) var phase: Phase = .idle
    public private(set) var port = 0
    public var settings: ServerSettings
    public let paths: Paths
    public var healthTimeout: Duration = .seconds(120)
    /// a server that stops before `/health` is ok gets a new port, up to this number of tries (another app can take the port)
    public var tries = 3
    /// the server command for a port; tests replace it
    @ObservationIgnored public var serverLaunch: (Int, ServerSettings) -> Launch
    /// the sync command; nil finds uv with `findUV` at each start, so Retry sees a uv that you installed since
    @ObservationIgnored public var syncLaunch: Launch?
    @ObservationIgnored public var findUV: () -> URL?
    @ObservationIgnored let uvEnv: [String: String]
    @ObservationIgnored public var onReady: ((URL) -> Void)?

    @ObservationIgnored let pin: URL?
    @ObservationIgnored private var server: Process?
    @ObservationIgnored private var sync: Process?
    @ObservationIgnored private var stopping = false
    @ObservationIgnored private var generation = 0

    /// `pin` is the bundled folder with pyproject.toml and uv.lock; nil skips the sync, for tests
    public init(paths: Paths, pin: URL?, settings: ServerSettings,
                parent: [String: String] = ProcessInfo.processInfo.environment, home: String = NSHomeDirectory()) {
        self.paths = paths
        self.pin = pin
        self.settings = settings
        uvEnv = ChildEnv.uv(parent, home: home, paths: paths)
        findUV = { ChildEnv.findUV(home: home, path: parent["PATH"]) }
        serverLaunch = { port, s in
            Launch(executable: paths.server, args: ChildEnv.serverArgs(port: port, settings: s, home: home),
                   env: ChildEnv.server(parent, home: home, paths: paths, settings: s))
        }
    }

    public var isRunning: Bool { server?.isRunning ?? false }

    /// stops a running server, then does each step again
    public func start() async {
        stop()
        stopping = false
        generation += 1
        let gen = generation
        do {
            try await syncIfNeeded()
        } catch SyncError.noUV {
            if gen == generation, !stopping { phase = .needsUV }
            return
        } catch {
            if gen == generation, !stopping {
                phase = .failed("Setup did not complete. Make sure that this Mac can connect to the internet. Then start again.\n\n"
                                + Self.tail(paths.syncLog))
            }
            return
        }
        guard gen == generation, !stopping else { return }
        for attempt in 1...max(tries, 1) {
            phase = .starting
            do {
                let p = try Port.free()
                let proc = try run(serverLaunch(p, settings), log: paths.log)
                server = proc
                port = p
                let box = Running(proc)
                try await Health.wait(Port.base(p), timeout: healthTimeout) { box.isRunning }
                guard gen == generation, !stopping else { return }
                phase = .ready(Port.base(p))
                onReady?(Port.base(p))
                return
            } catch HealthError.exited where attempt < tries {
                continue
            } catch {
                guard gen == generation, !stopping else { return }
                stop()
                stopping = false
                phase = .failed("The abhyasa server did not start.\n\n" + Self.tail(paths.log))
                return
            }
        }
    }

    /// stops the server (and a sync that runs); SIGTERM, then SIGKILL after 3 seconds
    public func stop() {
        stopping = true
        for p in [sync, server].compactMap({ $0 }) {
            if p.isRunning { p.terminate() }
            let end = Date().addingTimeInterval(3)
            while p.isRunning && Date() < end { usleep(20_000) }
            if p.isRunning { kill(p.processIdentifier, SIGKILL) }
        }
        sync = nil
        server = nil
        if case .ready = phase { phase = .idle }
        if case .starting = phase { phase = .idle }
    }

    func syncIfNeeded() async throws {
        guard let pin else { return }
        try Lock.copyProject(from: pin, paths: paths)
        let hash = try Lock.hash(dir: paths.project)
        guard Lock.needsSync(hash: hash, paths: paths) else { return }
        guard let launch = syncLaunch ?? findUV().map({ Launch(executable: $0, args: ChildEnv.uvArgs(paths), env: uvEnv) })
        else { throw SyncError.noUV }
        phase = .syncing("Getting Python and the packages")
        let code = try await runSync(launch)
        guard code == 0 else { throw HealthError.exited }
        try Lock.writeStamp(hash, paths: paths)
    }

    private func runSync(_ launch: Launch) async throws -> Int32 {
        let log = try Self.openLog(paths.syncLog)
        let pipe = Pipe()
        let p = Process()
        p.executableURL = launch.executable
        p.arguments = launch.args
        p.environment = launch.env
        // a writable working folder: a GUI app starts in /, which is read only, and the server writes files beside itself (.sesskey)
        p.currentDirectoryURL = paths.support
        p.standardInput = FileHandle.nullDevice
        p.standardOutput = pipe
        p.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let d = h.availableData
            guard !d.isEmpty else { return }
            log.write(d)
            let line = String(decoding: d, as: UTF8.self).split(whereSeparator: \.isNewline).last.map(String.init) ?? ""
            guard !line.isEmpty else { return }
            Task { @MainActor in if case .syncing = self?.phase { self?.phase = .syncing(line) } }
        }
        sync = p
        return try await withCheckedThrowingContinuation { c in
            p.terminationHandler = { p in
                pipe.fileHandleForReading.readabilityHandler = nil
                try? log.close()
                c.resume(returning: p.terminationStatus)
            }
            do { try p.run() } catch { c.resume(throwing: error) }
        }
    }

    private func run(_ launch: Launch, log url: URL) throws -> Process {
        let log = try Self.openLog(url)
        let p = Process()
        p.executableURL = launch.executable
        p.arguments = launch.args
        p.environment = launch.env
        // a writable working folder: a GUI app starts in /, which is read only, and the server writes files beside itself (.sesskey)
        p.currentDirectoryURL = paths.support
        p.standardInput = FileHandle.nullDevice
        p.standardOutput = log
        p.standardError = log
        p.terminationHandler = { [weak self] p in
            let code = p.terminationStatus
            try? log.close()
            Task { @MainActor in self?.exited(p, code: code) }
        }
        try p.run()
        return p
    }

    private func exited(_ p: Process, code: Int32) {
        guard p === server, !stopping else { return }
        server = nil
        if case .ready = phase {
            phase = .failed("The abhyasa server stopped (exit code \(code)).\n\n" + Self.tail(paths.log))
        }
    }

    static func openLog(_ url: URL) throws -> FileHandle {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        FileManager.default.createFile(atPath: url.path, contents: nil)
        return try FileHandle(forWritingTo: url)
    }

    /// the last lines of a log, for the failure message
    public static func tail(_ url: URL, lines: Int = 6) -> String {
        guard let d = try? Data(contentsOf: url) else { return "" }
        let text = String(decoding: d.suffix(8192), as: UTF8.self)
        return text.split(whereSeparator: \.isNewline).suffix(lines).joined(separator: "\n")
    }
}
