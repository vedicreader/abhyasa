import Foundation

/// The settings that the server reads: the model, the speech engine and the vault.
public struct ServerSettings: Equatable, Sendable {
    /// a rishi model name; empty gives the server default
    public var model: String
    /// `gemma` or `whisper`
    public var stt: String
    public var vault: String

    public init(model: String = "", stt: String = "gemma", vault: String = ServerSettings.defaultVault) {
        self.model = model
        self.stt = stt
        self.vault = vault
    }

    public static let defaultVault = "~/.vishalakshi/vault.db"
    public static let defaultModel = "claude/sonnet"
    public static let engines = ["gemma", "whisper"]
}

/// The command lines and environments for uv and the server. A GUI app does not get the shell environment, so the
/// app sets each value that the children need.
public enum ChildEnv {
    /// the folders that hold `claude` and the other tools; a GUI app gets only /usr/bin:/bin:/usr/sbin:/sbin
    public static let toolDirs = ["~/.local/bin", "/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin",
                                  "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    /// variables from the parent that could send the children to another Python or another vault
    static let dropped = ["VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP"]
    static let droppedPrefixes = ["UV_", "ABHYASA_"]

    public static func expand(_ p: String, home: String) -> String {
        p == "~" ? home : p.hasPrefix("~/") ? home + p.dropFirst(1) : p
    }

    /// `first`, then `toolDirs`, then the inherited entries, each one time
    public static func path(first: [String], home: String, inherited: String?) -> String {
        var seen = Set<String>(), out = [String]()
        for d in first + toolDirs.map({ expand($0, home: home) }) + (inherited ?? "").split(separator: ":").map(String.init)
        where !d.isEmpty && seen.insert(d).inserted { out.append(d) }
        return out.joined(separator: ":")
    }

    static func base(_ parent: [String: String], home: String, first: [String]) -> [String: String] {
        var e = parent.filter { k, _ in !dropped.contains(k) && !droppedPrefixes.contains { k.hasPrefix($0) } }
        e["HOME"] = home
        e["PATH"] = path(first: first, home: home, inherited: parent["PATH"])
        if e["LANG"] == nil { e["LANG"] = "en_US.UTF-8" }
        e["NO_COLOR"] = "1"
        return e
    }

    /// the places to look for uv, in order: Homebrew on Apple Silicon, Homebrew on Intel, the uv installer
    public static let uvPlaces = ["/opt/homebrew/bin/uv", "/usr/local/bin/uv", "~/.local/bin/uv"]

    /// the first uv in `uvPlaces`, then in the folders of `path`; nil when there is no uv
    public static func findUV(home: String, path: String?,
                              isCommand: (String) -> Bool = FileManager.default.isExecutableFile(atPath:)) -> URL? {
        let dirs = (path ?? "").split(separator: ":").map { "\($0)/uv" }
        return (uvPlaces.map { expand($0, home: home) } + dirs).first(where: isCommand).map { URL(fileURLWithPath: $0) }
    }

    public static let uvInstall = "brew install uv"

    public static func uvArgs(_ paths: Paths) -> [String] {
        ["sync", "--frozen", "--no-install-project", "--project", paths.project.path]
    }

    /// uv puts the environment, the Python and its cache in the app's folders, and reads no user uv config
    public static func uv(_ parent: [String: String], home: String, paths: Paths) -> [String: String] {
        var e = base(parent, home: home, first: [])
        e["UV_PROJECT_ENVIRONMENT"] = paths.env.path
        e["UV_PYTHON_INSTALL_DIR"] = paths.python.path
        e["UV_CACHE_DIR"] = paths.uvCache.path
        e["UV_PYTHON_PREFERENCE"] = "only-managed"
        e["UV_NO_CONFIG"] = "1"
        e["UV_NO_PROGRESS"] = "1"
        return e
    }

    public static func serverArgs(port: Int, settings: ServerSettings, home: String) -> [String] {
        ["--port", String(port), "--vault", expand(settings.vault, home: home)]
    }

    public static func server(_ parent: [String: String], home: String, paths: Paths, settings: ServerSettings) -> [String: String] {
        var e = base(parent, home: home, first: [paths.env.appending(path: "bin").path])
        let model = settings.model.trimmingCharacters(in: .whitespaces)
        if !model.isEmpty { e["ABHYASA_MODEL"] = model }
        e["ABHYASA_STT"] = settings.stt
        e["ABHYASA_VAULT"] = expand(settings.vault, home: home)
        e["VIRTUAL_ENV"] = paths.env.path
        e["PYTHONUNBUFFERED"] = "1"
        return e
    }
}
