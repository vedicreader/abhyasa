import Foundation

/// The folders and files that the app keeps outside its bundle.
public struct Paths: Sendable, Equatable {
    /// ~/Library/Application Support/abhyasa
    public let support: URL
    /// ~/Library/Caches/abhyasa
    public let caches: URL

    public init(support: URL, caches: URL) {
        self.support = support
        self.caches = caches
    }

    public static var user: Paths {
        let fm = FileManager.default
        return Paths(support: fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appending(path: "abhyasa"),
                     caches: fm.urls(for: .cachesDirectory, in: .userDomainMask)[0].appending(path: "abhyasa"))
    }

    /// a copy of the pinned project from the bundle; uv syncs from here
    public var project: URL { support.appending(path: "project") }
    /// the Python environment with abhyasa in it
    public var env: URL { support.appending(path: "env") }
    /// the Python that uv downloads
    public var python: URL { support.appending(path: "python") }
    public var uvCache: URL { caches.appending(path: "uv") }
    /// the hash of the lock that the last good sync used
    public var stamp: URL { support.appending(path: "lock.sha256") }
    /// the output of the last server run
    public var log: URL { support.appending(path: "server.log") }
    /// the output of the last sync
    public var syncLog: URL { support.appending(path: "sync.log") }
    public var server: URL { env.appending(path: "bin/abhyasa") }
}
