import Foundation
import Testing
@testable import AbhyasaGuide

/// The sample paths that the page guide tests too (tests/data/gesture_paths.json in the repo).
struct PathFile: Decodable {
    struct Want: Decodable { let kind: String; let box: [Double] }
    struct Sample: Decodable { let pts: [[Double]]; let end: Double; let want: [Want] }
    let tolerance: Double
    let paths: [String: Sample]

    static func load() throws -> PathFile {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()   // mac/Tests/AbhyasaGuideTests
            .appendingPathComponent("../../../tests/data/gesture_paths.json").standardized
        return try JSONDecoder().decode(PathFile.self, from: Data(contentsOf: url))
    }
}

func pts(_ raw: [[Double]]) -> [Gestures.Point] { raw.map { Gestures.Point($0[0], $0[1], $0[2]) } }

@Suite struct GestureTests {
    @Test func eachSharedPathGivesTheSameGesturesAsThePage() throws {
        let f = try PathFile.load()
        #expect(f.paths.count >= 10)
        for (name, s) in f.paths.sorted(by: { $0.key < $1.key }) {
            let got = Gestures.find(pts(s.pts), end: s.end)
            #expect(got.map(\.kind.rawValue) == s.want.map(\.kind), "\(name): \(got)")
            for (g, w) in zip(got, s.want) {
                #expect(zip(g.box, w.box).allSatisfy { abs($0 - $1) <= f.tolerance }, "\(name): \(g.box) is not near \(w.box)")
            }
        }
    }

    @Test func aCircleSelectsTheAnchorItCoversMost() {
        // a circle round a word inside a passage: the word wins, then the passage, then the window; a far anchor does not count
        let g = Gestures.Gesture(kind: .circle, box: [100, 100, 200, 140], t: 900)
        let anchors: [(id: String, frame: CGRect)] = [("w", CGRect(x: 0, y: 0, width: 1400, height: 900)),
                                                      ("e1", CGRect(x: 50, y: 80, width: 600, height: 200)),
                                                      ("e2", CGRect(x: 110, y: 105, width: 80, height: 30)),
                                                      ("e3", CGRect(x: 700, y: 700, width: 50, height: 50))]
        let f = Gestures.focus([g], anchors: anchors)
        #expect(f.map(\.anchors) == [["e2", "e1", "w"]])
        #expect(f[0].box == [0, 0, 1000, 1000] && f[0].kind == .circle && f[0].t == 900)
    }

    @Test func aPointSelectsTheSmallestAnchorUnderIt() {
        let g = Gestures.Gesture(kind: .point, box: [138, 108, 162, 132], t: 400)
        let anchors: [(id: String, frame: CGRect)] = [("w", CGRect(x: 0, y: 0, width: 1400, height: 900)),
                                                      ("e1", CGRect(x: 100, y: 100, width: 400, height: 100))]
        let f = Gestures.focus([g], anchors: anchors) { _ in "why is this" }
        #expect(f.map(\.anchors) == [["e1", "w"]])
        #expect(f[0].box == [95, 80, 155, 320] && f[0].words == "why is this")
        #expect(Gestures.focus([g], anchors: [("e3", CGRect(x: 700, y: 700, width: 50, height: 50))]).isEmpty)   // on no anchor: left out
    }

    @Test func theWordsAreTheLastOnesALittleAfterTheGesture() {
        let said: [(t: Double, text: String)] = [(0, ""), (500, "what"), (1800, "what is this part"), (4000, "what is this part and that")]
        #expect(Gestures.words(said, at: 400) == "what is this part")
        #expect(Gestures.words(said, at: 3000) == "what is this part and that")
        #expect(Gestures.words([], at: 0) == "")
    }

    @Test func thePathKeepsThirtyPointsASecondForFifteenSeconds() {
        var path: [Gestures.Point] = []
        #expect(PointerTrail.keep(.init(0, 0, 0), in: &path))
        #expect(!PointerTrail.keep(.init(1, 1, 20), in: &path))   // under 1/30 s after the last point
        #expect(PointerTrail.keep(.init(2, 2, 40), in: &path))
        #expect(PointerTrail.keep(.init(3, 3, 16000), in: &path) && path.count == 1)   // the old points go
        for k in 1...700 { _ = PointerTrail.keep(.init(0, 0, 16000 + Double(k) * 34), in: &path) }
        #expect(path.count <= Gestures.most)
    }

    @Test func theFocusGoesInTheBodyAndNoFocusAddsNoKey() throws {
        let a = Anchor(id: "e1", kind: "text", text: "Alpha", role: "AXStaticText", near: "visible", frame: CGRect(x: 0, y: 0, width: 10, height: 10))
        var ctx = GuideContext(page: "app:x", title: "x", app: "x", anchors: [a])
        let plain = String(decoding: try AnchorList.body(said: "why", ctx: ctx), as: UTF8.self)
        #expect(!plain.contains("focus"))
        ctx.focus = [Gestures.Focus(kind: .circle, box: [0, 0, 500, 1000], anchors: ["e1"], t: 1200, words: nil)]
        let body = try JSONSerialization.jsonObject(with: AnchorList.body(said: "why", ctx: ctx)) as? [String: Any]
        let f = ((body?["ctx"] as? [String: Any])?["focus"] as? [[String: Any]])?.first
        #expect(f?["kind"] as? String == "circle" && f?["anchors"] as? [String] == ["e1"] && f?["box"] as? [Int] == [0, 0, 500, 1000])
        #expect(f?["t"] as? Int == 1200 && f?["words"] == nil)
    }
}
