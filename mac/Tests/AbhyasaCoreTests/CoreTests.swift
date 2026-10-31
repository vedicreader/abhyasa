import Foundation
import Testing
@testable import AbhyasaCore

@Suite struct PortTests {
    @Test func freeGivesAPortThatAServerCanUse() async throws {
        let p = try Port.free()
        #expect((1024...65535).contains(p))
        let s = FakeServer(["/health": (200, #"{"status":"ok"}"#)])
        try s.start(port: p)
        defer { s.stop() }
        #expect(await Health.check(Port.base(p)))
    }

    @Test func baseIsLoopback() {
        #expect(Port.base(5077).absoluteString == "http://127.0.0.1:5077/")
    }
}

@Suite struct HealthTests {
    @Test func waitReturnsWhenHealthIsOk() async throws {
        let p = try Port.free()
        let s = FakeServer(["/health": (200, #"{"status":"ok"}"#)])
        try s.start(port: p)
        defer { s.stop() }
        try await Health.wait(Port.base(p), timeout: .seconds(5))
    }

    @Test func waitGetsAServerThatStartsLate() async throws {
        let p = try Port.free()
        let s = FakeServer(["/health": (200, #"{"status":"ok"}"#)])
        Task.detached { try? await Task.sleep(for: .milliseconds(600)); try? s.start(port: p) }
        defer { s.stop() }
        try await Health.wait(Port.base(p), timeout: .seconds(10), every: .milliseconds(100))
    }

    @Test func waitTimesOutWithNoServer() async throws {
        let p = try Port.free()
        await #expect(throws: HealthError.timedOut) {
            try await Health.wait(Port.base(p), timeout: .milliseconds(500), every: .milliseconds(100))
        }
    }

    @Test func waitStopsWhenTheServerExits() async throws {
        let p = try Port.free()
        await #expect(throws: HealthError.exited) {
            try await Health.wait(Port.base(p), timeout: .seconds(10), alive: { false })
        }
    }

    @Test func checkNeedsStatusOk() async throws {
        let p = try Port.free()
        let s = FakeServer(["/health": (500, #"{"status":"ok"}"#)])
        try s.start(port: p)
        defer { s.stop() }
        #expect(await !Health.check(Port.base(p)))
    }

    @Test func dueReadsTheCountOrGivesNil() async throws {
        let p = try Port.free(), q = try Port.free()
        let a = FakeServer(["/due.json": (200, #"{"due":3}"#)]), b = FakeServer([:])
        try a.start(port: p)
        try b.start(port: q)
        defer { a.stop(); b.stop() }
        #expect(await Health.due(Port.base(p)) == 3)
        #expect(await Health.due(Port.base(q)) == nil)
    }
}

@Suite struct LockTests {
    func pin(_ lock: String) throws -> URL {
        let d = tempDir()
        try Data("[project]\nname = 'x'\n".utf8).write(to: d.appending(path: "pyproject.toml"))
        try Data(lock.utf8).write(to: d.appending(path: "uv.lock"))
        return d
    }

    @Test func hashChangesWithTheLock() throws {
        let a = try Lock.hash(dir: pin("one")), b = try Lock.hash(dir: pin("one")), c = try Lock.hash(dir: pin("two"))
        #expect(a == b)
        #expect(a != c)
        #expect(a.count == 64)
    }

    @Test func needsSyncUntilTheStampMatchesAndTheCommandExists() throws {
        let paths = tempPaths(), h = try Lock.hash(dir: pin("one"))
        #expect(Lock.needsSync(hash: h, paths: paths, isCommand: { _ in true }))
        try Lock.writeStamp(h, paths: paths)
        #expect(!Lock.needsSync(hash: h, paths: paths, isCommand: { _ in true }))
        #expect(Lock.needsSync(hash: h, paths: paths, isCommand: { _ in false }))
        #expect(Lock.needsSync(hash: try Lock.hash(dir: pin("two")), paths: paths, isCommand: { _ in true }))
    }

    @Test func isCommandChecksTheServerPath() throws {
        let paths = tempPaths()
        var seen = ""
        try Lock.writeStamp("x", paths: paths)
        _ = Lock.needsSync(hash: "x", paths: paths, isCommand: { seen = $0; return true })
        #expect(seen.hasSuffix("support/env/bin/abhyasa"))
    }

    @Test func copyProjectReplacesOldFiles() throws {
        let paths = tempPaths()
        try Lock.copyProject(from: pin("one"), paths: paths)
        try Lock.copyProject(from: pin("two"), paths: paths)
        #expect(try String(contentsOf: paths.project.appending(path: "uv.lock"), encoding: .utf8) == "two")
    }

    @Test func theBundledPinLocksTheReleasedAbhyasa() throws {
        let dir = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appending(path: "../../Resources/Pin").standardized
        let py = try String(contentsOf: dir.appending(path: "pyproject.toml"), encoding: .utf8)
        let lock = try String(contentsOf: dir.appending(path: "uv.lock"), encoding: .utf8)
        // the pin names one released abhyasa with the app's extras, and the lock holds that same version from PyPI
        let key = "abhyasa[whisper,tick,models,voice]=="   // voice: Kokoro needs its packages in the app
        let at = try #require(py.range(of: key))
        let v = py[at.upperBound...].prefix { $0.isNumber || $0 == "." }
        #expect(!v.isEmpty)
        #expect(lock.contains("name = \"abhyasa\"\nversion = \"\(v)\"\nsource = { registry = \"https://pypi.org/simple\" }"))
    }
}

@Suite struct ChildEnvTests {
    let home = "/Users/me"
    let paths = Paths(support: URL(fileURLWithPath: "/S/abhyasa"), caches: URL(fileURLWithPath: "/C/abhyasa"))
    let parent = ["PATH": "/usr/bin:/bin:/opt/extra", "HOME": "/Users/me", "USER": "me", "VIRTUAL_ENV": "/other",
                  "UV_INDEX_URL": "https://example.org", "ABHYASA_VAULT": "/real/vault.db", "PYTHONPATH": "/x"]

    @Test func pathPutsTheToolFoldersFirstAndKeepsEachOneTime() {
        let p = ChildEnv.path(first: ["/env/bin"], home: home, inherited: "/usr/bin:/opt/extra:/opt/extra").split(separator: ":")
        #expect(p.first == "/env/bin")
        #expect(p.contains("/Users/me/.local/bin"))
        #expect(p.contains("/opt/homebrew/bin"))
        #expect(p.last == "/opt/extra")
        #expect(Set(p).count == p.count)
    }

    @Test func expandHome() {
        #expect(ChildEnv.expand("~/.vishalakshi/vault.db", home: home) == "/Users/me/.vishalakshi/vault.db")
        #expect(ChildEnv.expand("/abs/v.db", home: home) == "/abs/v.db")
        #expect(ChildEnv.expand("~other/v.db", home: home) == "~other/v.db")
    }

    @Test func serverEnvSetsTheSettingsAndDropsParentPythonValues() {
        let e = ChildEnv.server(parent, home: home, paths: paths, settings: ServerSettings(model: "openai/gpt", stt: "whisper"))
        #expect(e["ABHYASA_MODEL"] == "openai/gpt")
        #expect(e["ABHYASA_STT"] == "whisper")
        #expect(e["ABHYASA_VAULT"] == "/Users/me/.vishalakshi/vault.db")
        #expect(e["VIRTUAL_ENV"] == "/S/abhyasa/env")
        #expect(e["UV_INDEX_URL"] == nil && e["PYTHONPATH"] == nil)
        #expect(e["USER"] == "me" && e["HOME"] == home)
        #expect(e["PATH"]!.hasPrefix("/S/abhyasa/env/bin:/Users/me/.local/bin:/opt/homebrew/bin"))
        #expect(e["PYTHONUNBUFFERED"] == "1")
    }

    @Test func emptyModelGivesTheServerDefault() {
        let e = ChildEnv.server(parent, home: home, paths: paths, settings: ServerSettings(model: "  "))
        #expect(e["ABHYASA_MODEL"] == nil)
        #expect(e["ABHYASA_STT"] == nil, "the Settings page in the app chooses the speech model")
    }

    @Test func serverArgs() {
        #expect(ChildEnv.serverArgs(port: 5123, settings: ServerSettings(vault: "~/v.db"), home: home)
                == ["--port", "5123", "--vault", "/Users/me/v.db"])
    }

    @Test func uvUsesTheAppFolders() {
        let e = ChildEnv.uv(parent, home: home, paths: paths)
        #expect(e["UV_PROJECT_ENVIRONMENT"] == "/S/abhyasa/env")
        #expect(e["UV_PYTHON_INSTALL_DIR"] == "/S/abhyasa/python")
        #expect(e["UV_CACHE_DIR"] == "/C/abhyasa/uv")
        #expect(e["UV_PYTHON_PREFERENCE"] == "only-managed")
        #expect(e["UV_INDEX_URL"] == nil && e["VIRTUAL_ENV"] == nil)
        #expect(ChildEnv.uvArgs(paths) == ["sync", "--frozen", "--no-install-project", "--project", "/S/abhyasa/project"])
    }

    @Test func findUVLooksInHomebrewThenTheInstallerThenPath() {
        let found = { (have: Set<String>) in ChildEnv.findUV(home: home, path: "/p1:/p2", isCommand: have.contains)?.path }
        #expect(found(["/opt/homebrew/bin/uv", "/usr/local/bin/uv"]) == "/opt/homebrew/bin/uv")
        #expect(found(["/usr/local/bin/uv", "/Users/me/.local/bin/uv"]) == "/usr/local/bin/uv")
        #expect(found(["/Users/me/.local/bin/uv", "/p1/uv"]) == "/Users/me/.local/bin/uv")
        #expect(found(["/p2/uv"]) == "/p2/uv")
        #expect(found([]) == nil)
    }

    @Test func defaultSettings() {
        let s = ServerSettings()
        #expect(s.vault == "~/.vishalakshi/vault.db" && s.stt.isEmpty && s.model.isEmpty)
    }

    @Test func theModelListHasNamesAndTheDefault() {
        let ids = ServerSettings.models.map(\.id)
        #expect(Set(ids).count == ids.count && ids.contains(ServerSettings.defaultModel))
        #expect(ServerSettings.models.allSatisfy { !$0.name.isEmpty && $0.name != $0.id })
        #expect(ServerSettings.isListed("") && ServerSettings.isListed("claude/opus") && !ServerSettings.isListed("openai/gpt-5.5"))
    }
}

@Suite struct LinkTests {
    func path(_ s: String) -> String? { Links.path(URL(string: s)!) }

    @Test func conceptLinksOpenTheConceptPage() {
        #expect(path("abhyasa://concept/reciprocal-rank-fusion") == "/c/reciprocal-rank-fusion")
        #expect(path("abhyasa://concept/Ranking") == "/c/ranking")
        #expect(path("ABHYASA://concept/ranking") == "/c/ranking")
    }

    @Test func todayAndEmptyOpenTheHomePage() {
        #expect(path("abhyasa://") == "/")
        #expect(path("abhyasa://today") == "/")
    }

    @Test func vaultLinksOpenTheVaultViewer() {
        #expect(path("abhyasa://vault/learning/reciprocal-rank-fusion") == "/v/learning/reciprocal-rank-fusion")
        #expect(path("abhyasa://vault/notes/Meeting_2026.10.27") == "/v/notes/Meeting_2026.10.27")
        #expect(path("abhyasa://vault/a/" + String(repeating: "x", count: 200)) == "/v/a/" + String(repeating: "x", count: 200))
    }

    @Test func badVaultLinksGiveNil() {
        #expect(path("abhyasa://vault/learning") == nil)
        #expect(path("abhyasa://vault/learning/") == nil)
        #expect(path("abhyasa://vault/a/b/c") == nil)
        #expect(path("abhyasa://vault/../x") == nil)
        #expect(path("abhyasa://vault/a/..") == nil)
        #expect(path("abhyasa://vault/a/...") == nil)
        #expect(path("abhyasa://vault/a/b%2Fc") == nil)
        #expect(path("abhyasa://vault/a/b%20c") == nil)
        #expect(path("abhyasa://vault/a/b%3Fc") == nil)
        #expect(path("abhyasa://vault/a/caf%C3%A9") == nil)
        #expect(path("abhyasa://vault/a/" + String(repeating: "x", count: 201)) == nil)
        #expect(path("abhyasa://vault/" + String(repeating: "s", count: 101) + "/x") == nil)
    }

    @Test func otherLinksGiveNil() {
        #expect(path("abhyasa://concept/") == nil)
        #expect(path("abhyasa://concept/a/b") == nil)
        #expect(path("abhyasa://concept/..") == nil)
        #expect(path("abhyasa://concept/a%2Fb") == nil)
        #expect(path("abhyasa://concept/a_b") == nil)
        #expect(path("abhyasa://graph") == nil)
        #expect(path("https://concept/ranking") == nil)
    }

    @Test func onlyTheAppServerIsTheServer() {
        #expect(Links.isServer(URL(string: "http://127.0.0.1:5123/c/x"), port: 5123))
        #expect(!Links.isServer(URL(string: "http://127.0.0.1:5124/"), port: 5123))
        #expect(!Links.isServer(URL(string: "http://localhost:5123/"), port: 5123))
        #expect(!Links.isServer(URL(string: "https://127.0.0.1:5123/"), port: 5123))
        #expect(!Links.isServer(URL(string: "http://127.0.0.1:5123/"), port: 0))
        #expect(Links.isServer(scheme: "http", host: "127.0.0.1", port: 5123, server: 5123))
        #expect(!Links.isServer(scheme: "http", host: "example.org", port: 5123, server: 5123))
        #expect(!Links.isServer(scheme: "http", host: "127.0.0.1", port: 80, server: 5123))
    }
}
