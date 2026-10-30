import Foundation

/// The words of the guide on the Mac, in ASD-STE100 Simplified Technical English.
public enum GuideText {
    public static let key = "⌥`"
    public static let ask = "What do you not understand?"
    public static let reading = "The tutor reads the window."
    public static let micOn = "The mic is on. Release \(key) to send."
    public static let writing = "The app writes what you said."
    public static let heardNothing = "The mic heard nothing. Type your question."
    public static let noMic = "Abhyasa cannot use the mic. Type your question."
    public static let noServer = "abhyasa does not run now. Open Abhyasa, then try again."
    public static let failed = "The tutor could not answer. Make sure that abhyasa runs, then try again."
    public static let keys = "\(key) again · Esc stop"
    public static let end = "In the tutor's own words. No source found."

    public static func windowOnly(_ app: String) -> String {
        "Abhyasa cannot read the parts of \(app). The guide sees the window only."
    }

    public static func neverLook(_ app: String) -> String {
        "The guide does not look at \(app). It sees the window only."
    }

    public static let password = "A password field has the focus. The guide does not look."

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
