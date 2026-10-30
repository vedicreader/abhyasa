@preconcurrency import AVFoundation

/// The answer of the server's `/guide/say` for one line: the natural voice of the Settings page, the browser voice, or a failure.
public enum SayReply: Equatable, Sendable {
    /// the WAV of the line, and the start of each word in seconds (split on white space)
    case line(wav: Data, words: [Double], engine: String, hosted: Bool)
    /// the setting is the browser voice: the Mac speaks the line itself
    case browser
    case failed(String)

    /// the reply for the status `code` and the JSON body `data`
    public static func parse(status code: Int, _ data: Data) -> SayReply {
        let o = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        if code == 409 { return .browser }
        guard code == 200, let o, let b64 = o["audio"] as? String, let wav = Data(base64Encoded: b64), !wav.isEmpty else {
            return .failed(o?["error"] as? String ?? "status \(code)")
        }
        let words = (o["words"] as? [Any] ?? []).compactMap { ($0 as? NSNumber)?.doubleValue }
        return .line(wav: wav, words: words, engine: o["engine"] as? String ?? "", hosted: (o["where"] as? String) == "hosted")
    }

    /// the last word that starts at or before `t` seconds; -1 before the first word
    public static func word(at t: Double, in words: [Double]) -> Int {
        var k = -1
        for (i, w) in words.enumerated() where w <= t + 0.02 { k = i }
        return k
    }
}

/// The voice out (design 5.3): the natural voice of the server when the Settings page sets one, played with AVAudioPlayer and a
/// mark for each word at its time; else AVSpeechSynthesizer, with a mark for each word that it says. When the server fails,
/// the line goes to AVSpeechSynthesizer.
@MainActor
public final class Speaker: NSObject, AVSpeechSynthesizerDelegate, AVAudioPlayerDelegate {
    let synth = AVSpeechSynthesizer()
    /// asks the server for one line; nil: the Mac voice only
    public var fetch: ((String) async -> SayReply)?
    /// the line in the natural voice now
    var player: AVAudioPlayer?
    var playing: (id: Int, words: [Double], k: Int)?
    var tick: Timer?
    var asking: Task<Void, Never>?
    /// after a `browser` reply the Mac voice speaks with no request until this time, so each line does not wait for the server
    var browserUntil = Date.distantPast
    /// the line that it says now: `text` is the whole line; `offset` is where the spoken part starts, after Voice off
    var now: (id: Int, text: String, spoken: String, offset: Int)?
    var at = 0
    public var onWord: ((Int, Int) -> Void)?
    public var onDone: ((Int) -> Void)?
    /// Voice off: the lines go on with their word marks and their time, with no sound
    public var muted = false {
        didSet { if muted != oldValue { player?.volume = muted ? 0 : 1; requeue() } }
    }

    public override init() {
        super.init()
        synth.delegate = self
    }

    public func speak(_ id: Int, _ text: String) {
        if synth.isSpeaking { now = nil; synth.stopSpeaking(at: .immediate) }
        quiet()
        guard let fetch, Date() >= browserUntil else { return say(id, text, from: 0) }
        asking = Task { @MainActor in
            let r = await fetch(text)
            guard !Task.isCancelled else { return }
            switch r {
            case let .line(wav, words, _, _) where self.play(id, wav, words): return
            case .browser: self.browserUntil = Date().addingTimeInterval(30)
            default: break
            }
            self.say(id, text, from: 0)
        }
    }

    /// plays the WAV of a line and marks each word at its time; false when the WAV does not play
    func play(_ id: Int, _ wav: Data, _ words: [Double]) -> Bool {
        guard let p = try? AVAudioPlayer(data: wav) else { return false }
        p.delegate = self
        p.volume = muted ? 0 : 1
        guard p.play() else { return false }
        player = p
        playing = (id, words, -1)
        tick = Timer.scheduledTimer(withTimeInterval: 0.04, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.mark() }
        }
        mark()
        return true
    }

    func mark() {
        guard let p = player, var n = playing else { return }
        let k = SayReply.word(at: p.currentTime, in: n.words)
        while n.k < k { n.k += 1; onWord?(n.id, n.k) }
        playing = n
    }

    /// stops the natural voice and the request for its line
    func quiet() {
        asking?.cancel(); asking = nil
        tick?.invalidate(); tick = nil
        player?.stop(); player = nil
        playing = nil
    }

    public nonisolated func audioPlayerDidFinishPlaying(_ p: AVAudioPlayer, successfully ok: Bool) {
        Task { @MainActor in
            guard p === self.player, var n = self.playing else { return }
            while n.k < n.words.count - 1 { n.k += 1; self.onWord?(n.id, n.k) }
            self.quiet()
            self.onDone?(n.id)
        }
    }

    func say(_ id: Int, _ text: String, from offset: Int) {
        let u16 = Array(text.utf16)
        let spoken = String(decoding: u16[min(offset, u16.count)...], as: UTF16.self)
        now = (id, text, spoken, offset)
        at = offset
        let u = AVSpeechUtterance(string: spoken)
        u.volume = muted ? 0 : 1
        synth.speak(u)
    }

    /// Voice off (or on) in the middle of a line: say the rest of the line again from the word that it says now, so the sound
    /// stops (or starts) at once and the board keeps its place
    func requeue() {
        guard let n = now, synth.isSpeaking else { return }
        now = nil
        synth.stopSpeaking(at: .immediate)
        say(n.id, n.text, from: at)
    }

    public func hush(_ id: Int) {
        if playing?.id == id || asking != nil { quiet() }
        guard now?.id == id else { return }
        now = nil
        synth.stopSpeaking(at: .immediate)
    }

    // the delegate can be called on any thread: each call goes to the main actor
    public nonisolated func speechSynthesizer(_ s: AVSpeechSynthesizer, willSpeakRangeOfSpeechString r: NSRange, utterance u: AVSpeechUtterance) {
        let text = u.speechString, loc = r.location
        Task { @MainActor in
            guard let n = self.now, n.spoken == text else { return }
            self.at = n.offset + loc
            self.onWord?(n.id, Audio.wordIndex(n.text, at: self.at))
        }
    }

    public nonisolated func speechSynthesizer(_ s: AVSpeechSynthesizer, didFinish u: AVSpeechUtterance) {
        let text = u.speechString
        Task { @MainActor in
            guard let n = self.now, n.spoken == text else { return }
            self.now = nil
            self.onDone?(n.id)
        }
    }
}

/// The voice in, while the learner holds the key: the mic at 16 kHz, mono, in memory only. The release gives a WAV for the
/// server's `/voice/stt`, which uses the speech engine of abhyasa's Settings. At most `SampleBox.longest` seconds.
@MainActor
public final class Recorder {
    let engine = AVAudioEngine()
    let box = SampleBox()
    public private(set) var on = false
    /// the level of the last buffer, from 0 to 1, for the strip while the mic is on
    public var level: Float { box.level }

    public init() {}

    /// true when the app may use the mic now; the first hold of the key asks (design 8.4)
    public static func allowed() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized: return true
        case .notDetermined: return await AVCaptureDevice.requestAccess(for: .audio)
        default: return false
        }
    }

    public func start() throws {
        guard !on else { return }
        let input = engine.inputNode
        let from = input.outputFormat(forBus: 0)
        guard let to = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16000, channels: 1, interleaved: false),
              let conv = AVAudioConverter(from: from, to: to) else { throw RecorderError.format }
        box.reset()
        input.installTap(onBus: 0, bufferSize: 4096, format: from, block: Self.tap(box, conv, from, to))
        engine.prepare()
        try engine.start()
        on = true
    }

    /// the tap on the audio thread: each buffer at 16 kHz into the box. It is not on the main actor.
    nonisolated static func tap(_ box: SampleBox, _ conv: AVAudioConverter, _ from: AVAudioFormat, _ to: AVAudioFormat) -> AVAudioNodeTapBlock {
        { buf, _ in
            let n = AVAudioFrameCount(Double(buf.frameLength) * 16000 / from.sampleRate) + 32
            guard let out = AVAudioPCMBuffer(pcmFormat: to, frameCapacity: n) else { return }
            var fed = false
            conv.convert(to: out, error: nil) { _, status in
                if fed { status.pointee = .noDataNow; return nil }
                fed = true
                status.pointee = .haveData
                return buf
            }
            if let p = out.floatChannelData?[0] {
                let s = Array(UnsafeBufferPointer(start: p, count: Int(out.frameLength)))
                box.add(s)
                box.set(level: Audio.level(s))
            }
        }
    }

    /// stops the mic and gives the WAV; nil when it heard less than a quarter second
    public func stop() -> Data? {
        guard on else { return nil }
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        on = false
        let s = box.take()
        return s.count < 4000 ? nil : Audio.wav(Audio.pcm16(s))
    }
}

enum RecorderError: Error { case format }

/// The samples from the audio thread, behind a lock.
final class SampleBox: @unchecked Sendable {
    static let longest = 30.0
    let lock = NSLock()
    var samples: [Float] = []
    var last: Float = 0
    var level: Float { lock.withLock { last } }
    func set(level: Float) { lock.withLock { last = level } }
    func reset() { lock.withLock { samples = []; last = 0 } }
    func add(_ s: [Float]) { lock.withLock { if Double(samples.count) < Self.longest * 16000 { samples += s } } }
    func take() -> [Float] { lock.withLock { defer { samples = [] }; return samples } }
}
