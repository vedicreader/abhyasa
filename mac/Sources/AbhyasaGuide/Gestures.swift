import CoreGraphics
import Foundation

/// Show while you talk: what the learner shows with the pointer while they ask. The rules are the same as `gestures` in the
/// page guide (abhyasa/blocks/guide/guide.js), and both test against tests/data/gesture_paths.json. Points are CG global points
/// (y down), with `t` in ms from the start of the question.
public enum Gestures {
    public static let hz = 30.0, keepMs = 15000.0, most = 600
    public static let dwellPx = 12.0, dwellMs = 400.0, travelPx = 40.0
    public static let turnDeg = 300.0, maxTurnDeg = 540.0, minSide = 24.0, closePx = 20.0, closeFrac = 0.35, thinPx = 3.0
    public static let loopMs = 8000.0, nearMs = 1000.0, items = 5, fadeMs = 1500.0, lenFrac = 1.5, stepFrac = 0.5

    public struct Point: Equatable, Sendable {
        public var x, y, t: Double
        public init(_ x: Double, _ y: Double, _ t: Double) { self.x = x; self.y = y; self.t = t }
    }

    public enum Kind: String, Sendable, Encodable { case circle, point }

    /// one gesture: its kind, its box `[x0, y0, x1, y1]` in the same points as the path, and its time
    public struct Gesture: Equatable, Sendable {
        public var kind: Kind
        public var box: [Double]
        public var t: Double
        var t0 = 0.0
        public static func == (a: Gesture, b: Gesture) -> Bool { a.kind == b.kind && a.box == b.box && a.t == b.t }
    }

    static func dist(_ a: Point, _ b: Point) -> Double { hypot(a.x - b.x, a.y - b.y) }
    static func dist(_ a: Point, _ x: Double, _ y: Double) -> Double { hypot(a.x - x, a.y - y) }

    /// the gestures in `path` (in time order), the latest first, at most 5. `end` is when the question ended (default: the last point).
    /// A closed smooth loop is a circle: a shaking pointer is not, and a second loop on a circle in the same second is the same circle.
    /// A still pointer after a move is a point. A rest at the end of a circle is part of the circle.
    public static func find(_ path: [Point], end: Double? = nil) -> [Gesture] {
        let pts = Array(path.suffix(most)), n = pts.count
        let end = end ?? pts.last?.t ?? 0
        var q: [Point] = []   // the path with no steps under thinPx, for the turns
        for p in pts where q.isEmpty || dist(p, q[q.count - 1]) >= thinPx { q.append(p) }
        var circles: [Gesture] = []
        var i = 0
        while i < q.count - 2 {
            var turn = 0.0, x0 = q[i].x, y0 = q[i].y, x1 = x0, y1 = y0, hit = -1, len = 0.0, step = 0.0
            var j = i + 1
            while j < q.count {
                x0 = min(x0, q[j].x); y0 = min(y0, q[j].y); x1 = max(x1, q[j].x); y1 = max(y1, q[j].y)
                let d = dist(q[j], q[j - 1]); len += d; step = max(step, d)
                if q[j].t - q[i].t > loopMs { break }
                if j >= i + 2 {
                    let ax = q[j - 1].x - q[j - 2].x, ay = q[j - 1].y - q[j - 2].y, bx = q[j].x - q[j - 1].x, by = q[j].y - q[j - 1].y
                    turn += atan2(ax * by - ay * bx, ax * bx + ay * by) * 180 / .pi
                }
                if abs(turn) > maxTurnDeg { break }
                let w = x1 - x0, h = y1 - y0
                if abs(turn) >= turnDeg, min(w, h) >= minSide, dist(q[j], q[i]) <= max(closePx, closeFrac * max(w, h)) { hit = j; break }
                j += 1
            }
            // a smooth loop only: its path is not much longer than the round of its box, and no one step jumps across it
            let half = (x1 - x0 + y1 - y0) / 2
            if hit < 0 || len > lenFrac * .pi * half || step > stepFrac * half { i += 1; continue }
            let box = [x0, y0, x1, y1].map { jsRound($0) }, t0 = q[i].t
            let same = circles.contains { g in
                g.t >= t0 - nearMs && min(box[2], g.box[2]) > max(box[0], g.box[0]) && min(box[3], g.box[3]) > max(box[1], g.box[1])
            }
            if !same { circles.append(Gesture(kind: .circle, box: box, t: jsRound(q[hit].t), t0: t0)) }
            i = hit
        }
        var points: [Gesture] = []
        var k = 0, from = 0
        while k < n {
            var j = k
            while j + 1 < n, dist(pts[j + 1], pts[k]) <= dwellPx { j += 1 }
            let until = j + 1 < n ? pts[j + 1].t : end
            if until - pts[k].t < dwellMs { k += 1; continue }
            let blob = pts[k...j], cx = blob.map(\.x).reduce(0, +) / Double(blob.count), cy = blob.map(\.y).reduce(0, +) / Double(blob.count)
            if pts[from..<k].contains(where: { dist($0, cx, cy) >= travelPx }) {   // only after a move: a hand that rests on the mouse shows nothing
                let inCircle = circles.contains { g in
                    cx >= g.box[0] - dwellPx && cx <= g.box[2] + dwellPx && cy >= g.box[1] - dwellPx && cy <= g.box[3] + dwellPx &&
                        pts[k].t >= g.t0 && pts[k].t <= g.t + nearMs
                }
                if !inCircle {
                    points.append(Gesture(kind: .point, box: [cx - dwellPx, cy - dwellPx, cx + dwellPx, cy + dwellPx].map { jsRound($0) }, t: jsRound(pts[k].t)))
                }
            }
            from = k
            k = j + 1
        }
        return Array((circles + points).sorted { $0.t > $1.t }.prefix(items))
    }

    /// Math.round of JavaScript (halves go up), so a box is the same on the page and here
    static func jsRound(_ v: Double) -> Double { (v + 0.5).rounded(.down) }

    /// one item of the focus that goes in the ask body: the same shape as the page sends
    public struct Focus: Equatable, Sendable, Encodable {
        public var kind: Kind
        /// from 0 to 1000 of the first anchor: the part of the gesture inside it
        public var box: [Int]
        public var anchors: [String]
        public var t: Int
        public var words: String?
    }

    static func area(_ b: [Double]) -> Double { max(0, b[2] - b[0]) * max(0, b[3] - b[1]) }
    static func meet(_ a: [Double], _ b: [Double]) -> [Double] { [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])] }
    static func box(_ r: CGRect) -> [Double] { [Double(r.minX), Double(r.minY), Double(r.maxX), Double(r.maxY)] }

    /// the anchors under `g`, the best first, at most 4: for a circle, those that it covers most (by the share of the two boxes);
    /// for a point, those that hold it, the smallest first
    public static func under(_ g: Gesture, _ anchors: [(id: String, frame: CGRect)]) -> [(id: String, frame: CGRect)] {
        if g.kind == .point {
            let cx = (g.box[0] + g.box[2]) / 2, cy = (g.box[1] + g.box[3]) / 2
            return Array(anchors.filter { a in let b = box(a.frame); return cx >= b[0] && cx <= b[2] && cy >= b[1] && cy <= b[3] }
                .sorted { area(box($0.frame)) < area(box($1.frame)) }.prefix(4))
        }
        let ga = area(g.box)
        let scored = anchors.map { a -> (a: (id: String, frame: CGRect), i: Double, s: Double) in
            let b = box(a.frame), i = area(meet(g.box, b)), u = ga + area(b) - i
            return (a, i, u > 0 ? i / u : 0)
        }
        return Array(scored.filter { $0.i > 0 && ($0.i >= 0.25 * ga || $0.i >= 0.5 * area(box($0.a.frame))) }.sorted { $0.s > $1.s }.prefix(4).map(\.a))
    }

    /// the focus for the ask: each gesture with its anchors and its box from 0 to 1000 of the first anchor. A gesture on no
    /// anchor is left out. `words(t)` gives what the learner typed near time `t`, or "".
    public static func focus(_ gs: [Gesture], anchors: [(id: String, frame: CGRect)], words: (Double) -> String = { _ in "" }) -> [Focus] {
        gs.compactMap { g in
            let as_ = under(g, anchors)
            guard let first = as_.first else { return nil }
            let a = box(first.frame), w = a[2] - a[0], h = a[3] - a[1], m = meet(g.box, a)
            guard w > 0, h > 0 else { return nil }
            let rel = [(m[0] - a[0]) / w, (m[1] - a[1]) / h, (m[2] - a[0]) / w, (m[3] - a[1]) / h].map { Int(jsRound(max(0, min(1, $0)) * 1000)) }
            guard rel[0] < rel[2], rel[1] < rel[3] else { return nil }
            let said = words(g.t)
            return Focus(kind: g.kind, box: rel, anchors: as_.map(\.id), t: Int(g.t), words: said.isEmpty ? nil : said)
        }
    }

    /// the last words of `said` (times and texts) a little after `t`: speech and typing come in late. At most 8 words, 80 characters.
    public static func words(_ said: [(t: Double, text: String)], at t: Double) -> String {
        let v = said.last { $0.t <= t + 1500 }?.text ?? ""
        let w = v.split(whereSeparator: { $0.isWhitespace || $0.isNewline }).suffix(8).joined(separator: " ")
        return String(w.prefix(80))
    }
}
