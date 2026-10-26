import Foundation
import CryptoKit

/// The pinned project in the bundle, and the check that tells if the environment must sync again.
public enum Lock {
    /// the files of the pinned project, in the order that the hash reads them
    public static let files = ["pyproject.toml", "uv.lock"]

    /// SHA-256 over the names and contents of `files` in `dir`
    public static func hash(dir: URL) throws -> String {
        var h = SHA256()
        for name in files {
            h.update(data: Data(name.utf8))
            h.update(data: try Data(contentsOf: dir.appending(path: name)))
        }
        return h.finalize().map { String(format: "%02x", $0) }.joined()
    }

    /// true when the last good sync used another lock, or the environment has no `abhyasa` command
    public static func needsSync(hash: String, paths: Paths,
                                 isCommand: (String) -> Bool = FileManager.default.isExecutableFile(atPath:)) -> Bool {
        let old = (try? String(contentsOf: paths.stamp, encoding: .utf8))?.trimmingCharacters(in: .whitespacesAndNewlines)
        return old != hash || !isCommand(paths.server.path)
    }

    /// copies the pinned project from the bundle to `paths.project`, so uv never writes in the bundle
    public static func copyProject(from dir: URL, paths: Paths, fm: FileManager = .default) throws {
        try fm.createDirectory(at: paths.project, withIntermediateDirectories: true)
        for name in files {
            let dst = paths.project.appending(path: name)
            if fm.fileExists(atPath: dst.path) { try fm.removeItem(at: dst) }
            try fm.copyItem(at: dir.appending(path: name), to: dst)
        }
    }

    public static func writeStamp(_ hash: String, paths: Paths) throws {
        try FileManager.default.createDirectory(at: paths.support, withIntermediateDirectories: true)
        try Data((hash + "\n").utf8).write(to: paths.stamp, options: .atomic)
    }
}
