import Foundation

/// The words of the guide on the Mac, in ASD-STE100 Simplified Technical English.
public enum GuideText {
    public static let key = "Caps+E"
    public static let ask = "What do you not understand?"
    public static let reading = "The tutor reads the window."
    /// U11: in the strip at key down, before the Accessibility read
    public static let readsWindow = "The guide reads this window."
    public static let micOn = "The mic is on. Let go of \(key) to send."
    public static let writing = "The app writes what you said."
    public static let heardNothing = "The mic heard nothing. Type your question."
    public static let noMic = "Abhyasa cannot use the mic. Type your question."
    public static let noServer = "abhyasa does not run now. Open Abhyasa, then try again."
    public static let failed = "The tutor could not answer. Make sure that abhyasa runs, then try again."
    public static let keys = "\(key) again · Esc stop"
    public static let end = "In the tutor's own words. No source found."
    public static let trail = "The guide follows your pointer while you ask."
    public static let drawing = "The tutor draws over the window."
    public static let drawingQuiet = "The tutor draws over the window. The voice is off."
    public static let stopped = "Stopped. The tutor got the question, but the guide shows no answer."
    public static let kept = "The board stays. Esc or Stop closes it."
    public static let undone = "Removed from your vault."
    public static let undoFailed = "Abhyasa could not remove it. Open your vault to remove it."

    // the buttons
    public static let stop = "Stop"
    public static let voiceOff = "Voice off"
    public static let voiceOn = "Voice on"
    public static let undo = "Undo"
    public static let start = "Start"
    public static let turnOff = "Turn off the guide"
    public static let turnOn = "Turn on the guide…"
    public static let useLocal = "Use a model on this Mac"
    public static let ok = "OK"
    public static let settings = "Settings…"

    // the where chip
    public static let onThisMac = "on this Mac"
    public static func hosted(_ who: String) -> String { who.isEmpty ? "hosted" : "hosted · \(who)" }
    public static let web = "web"

    /// U14: the quiet line under the countdown of the board's end
    public static func closesIn(_ s: Int) -> String {
        "The board closes in \(s) seconds. Move the pointer or push a key to keep it."
    }

    /// U12: what leaves the Mac, before the request
    public static func reads(_ app: String, parts: Int) -> String {
        parts == 0 ? "Reads \(app): the window title only." : "Reads \(app): the window title and \(parts) \(parts == 1 ? "part" : "parts") with text."
    }

    public static func sends(parts: Int, to model: String, local: Bool) -> String {
        let what = parts == 0 ? "your question and the window title" : "your question, the window title and \(parts) text \(parts == 1 ? "part" : "parts")"
        return "Sends \(what) to \(model)." + (local ? " Nothing leaves this Mac." : "")
    }

    /// the saved line at the end of a board (P0 item 2)
    public static func saved(_ title: String) -> String { "Saved to your vault: \(title)." }
    public static func sources(_ n: Int) -> String { n == 1 ? "1 source found." : "\(n) sources found." }

    public static func windowOnly(_ app: String) -> String {
        "Abhyasa cannot read the parts of \(app). The guide sees the window only."
    }

    public static func neverLook(_ app: String) -> String {
        "The guide does not look at \(app). It sees the window only."
    }

    public static let password = "A password field has the focus. The guide does not look."

    // --- the menu bar mark ---------------------------------------------------------------------------------------------------
    public static let menuOff = "Screen guide: off."
    public static let menuReady = "Screen guide: ready. \(key) to ask."
    public static let menuListening = "Screen guide: the mic is on."
    public static let menuWriting = "Screen guide: writes what you said."
    public static let menuReading = "Screen guide: reads the window."
    public static func menuAsking(_ model: String, _ place: String) -> String {
        model.isEmpty ? "Screen guide: asks the tutor (\(place))." : "Screen guide: asks \(model) (\(place))."
    }
    public static let menuSearching = "Screen guide: searches the web."
    public static let menuSaving = "Screen guide: saves to your vault."
    public static let menuDrawing = "Screen guide: draws over the window."

    // --- the first-use sheet of the guide (U10, review 1.4) ------------------------------------------------------------------
    public static let guideTitle = "The screen guide"
    public static let guideKey = "Press \(key) over any app. Hold the keys to talk, or tap them to type."
    public static func guideSends(model: String, local: Bool, who: String) -> String {
        let read = "When you ask, Abhyasa reads the window in front: its title and the text of its parts. macOS calls this Accessibility. "
        if local { return read + "It sends this and your question to \(model) on this Mac. Nothing leaves this Mac." }
        let place = who.isEmpty ? "on a server" : "on a server of \(who)"
        return read + "It sends this and your question to \(model). \(model) runs \(place), not on this Mac."
    }
    public static func guideKeeps(vision: Bool) -> String {
        vision
            ? "Abhyasa reads the window only when you ask. The vision setting is on, so it also sends one picture of the window. It keeps no picture and no window text."
            : "Abhyasa reads the window only when you ask. It takes no picture of the window. It keeps no window text."
    }
    public static let guideDraws = "The tutor draws over the window and speaks. Esc stops it."
    public static let guideOff = "To turn off the guide, use the Abhyasa mark in the menu bar, or Settings."

    // --- the first-use sheet of the voice --------------------------------------------------------------------------------------
    public static let voiceTitle = "Talk and listen"
    public static let voiceHold = "Hold \(key) to talk. The mic is on only while you hold the keys."
    public static func voiceWhere(_ s: Speech) -> String {
        switch s {
        case .local(let name): "\(name) writes your words on this Mac. No sound leaves this Mac."
        case .hosted(let who): "\(who) writes your words. Your voice goes to \(who)."
        case .unknown: "The speech engine of the Settings page writes your words. Look there to see if your voice leaves this Mac."
        }
    }
    public static let voiceSpeaks = "The tutor speaks each step aloud. Use Voice off in the strip or in the menu bar."

    /// the speech chip while the mic is on
    public static func speechChip(_ s: Speech) -> String {
        switch s {
        case .local: "speech: on this Mac"
        case .hosted(let who): "speech: hosted · \(who)"
        case .unknown: "speech: see Settings"
        }
    }

    /// the first-use sheet for Accessibility (design 8.4): one plain line, then the choice
    public static func accessTitle(_ app: String) -> String { "Let Abhyasa find the parts of \(app)?" }
    public static func accessBody(_ app: String) -> String {
        "To point at the parts of \(app), Abhyasa must read where they are on the screen. "
            + "macOS calls this Accessibility. Abhyasa reads it only when you ask the guide. No text is kept. "
            + "Without it, the guide sees the window only."
    }
    public static let openSettings = "Open System Settings"
    public static let notNow = "Not Now"

    /// the first-use sheet for Screen Recording, for a later vision board
    public static func pictureTitle(_ app: String) -> String { "Let Abhyasa take a picture of \(app)?" }
    public static func pictureBody(_ app: String) -> String {
        "Some apps do not tell where their parts are. Then the guide needs a picture of the window in front. "
            + "Abhyasa takes one picture of that window only, only when you ask. It does not keep the picture. "
            + "macOS calls this Screen Recording."
    }
}
