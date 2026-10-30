import Foundation

/// Small pure parts of the voice in and out.
public enum Audio {
    /// the number of the word (from 0, split on white space, as board.js does) that starts at or holds the UTF-16 offset
    /// `at` of `text`. AVSpeechSynthesizer gives the range of each word that it says in UTF-16 units.
    public static func wordIndex(_ text: String, at: Int) -> Int {
        var k = -1, inWord = false, i = 0
        for u in text.utf16 {
            if i > at { break }
            let space = u == 0x20 || u == 0x09 || u == 0x0A || u == 0x0D || u == 0xA0
            if !space && !inWord { k += 1 }
            inWord = !space
            i += 1
        }
        return max(0, k)
    }

    /// a WAV file (mono, 16-bit PCM) of `samples` at `rate`, as the server's `/voice/stt` takes it
    public static func wav(_ samples: [Int16], rate: Int = 16000) -> Data {
        var d = Data()
        func u32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
        func u16(_ v: UInt16) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
        let bytes = UInt32(samples.count * 2)
        d.append(contentsOf: Array("RIFF".utf8)); u32(36 + bytes); d.append(contentsOf: Array("WAVE".utf8))
        d.append(contentsOf: Array("fmt ".utf8)); u32(16); u16(1); u16(1); u32(UInt32(rate)); u32(UInt32(rate * 2)); u16(2); u16(16)
        d.append(contentsOf: Array("data".utf8)); u32(bytes)
        samples.withUnsafeBufferPointer { p in
            for s in p { u16(UInt16(bitPattern: s)) }
        }
        return d
    }

    /// float samples from -1 to 1 as 16-bit samples, clipped
    public static func pcm16(_ f: [Float]) -> [Int16] {
        f.map { Int16(max(-1, min(1, $0)) * 32767) }
    }

    /// the level of the mic for the strip, from 0 (silence, -60 dBFS or less) to 1 (0 dBFS), from the RMS of `f`
    public static func level(_ f: [Float]) -> Float {
        guard !f.isEmpty else { return 0 }
        let rms = (f.reduce(Float(0)) { $0 + $1 * $1 } / Float(f.count)).squareRoot()
        guard rms > 0 else { return 0 }
        return max(0, min(1, (20 * log10(rms) + 60) / 60))
    }
}
