import Foundation
import Testing
@testable import AbhyasaGuide

/// The reply of `/guide/say`: the parser and the word at a time only. No test plays a sound.
@Suite struct SayReplyTests {
    let wav = Data("RIFF....WAVE".utf8)

    func body(_ o: [String: Any]) -> Data { try! JSONSerialization.data(withJSONObject: o) }

    @Test func aLineHasItsAudioAndItsWordTimes() {
        let r = SayReply.parse(status: 200, body(["audio": wav.base64EncodedString(), "words": [0, 0.25, 0.5], "engine": "pocket", "where": "on this Mac"]))
        #expect(r == .line(wav: wav, words: [0, 0.25, 0.5], engine: "pocket", hosted: false))
        let o = SayReply.parse(status: 200, body(["audio": wav.base64EncodedString(), "words": [0.1], "engine": "openai", "where": "hosted"]))
        #expect(o == .line(wav: wav, words: [0.1], engine: "openai", hosted: true))
    }

    @Test func theBrowserVoiceAndFailures() {
        #expect(SayReply.parse(status: 409, body(["error": "The browser speaks with its own voice."])) == .browser)
        #expect(SayReply.parse(status: 502, body(["error": "The natural voice could not say this line."])) == .failed("The natural voice could not say this line."))
        #expect(SayReply.parse(status: 200, body(["words": [0]])) == .failed("status 200"))   // no audio
        #expect(SayReply.parse(status: 200, body(["audio": "not base64!"])) == .failed("status 200"))
        #expect(SayReply.parse(status: 0, Data()) == .failed("status 0"))
    }

    @Test func theWordAtATime() {
        let w = [0.0, 0.3, 0.6]
        #expect(SayReply.word(at: -0.1, in: w) == -1)
        #expect(SayReply.word(at: 0, in: w) == 0)
        #expect(SayReply.word(at: 0.29, in: w) == 1)   // a word lights up a little before its time
        #expect(SayReply.word(at: 5, in: w) == 2)
        #expect(SayReply.word(at: 1, in: []) == -1)
    }
}
