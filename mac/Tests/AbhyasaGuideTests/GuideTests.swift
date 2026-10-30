import Foundation
import Testing
@testable import AbhyasaGuide

// Two displays: a laptop (main, 1512 x 982 points at 2x) and a monitor (2560 x 1440 at 1x) to its right, its top 200 points
// above the laptop's top. AppKit y goes up from the bottom of the main display.
let laptop = Display(id: 1, frame: CGRect(x: 0, y: 0, width: 1512, height: 982), scale: 2)
let monitor = Display(id: 2, frame: CGRect(x: 1512, y: -258, width: 2560, height: 1440), scale: 1)
let both = [laptop, monitor]

@Suite struct GeometryTests {
    @Test func cgToAppKitFlipsOnTheMainDisplayHeight() {
        let r = Geometry.appKit(fromCG: CGRect(x: 100, y: 50, width: 200, height: 30), mainHeight: 982)
        #expect(r == CGRect(x: 100, y: 982 - 80, width: 200, height: 30))
        #expect(Geometry.cg(fromAppKit: r, mainHeight: 982) == CGRect(x: 100, y: 50, width: 200, height: 30))
    }

    @Test func panelPointsOnTheMainDisplayAreTheCGPoints() {
        let r = CGRect(x: 100, y: 50, width: 200, height: 30)
        #expect(Geometry.panel(fromCG: r, display: laptop, mainHeight: 982) == r)
    }

    @Test func panelPointsOnASecondDisplayStartAtItsTopLeft() {
        // the monitor's top left in CG: x 1512, y = 982 - (-258 + 1440) = -200
        let r = CGRect(x: 1512 + 40, y: -200 + 10, width: 100, height: 20)
        #expect(Geometry.panel(fromCG: r, display: monitor, mainHeight: 982) == CGRect(x: 40, y: 10, width: 100, height: 20))
    }

    @Test func theScaleNeverChangesAPosition() {
        let hi = Display(id: 3, frame: monitor.frame, scale: 2)
        let r = CGRect(x: 1600, y: 300, width: 50, height: 50)
        #expect(Geometry.panel(fromCG: r, display: hi, mainHeight: 982) == Geometry.panel(fromCG: r, display: monitor, mainHeight: 982))
    }

    @Test func aRectGoesToTheDisplayOfItsCentre() {
        let onMonitor = Geometry.appKit(fromCG: CGRect(x: 1400, y: 100, width: 400, height: 100), mainHeight: 982)   // centre x 1600
        #expect(Geometry.display(for: onMonitor, in: both)?.id == 2)
        let onLaptop = Geometry.appKit(fromCG: CGRect(x: 10, y: 10, width: 100, height: 100), mainHeight: 982)
        #expect(Geometry.display(for: onLaptop, in: both)?.id == 1)
        #expect(Geometry.display(for: CGRect(x: -9000, y: -9000, width: 5, height: 5), in: both)?.id == 1)   // off all: the main one
    }

    @Test func aRectAcrossTwoDisplaysSplitsInTwo() {
        let parts = Geometry.split(CGRect(x: 1400, y: 100, width: 300, height: 50), in: both)
        #expect(parts.map(\.0.id) == [1, 2])
        #expect(parts[0].1.width == 112 && parts[1].1.width == 188)
    }

    @Test func captureSizeFitsTheModelSizeAndKeepsTheShape() {
        #expect(Geometry.captureSize(window: CGSize(width: 1440, height: 900), scale: 2) == CGSize(width: 1280, height: 800))
        #expect(Geometry.captureSize(window: CGSize(width: 400, height: 300), scale: 2) == CGSize(width: 800, height: 600))   // never larger
        #expect(Geometry.captureSize(window: .zero, scale: 2) == .zero)
    }

    @Test func aPictureBoxMapsToTheWindowInPoints() {
        let r = Geometry.cg(fromPicture: CGRect(x: 640, y: 400, width: 128, height: 80), picture: CGSize(width: 1280, height: 800),
                            window: CGRect(x: 100, y: 50, width: 1440, height: 900))
        #expect(r == CGRect(x: 100 + 720, y: 50 + 450, width: 144, height: 90))
    }
}

@Suite struct AnchorListTests {
    let win = FrontWindow(app: "Safari", bundle: "com.apple.Safari", title: "Hugging Face – Hub", frame: CGRect(x: 0, y: 0, width: 1000, height: 800), windowID: 7)

    @Test func theTargetComesFirstThenTheSelectionThenTheWindow() {
        let items = [AXItem(role: "AXStaticText", text: "far", frame: CGRect(x: 900, y: 700, width: 50, height: 20)),
                     AXItem(role: "AXStaticText", text: "near", frame: CGRect(x: 110, y: 110, width: 50, height: 20)),
                     AXItem(role: "AXStaticText", text: "the selected words", frame: CGRect(x: 300, y: 300, width: 80, height: 16), near: .selection),
                     AXItem(role: "AXButton", text: "Train", frame: CGRect(x: 100, y: 100, width: 60, height: 24), near: .target)]
        let c = AnchorList.build(window: win, items: items)
        #expect(c.anchors.map(\.id) == ["t", "s", "w", "e1", "e2"])
        #expect(c.anchors[0].text == "button: Train")
        #expect(c.anchors[2].text == "Safari · Hugging Face – Hub" && c.anchors[2].kind == "title")
        #expect(c.anchors[3].text == "near" && c.anchors[4].text == "far")   // nearest to the target first
        #expect(c.page == "app:com.apple.Safari" && c.title == "Safari · Hugging Face – Hub" && c.app == "Safari")
    }

    @Test func secureFieldsAndPartsOutOfTheWindowAreLeftOut() {
        let items = [AXItem(role: "AXSecureTextField", text: "hunter2", frame: CGRect(x: 10, y: 10, width: 100, height: 20), secure: true),
                     AXItem(role: "AXStaticText", text: "outside", frame: CGRect(x: 5000, y: 10, width: 100, height: 20)),
                     AXItem(role: "AXStaticText", text: "   ", frame: CGRect(x: 10, y: 40, width: 100, height: 20))]
        let c = AnchorList.build(window: win, items: items)
        #expect(c.anchors.map(\.id) == ["w"])
        #expect(AnchorList.isSecret(role: "AXTextField", subrole: "", name: "API key"))
        #expect(AnchorList.isSecret(role: "AXTextField", subrole: "AXSecureTextField", name: ""))
        #expect(!AnchorList.isSecret(role: "AXStaticText", subrole: "", name: "token economy"))
    }

    @Test func withALimitOnlyTheWindowGoes() {
        let items = [AXItem(role: "AXStaticText", text: "x", frame: CGRect(x: 10, y: 10, width: 10, height: 10))]
        for l in [Limit.noAccess, .password, .neverLook("Mail")] {
            #expect(AnchorList.build(window: win, items: items, limit: l).anchors.map(\.id) == ["w"])
        }
    }

    @Test func textIsCutTo300AndTheListTo40() {
        let long = String(repeating: "word ", count: 200)
        let items = (0..<60).map { AXItem(role: "AXStaticText", text: "\($0) " + long, frame: CGRect(x: 10, y: 10 + Double($0) * 10, width: 300, height: 9)) }
        let c = AnchorList.build(window: win, items: items)
        #expect(c.anchors.count == AnchorList.most)
        #expect(c.anchors.allSatisfy { $0.text.count <= AnchorList.textMost })
        #expect(c.anchors.reduce(0) { $0 + $1.text.count } <= AnchorList.totalMost)
        #expect(c.anchors[1].kind == "passage")
        #expect(c.anchors.allSatisfy { $0.id.range(of: #"^[A-Za-z0-9:_-]{1,40}$"#, options: .regularExpression) != nil })
    }

    @Test func theSameThingTwiceIsOneAnchor() {
        let a = AXItem(role: "AXStaticText", text: "Loss", frame: CGRect(x: 10, y: 10, width: 40, height: 12))
        #expect(AnchorList.build(window: win, items: [a, a]).anchors.count == 2)   // the window and one "Loss"
    }

    @Test func theBodyHasSaidAndCtxWithNoFrames() throws {
        let c = AnchorList.build(window: win, items: [AXItem(role: "AXImage", text: "", frame: CGRect(x: 10, y: 10, width: 40, height: 40))])
        let d = try AnchorList.body(said: "  I don't get\nthis  ", ctx: c)
        let o = try #require(try JSONSerialization.jsonObject(with: d) as? [String: Any])
        #expect(o["said"] as? String == "I don't get this")
        let ctx = try #require(o["ctx"] as? [String: Any])
        #expect(ctx["page"] as? String == "app:com.apple.Safari")
        let anchors = try #require(ctx["anchors"] as? [[String: Any]])
        #expect(anchors.count == 2)
        #expect(anchors[1]["kind"] as? String == "figure")
        #expect(Set(anchors[0].keys) == ["id", "kind", "text", "role", "near"])
    }

    @Test func noWindowGivesAnEmptyList() {
        let c = AnchorList.build(window: nil, items: [])
        #expect(c.anchors.isEmpty && c.page == "app:")
    }
}

@Suite struct SSETests {
    @Test func eventsCanComeInPieces() {
        var p = SSEParser()
        #expect(p.feed("data: {\"wait\": \"The tutor looks").isEmpty)
        #expect(p.feed(" in your vault.\"}\n").isEmpty)
        #expect(p.feed("\n") == [#"{"wait": "The tutor looks in your vault."}"#])
    }

    @Test func commentsAreIgnoredAndCRLFWorks() {
        var p = SSEParser()
        #expect(p.feed(": still listening\r\n\r\ndata: {\"error\": \"x\"}\r\n\r\n") == [#"{"error": "x"}"#])
    }

    @Test func aCRLFSplitAcrossTwoChunksIsOneLineEnd() {
        var p = SSEParser()
        #expect(p.feed("data: a\r").isEmpty)
        #expect(p.feed("\n\r\n") == ["a"])
    }

    @Test func twoDataLinesJoinWithANewLine() {
        var p = SSEParser()
        #expect(p.feed("data: one\ndata:two\nevent: x\n\n") == ["one\ntwo"])
    }

    @Test func theGuideEventsHaveTheirKinds() throws {
        #expect(GuideEvent.parse(#"{"wait": "w"}"#)?.kind == .wait("w"))
        #expect(GuideEvent.parse(#"{"step": {"say": "s", "strokes": []}, "k": 2, "tier": "tutor"}"#)?.kind == .step(2))
        #expect(GuideEvent.parse(#"{"board": {"steps": []}}"#)?.kind == .board)
        #expect(GuideEvent.parse(#"{"error": "e"}"#)?.kind == .error("e"))
        #expect(GuideEvent.parse(#"{"x": 1}"#)?.kind == .other)
        #expect(GuideEvent.parse("not json") == nil)
        #expect(try #require(GuideEvent.parse(#"{"board": {}}"#)).isLast)
        #expect(try !#require(GuideEvent.parse(#"{"step": {}, "k": 0}"#)).isLast)
    }

    @Test func aWaitCanTellTheStateAndWhoGetsTheText() throws {
        let e = try #require(GuideEvent.parse(#"{"wait": "Asks Claude Sonnet.", "state": "asking", "model": "Claude Sonnet", "where": "hosted", "who": "Anthropic"}"#))
        #expect(e.kind == .wait("Asks Claude Sonnet."))
        #expect(e.status == GuideEvent.Status(state: "asking", model: "Claude Sonnet", place: "hosted", who: "Anthropic"))
        let q = try #require(GuideEvent.parse(#"{"wait": "Searches the web.", "state": "searching", "query": "rnn speed", "sources": 2}"#))
        #expect(q.status?.query == "rnn speed" && q.status?.sources == 2 && q.status?.model == nil)
    }

    @Test func anOldWaitHasNoStatus() throws {
        #expect(try #require(GuideEvent.parse(#"{"wait": "w"}"#)).status == nil)
        #expect(try #require(GuideEvent.parse(#"{"wait": "w", "state": 3}"#)).status == nil)   // a wrong type reads as missing
    }

    @Test func aSavedEventHasItsTitleAndUndo() throws {
        let e = try #require(GuideEvent.parse(#"{"saved": {"title": "Attention", "url": "https://x.org/a", "undo": "/guide/undo/7"}}"#))
        #expect(e.kind == .saved(GuideEvent.Saved(title: "Attention", url: "https://x.org/a", undo: "/guide/undo/7")))
        #expect(!e.isLast)
        let bare = try #require(GuideEvent.parse(#"{"saved": {}}"#))
        #expect(bare.kind == .saved(GuideEvent.Saved(title: "", url: "", undo: "")))
    }
}

@Suite struct KeyMachineTests {
    @Test func aTapOpensTheStripWhenNoBoardShows() {
        var m = KeyMachine()
        #expect(m.down(10) == [.armTimer(KeyMachine.hold)])
        #expect(m.up(10.1, boardShows: false) == [.open])
        #expect(m.state == .idle)
    }

    @Test func aTapSaysAgainWhileABoardShows() {
        var m = KeyMachine()
        _ = m.down(10)
        #expect(m.up(10.1, boardShows: true) == [.again])
    }

    @Test func aHoldTalksAndTheReleaseSends() {
        var m = KeyMachine()
        _ = m.down(10)
        #expect(m.tick(10.1).isEmpty)   // too soon
        #expect(m.tick(10.3) == [.startTalk])
        #expect(m.state == .talking)
        #expect(m.up(12, boardShows: true) == [.endTalk])
        #expect(m.state == .idle)
    }

    @Test func aRepeatOfTheKeyDoesNothing() {
        var m = KeyMachine()
        _ = m.down(10)
        #expect(m.down(10.05).isEmpty)
        _ = m.tick(10.3)
        #expect(m.down(10.4).isEmpty)
    }

    @Test func aLateTimerAfterTheReleaseDoesNothing() {
        var m = KeyMachine()
        _ = m.down(10)
        _ = m.up(10.1, boardShows: false)
        #expect(m.tick(10.3).isEmpty)
        #expect(m.up(10.4, boardShows: false).isEmpty)
    }

    @Test func escStopsOnlyABoard() {
        let m = KeyMachine()
        #expect(m.escape(boardShows: true) == [.stop])
        #expect(m.escape(boardShows: false).isEmpty)
        #expect(KeyMachine.wantsEscape(boardShows: true) && !KeyMachine.wantsEscape(boardShows: false))
    }
}

@Suite struct AudioTests {
    @Test func wordIndexCountsWordsAsBoardJSDoes() {
        let t = "Look at  the loss\ncurve"
        #expect(Audio.wordIndex(t, at: 0) == 0)
        #expect(Audio.wordIndex(t, at: 5) == 1)
        #expect(Audio.wordIndex(t, at: 9) == 2)
        #expect(Audio.wordIndex(t, at: 18) == 4)
        #expect(Audio.wordIndex("", at: 3) == 0)
    }

    @Test func wavHasAHeaderThatTheServerReads() {
        let d = Audio.wav([0, 1000, -1000, 32767], rate: 16000)
        #expect(d.count == 44 + 8)
        #expect(String(decoding: d.prefix(4), as: UTF8.self) == "RIFF")
        #expect(String(decoding: d[8..<12], as: UTF8.self) == "WAVE")
        let rate = d[24..<28].enumerated().reduce(0) { $0 | Int($1.element) << (8 * $1.offset) }
        #expect(rate == 16000)
        #expect(Audio.pcm16([2, -2, 0.5]) == [32767, -32767, 16383])
    }
}

@Suite struct TextTests {
    @Test func theWordsNameTheAppAndTheKey() {
        #expect(GuideText.windowOnly("Preview").contains("Preview"))
        #expect(GuideText.accessBody("Xcode").contains("Accessibility"))
        #expect(GuideText.micOn.contains("Caps+E"))
        #expect(GuideText.end == "In the tutor's own words. No source found.")
    }
}
