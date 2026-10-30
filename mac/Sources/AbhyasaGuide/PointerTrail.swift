import AppKit

/// Show while you talk, over other apps. While the guide asks (the key is held, or the strip is open), a global monitor of mouse
/// moves keeps the pointer path in memory: CG global points, at most 30 a second, the last 15 s and 600 points. The question
/// takes the path, and nothing of it stays. The monitor is off at all other times. It uses the Accessibility permission that
/// the guide already explains, and asks for nothing new.
@MainActor
public final class PointerTrail {
    /// the path and what the strip box said with it, as the question takes them
    public struct Shown: Sendable {
        public var points: [Gestures.Point]
        public var said: [(t: Double, text: String)]
        public var end: Double
    }

    var monitor: Any?
    var t0 = 0.0, mainHeight: CGFloat = 0
    var points: [Gestures.Point] = []
    var said: [(t: Double, text: String)] = []
    var rung = Set<String>()
    var still: Timer?
    /// the trail of the last 1.5 s (CG global points), a ring on each gesture as the learner makes it, and the end of both
    var onTrail: (([CGPoint]) -> Void)?
    var onRing: ((Gestures.Gesture) -> Void)?
    var onEnd: (() -> Void)?
    /// the text in the strip box now
    var text: () -> String = { "" }

    public init() {}

    public var isOn: Bool { monitor != nil }
    var now: Double { ProcessInfo.processInfo.systemUptime * 1000 - t0 }

    public func start() {
        guard monitor == nil else { return }
        t0 = ProcessInfo.processInfo.systemUptime * 1000
        mainHeight = Geometry.mainHeight(Display.all)
        points = []; said = []; rung = []
        monitor = NSEvent.addGlobalMonitorForEvents(matching: [.mouseMoved, .leftMouseDragged]) { [weak self] _ in
            MainActor.assumeIsolated { self?.moved() }
        }
    }

    /// the path, and the end of the monitor; nil when it was off
    @discardableResult
    public func stop() -> Shown? {
        guard let m = monitor else { return nil }
        NSEvent.removeMonitor(m)
        monitor = nil
        still?.invalidate()
        heard()
        let out = Shown(points: points, said: said, end: now)
        points = []; said = []
        onEnd?()
        return out
    }

    /// adds `p` to `path` when it is 1/30 s or more after the last point, and drops the points older than 15 s and over 600
    nonisolated public static func keep(_ p: Gestures.Point, in path: inout [Gestures.Point]) -> Bool {
        if let last = path.last, p.t - last.t < 1000 / Gestures.hz { return false }
        path.append(p)
        path.removeFirst(path.filter { p.t - $0.t > Gestures.keepMs }.count)
        if path.count > Gestures.most { path.removeFirst(path.count - Gestures.most) }
        return true
    }

    func heard() {
        let v = text()
        if said.last?.text != v { said.append((now, v)) }
    }

    func moved() {
        let m = NSEvent.mouseLocation, t = now
        guard Self.keep(Gestures.Point(Double(m.x), Double(mainHeight - m.y), t.rounded()), in: &points) else { return }
        heard()
        onTrail?(points.filter { t - $0.t < Gestures.fadeMs }.map { CGPoint(x: $0.x, y: $0.y) })
        spot()
        still?.invalidate()   // a still pointer shows its ring
        still = Timer.scheduledTimer(withTimeInterval: (Gestures.dwellMs + 50) / 1000, repeats: false) { [weak self] _ in
            MainActor.assumeIsolated { self?.spot() }
        }
    }

    /// rings each gesture of the last 4 s once
    func spot() {
        guard monitor != nil else { return }
        let t = now
        for g in Gestures.find(points.filter { t - $0.t < 4000 }, end: t) {
            let k = "\(g.kind.rawValue)\(Int((g.box[0] / 24).rounded())):\(Int((g.box[1] / 24).rounded()))"
            if rung.insert(k).inserted { onRing?(g) }
        }
    }

    /// the focus of a question: the gestures of `shown`, mapped to the anchors (CG global frames)
    nonisolated public static func focus(_ shown: Shown?, anchors: [Anchor]) -> [Gestures.Focus] {
        guard let s = shown, !s.points.isEmpty else { return [] }
        return Gestures.focus(Gestures.find(s.points, end: s.end), anchors: anchors.map { ($0.id, $0.frame) },
                              words: { Gestures.words(s.said, at: $0) })
    }
}
