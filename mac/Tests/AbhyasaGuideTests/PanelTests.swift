import AppKit
import Foundation
import Testing
@testable import AbhyasaGuide

@Suite struct OverlayPageTests {
    @Test func boxesAreInThePanelPointsOfTheirDisplay() {
        let a = Anchor(id: "e1", kind: "text", text: "x", role: "AXStaticText", near: "visible", frame: CGRect(x: 1552, y: -190, width: 100, height: 20))
        #expect(OverlayPage.boxes([a], display: monitor, mainHeight: 982) == [OverlayPage.Box(id: "e1", rect: CGRect(x: 40, y: 10, width: 100, height: 20))])
    }

    @Test func jsTextIsSafeForThePage() throws {
        let s = try #require(OverlayPage.js(["</script>\u{2028}"]))
        #expect(!s.contains("\u{2028}"))
        #expect(s.contains("\\u2028"))
    }

    @Test func thePageLoadsBoardJSFromTheServerAndHasNoOtherScriptSource() {
        let h = OverlayPage.html
        #expect(h.contains(#"<script src="/assets/board.js"></script>"#))
        #expect(h.contains("assets: '/vendor/'"))
        #expect(!h.contains("http://") && !h.contains("https://"))
        #expect(h.contains("background: transparent"))
    }

    @Test func thePointLookOfTheServerGoesToBoardJS() throws {
        let e = try #require(GuideEvent.parse(#"{"step": {"say": "x", "strokes": []}, "k": 1, "tier": "tutor", "point": "dot"}"#))
        #expect(e.kind == .step(1) && e.raw.contains(#""point": "dot""#))   // the raw event goes to overlay.event as it came
        #expect(OverlayPage.html.contains("if (typeof m.point === 'string') point = m.point;"))
        #expect(OverlayPage.html.contains("const opts = () => ({host, labels: {}, point});"))
    }
}

/// The panels are made but never ordered front: no window shows and nothing takes the focus.
@MainActor @Suite struct PanelTests {
    @Test func theOverlayPanelNeverTakesAClickOrTheFocus() {
        let p = OverlayPanel(display: monitor)
        #expect(!p.isVisible)
        #expect(p.styleMask.contains(.nonactivatingPanel) && p.styleMask.contains(.borderless))
        #expect(p.ignoresMouseEvents)
        #expect(!p.canBecomeKey && !p.canBecomeMain)
        #expect(p.collectionBehavior.contains(.canJoinAllSpaces))
        #expect(p.collectionBehavior.contains(.fullScreenAuxiliary))
        #expect(p.collectionBehavior.contains(.stationary))
        #expect(!p.hasShadow && !p.isOpaque && p.backgroundColor == .clear)
        #expect(p.level.rawValue > NSWindow.Level.normal.rawValue)
        #expect(!p.hidesOnDeactivate)
        #expect(p.frame == monitor.frame)
    }

    @Test func theStripTakesTheKeyWindowOnlyWhileTyping() {
        let s = StripPanel()
        #expect(!s.isVisible)
        #expect(s.styleMask.contains(.nonactivatingPanel))
        #expect(!s.canBecomeKey && !s.canBecomeMain)
        s.typing = true
        #expect(s.canBecomeKey && !s.canBecomeMain)
        #expect(s.level.rawValue > OverlayPanel.level.rawValue)
    }

    @Test func theStripSitsAtTheTopCentre() {
        let f = StripPanel.frame(in: CGRect(x: 0, y: 0, width: 1512, height: 950), height: 96)
        #expect(f.midX == 756 && f.maxY == 950 - 12)
    }
}
