import Foundation
import Testing
@testable import AbhyasaGuide

/// The thread of a window: its bounds and when it clears. No launch, no window.
@Suite struct GuideThreadTests {
    let safari = GuideThread.key(bundle: "com.apple.Safari", title: "Attention Is All You Need")

    @Test func aBoardAddsATurnAndTheNextQuestionGetsIt() {
        var t = GuideThread()
        #expect(t.current(key: safari, now: 0).isEmpty)
        t.keep(said: "I don't get alpha bar", says: ["Alpha bar is the share that is left.", "It falls as t grows."], tier: "tutor", key: safari, now: 10)
        #expect(t.current(key: safari, now: 20) == [.init(said: "I don't get alpha bar", says: ["Alpha bar is the share that is left.", "It falls as t grows."], t: "tutor")])
        #expect(t.last == "I don't get alpha bar")
    }

    @Test func theThreadKeepsTheLastThreeTurnsAndCutsEachLine() {
        var t = GuideThread()
        for k in 0..<5 { t.keep(said: "question \(k)", says: ["a line"], tier: "web", key: safari, now: Double(k)) }
        #expect(t.turns.map(\.said) == ["question 2", "question 3", "question 4"])
        t.keep(said: "long", says: [String(repeating: "x", count: 200)] + Array(repeating: "y", count: 9), tier: "magic", key: safari, now: 6)
        let l = t.turns.last!
        #expect(l.says.count == 6 && l.says[0].count == 160 && l.t == "tutor")
    }

    @Test func atMost1500CharactersStayAndTheOldestGoesFirst() {
        var t = GuideThread()
        for k in 0..<3 { t.keep(said: "q\(k)", says: Array(repeating: String(repeating: "y", count: 160), count: 6), tier: "tutor", key: safari, now: Double(k)) }
        #expect(t.turns.map(\.said) == ["q2"])
        #expect(t.turns.reduce(0) { $0 + GuideThread.size($1) } <= GuideThread.total)
    }

    @Test func aBoardWithNoLineAddsNothing() {
        var t = GuideThread()
        t.keep(said: "why?", says: [], tier: "tutor", key: safari, now: 0)
        t.keep(said: "  ", says: ["a line"], tier: "tutor", key: safari, now: 0)
        #expect(t.turns.isEmpty && t.last == nil)
    }

    @Test func anotherWindowClearsTheThread() {
        var t = GuideThread()
        t.keep(said: "what is this", says: ["A line."], tier: "tutor", key: safari, now: 0)
        #expect(t.current(key: GuideThread.key(bundle: "com.apple.Safari", title: "Another page"), now: 1).isEmpty)
        #expect(t.current(key: safari, now: 2).isEmpty)   // back to the first window: the thread is gone
    }

    @Test func tenMinutesWithNoQuestionClearTheThread() {
        var t = GuideThread()
        t.keep(said: "what is this", says: ["A line."], tier: "tutor", key: safari, now: 0)
        #expect(t.current(key: safari, now: 540).count == 1)   // 9 minutes: it stays
        t.asked(now: 540)
        #expect(t.current(key: safari, now: 1100).count == 1)   // the question at 9 minutes started the 10 minutes again
        #expect(t.current(key: safari, now: 1141).isEmpty)
    }

    @Test func startFreshClearsTheThread() {
        var t = GuideThread()
        t.keep(said: "what is this", says: ["A line."], tier: "tutor", key: safari, now: 0)
        t.clear()
        #expect(t.current(key: safari, now: 1).isEmpty)
    }

    @Test func theLinesOfABoardEvent() {
        let raw = #"{"board": {"tier": "vault", "steps": [{"say": "One.", "strokes": []}, {"say": "Two."}]}, "point": "dot"}"#
        let b = GuideThread.board(raw)
        #expect(b?.says == ["One.", "Two."] && b?.tier == "vault")
        #expect(GuideThread.board(#"{"step": {"say": "One."}, "k": 1}"#) == nil)
    }

    @Test func theBodyHasTheThreadOnlyWhenThereIsOne() throws {
        var ctx = AnchorList.build(window: FrontWindow(app: "Safari", bundle: "com.apple.Safari", title: "A page", frame: CGRect(x: 0, y: 0, width: 100, height: 100)), items: [])
        #expect(!String(decoding: try AnchorList.body(said: "x", ctx: ctx), as: UTF8.self).contains("thread"))
        ctx.thread = [.init(said: "what is this", says: ["A line."], t: "tutor")]
        let o = try JSONSerialization.jsonObject(with: try AnchorList.body(said: "why?", ctx: ctx)) as? [String: Any]
        let th = (o?["ctx"] as? [String: Any])?["thread"] as? [[String: Any]]
        #expect(th?.first?["said"] as? String == "what is this" && th?.first?["says"] as? [String] == ["A line."] && th?.first?["t"] as? String == "tutor")
    }

    @Test func theWordsOfTheThread() {
        #expect(GuideText.followsUp("what is this") == "Follows up on: what is this")
        #expect(GuideText.followsUp(String(repeating: "a", count: 80)).count == "Follows up on: ".count + 60)
        #expect(GuideText.sends(parts: 3, to: "Claude Sonnet", local: false, thread: true)
                == "Sends your question, the window title, 3 text parts and your last questions on this window to Claude Sonnet.")
        #expect(GuideText.sends(parts: 0, to: "Gemma", local: true) == "Sends your question and the window title to Gemma. Nothing leaves this Mac.")
    }
}
