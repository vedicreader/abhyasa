import Carbon.HIToolbox
import Foundation
import Testing
@testable import AbhyasaGuide

@Suite struct HyperKeyTests {
    @Test func theGuideKeyIsHyperE() {
        #expect(HotKeys.Key.guide.code == UInt32(kVK_ANSI_E))
        #expect(HotKeys.Key.guide.mods == UInt32(controlKey | optionKey | shiftKey | cmdKey))
        #expect(HotKeys.Key.guide.code != UInt32(kVK_ANSI_Grave))   // ⌥` types as before in all apps
        #expect(GuideText.key == "Caps+E")
    }
}

/// The switch is off until Start. These tests use their own defaults, never the app's.
@MainActor @Suite(.serialized) struct OffUntilStartTests {
    @Test func aFreshInstallHoldsNoKey() {
        let keep = Guide.defaults
        defer { Guide.defaults = keep }
        Guide.defaults = UserDefaults(suiteName: "abhyasa-test-\(UUID().uuidString)")!
        #expect(!Guide.on && !Guide.holdsKey)
        Guide.on = true   // an on switch with no Start (an old install) still holds no key
        #expect(!Guide.holdsKey)
        Guide.started = true
        #expect(Guide.holdsKey)
        Guide.on = false
        #expect(!Guide.holdsKey)
    }

    @Test func theOldSwitchDoesNotTurnTheGuideOn() {
        let keep = Guide.defaults
        defer { Guide.defaults = keep }
        let d = UserDefaults(suiteName: "abhyasa-test-\(UUID().uuidString)")!
        d.set(true, forKey: "guide")   // the 0.0.14 switch, on by default
        Guide.defaults = d
        #expect(!Guide.holdsKey)
    }
}

@Suite struct WhoTests {
    @Test func theDefaultIsClaudeSonnetHostedByAnthropic() {
        let w = Who.guess("", names: ["claude/sonnet": "Claude Sonnet"])
        #expect(w == Who(model: "Claude Sonnet", local: false, company: "Anthropic"))
        #expect(w.chip == "hosted · Anthropic")
    }

    @Test func aLocalModelSaysOnThisMac() {
        let w = Who.guess("litert/gemma-4-e4b")
        #expect(w.local && w.chip == "on this Mac")
        #expect(Who.guess("ollama/qwen3").local)
    }

    @Test func anUnknownModelIsHostedWithNoCompany() {
        let w = Who.guess("acme/brain-2")
        #expect(!w.local && w.company.isEmpty && w.chip == "hosted")
        #expect(w.model == "Acme Brain 2")
        #expect(Who.guess("openai/gpt-6").company == "OpenAI")
        #expect(Who.guess("gemini/pro").company == "Google")
    }

    @Test func theServerNamesTheRealModel() {
        let guess = Who.guess("")
        let w = guess.with(GuideEvent.Status(state: "asking", model: "Gemma 4 E4B", place: "on this Mac", who: ""))
        #expect(w == Who(model: "Gemma 4 E4B", local: true, company: ""))
        #expect(guess.with(GuideEvent.Status(state: "asking")) == guess)   // no fields: the guess stays
        #expect(guess.with(GuideEvent.Status(place: "hosted", who: "OpenAI")).chip == "hosted · OpenAI")
    }

    @Test func speechSaysWhereItRuns() {
        #expect(Speech.of("mlx") == .local("Qwen3-ASR"))
        #expect(Speech.of("gemma") == .local("Qwen3-ASR"))   // an old setting: the server reads it as mlx
        #expect(Speech.of("whisper") == .local("Whisper"))
        #expect(Speech.of("mlx:mlx-community/whisper-large-v3-turbo-asr-fp16") == .local("Whisper"))
        #expect(Speech.of("openai:gpt-4o-transcribe") == .hosted("OpenAI"))
        #expect(Speech.of("") == .unknown)
        #expect(Speech.of("openai").isHosted && !Speech.of("mlx").isHosted)
        #expect(GuideText.speechChip(.local("Qwen3-ASR")) == "speech: on this Mac")
        #expect(GuideText.speechChip(.hosted("OpenAI")) == "speech: hosted · OpenAI")
    }
}

@Suite struct GuideStateTests {
    let sonnet = Who(model: "Claude Sonnet", local: false, company: "Anthropic")
    var all: [GuideState] { [.off, .ready, .listening, .writing, .reading, .asking(sonnet), .searching, .saving, .drawing] }

    @Test func eachStateHasItsOwnMarkAndLine() {
        #expect(Set(all.map(\.symbol)).count == all.count)
        #expect(Set(all.map(\.line)).count == all.count)
        #expect(GuideState.ready.line == "Screen guide: ready. Caps+E to ask.")
        #expect(GuideState.asking(sonnet).line == "Screen guide: asks Claude Sonnet (hosted · Anthropic).")
        #expect(GuideState.off.line == "Screen guide: off.")
    }

    @Test func onlyAWorkingStateCanStop() {
        #expect(!GuideState.off.busy && !GuideState.ready.busy)
        #expect(GuideState.listening.busy && GuideState.asking(sonnet).busy && GuideState.drawing.busy)
    }

    @Test func theServerStatesMapToTheMark() {
        #expect(GuideState.server("reading", who: sonnet) == .reading)
        #expect(GuideState.server("asking", who: sonnet) == .asking(sonnet))
        #expect(GuideState.server("searching", who: sonnet) == .searching)
        #expect(GuideState.server("saving", who: sonnet) == .saving)
        #expect(GuideState.server("drawing", who: sonnet) == .drawing)
        #expect(GuideState.server("dreaming", who: sonnet) == nil)
        #expect(GuideState.server(nil, who: sonnet) == nil)
    }

    @Test func theMenuHasTheStateStopVoiceTurnAndSettings() {
        let off = MenuMark.items(.off, muted: false)
        #expect(off.map(\.title) == ["Screen guide: off.", "Stop", "Voice off", "Turn on the guide…", "Settings…"])
        #expect(!off[0].enabled && !off[1].enabled && !off[2].enabled)
        let busy = MenuMark.items(.drawing, muted: true)
        #expect(busy[1].enabled && busy[2].checked)
        #expect(busy[3].title == "Turn off the guide")
    }
}

@Suite struct LinesTests {
    let sonnet = Who(model: "Claude Sonnet", local: false, company: "Anthropic")

    @Test func anOldWaitHasNoChip() {
        #expect(Lines.wait("The tutor reads the page.", nil, who: sonnet) == Lines.Line(text: "The tutor reads the page."))
    }

    @Test func askingShowsWhoAndWhere() {
        let s = GuideEvent.Status(state: "asking", model: "Claude Sonnet", place: "hosted", who: "Anthropic")
        let l = Lines.wait("Asks Claude Sonnet.", s, who: sonnet.with(s))
        #expect(l.chip == "hosted · Anthropic" && l.hosted)
        let local = Who(model: "Gemma 4 E4B", local: true)
        #expect(Lines.wait("Asks Gemma 4 E4B.", GuideEvent.Status(state: "asking"), who: local).chip == "on this Mac")
    }

    @Test func searchingShowsTheQueryWordForWord() {
        let s = GuideEvent.Status(state: "searching", query: "why recurrent nets train slowly", sources: 3)
        let l = Lines.wait("Searches the web.", s, who: sonnet)
        #expect(l.chip == "web" && l.hosted)
        #expect(l.detail == "\u{201C}why recurrent nets train slowly\u{201D} 3 sources found.")
        // the query is not said two times when the line has it
        let in1 = Lines.wait("Searches the web for: \"why\"", GuideEvent.Status(state: "searching", query: "why"), who: sonnet)
        #expect(in1.detail.isEmpty)
    }

    @Test func readingAndSavingStayOnThisMac() {
        #expect(Lines.wait("Reads the window.", GuideEvent.Status(state: "reading"), who: sonnet).chip == "on this Mac")
        #expect(Lines.wait("Saves to your vault.", GuideEvent.Status(state: "saving"), who: sonnet).chip == "on this Mac")
    }

    @Test func theBoardChipNamesTheModel() {
        #expect(Lines.boardChip(sonnet) == "Claude Sonnet · hosted")
        #expect(Lines.boardChip(Who(model: "Gemma 4 E4B", local: true)) == "Gemma 4 E4B · on this Mac")
    }

    @Test func partsLeaveOutTheWindowTitle() {
        let a = [Anchor(id: "w", kind: "title", text: "Safari · x", role: "AXWindow", near: "window", frame: .zero),
                 Anchor(id: "e1", kind: "text", text: "y", role: "AXStaticText", near: "visible", frame: .zero)]
        #expect(Lines.parts(a) == 1)
    }
}

@Suite struct SignTextTests {
    @Test func theSignsSayWhatLeavesAndWhen() {
        #expect(GuideText.readsWindow == "The guide reads this window.")
        #expect(GuideText.reads("Safari", parts: 38) == "Reads Safari: the window title and 38 parts with text.")
        #expect(GuideText.reads("Preview", parts: 0) == "Reads Preview: the window title only.")
        #expect(GuideText.sends(parts: 38, to: "Claude Sonnet", local: false)
                == "Sends your question, the window title and 38 text parts to Claude Sonnet.")
        #expect(GuideText.sends(parts: 1, to: "Gemma 4 E4B", local: true)
                == "Sends your question, the window title and 1 text part to Gemma 4 E4B. Nothing leaves this Mac.")
        #expect(GuideText.micOn == "The mic is on. Let go of Caps+E to stop.")
        #expect(GuideText.trail == "The guide follows your pointer while you ask.")
        #expect(GuideText.closesIn(8) == "The board closes in 8 seconds. Move the pointer or push a key to keep it.")
        #expect(GuideText.keys == "Caps+E again · Esc stop")
        #expect(GuideText.saved("Attention") == "Saved to your vault: Attention.")
    }

    @Test func theStartSheetSaysWhatTheGuideReadsAndWhereItGoes() {
        let s = Guide.startSheet(who: Who(model: "Claude Sonnet", local: false, company: "Anthropic"), vision: false)
        #expect(s.title == "The screen guide")
        #expect(s.body[0] == "Press Caps+E over any app. Hold the keys to talk, or tap them to type.")
        #expect(s.body[1].contains("its title and the text of its parts") && s.body[1].contains("Accessibility"))
        #expect(s.body[1].hasSuffix("Claude Sonnet runs on a server of Anthropic, not on this Mac."))
        #expect(s.body[2].contains("takes no picture"))
        #expect(s.body[3] == "The tutor draws over the window and speaks. Esc stops it.")
        #expect(s.body[4].contains("turn off"))
        #expect(s.buttons.map(\.id) == ["off", "local", "start"])
        #expect(s.buttons.last?.main == true && s.buttons.last?.title == "Start")
    }

    @Test func withALocalModelNothingLeaves() {
        let s = Guide.startSheet(who: Who(model: "Gemma 4 E4B", local: true), vision: true)
        #expect(s.body[1].hasSuffix("It sends this and your question to Gemma 4 E4B on this Mac. Nothing leaves this Mac."))
        #expect(s.body[2].contains("vision setting is on"))
        #expect(s.buttons.map(\.id) == ["off", "start"])   // no "Use a model on this Mac" when it is one
    }

    @Test func theVoiceSheetSaysWhereTheVoiceGoes() {
        #expect(Guide.voiceSheet(.local("Qwen3-ASR")).body[1] == "Qwen3-ASR writes your words on this Mac. No sound leaves this Mac.")
        #expect(Guide.voiceSheet(.hosted("OpenAI")).body[1] == "OpenAI writes your words. Your voice goes to OpenAI.")
        #expect(Guide.voiceSheet(.unknown).body[1].contains("Settings"))
        #expect(Guide.voiceSheet(.unknown).buttons.map(\.id) == ["ok"])
    }
}

@Suite struct LevelTests {
    @Test func theLevelGoesFromSilenceToFull() {
        #expect(Audio.level([]) == 0)
        #expect(Audio.level([0, 0, 0]) == 0)
        #expect(Audio.level([1, -1, 1, -1]) == 1)
        #expect(Audio.level([0.0001, -0.0001]) == 0)   // under -60 dBFS
        let mid = Audio.level([0.03, -0.03])   // about -30 dBFS
        #expect(mid > 0.4 && mid < 0.6)
    }
}

@Suite struct OverlayLingerTests {
    @Test func thePageTellsTheCountdownAndCanKeepTheBoard() {
        #expect(OverlayPage.html.contains("post({op: 'linger', ms: 8000})"))
        #expect(OverlayPage.html.contains("keep() { calm(); }"))
        #expect(OverlayPage.html.contains("Caps+E again · Esc stop"))
    }
}
