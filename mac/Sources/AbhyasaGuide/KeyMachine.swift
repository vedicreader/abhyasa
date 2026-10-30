import Foundation

/// What the guide's key means (design 5.2, phase 2). A tap of the key says "again" while a board shows, and opens the strip to
/// type when no board shows. A hold of `hold` seconds or more opens the mic; the release sends what you said. `Esc` stops a
/// board, and the guide takes `Esc` only while a board shows.
public struct KeyMachine: Equatable {
    public enum State: Equatable { case idle, pressed(Double), talking }
    public enum Action: Equatable { case armTimer(Double), startTalk, endTalk, again, open, stop }

    public static let hold = 0.3
    public private(set) var state: State = .idle

    public init() {}

    /// the key goes down at time `t` (seconds)
    public mutating func down(_ t: Double) -> [Action] {
        guard state == .idle else { return [] }   // a repeat of the key, or a second press before the release
        state = .pressed(t)
        return [.armTimer(Self.hold)]
    }

    /// the hold timer fires at time `t`
    public mutating func tick(_ t: Double) -> [Action] {
        guard case .pressed(let t0) = state, t - t0 >= Self.hold - 0.001 else { return [] }
        state = .talking
        return [.startTalk]
    }

    /// the key comes up; `boardShows` is true while a board shows
    public mutating func up(_ t: Double, boardShows: Bool) -> [Action] {
        defer { state = .idle }
        switch state {
        case .idle: return []
        case .pressed: return [boardShows ? .again : .open]
        case .talking: return [.endTalk]
        }
    }

    /// `Esc` while the guide holds it
    public func escape(boardShows: Bool) -> [Action] { boardShows ? [.stop] : [] }

    /// whether the guide must hold `Esc` now; at other times the app in front gets it
    public static func wantsEscape(boardShows: Bool) -> Bool { boardShows }
}
