import Foundation
import Testing
@testable import AbhyasaCore

@Suite struct ResearchTests {
    let walk = ResearchWalk(id: "fine-tune-1a2b", title: "Fine-tune Diffusion for Comics", url: "/w/fine-tune-1a2b?plan=1#gather", end: 2000, have: 9, total: 11)

    @Test func theAppRunsUntilYouQuitIt() {
        #expect(!Life.quitOnLastWindow)                   // closing the window never quits: the server and research go on
        #expect(Life.reopen(visibleWindows: false))       // the Dock icon opens the window again
        #expect(!Life.reopen(visibleWindows: true))
    }

    @Test func notificationTextIsPlain() {
        #expect(Research.notifyTitle == "Sources are ready")
        #expect(Research.notifyBody(walk) == "Sources for your walk \u{2018}Fine-tune Diffusion for Comics\u{2019} are ready. 9 of 11 ideas have a source.")
        let one = ResearchWalk(id: "a", title: "A", url: "/w/a", end: 1, have: 1, total: 1)
        #expect(Research.notifyBody(one).hasSuffix("1 of 1 idea has a source."))
    }

    @Test func tellsEachEndOnceAndNothingFromBeforeTheStart() {
        let old = ResearchWalk(id: "old", title: "Old", url: "/w/old", end: 500, have: 1, total: 2)
        let s = ResearchStatus(running: [], ended: [walk, old])
        #expect(Research.toTell(s, since: 1000, told: []) == [walk])
        #expect(Research.toTell(s, since: 1000, told: [Research.key(walk)]).isEmpty)
    }

    @Test func parsesTheServerStateAndOpensOnlyAWalkPage() throws {
        let json = #"{"running": [{"key": "walk:r:research", "kind": "research", "id": "r", "title": "R", "url": "/w/r#sources", "end": null, "have": 0, "total": 3},"# +
                   #" {"key": "build:1", "kind": "build", "title": "A walk from a link", "url": "", "end": null}], "ended": []}"#
        let s = try #require(Research.parse(Data(json.utf8)))
        #expect(s.running.count == 1 && s.running[0].id == "r" && s.running[0].end == nil && s.ended.isEmpty)   // a build is not research
        #expect(Research.walkPath(walk) == "/w/fine-tune-1a2b?plan=1#gather")
        #expect(Research.walkPath(ResearchWalk(id: "x", title: "X", url: "https://evil.example/w/x", end: 1, have: 0, total: 1)) == nil)
        #expect(Research.parse(Data("not json".utf8)) == nil)
    }

    @Test func statusReadsTheServer() async throws {
        let p = try Port.free()
        let s = FakeServer(["/jobs.json": (200, #"{"running": [], "ended": []}"#)])
        try s.start(port: p)
        defer { s.stop() }
        #expect(await Research.status(Port.base(p)) == .idle)
    }
}
